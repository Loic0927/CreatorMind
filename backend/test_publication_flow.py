from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

from backend import draft_api, instagram_api
from backend.auth import AuthenticatedUser
from backend.services.publishing import InstagramPublishingAdapter, PublishingAdapterRegistry
from backend.storage.content_repository import ContentRepository
from backend.storage.database import engine_for_url, session_factory_for_url
from backend.storage.draft_repository import DraftRepository
from backend.storage.sql_models import InstagramMediaRecord, TrackedPostRecord, UserRecord


def test_draft_publish_to_track_vertical_slice_is_idempotent(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'publication-flow.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", url)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine = engine_for_url(url)
    factory = session_factory_for_url(url)
    now = datetime.now(timezone.utc)
    with factory.begin() as session:
        session.add(UserRecord(id="user-1", email="creator@example.test", created_at=now, updated_at=now))

    draft_repository = DraftRepository.from_engine(engine)
    asset = draft_repository.create_media_asset(
        "user-1", storage_provider="oci", object_name="draft-assets/user-1/image.jpg",
        original_filename="image.jpg", mime_type="image/jpeg", byte_size=100,
        checksum_sha256="a" * 64, status="ready",
    )
    draft = draft_repository.create_draft(
        "user-1", media_asset_id=asset.id, target_platforms=["Instagram"],
        content_brief="Launch", goal="Engagement", caption="Caption", hashtags=["#launch"],
    )
    provider_calls = []
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user", status="connected")
    adapter = InstagramPublishingAdapter(
        account_loader=lambda user_id: account,
        token_loader=lambda value: "server-token",
        repository_loader=ContentRepository,
        temporary_url_factory=lambda name, lifetime_minutes: "https://temporary.example/image.jpg",
        provider_publisher=lambda *args: provider_calls.append(args) or {
            "id": "provider-post-1", "media_type": "IMAGE",
            "media_url": "https://cdn.example/image.jpg",
            "permalink": "https://instagram.example/p/1", "caption": "Caption\n\n#launch",
            "timestamp": now.isoformat(),
        },
    )
    registry = PublishingAdapterRegistry([adapter])
    monkeypatch.setattr(draft_api, "get_draft_repository", lambda: draft_repository)
    monkeypatch.setattr(instagram_api, "publishing_registry", lambda: registry)
    user = AuthenticatedUser(id="user-1", email="creator@example.test", token_hash="hash")
    payload = draft_api.DraftPublishRequest(platforms=["Instagram"], idempotency_key="same-request-1")

    first = draft_api.publish_draft(payload, draft.id, user)
    repeated = draft_api.publish_draft(payload, draft.id, user)

    with factory() as session:
        media_count = session.scalar(select(func.count()).select_from(InstagramMediaRecord))
        tracked_count = session.scalar(select(func.count()).select_from(TrackedPostRecord))
    assert first["results"][0]["status"] == "published"
    assert repeated["results"][0]["status"] == "published"
    assert len(provider_calls) == 1
    assert media_count == 1
    assert tracked_count == 1
    engine.dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
