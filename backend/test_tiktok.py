from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import tiktok_api
from backend.services import tiktok
from backend.services.publishing import PublishInput, TikTokPublishingAdapter
from backend.storage.models import TikTokConnection
from backend.storage.sql_models import Base, UserRecord
from backend.storage.tiktok_repository import TikTokRepository


@pytest.fixture
def tiktok_environment(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    repository = TikTokRepository(factory)
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(UserRecord(id="user-1", email="creator@example.test", created_at=now, updated_at=now))
    monkeypatch.setattr(tiktok, "get_tiktok_repository", lambda: repository)
    monkeypatch.setattr(tiktok_api, "get_tiktok_repository", lambda: repository)
    monkeypatch.setenv("POSTBRIDGE_TIKTOK_CLIENT_KEY", "sandbox-key")
    monkeypatch.setenv("POSTBRIDGE_TIKTOK_CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setenv("POSTBRIDGE_TIKTOK_REDIRECT_URI", "https://api.example.test/api/tiktok/connect/callback")
    monkeypatch.setenv("POSTBRIDGE_TIKTOK_SCOPES", "user.info.basic,video.list,video.publish")
    monkeypatch.setenv("POSTBRIDGE_TIKTOK_MEDIA_URL_SECRET", "media-url-secret")
    monkeypatch.setenv("POSTBRIDGE_PUBLIC_API_URL", "https://api.example.test")
    monkeypatch.setenv("POSTBRIDGE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.test")
    try:
        yield repository
    finally:
        engine.dispose()


def _connection(**changes):
    now = datetime.now(UTC)
    values = {
        "id": "connection-1",
        "user_id": "user-1",
        "open_id": "open-1",
        "union_id": "union-1",
        "display_name": "Creator",
        "avatar_url": "https://example.test/avatar.jpg",
        "access_token_expires_at": now + timedelta(hours=1),
        "refresh_token_expires_at": now + timedelta(days=30),
        "scopes": ["user.info.basic", "video.publish"],
        "status": "connected",
        "connected_at": now,
        "updated_at": now,
    }
    values.update(changes)
    return TikTokConnection(**values)


def test_oauth_state_is_single_use_and_authorization_url_is_sandbox_ready(tiktok_environment):
    state = tiktok.create_oauth_state("user-1")
    url = tiktok.build_authorization_url(state)
    query = parse_qs(urlparse(url).query)

    assert query["client_key"] == ["sandbox-key"]
    assert query["redirect_uri"] == ["https://api.example.test/api/tiktok/connect/callback"]
    assert query["scope"] == ["user.info.basic,video.list,video.publish"]
    assert tiktok.consume_oauth_state(state) == ("user-1", "web")
    with pytest.raises(tiktok.TikTokServiceError) as replayed:
        tiktok.consume_oauth_state(state)
    assert replayed.value.code == "invalid_oauth_state"


def test_token_exchange_uses_server_side_credentials(monkeypatch, tiktok_environment):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {
            "access_token": "access-sensitive",
            "refresh_token": "refresh-sensitive",
            "open_id": "open-1",
            "scope": "user.info.basic,video.publish",
        }

    monkeypatch.setattr(tiktok, "_request_json", fake_request)
    result = tiktok.exchange_authorization_code("private-code")

    assert result["open_id"] == "open-1"
    assert calls[0][2]["form"]["client_secret"] == "sandbox-secret"
    assert calls[0][2]["form"]["redirect_uri"] == "https://api.example.test/api/tiktok/connect/callback"


def test_fetch_user_videos_uses_the_display_api(monkeypatch, tiktok_environment):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"data": {"videos": [{"id": "video-1", "title": "A TikTok post"}]}}

    monkeypatch.setattr(tiktok, "_request_json", fake_request)

    assert tiktok.fetch_user_videos("access-sensitive") == [{"id": "video-1", "title": "A TikTok post"}]
    assert calls[0][0] == "POST"
    assert calls[0][1] == tiktok.TIKTOK_VIDEO_LIST_URL
    assert calls[0][2]["access_token"] == "access-sensitive"
    assert "cover_image_url" in calls[0][2]["query"]["fields"]
    assert "like_count" in calls[0][2]["query"]["fields"]
    assert "view_count" in calls[0][2]["query"]["fields"]


def test_fetch_videos_by_ids_refreshes_public_metrics(monkeypatch, tiktok_environment):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"data": {"videos": [{"id": "video-1", "view_count": 120}]}}

    monkeypatch.setattr(tiktok, "_request_json", fake_request)

    assert tiktok.fetch_videos_by_ids("access-sensitive", ["video-1"]) == [{"id": "video-1", "view_count": 120}]
    assert calls[0][1] == tiktok.TIKTOK_VIDEO_QUERY_URL
    assert calls[0][2]["json_body"] == {"filters": {"video_ids": ["video-1"]}}


