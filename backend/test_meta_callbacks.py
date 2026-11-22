import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import instagram_api
from backend.storage.instagram_repository import SQLAlchemyInstagramRepository
from backend.storage.sql_models import (
    AIGenerationLogRecord,
    Base,
    InsightTextCacheRecord,
    InstagramCommentRecord,
    InstagramConnectionRecord,
    InstagramDataDeletionRequestRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    OAuthStateRecord,
    TrackedPostRecord,
    UserRecord,
)


def _signed_request(user_id: str, secret: str, *, algorithm: str = "HMAC-SHA256") -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"algorithm": algorithm, "user_id": user_id}, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}.{payload.decode('ascii')}"


@pytest.fixture
def callback_repository(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    repository = SQLAlchemyInstagramRepository.from_engine(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(instagram_api, "get_instagram_repository", lambda: repository)
    monkeypatch.setenv("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET", "meta-test-secret")
    monkeypatch.setenv("POSTBRIDGE_PUBLIC_API_URL", "https://api.example.test")
    try:
        yield repository, factory
    finally:
        engine.dispose()


def _seed_connection(factory, *, instagram_user_id: str = "ig-user", user_id: str = "user-1") -> datetime:
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            UserRecord(
                id=user_id,
                email=f"{user_id}@example.test",
                account_context="",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            InstagramConnectionRecord(
                id="connection-1",
                user_id=user_id,
                instagram_user_id=instagram_user_id,
                username="creator",
                account_type="BUSINESS",
                media_count=1,
                encrypted_access_token="encrypted-token",
                token_expires_at=now + timedelta(days=30),
                scopes=["instagram_business_basic", "instagram_business_manage_comments"],
                session_synced_at=None,
                session_sync_error=None,
                tracking_start_at=now,
                status="connected",
                created_at=now,
                updated_at=now,
            )
        )
    return now


def _seed_instagram_derived_data(factory) -> None:
    now = _seed_connection(factory)
    with factory.begin() as session:
        session.add(
            InstagramMediaRecord(
                id="media-1",
                account_id="connection-1",
                instagram_media_id="provider-media-1",
                media_type="IMAGE",
                media_url="https://instagram.example.test/media.jpg",
                thumbnail_url=None,
                permalink=None,
                caption="A caption from Instagram",
                published_at=now,
                last_synced_at=now,
            )
        )
        session.add(
            TrackedPostRecord(
                id="tracked-1",
                user_id="user-1",
                media_id="media-1",
                is_active=True,
                started_at=now,
                stopped_at=None,
                first_24h_status="collecting",
                first_24h_reason=None,
            )
        )
        session.flush()
        session.add_all(
            [
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
                    scheduled_for=None,
                    milestone_hours=None,
                    source="api",
                    lateness_seconds=None,
                ),
                InstagramCommentRecord(
                    id="comment-1",
                    provider_id="provider-comment-1",
                    user_id="user-1",
                    tracked_post_id="tracked-1",
                    text="A viewer comment",
                    like_count=2,
                    timestamp=now,
                    is_owner_reply=False,
                    fetched_at=now,
                ),
                InsightTextCacheRecord(
                    id="cache-1",
                    user_id="user-1",
                    tracked_post_id="tracked-1",
                    cache_key="summary:tracked-1",
                    input_hash="input-hash",
                    text="Generated summary",
                    model_name="test-model",
                    provider="template",
                    prompt_version="test",
                    facts_json=[],
                    created_at=now,
                    updated_at=now,
                ),
                AIGenerationLogRecord(
                    id="log-1",
                    generator="summary",
                    tracked_post_id="tracked-1",
                    provider="template",
                    model="test-model",
                    prompt_version="test",
                    input_hash="input-hash",
                    status="success",
                    latency_ms=1,
                    token_usage=None,
                    raw_response=None,
                    created_at=now,
                ),
                OAuthStateRecord(
                    nonce="oauth-state-1",
                    user_id="user-1",
                    expires_at=now + timedelta(minutes=10),
                    consumed_at=None,
                    created_at=now,
                ),
            ]
        )
        session.flush()
        session.add(
            InstagramInsightCollectionJobRecord(
                id="job-1",
                user_id="user-1",
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
            )
        )


def _count(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_valid_signed_request_deauthorizes_connection_and_erases_token(callback_repository):
    repository, factory = callback_repository
    _seed_connection(factory)

    result = instagram_api.deauthorize(_signed_request("ig-user", "meta-test-secret"))

    assert result == {"deauthorized": True}
    assert repository.get_encrypted_token("connection-1") == ""
    with factory() as session:
        connection = session.get(InstagramConnectionRecord, "connection-1")
        assert connection.status == "disconnected"
        assert connection.token_expires_at is None


@pytest.mark.parametrize(
    "signed_request",
    [
        "not-a-signed-request",
        _signed_request("ig-user", "wrong-secret"),
        _signed_request("ig-user", "meta-test-secret", algorithm="HMAC-SHA1"),
    ],
)
def test_invalid_signed_request_is_rejected(callback_repository, signed_request):
    with pytest.raises(HTTPException) as failure:
        instagram_api.deauthorize(signed_request)

    assert failure.value.status_code == 400
    assert failure.value.detail["code"] == "invalid_signed_request"


def test_unknown_meta_user_still_receives_completed_deletion_confirmation(callback_repository):
    _, _factory = callback_repository

    result = instagram_api.data_deletion(_signed_request("unknown-instagram-user", "meta-test-secret"))

    assert result["url"] == (
        "https://api.example.test/api/instagram/data-deletion/status?code=" + result["confirmation_code"]
    )
    status = instagram_api.data_deletion_status(result["confirmation_code"])
    assert status["status"] == "completed"
    assert status["completed_at"] is not None


def test_data_deletion_removes_all_instagram_records_but_keeps_postbridge_user(callback_repository):
    _repository, factory = callback_repository
    _seed_instagram_derived_data(factory)

    result = instagram_api.data_deletion(_signed_request("ig-user", "meta-test-secret"))

    models_removed = (
        InstagramInsightCollectionJobRecord,
        AIGenerationLogRecord,
        InstagramCommentRecord,
        InsightTextCacheRecord,
        InstagramInsightSnapshotRecord,
        TrackedPostRecord,
        InstagramMediaRecord,
        InstagramConnectionRecord,
        OAuthStateRecord,
    )
    with factory() as session:
        for model in models_removed:
            assert _count(session, model) == 0, model.__tablename__
        assert _count(session, UserRecord) == 1
        request = session.get(InstagramDataDeletionRequestRecord, result["confirmation_code"])
        assert request is not None
        assert request.status == "completed"
