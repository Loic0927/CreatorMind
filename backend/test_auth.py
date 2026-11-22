from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select, text

from backend import auth
from backend.auth_api import (
    AccountContextRequest,
    EmailRequest,
    VerifyCodeRequest,
    account_context,
    delete_account,
    request_code,
    save_account_context,
    verify_code,
)
from backend.services.account_context import suggest_context_from_posts
from backend.storage import json_store, token_store
from backend.storage.content_repository import get_content_repository
from backend.storage.database import engine_for_url, session_factory_for_url
from backend.storage.instagram_repository import delete_local_user_data
from backend.storage.models import (
    InsightTextCache,
    InstagramAccount,
    InstagramComment,
    InstagramInsightSnapshot,
    InstagramMedia,
    StoreData,
    TrackedPost,
)
from backend.storage.sql_models import (
    AIGenerationLogRecord,
    AuthSessionRecord,
    InsightTextCacheRecord,
    InstagramCommentRecord,
    InstagramConnectionRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    LoginCodeRecord,
    MediaAssetRecord,
    OAuthStateRecord,
    PostDraftRecord,
    PostPublicationRecord,
    PredictionHistoryRecord,
    TrackedPostRecord,
    UserRecord,
)


@pytest.fixture
def auth_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{(tmp_path / 'auth.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    monkeypatch.setenv("POSTBRIDGE_AUTH_SECRET", "unit-test-auth-secret")
    monkeypatch.delenv("POSTBRIDGE_SMTP_HOST", raising=False)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine = engine_for_url(database_url)

    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    engine.dispose()
    factory = session_factory_for_url(database_url)
    yield factory
    event.remove(engine, "connect", enable_sqlite_foreign_keys)
    engine.dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()


def test_email_code_creates_a_reusable_cross_client_session(auth_database):
    requested = request_code(EmailRequest(email="Owner@Example.Test"))
    assert requested["sent"] is True
    assert len(requested["development_code"]) == 6

    verified = verify_code(VerifyCodeRequest(email="owner@example.test", code=requested["development_code"]))
    identity = auth.authenticate_token(verified["access_token"])
    assert identity.email == "owner@example.test"
    assert identity.id == verified["user"]["id"]


def test_login_code_cannot_be_replayed(auth_database):
    requested = request_code(EmailRequest(email="owner@example.test"))
    payload = VerifyCodeRequest(email="owner@example.test", code=requested["development_code"])
    verify_code(payload)
    with pytest.raises(HTTPException) as replayed:
        verify_code(payload)
    assert replayed.value.status_code == 401


def test_failed_login_attempts_are_persisted(auth_database):
    requested = request_code(EmailRequest(email="owner@example.test"))
    incorrect_code = "000000" if requested["development_code"] != "000000" else "999999"
    for _ in range(5):
        with pytest.raises(HTTPException):
            verify_code(VerifyCodeRequest(email="owner@example.test", code=incorrect_code))

    with pytest.raises(HTTPException) as locked:
        verify_code(VerifyCodeRequest(email="owner@example.test", code=requested["development_code"]))
    assert locked.value.status_code == 401


def test_account_context_is_persisted_and_scoped_to_the_user(auth_database):
    first_code = request_code(EmailRequest(email="first@example.test"))["development_code"]
    first_session = verify_code(VerifyCodeRequest(email="first@example.test", code=first_code))
    first = auth.authenticate_token(first_session["access_token"])
    second_code = request_code(EmailRequest(email="second@example.test"))["development_code"]
    second_session = verify_code(VerifyCodeRequest(email="second@example.test", code=second_code))
    second = auth.authenticate_token(second_session["access_token"])

    saved = save_account_context(
        AccountContextRequest(
            account_theme="Practical magic tutorials",
            about_this_account="Beginner-friendly lessons.",
            target_audience="Beginner creators",
            preferred_hashtags=["#Magic", "tutorial", "#Magic"],
        ),
        first,
    )

    assert {
        "account_theme",
        "about_this_account",
        "target_audience",
        "tone_keys",
        "content_formats",
        "caption_language",
        "primary_category",
        "audience_age_ranges",
    }.issubset(saved)
    assert saved["account_theme"] == "Practical magic tutorials"
    assert saved["preferred_hashtags"] == ("#Magic", "#tutorial")
    assert account_context(first) == saved
    assert account_context(second)["account_theme"] == ""
    assert account_context(second)["about_this_account"] == ""


def test_legacy_account_context_fields_are_ignored(auth_database):
    code = request_code(EmailRequest(email="legacy@example.test"))["development_code"]
    verified = verify_code(VerifyCodeRequest(email="legacy@example.test", code=code))
    user = auth.authenticate_token(verified["access_token"])
    auth.update_account_context(
        user.id,
        '{"version":1,"account_theme":"Travel video","about_this_account":"City guides",'
        '"target_audience":"Weekend travellers","brand_voice":"Personal legacy value",'
        '"analysis_guidance":"Legacy analysis value","creation_guidance":"Legacy creation value"}',
    )

    restored = account_context(user)
    assert restored["account_theme"] == "Travel video"
    assert restored["about_this_account"] == "City guides"
    assert restored["target_audience"] == "Weekend travellers"
    assert restored["tone_keys"] == ()


def test_recent_post_suggestion_is_editable_and_never_infers_sensitive_or_demographic_fields():
    result = suggest_context_from_posts(
        [
            {
                "caption": "How do you plan this update? ✨",
                "media_type": "REELS",
                "thumbnail_url": "https://example.test/a.jpg",
            },
            {
                "caption": "A practical update and planning notes ✨",
                "media_type": "IMAGE",
                "thumbnail_url": "https://example.test/b.jpg",
            },
        ]
    )
    draft = result["draft"]
    assert result["source"]["posts_considered"] == 2
    assert set(draft["content_formats"]) == {"reel_video", "image"}
    assert draft["audience_age_ranges"] == []
    assert draft["target_audience"] == ""
    assert result["not_inferred"] == ["audience demographics", "sensitive traits"]


def test_login_codes_are_capped_per_email_per_day(auth_database, monkeypatch):
    monkeypatch.setenv("POSTBRIDGE_LOGIN_CODE_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("POSTBRIDGE_LOGIN_CODES_PER_DAY", "2")
    first = request_code(EmailRequest(email="owner@example.test"))["development_code"]
    request_code(EmailRequest(email="owner@example.test"))

    with pytest.raises(HTTPException) as capped:
        request_code(EmailRequest(email="owner@example.test"))
    assert capped.value.status_code == 429
    assert capped.value.detail["code"] == "too_many_codes"

    with pytest.raises(HTTPException):
        verify_code(VerifyCodeRequest(email="owner@example.test", code=first))
    assert request_code(EmailRequest(email="other@example.test"))["sent"] is True


def test_delete_account_removes_all_sql_records_with_foreign_keys_enabled(auth_database, monkeypatch):
    monkeypatch.setenv("POSTBRIDGE_MEDIA_STORAGE", "local")
    requested = request_code(EmailRequest(email="delete@example.test"))
    verified = verify_code(VerifyCodeRequest(email="delete@example.test", code=requested["development_code"]))
    user = auth.authenticate_token(verified["access_token"])
    now = datetime.now(UTC)

    with auth_database.begin() as session:
        records = [
            InstagramConnectionRecord(
                id="account-1",
                user_id=user.id,
                instagram_user_id="instagram-user-1",
                username="creator",
                account_type="BUSINESS",
                media_count=1,
                encrypted_access_token="encrypted-token",
                token_expires_at=None,
                scopes=[],
                session_synced_at=None,
                session_sync_error=None,
                tracking_start_at=now,
                status="connected",
                created_at=now,
                updated_at=now,
            ),
            InstagramMediaRecord(
                id="media-1",
                account_id="account-1",
                instagram_media_id="instagram-media-1",
                media_type="IMAGE",
                media_url="https://example.test/media.jpg",
                thumbnail_url=None,
                permalink=None,
                caption="Caption",
                published_at=now,
                last_synced_at=now,
            ),
            TrackedPostRecord(
                id="tracked-1",
                user_id=user.id,
                media_id="media-1",
                is_active=True,
                started_at=now,
                stopped_at=None,
                first_24h_status="collecting",
                first_24h_reason=None,
            ),
            InstagramInsightSnapshotRecord(
                id="snapshot-1",
                media_id="media-1",
                captured_at=now,
                likes=1,
                comments=1,
                saves=1,
                shares=1,
                reach=10,
                views=10,
                engagement_rate=40.0,
                average_watch_time_ms=None,
                total_watch_time_ms=None,
                raw_metrics={},
                metric_status={},
                scheduled_for=now,
                milestone_hours=1,
                source="api",
                lateness_seconds=0,
            ),
            InstagramCommentRecord(
                id="comment-1",
                provider_id="provider-comment-1",
                user_id=user.id,
                tracked_post_id="tracked-1",
                text="Comment",
                like_count=1,
                timestamp=now,
                is_owner_reply=False,
                fetched_at=now,
            ),
            InsightTextCacheRecord(
                id="cache-1",
                user_id=user.id,
                tracked_post_id="tracked-1",
                cache_key="summary:tracked-1",
                input_hash="hash",
                text="Summary",
                model_name="test-model",
                provider="template",
                prompt_version="test",
                facts_json=[],
                created_at=now,
                updated_at=now,
            ),
            InstagramInsightCollectionJobRecord(
                id="job-1",
                user_id=user.id,
                tracked_post_id="tracked-1",
                media_id="media-1",
                milestone_hours=1,
                due_at=now,
                deadline_at=now + timedelta(hours=1),
                next_attempt_at=now,
                attempt_count=0,
                status="pending",
                snapshot_id="snapshot-1",
                reason=None,
                locked_at=None,
                locked_by=None,
                completed_at=None,
                created_at=now,
                updated_at=now,
            ),
            AIGenerationLogRecord(
                id="generation-1",
                generator="summary",
                tracked_post_id="tracked-1",
                provider="template",
                model="test-model",
                prompt_version="test",
                input_hash="hash",
                status="success",
                latency_ms=1,
                token_usage=None,
                raw_response=None,
                created_at=now,
            ),
            MediaAssetRecord(
                id="asset-1",
                user_id=user.id,
                storage_provider="oci",
                object_name=f"draft-assets/{user.id}/asset.jpg",
                original_filename="asset.jpg",
                mime_type="image/jpeg",
                byte_size=4,
                checksum_sha256="checksum",
                status="ready",
                created_at=now,
                updated_at=now,
            ),
            PostDraftRecord(
                id="draft-1",
                user_id=user.id,
                media_asset_id="asset-1",
                target_platforms=["Instagram"],
                content_brief="Brief",
                goal="Goal",
                caption="Caption",
                hashtags=["#test"],
                status="draft",
                created_at=now,
                updated_at=now,
            ),
            PostPublicationRecord(
                id="publication-1",
                user_id=user.id,
                draft_id="draft-1",
                platform="Instagram",
                provider_media_id=None,
                provider_post_id=None,
                idempotency_key="delete-test-key",
                status="pending",
                error_code=None,
                error_message=None,
                created_at=now,
                updated_at=now,
                published_at=None,
            ),
            PredictionHistoryRecord(
                id="prediction-1",
                user_id=user.id,
                input_payload={},
                output_payload={},
                created_at=now,
            ),
            OAuthStateRecord(
                nonce="oauth-state-1",
                user_id=user.id,
                expires_at=now + timedelta(minutes=10),
                consumed_at=None,
                created_at=now,
            ),
        ]
        insertion_groups = (
            (InstagramConnectionRecord, MediaAssetRecord, PredictionHistoryRecord, OAuthStateRecord),
            (InstagramMediaRecord, PostDraftRecord),
            (TrackedPostRecord, PostPublicationRecord),
            (
                InstagramInsightSnapshotRecord,
                InstagramCommentRecord,
                InsightTextCacheRecord,
                AIGenerationLogRecord,
            ),
            (InstagramInsightCollectionJobRecord,),
        )
        for record_types in insertion_groups:
            session.add_all([record for record in records if isinstance(record, record_types)])
            session.flush()

    with auth_database() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1

    assert delete_account(user) == {"deleted": True}

    models = (
        PostPublicationRecord,
        PostDraftRecord,
        MediaAssetRecord,
        AIGenerationLogRecord,
        InstagramInsightCollectionJobRecord,
        InstagramCommentRecord,
        InsightTextCacheRecord,
        InstagramInsightSnapshotRecord,
        TrackedPostRecord,
        InstagramMediaRecord,
        InstagramConnectionRecord,
        PredictionHistoryRecord,
        AuthSessionRecord,
        OAuthStateRecord,
        LoginCodeRecord,
        UserRecord,
    )
    with auth_database() as session:
        for model in models:
            assert session.scalar(select(func.count()).select_from(model)) == 0, model.__tablename__


def test_local_account_cleanup_removes_only_the_selected_users_data(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    monkeypatch.setattr(token_store, "TOKEN_STORE_PATH", tmp_path / "tokens.json")
    get_content_repository.cache_clear()
    now = datetime.now(UTC)

    json_store.save_store(
        StoreData(
            instagram_accounts=[
                InstagramAccount(
                    id="account-delete",
                    user_id="user-delete",
                    instagram_user_id="ig-delete",
                    username="delete",
                    encrypted_access_token="",
                    connected_at=now,
                ),
                InstagramAccount(
                    id="account-keep",
                    user_id="user-keep",
                    instagram_user_id="ig-keep",
                    username="keep",
                    encrypted_access_token="",
                    connected_at=now,
                ),
            ],
            instagram_media=[
                InstagramMedia(
                    id="media-delete",
                    account_id="account-delete",
                    instagram_media_id="provider-delete",
                    media_type="IMAGE",
                    published_at=now,
                    last_synced_at=now,
                ),
                InstagramMedia(
                    id="media-keep",
                    account_id="account-keep",
                    instagram_media_id="provider-keep",
                    media_type="IMAGE",
                    published_at=now,
                    last_synced_at=now,
                ),
            ],
            tracked_posts=[
                TrackedPost(id="tracked-delete", user_id="user-delete", media_id="media-delete", started_at=now),
                TrackedPost(id="tracked-keep", user_id="user-keep", media_id="media-keep", started_at=now),
            ],
            instagram_insight_snapshots=[
                InstagramInsightSnapshot(id="snapshot-delete", media_id="media-delete", captured_at=now),
                InstagramInsightSnapshot(id="snapshot-keep", media_id="media-keep", captured_at=now),
            ],
            instagram_comments=[
                InstagramComment(
                    id="comment-delete",
                    provider_id="provider-comment-delete",
                    user_id="user-delete",
                    tracked_post_id="tracked-delete",
                    text="Delete",
                    timestamp=now,
                    fetched_at=now,
                ),
                InstagramComment(
                    id="comment-keep",
                    provider_id="provider-comment-keep",
                    user_id="user-keep",
                    tracked_post_id="tracked-keep",
                    text="Keep",
                    timestamp=now,
                    fetched_at=now,
                ),
            ],
        )
    )
    token_store.save_encrypted_token("account-delete", "token-delete")
    token_store.save_encrypted_token("account-keep", "token-keep")
    repository = get_content_repository()
    repository.upsert_text_cache(
        InsightTextCache(
            id="cache-delete",
            user_id="user-delete",
            cache_key="summary",
            input_hash="hash",
            text="Delete",
            model_name="test",
            created_at=now,
            updated_at=now,
        )
    )
    repository.upsert_text_cache(
        InsightTextCache(
            id="cache-keep",
            user_id="user-keep",
            cache_key="summary",
            input_hash="hash",
            text="Keep",
            model_name="test",
            created_at=now,
            updated_at=now,
        )
    )

    delete_local_user_data("user-delete")

    store = json_store.load_store()
    assert [item.user_id for item in store.instagram_accounts] == ["user-keep"]
    assert [item.id for item in store.instagram_media] == ["media-keep"]
    assert [item.id for item in store.tracked_posts] == ["tracked-keep"]
    assert [item.id for item in store.instagram_insight_snapshots] == ["snapshot-keep"]
    assert [item.id for item in store.instagram_comments] == ["comment-keep"]
    assert token_store.get_encrypted_token("account-delete") is None
    assert token_store.get_encrypted_token("account-keep") == "token-keep"
    assert repository.get_text_cache("user-delete", "summary") is None
    assert repository.get_text_cache("user-keep", "summary") is not None
    get_content_repository.cache_clear()
