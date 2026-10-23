import base64
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import draft_api
from backend import instagram_api
from backend.auth import AuthenticatedUser, require_user
from backend.services.publishing import PublicationResult, PublishingCapability
from backend.storage.draft_repository import (
    DraftConflictError,
    DraftNotFoundError,
    DraftRepository,
    MediaAssetNotFoundError,
)
from backend.storage.sql_models import Base, PostDraftRecord, UserRecord
from datetime import datetime, timezone


@pytest.fixture
def draft_repository():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with factory.begin() as session:
        session.add_all([
            UserRecord(id="user-1", email="one@example.test", created_at=now, updated_at=now),
            UserRecord(id="user-2", email="two@example.test", created_at=now, updated_at=now),
        ])
    try:
        yield DraftRepository.from_engine(engine), factory
    finally:
        engine.dispose()


def _asset(repository: DraftRepository, user_id: str = "user-1"):
    return repository.create_media_asset(
        user_id,
        storage_provider="oci",
        object_name=f"draft-assets/{user_id}/image.jpg",
        original_filename="image.jpg",
        mime_type="image/jpeg",
        byte_size=1024,
        checksum_sha256="a" * 64,
        status="ready",
    )


def _draft(repository: DraftRepository, user_id: str = "user-1", media_asset_id: str | None = None):
    return repository.create_draft(
        user_id,
        media_asset_id=media_asset_id,
        target_platforms=["Instagram", "Threads"],
        content_brief="A calm workspace",
        goal="Engagement",
        caption="Editable caption",
        hashtags=["#creator"],
    )


def test_drafts_survive_repository_instances_and_are_account_scoped(draft_repository):
    repository, factory = draft_repository
    asset = _asset(repository)
    created = _draft(repository, media_asset_id=asset.id)

    restarted = DraftRepository(factory)
    assert restarted.get_draft("user-1", created.id) == created
    assert restarted.get_draft("user-2", created.id) is None
    assert restarted.list_drafts("user-2") == []
    with pytest.raises(DraftNotFoundError):
        restarted.update_draft("user-2", created.id, {"caption": "stolen"})
    assert restarted.delete_draft("user-2", created.id) is False


def test_media_ownership_and_draft_state_are_enforced(draft_repository):
    repository, factory = draft_repository
    asset = _asset(repository)
    with pytest.raises(MediaAssetNotFoundError):
        _draft(repository, user_id="user-2", media_asset_id=asset.id)

    created = _draft(repository, media_asset_id=asset.id)
    with factory.begin() as session:
        session.get(PostDraftRecord, created.id).status = "publishing"
    with pytest.raises(DraftConflictError):
        repository.update_draft("user-1", created.id, {"caption": "too late"})
    with pytest.raises(DraftConflictError):
        repository.delete_draft("user-1", created.id)


def test_publication_idempotency_and_platform_targets(draft_repository):
    repository, _ = draft_repository
    created = _draft(repository)

    first, first_created = repository.create_publication("user-1", created.id, "Instagram", "request-1")
    repeated, repeated_created = repository.create_publication("user-1", created.id, "Instagram", "request-1")
    assert first_created is True
    assert repeated_created is False
    assert repeated.id == first.id
    assert len(repository.list_publications("user-1", created.id)) == 1
    with pytest.raises(DraftConflictError):
        repository.create_publication("user-1", created.id, "YouTube", "request-2")
    with pytest.raises(DraftNotFoundError):
        repository.create_publication("user-2", created.id, "Instagram", "request-3")


def test_draft_and_publication_state_transitions_are_controlled(draft_repository):
    repository, _ = draft_repository
    draft = _draft(repository)
    publication, _ = repository.create_publication("user-1", draft.id, "Instagram", "request-1")

    assert repository.transition_draft_status("user-1", draft.id, "publishing").status == "publishing"
    with pytest.raises(DraftConflictError):
        repository.transition_draft_status("user-1", draft.id, "draft")
    assert repository.transition_publication("user-1", publication.id, "validating").status == "validating"
    assert repository.transition_publication("user-1", publication.id, "publishing").status == "publishing"
    with pytest.raises(DraftConflictError):
        repository.transition_publication("user-1", publication.id, "published")
    published = repository.transition_publication(
        "user-1", publication.id, "published", provider_post_id="provider-1"
    )
    assert published.published_at is not None
    assert repository.transition_draft_status("user-1", draft.id, "published").status == "published"


def test_draft_api_happy_path_validation_and_isolation(draft_repository, monkeypatch):
    repository, _ = draft_repository
    asset = _asset(repository)
    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: repository)
    user_one = AuthenticatedUser(id="user-1", email="one@example.test", token_hash="hash")
    user_two = AuthenticatedUser(id="user-2", email="two@example.test", token_hash="hash")

    created = draft_api.create_draft(draft_api.DraftCreate(**{
        "media_asset_id": asset.id,
        "target_platforms": ["Instagram", "Instagram"],
        "content_brief": "A calm workspace",
        "goal": "Engagement",
        "caption": "Editable caption",
        "hashtags": ["creator", "#Creator", "#workflow"],
    }), user_one)
    assert created.target_platforms == ["Instagram"]
    assert created.hashtags == ["#creator", "#workflow"]

    updated = draft_api.update_draft(draft_api.DraftUpdate(caption="Edited"), created.id, user_one)
    assert updated.caption == "Edited"

    with pytest.raises(HTTPException) as hidden:
        draft_api.get_draft(created.id, user_two)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as protected:
        draft_api.update_draft(draft_api.DraftUpdate(caption="stolen"), created.id, user_two)
    assert protected.value.status_code == 404

    with pytest.raises(HTTPException) as invalid_media:
        draft_api.create_draft(draft_api.DraftCreate(**{
        "media_asset_id": asset.id, "target_platforms": ["Instagram"], "caption": "No access",
        }), user_two)
    assert invalid_media.value.status_code == 404