def test_tracked_tiktok_post_stores_metrics_and_can_be_removed(tiktok_environment):
    tracked = tiktok_environment.track_post(
        "user-1",
        {
            "id": "video-1",
            "title": "A TikTok post",
            "create_time": 1_700_000_000,
            "like_count": 20,
            "comment_count": 5,
            "share_count": 3,
            "view_count": 200,
        },
    )

    assert tracked["likes"] == 20
    assert tracked["views"] == 200
    assert tracked["engagement_rate"] == 14.0
    assert tiktok_environment.delete_tracked_post("user-1", tracked["id"]) is True
    assert tiktok_environment.tracked_posts("user-1") == []


def test_tiktok_analysis_compares_official_metrics():
    selected = {
        "id": "selected",
        "views": 300,
        "likes": 30,
        "comments": 4,
        "shares": 6,
        "engagement_rate": 13.3,
        "published_at": datetime.now(UTC),
    }
    peers = [
        {"id": "one", "views": 100, "likes": 10, "comments": 2, "shares": 2, "engagement_rate": 14.0},
        {"id": "two", "views": 200, "likes": 20, "comments": 3, "shares": 3, "engagement_rate": 13.0},
    ]

    analysis = tiktok_api._tiktok_analysis(selected, [selected, *peers])

    assert analysis["comparable"] is True
    assert next(row for row in analysis["usual_ranges"] if row["metric"] == "views")["status"] == "above"
    assert "300 views" in analysis["summary"]


def test_callback_encrypts_both_tokens_and_redirects_without_secrets(monkeypatch, tiktok_environment):
    state = tiktok.create_oauth_state("user-1")
    monkeypatch.setattr(
        tiktok_api,
        "exchange_authorization_code",
        lambda code: {
            "access_token": "access-sensitive",
            "refresh_token": "refresh-sensitive",
            "open_id": "open-1",
            "scope": "user.info.basic,video.publish",
            "expires_in": 7200,
            "refresh_expires_in": 3600 * 24 * 180,
        },
    )
    monkeypatch.setattr(
        tiktok_api,
        "fetch_user_info",
        lambda token: {
            "open_id": "open-1",
            "union_id": "union-1",
            "display_name": "Creator",
            "avatar_url": "https://example.test/avatar.jpg",
        },
    )

    response = tiktok_api.connect_callback(code="private-code", state=state)

    assert response.status_code == 302
    assert response.headers["location"] == "https://app.example.test/dashboard?tab=settings&tiktok=connected"
    stored = tiktok_environment.get_connection("user-1")
    encrypted = tiktok_environment.get_encrypted_tokens(stored.id)
    assert tiktok.decrypt_token(encrypted[0]) == "access-sensitive"
    assert tiktok.decrypt_token(encrypted[1]) == "refresh-sensitive"
    assert "sensitive" not in response.headers["location"]


def test_expiring_access_token_is_refreshed_and_rotated(monkeypatch, tiktok_environment):
    connection = _connection(access_token_expires_at=datetime.now(UTC) + timedelta(minutes=2))
    tiktok_environment.upsert_connection(
        connection,
        encrypted_access_token=tiktok.encrypt_token("old-access"),
        encrypted_refresh_token=tiktok.encrypt_token("old-refresh"),
    )
    monkeypatch.setattr(
        tiktok_api,
        "refresh_access_token",
        lambda token: {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 7200,
            "refresh_expires_in": 3600 * 24 * 180,
            "scope": "user.info.basic,video.publish",
        },
    )

    assert tiktok_api.access_token_for(connection) == "new-access"
    encrypted = tiktok_environment.get_encrypted_tokens(connection.id)
    assert tiktok.decrypt_token(encrypted[0]) == "new-access"
    assert tiktok.decrypt_token(encrypted[1]) == "new-refresh"