def test_draft_api_rejects_caption_over_selected_platform_limit(draft_repository, monkeypatch):
    repository, _ = draft_repository
    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: repository)
    user = AuthenticatedUser(id="user-1", email="one@example.test", token_hash="hash")
    with pytest.raises(HTTPException) as response:
        draft_api.create_draft(draft_api.DraftCreate(
            target_platforms=["Twitter"], caption="x" * 281,
        ), user)
    assert response.value.status_code == 422
    assert response.value.detail["code"] == "caption_too_long"


def test_draft_api_requires_a_session():
    with pytest.raises(HTTPException) as response:
        require_user(None)
    assert response.value.status_code == 401


def test_media_upload_validates_content_and_persists_private_metadata(draft_repository, monkeypatch):
    repository, _ = draft_repository
    uploaded = []
    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: repository)
    monkeypatch.setattr(
        draft_api, "upload_private_bytes",
        lambda body, object_name, mime_type: uploaded.append((body, object_name, mime_type)),
    )
    user = AuthenticatedUser(id="user-1", email="one@example.test", token_hash="hash")
    body = b"\xff\xd8\xff" + b"safe-jpeg"

    asset = draft_api.upload_media_asset(draft_api.MediaAssetUpload(
        filename="../campaign.jpg", mime_type="image/jpeg",
        data=base64.b64encode(body).decode(),
    ), user)

    assert asset.user_id == "user-1"
    assert asset.original_filename == "campaign.jpg"
    assert asset.byte_size == len(body)
    assert asset.status == "ready"
    assert uploaded[0][1] == asset.object_name
    assert "user-1" in asset.object_name

    with pytest.raises(HTTPException) as invalid:
        draft_api.upload_media_asset(draft_api.MediaAssetUpload(
            filename="fake.jpg", mime_type="image/jpeg",
            data=base64.b64encode(b"not really jpeg").decode(),
        ), user)
    assert invalid.value.status_code == 422
    assert len(uploaded) == 1


def test_durable_publish_is_idempotent_and_records_provider_result(draft_repository, monkeypatch):
    repository, _ = draft_repository
    asset = _asset(repository)
    draft = _draft(repository, media_asset_id=asset.id)
    user = AuthenticatedUser(id="user-1", email="one@example.test", token_hash="hash")
    calls = []

    class FakeAdapter:
        platform = "Instagram"

        def capability(self, user_id):
            return PublishingCapability("Instagram", True)

        def validate(self, request):
            assert request.object_name == asset.object_name
            return None

        def publish(self, user_id, request):
            calls.append((user_id, request.object_name))
            return PublicationResult(
                "Instagram", "published", "Published and tracked.",
                provider_post_id="provider-1", tracked_post_id="tracked-1",
            )

    class FakeRegistry:
        def get(self, platform):
            return FakeAdapter() if platform == "Instagram" else None

    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "publishing_registry", lambda: FakeRegistry())
    payload = draft_api.DraftPublishRequest(
        platforms=["Instagram"], idempotency_key="request-1234",
    )

    first = draft_api.publish_draft(payload, draft.id, user)
    repeated = draft_api.publish_draft(payload, draft.id, user)

    assert first["draft"].status == "published"
    assert first["results"][0]["tracked_post_id"] == "tracked-1"
    assert repeated["results"][0]["provider_post_id"] == "provider-1"
    assert len(calls) == 1
    publications = repository.list_publications("user-1", draft.id)
    assert len(publications) == 1
    assert publications[0].status == "published"
    assert publications[0].provider_post_id == "provider-1"


def test_platform_media_validation_happens_before_publication_record(draft_repository, monkeypatch):
    repository, _ = draft_repository
    asset = repository.create_media_asset(
        "user-1", storage_provider="oci", object_name="draft-assets/user-1/image.png",
        original_filename="image.png", mime_type="image/png", byte_size=100,
        checksum_sha256="b" * 64, status="ready",
    )
    draft = _draft(repository, media_asset_id=asset.id)
    user = AuthenticatedUser(id="user-1", email="one@example.test", token_hash="hash")

    class RejectingAdapter:
        def capability(self, user_id):
            return PublishingCapability("Instagram", True)

        def validate(self, request):
            return PublicationResult(
                "Instagram", "failed", "Instagram publishing currently supports JPEG images only.",
                code="instagram_jpeg_required",
            )

        def publish(self, user_id, request):
            raise AssertionError("invalid media must not reach the provider")

    class FakeRegistry:
        def get(self, platform):
            return RejectingAdapter()

    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "publishing_registry", lambda: FakeRegistry())

    result = draft_api.publish_draft(draft_api.DraftPublishRequest(
        platforms=["Instagram"], idempotency_key="invalid-media-1",
    ), draft.id, user)

    assert result["results"][0]["code"] == "instagram_jpeg_required"
    assert repository.list_publications("user-1", draft.id) == []
    assert repository.get_draft("user-1", draft.id).status == "draft"