def test_signed_media_url_round_trip_and_expiry(monkeypatch, tiktok_environment):
    token = tiktok.create_media_token("draft-assets/user-1/photo.jpg", "image/jpeg")
    assert tiktok.verify_media_token(token) == ("draft-assets/user-1/photo.jpg", "image/jpeg")
    assert tiktok.create_media_url("draft-assets/user-1/photo.jpg", "image/jpeg").startswith(
        "https://api.example.test/api/tiktok/media/"
    )
    monkeypatch.setattr(tiktok.time, "time", lambda: 9_999_999_999)
    with pytest.raises(tiktok.TikTokServiceError) as expired:
        tiktok.verify_media_token(token)
    assert expired.value.code == "tiktok_media_url_invalid"


def _publish_request(mime_type="image/jpeg", **options):
    platform_options = {
        "TikTok": {
            "privacy_level": "SELF_ONLY",
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
            **options,
        }
    }
    return PublishInput(
        caption="Caption",
        hashtags="#tag",
        mime_type=mime_type,
        object_name="draft-assets/user-1/media.jpg" if mime_type.startswith("image/") else None,
        encoded_media=None if mime_type.startswith("image/") else "dmlkZW8=",
        duration_seconds=10 if mime_type.startswith("video/") else None,
        platform_options=platform_options,
    )


def test_tiktok_adapter_publishes_photo_as_async_job():
    calls = []
    adapter = TikTokPublishingAdapter(
        account_loader=lambda user_id: SimpleNamespace(status="connected", scopes=["video.publish"]),
        token_loader=lambda account: "access-token",
        creator_info_loader=lambda token: {
            "privacy_level_options": ["SELF_ONLY"],
            "comment_disabled": False,
        },
        media_url_factory=lambda name, mime: f"https://api.example.test/media/{name}",
        photo_publisher=lambda token, **kwargs: calls.append((token, kwargs)) or "photo-publish-1",
        video_publisher=lambda *args, **kwargs: "unused",
        status_loader=lambda token, publish_id: {"status": "PROCESSING_DOWNLOAD"},
    )

    result = adapter.publish("user-1", _publish_request())

    assert result.status == "publishing"
    assert result.provider_post_id == "photo-publish-1"
    assert calls[0][1]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert calls[0][1]["description"] == "Caption\n\n#tag"


def test_tiktok_adapter_publishes_video_by_file_upload_and_maps_status():
    calls = []
    statuses = iter([{"status": "PROCESSING_UPLOAD"}, {"status": "PUBLISH_COMPLETE"}])
    adapter = TikTokPublishingAdapter(
        account_loader=lambda user_id: SimpleNamespace(status="connected", scopes=["video.publish"]),
        token_loader=lambda account: "access-token",
        creator_info_loader=lambda token: {
            "privacy_level_options": ["SELF_ONLY"],
            "max_video_post_duration_sec": 60,
            "comment_disabled": False,
            "duet_disabled": False,
            "stitch_disabled": False,
        },
        media_url_factory=lambda name, mime: "unused",
        photo_publisher=lambda *args, **kwargs: "unused",
        video_publisher=lambda token, **kwargs: calls.append((token, kwargs)) or "video-publish-1",
        status_loader=lambda token, publish_id: next(statuses),
    )

    result = adapter.publish("user-1", _publish_request("video/mp4"))

    assert result.status == "publishing"
    assert calls[0][1]["media_bytes"] == b"video"
    assert adapter.status("user-1", "video-publish-1") == "publishing"
    assert adapter.status("user-1", "video-publish-1") == "published"


def test_tiktok_adapter_requires_explicit_privacy():
    adapter = TikTokPublishingAdapter(
        account_loader=lambda user_id: SimpleNamespace(status="connected", scopes=["video.publish"]),
        token_loader=lambda account: "access-token",
        creator_info_loader=lambda token: {},
        media_url_factory=lambda name, mime: "unused",
        photo_publisher=lambda *args, **kwargs: "unused",
        video_publisher=lambda *args, **kwargs: "unused",
        status_loader=lambda token, publish_id: {},
    )
    request = PublishInput(
        caption="Caption",
        hashtags="",
        mime_type="image/jpeg",
        object_name="draft-assets/user-1/photo.jpg",
    )

    result = adapter.validate(request)

    assert result.code == "tiktok_privacy_required"
