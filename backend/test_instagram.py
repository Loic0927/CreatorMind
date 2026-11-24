from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, HTTPException

from backend import instagram_api
from backend.auth import AuthenticatedUser
from backend.services import feedback, insight_texts, instagram
from backend.services.instagram import (
    InstagramServiceError,
    aggregate_seven_days,
    consume_oauth_state,
    create_oauth_state,
    engagement_rate,
    exchange_authorization_code,
    exchange_long_lived_token,
    fetch_instagram_media_insights,
    refresh_long_lived_token,
    safe_raw_metrics,
)
from backend.storage import json_store
from backend.storage.instagram_repository import LocalDevelopmentInstagramRepository
from backend.storage.models import (
    InstagramAccount,
    InstagramInsightSnapshot,
    InstagramMedia,
)


@pytest.fixture(autouse=True)
def instagram_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTBRIDGE_INSTAGRAM_CLIENT_ID", "test-client")
    monkeypatch.setenv("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "POSTBRIDGE_INSTAGRAM_REDIRECT_URI",
        "https://example.test/api/instagram/connect/callback",
    )
    monkeypatch.setenv(
        "POSTBRIDGE_INSTAGRAM_APP_RETURN_URI",
        "creatormind://instagram-connected",
    )
    monkeypatch.setenv("POSTBRIDGE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("POSTBRIDGE_OAUTH_STATE_SECRET", "test-state-secret")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.test")
    repository = LocalDevelopmentInstagramRepository()
    monkeypatch.setattr(instagram, "get_instagram_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "get_instagram_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "has_ai_processing_consent", lambda _user_id: True)
    monkeypatch.setattr(json_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    from backend.storage import token_store

    monkeypatch.setattr(token_store, "TOKEN_STORE_PATH", tmp_path / "postbridge_tokens.local.json")
    return repository


def test_oauth_state_valid_and_single_use():
    state = create_oauth_state("user-a")
    assert consume_oauth_state(state) == "user-a"
    with pytest.raises(InstagramServiceError) as replayed:
        consume_oauth_state(state)
    assert replayed.value.code == "invalid_oauth_state"


def test_oauth_state_expired():
    state = create_oauth_state("user-a", lifetime_seconds=-1)
    with pytest.raises(InstagramServiceError) as expired:
        consume_oauth_state(state)
    assert expired.value.code == "invalid_oauth_state"


def test_oauth_state_tampered():
    state = create_oauth_state("user-a")
    encoded, signature = state.split(".", 1)
    with pytest.raises(InstagramServiceError) as tampered:
        consume_oauth_state(f"{encoded}x.{signature}")
    assert tampered.value.code == "invalid_oauth_state"


def test_authorization_url_has_required_scopes():
    url = instagram.build_authorization_url(create_oauth_state("user-a"))
    assert "instagram_business_basic" in url
    assert "instagram_business_manage_insights" in url
    assert "instagram_business_content_publish" in url


def test_authorization_url_uses_configured_redirect_uri():
    url = instagram.build_authorization_url(create_oauth_state("user-a"))
    query = parse_qs(urlparse(url).query)
    assert query["redirect_uri"] == ["https://example.test/api/instagram/connect/callback"]


def test_token_exchange_success(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "POST":
            return {"access_token": "short-token", "user_id": 1}
        return {"access_token": "long-token", "expires_in": 3600}

    monkeypatch.setattr(instagram, "_request_json", fake_request)
    short = exchange_authorization_code("authorization-code")
    long_lived = exchange_long_lived_token(short["access_token"])
    assert long_lived["access_token"] == "long-token"
    assert calls[0][0] == "POST"
    assert calls[1][0] == "GET"


def test_token_exchange_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(instagram, "_request_json", lambda *args, **kwargs: {})
    with pytest.raises(InstagramServiceError) as failure:
        exchange_authorization_code("sensitive-code")
    assert failure.value.code == "instagram_short_token_exchange_failed"
    assert "sensitive-code" not in str(failure.value)


def test_publish_instagram_reel_waits_for_processing_then_publishes(monkeypatch):
    calls = []
    statuses = iter(["IN_PROGRESS", "FINISHED"])

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "POST" and url.endswith("/ig-user/media"):
            return {"id": "container-1"}
        if method == "GET" and url.endswith("/container-1"):
            return {"status_code": next(statuses)}
        if method == "POST" and url.endswith("/ig-user/media_publish"):
            return {"id": "media-1"}
        if method == "GET" and url.endswith("/media-1"):
            return {"id": "media-1", "media_type": "VIDEO", "permalink": "https://instagram.test/reel/1"}
        raise AssertionError(f"Unexpected provider request: {method} {url}")

    monkeypatch.setattr(instagram, "_request_json", fake_request)
    monkeypatch.setattr(instagram.time, "sleep", lambda seconds: None)

    result = instagram.publish_instagram_reel(
        "token",
        "ig-user",
        "https://objects.test/video.mp4",
        "Caption",
        status_attempts=3,
        status_interval_seconds=0,
    )

    assert result["id"] == "media-1"
    create_form = calls[0][2]["form"]
    assert create_form["media_type"] == "REELS"
    assert create_form["video_url"] == "https://objects.test/video.mp4"
    assert sum(url.endswith("/container-1") for _, url, _ in calls) == 2


def _account(encrypted_token: str = "encrypted") -> InstagramAccount:
    return InstagramAccount(
        id="account-1",
        user_id="owner@example.test",
        instagram_user_id="ig-1",
        username="creator",
        account_type="BUSINESS",
        media_count=2,
        encrypted_access_token=encrypted_token,
        connected_at=datetime.now(UTC),
    )


def test_callback_success_encrypts_before_storage_and_hides_tokens(monkeypatch, caplog, instagram_environment):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(
        instagram_api,
        "exchange_authorization_code",
        lambda code: {
            "access_token": "short-sensitive",
            "permissions": "instagram_business_basic,instagram_business_manage_comments",
        },
    )
    monkeypatch.setattr(
        instagram_api,
        "exchange_long_lived_token",
        lambda token: {"access_token": "long-sensitive", "expires_in": 3600},
    )
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: {
            "id": "ig-1",
            "username": "creator",
            "account_type": "BUSINESS",
            "media_count": 4,
        },
    )
    response = instagram_api.connect_callback(code="private-code", state=state)

    assert response.status_code == 302
    assert response.headers["location"] == "creatormind://instagram-connected?status=success"
    stored = instagram_environment.get_connection("owner@example.test")
    assert stored.encrypted_access_token == ""
    assert stored.scopes == ["instagram_business_basic", "instagram_business_manage_comments"]
    encrypted = instagram_environment.get_encrypted_token(stored.id)
    assert instagram.decrypt_access_token(encrypted) == "long-sensitive"
    rendered = response.headers["location"] + caplog.text
    for secret in ("private-code", "short-sensitive", "long-sensitive", "test-client-secret"):
        assert secret not in rendered


@pytest.mark.parametrize(
    "kwargs,expected_code",
    [
        ({"code": None, "state": None}, "invalid_oauth_callback"),
        ({"code": None, "state": None, "error": "access_denied"}, "instagram_authorization_denied"),
    ],
)
def test_callback_rejects_invalid_or_denied_requests(kwargs, expected_code):
    response = instagram_api.connect_callback(**kwargs)
    assert response.status_code == 302
    assert parse_qs(urlparse(response.headers["location"]).query) == {
        "status": ["error"],
        "code": [expected_code],
    }
    assert "access_denied" not in response.headers["location"]


def test_web_callback_denial_returns_to_web_app():
    state = create_oauth_state("owner@example.test", client="web")
    response = instagram_api.connect_callback(state=state, error="access_denied")
    assert response.headers["location"] == (
        "https://app.example.test/dashboard?instagram=error&code=instagram_authorization_denied"
    )


def test_callback_exchange_error_is_sanitized(monkeypatch):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(
        instagram_api,
        "exchange_authorization_code",
        lambda code: (_ for _ in ()).throw(
            InstagramServiceError("instagram_upstream_error", "Instagram could not complete the request.")
        ),
    )
    response = instagram_api.connect_callback(code="private-code", state=state)
    assert response.headers["location"].endswith("?status=error&code=instagram_upstream_error")
    assert "private-code" not in response.headers["location"]


def test_callback_profile_failure_redirects_with_safe_code(monkeypatch):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(instagram_api, "exchange_authorization_code", lambda code: {"access_token": "short-secret"})
    monkeypatch.setattr(instagram_api, "exchange_long_lived_token", lambda token: {"access_token": "long-secret"})
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: (_ for _ in ()).throw(InstagramServiceError("instagram_profile_failed", "safe failure")),
    )
    response = instagram_api.connect_callback(code="private-code", state=state)
    assert response.headers["location"].endswith("?status=error&code=instagram_profile_failed")
    assert "secret" not in response.headers["location"]


def test_callback_requires_professional_account(monkeypatch):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(instagram_api, "exchange_authorization_code", lambda code: {"access_token": "short-secret"})
    monkeypatch.setattr(instagram_api, "exchange_long_lived_token", lambda token: {"access_token": "long-secret"})
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: {
            "id": "ig-personal",
            "username": "personal",
            "account_type": "PERSONAL",
            "media_count": 1,
        },
    )

    response = instagram_api.connect_callback(code="private-code", state=state)

    assert response.headers["location"].endswith("?status=error&code=instagram_professional_account_required")


def test_invalid_and_replayed_state_redirect_with_safe_code():
    invalid = instagram_api.connect_callback(code="private-code", state="invalid")
    assert invalid.headers["location"].endswith("?status=error&code=invalid_oauth_state")

    state = create_oauth_state("owner@example.test")
    consume_oauth_state(state)
    replayed = instagram_api.connect_callback(code="private-code", state=state)
    assert replayed.headers["location"].endswith("?status=error&code=invalid_oauth_state")


def test_arbitrary_mobile_return_uri_is_rejected():
    with pytest.raises(InstagramServiceError) as failure:
        instagram.instagram_app_return_uri("https://attacker.example/callback")
    assert failure.value.code == "instagram_return_uri_not_allowed"


def test_refresh_long_lived_token_interface(monkeypatch):
    calls = []
    monkeypatch.setattr(
        instagram,
        "_request_json",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or {"access_token": "refreshed-secret", "expires_in": 3600}
        ),
    )
    result = refresh_long_lived_token("existing-secret")
    assert result["expires_in"] == 3600
    assert calls[0][2]["query"]["grant_type"] == "ig_refresh_token"


def test_revoked_token_marks_connection_reconnect_required(monkeypatch, instagram_environment):
    encrypted = instagram.encrypt_access_token("private-token")
    instagram_environment.upsert_connection(_account(), encrypted_token=encrypted)
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: (_ for _ in ()).throw(
            InstagramServiceError(
                "instagram_token_invalid",
                "Instagram authorization is no longer valid.",
                401,
            )
        ),
    )
    with pytest.raises(HTTPException) as failure:
        instagram_api.account("owner@example.test")
    assert failure.value.detail["code"] == "reconnect_required"
    stored = instagram_environment.get_connection("owner@example.test")
    assert stored is not None
    assert stored.status == "reconnect_required"
    assert instagram_environment.get_encrypted_token(stored.id) == encrypted


def test_account_upstream_success_and_error(monkeypatch, instagram_environment):
    encrypted = instagram.encrypt_access_token("private-token")
    existing = _account(encrypted)
    instagram_environment.upsert_connection(existing, encrypted_token=encrypted)
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: {
            "id": "ig-1",
            "username": "updated",
            "account_type": "BUSINESS",
            "media_count": 5,
        },
    )
    response = instagram_api.account("owner@example.test")
    assert response["username"] == "updated"
    assert "encrypted_access_token" not in response

    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: (_ for _ in ()).throw(
            InstagramServiceError("instagram_upstream_error", "Instagram could not complete the request.")
        ),
    )
    with pytest.raises(HTTPException) as failure:
        instagram_api.account("owner@example.test")
    assert failure.value.status_code == 502


def test_media_upstream_success_and_error(monkeypatch, instagram_environment):
    existing = _account(instagram.encrypt_access_token("private-token"))
    instagram_environment.upsert_connection(existing, encrypted_token=existing.encrypted_access_token)
    monkeypatch.setattr(instagram_api, "upsert_instagram_media", lambda items: items)
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_media",
        lambda token: [
            {
                "id": "media-1",
                "media_type": "IMAGE",
                "caption": "Post",
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    response = instagram_api.media("owner@example.test")
    assert response["items"][0].instagram_media_id == "media-1"
    assert "private-token" not in repr(response)

    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_media",
        lambda token: (_ for _ in ()).throw(
            InstagramServiceError("instagram_upstream_error", "Instagram could not complete the request.")
        ),
    )
    with pytest.raises(HTTPException) as failure:
        instagram_api.media("owner@example.test")
    assert failure.value.status_code == 502


def test_engagement_rate_handles_zero_reach_and_partial_metrics():
    assert engagement_rate({"reach": 0, "likes": 4}) is None
    assert engagement_rate({"reach": 100}) is None
    assert engagement_rate({"reach": 100, "likes": 4, "comments": 1, "saves": None, "shares": 2}) == 7
    assert safe_raw_metrics({"reach": 4, "views": 9, "access_token": "secret"}) == {
        "reach": 4,
        "views": 9,
    }


def test_media_insights_preserve_partial_metric_availability(monkeypatch):
    requested_metrics = []

    def fake_request(method, url, **kwargs):
        metric = kwargs.get("query", {}).get("metric")
        if metric is None:
            return {"like_count": 4, "comments_count": 1}
        requested_metrics.append(metric)
        if "," in metric:
            # A non-retryable batch error must degrade to individual metric
            # requests, not discard all supported data.
            raise InstagramServiceError("instagram_request_rejected", "safe", 400)
        if metric == "reach":
            return {"data": [{"name": "reach", "total_value": {"value": 100}}]}
        if metric == "views":
            return {"data": [{"name": "views", "total_value": {"value": 120}}]}
        if metric == "shares":
            raise InstagramServiceError("instagram_permission_required", "safe", 403)
        raise InstagramServiceError("instagram_request_rejected", "safe", 400)

    monkeypatch.setattr(instagram, "_request_json", fake_request)
    result = fetch_instagram_media_insights("secret", "media-1", "IMAGE")

    assert result["likes"] == 4
    assert result["comments"] == 1
    assert result["reach"] == 100
    assert result["views"] == 120
    assert "saves" not in result and "shares" not in result
    assert result["_metric_status"]["saves"] == "unavailable"
    assert result["_metric_status"]["shares"] == "permission_required"
    assert engagement_rate(result) == 5.0
    assert any("," in metric for metric in requested_metrics)


def test_media_insights_do_not_swallow_invalid_token(monkeypatch):
    monkeypatch.setattr(
        instagram,
        "_request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(InstagramServiceError("instagram_token_invalid", "safe", 401)),
    )

    with pytest.raises(InstagramServiceError) as failure:
        fetch_instagram_media_insights("secret", "media-1", "VIDEO")

    assert failure.value.code == "instagram_token_invalid"


def test_media_insights_fetches_a_single_comma_separated_batch(monkeypatch):
    requested_metrics = []

    def fake_request(method, url, **kwargs):
        metric = kwargs.get("query", {}).get("metric")
        if metric is None:
            return {"like_count": 4, "comments_count": 1}
        requested_metrics.append(metric)
        return {
            "data": [
                {"name": "reach", "total_value": {"value": 100}},
                {"name": "views", "values": [{"value": 321}]},
                {"name": "saved", "total_value": {"value": 4}},
            ]
        }

    monkeypatch.setattr(instagram, "_request_json", fake_request)
    result = fetch_instagram_media_insights("secret", "media-1", "IMAGE")

    assert requested_metrics == ["views,reach,saved,shares,comments"]
    assert result["views"] == 321
    assert result["reach"] == 100
    assert result["saves"] == 4
    assert result["_media_type"] == "IMAGE"


def test_media_insights_transient_views_error_retries_whole_capture(monkeypatch):
    def fake_request(method, url, **kwargs):
        metric = kwargs.get("query", {}).get("metric")
        if metric is None:
            return {"like_count": 4, "comments_count": 1}
        if metric and "," in metric:
            raise InstagramServiceError("instagram_upstream_error", "safe", 502)
        return {"data": [{"total_value": {"value": 100}}]}

    monkeypatch.setattr(instagram, "_request_json", fake_request)

    with pytest.raises(InstagramServiceError) as failure:
        fetch_instagram_media_insights("secret", "media-1", "VIDEO")

    assert failure.value.code == "instagram_upstream_error"


def test_reels_watch_time_metrics_are_requested_and_preserved(monkeypatch):
    def fake_request(method, url, **kwargs):
        metric = kwargs.get("query", {}).get("metric")
        if metric is None:
            return {"like_count": 4, "comments_count": 1}
        values = {
            "reach": 100,
            "views": 120,
            "saved": 3,
            "shares": 2,
            "ig_reels_avg_watch_time": 12500,
            "ig_reels_video_view_total_time": 250000,
        }
        return {"data": [{"name": name, "total_value": {"value": value}} for name, value in values.items()]}

    monkeypatch.setattr(instagram, "_request_json", fake_request)
    result = fetch_instagram_media_insights("secret", "media-1", "REELS")

    assert result["average_watch_time_ms"] == 12500
    assert result["total_watch_time_ms"] == 250000
    assert result["_metric_status"]["average_watch_time_ms"] == "available"
    assert safe_raw_metrics(result)["total_watch_time_ms"] == 250000


def test_seven_day_aggregation_uses_latest_snapshot_and_unavailable_metrics():
    now = datetime.now(UTC)
    media = [SimpleNamespace(id="media-1", published_at=now - timedelta(days=1))]
    snapshots = [
        SimpleNamespace(
            media_id="media-1",
            captured_at=now - timedelta(hours=2),
            reach=10,
            views=None,
            likes=1,
            comments=0,
            saves=None,
            shares=None,
        ),
        SimpleNamespace(
            media_id="media-1",
            captured_at=now - timedelta(hours=1),
            reach=20,
            views=None,
            likes=2,
            comments=1,
            saves=None,
            shares=None,
        ),
    ]
    result = aggregate_seven_days(media, snapshots, now)
    assert result["posts"] == 1
    assert result["metrics"]["reach"] == 20
    assert result["metrics"]["views"] is None
    assert result["metrics"]["engagement_rate"] == 15


def test_local_store_media_upsert_and_tracking(tmp_path, monkeypatch):
    monkeypatch.setattr(json_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    now = datetime.now(UTC)
    account = _account()
    json_store.upsert_instagram_account(account)
    first = InstagramMedia(
        id="media-1",
        account_id=account.id,
        instagram_media_id="external-1",
        media_type="IMAGE",
        caption="First",
        published_at=now,
        last_synced_at=now,
    )
    json_store.upsert_instagram_media([first])
    json_store.upsert_instagram_media([first.model_copy(update={"caption": "Updated"})])
    assert len(json_store.get_instagram_media(account.id)) == 1
    tracked_a = json_store.create_tracked_post("owner@example.test", first.id)
    tracked_b = json_store.create_tracked_post("owner@example.test", first.id)
    assert tracked_a.id == tracked_b.id
    snapshot = InstagramInsightSnapshot(
        id=str(uuid4()), media_id=first.id, captured_at=now, reach=10, engagement_rate=0
    )
    json_store.append_instagram_snapshot(snapshot)
    assert json_store.load_store().instagram_insight_snapshots == [snapshot]


def _api_snapshot(identifier: str, media_id: str, captured_at: datetime, *, views: int = 100):
    return SimpleNamespace(
        id=identifier,
        media_id=media_id,
        captured_at=captured_at,
        likes=5,
        comments=3,
        saves=2,
        shares=1,
        reach=100,
        views=views,
        engagement_rate=11.0,
        average_watch_time_ms=None,
        total_watch_time_ms=None,
        raw_metrics={},
        metric_status={},
    )


def _api_item(identifier: str, captured_at: datetime, *, views: int = 100):
    media_id = f"media-{identifier}"
    snapshot = _api_snapshot(f"snapshot-{identifier}", media_id, captured_at, views=views)
    return {
        "tracking": SimpleNamespace(
            id=f"tracked-{identifier}",
            media_id=media_id,
            is_active=True,
            started_at=captured_at - timedelta(days=8),
            stopped_at=None,
        ),
        "media": SimpleNamespace(
            id=media_id,
            instagram_media_id=f"provider-{identifier}",
            media_type="IMAGE",
            thumbnail_url=None,
            media_url=None,
            caption=f"Stored caption {identifier}",
            published_at=captured_at - timedelta(days=8),
        ),
        "latest": snapshot,
        "snapshots": [snapshot],
    }


class _CacheContent:
    def __init__(self, caches=None):
        self.caches = caches or {}

    def get_text_cache(self, user_id, cache_key):
        return self.caches.get((user_id, cache_key))


def test_tracked_detail_reads_cached_text_in_bulk_without_generation_or_downloads(monkeypatch):
    now = datetime.now(UTC)
    item = _api_item("one", now)
    comments = [
        SimpleNamespace(
            is_owner_reply=False,
            text=f"Viewer comment {index}",
            like_count=index,
            timestamp=now + timedelta(seconds=index),
        )
        for index in range(3)
    ]
    content = _CacheContent(
        {
            ("user-1", "summary:tracked-one"): SimpleNamespace(text="Stored summary."),
            ("user-1", "audience:tracked-one"): SimpleNamespace(text="Stored audience summary."),
        }
    )
    account = SimpleNamespace(
        instagram_user_id="ig-1",
        scopes=["instagram_business_manage_comments"],
        session_sync_error=None,
    )
    load_calls = []

    def load(user_id, **kwargs):
        load_calls.append((user_id, kwargs))
        return [item], {"tracked-one": comments}

    def forbidden(*args, **kwargs):
        raise AssertionError("GET endpoints must not generate AI text or download media")

    monkeypatch.setattr(instagram_api, "stored_connection", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: content)
    monkeypatch.setattr(instagram_api, "load_tracked_items", load)
    monkeypatch.setattr(instagram_api, "instagram_comment_ingestion_enabled", lambda *args: True)
    monkeypatch.setattr(feedback, "load_media_input", forbidden)
    monkeypatch.setattr(feedback, "refresh_summary_for_user", forbidden)
    monkeypatch.setattr(insight_texts, "audience_description", forbidden)
    monkeypatch.setattr(insight_texts, "next_post_suggestion", forbidden)

    result = instagram_api.tracked_detail(
        "tracked-one", AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    )

    assert len(load_calls) == 1
    assert load_calls[0][1]["active_only"] is False
    assert load_calls[0][1]["include_comments"] is True
    assert result["analysis"]["summary"] == "Stored summary."
    assert result["analysis"]["summary_status"] == "ready"
    assert result["analysis"]["audience_comments"] == {
        "state": "ready",
        "description": "Stored audience summary.",
        "items": [
            {"text": comment.text, "like_count": comment.like_count, "timestamp": comment.timestamp}
            for comment in reversed(comments)
        ],
    }


def test_tracked_detail_distinguishes_pending_and_resolved_empty_summary(monkeypatch):
    now = datetime.now(UTC)
    item = _api_item("one", now)
    content = _CacheContent()
    account = SimpleNamespace(instagram_user_id="ig-1", scopes=[], session_sync_error=None)

    monkeypatch.setattr(instagram_api, "stored_connection", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: content)
    monkeypatch.setattr(
        instagram_api,
        "load_tracked_items",
        lambda *args, **kwargs: ([item], {}),
    )

    user = AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    assert instagram_api.tracked_detail("tracked-one", user)["analysis"]["summary_status"] == "pending"

    content.caches[("user-1", "summary:tracked-one")] = SimpleNamespace(text="")
    result = instagram_api.tracked_detail("tracked-one", user)
    assert result["analysis"]["summary"] is None
    assert result["analysis"]["summary_status"] == "none"


def test_tracked_detail_keeps_comment_items_when_comment_access_is_denied(monkeypatch):
    now = datetime.now(UTC)
    item = _api_item("one", now)
    comments = [
        SimpleNamespace(is_owner_reply=False, text="Recent", like_count=1, timestamp=now),
        SimpleNamespace(is_owner_reply=False, text="Older", like_count=0, timestamp=now - timedelta(minutes=1)),
    ]
    account = SimpleNamespace(
        instagram_user_id="ig-1",
        scopes=["instagram_business_manage_comments"],
        session_sync_error="comment_access_denied",
    )

    monkeypatch.setattr(instagram_api, "stored_connection", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: _CacheContent())
    monkeypatch.setattr(
        instagram_api, "load_tracked_items", lambda *args, **kwargs: ([item], {"tracked-one": comments})
    )
    monkeypatch.setattr(instagram_api, "instagram_comment_ingestion_enabled", lambda *args: True)

    audience = instagram_api.tracked_detail(
        "tracked-one", AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    )["analysis"]["audience_comments"]

    assert audience == {
        "state": "access_denied",
        "message": "Instagram denied access to comments.",
        "items": [
            {"text": "Recent", "like_count": 1, "timestamp": now},
            {"text": "Older", "like_count": 0, "timestamp": now - timedelta(minutes=1)},
        ],
    }


def test_tracked_detail_requires_consent_for_comment_summary_but_keeps_safe_items(monkeypatch):
    now = datetime.now(UTC)
    item = _api_item("one", now)
    comments = [
        SimpleNamespace(is_owner_reply=False, text="Recent", like_count=1, timestamp=now),
        SimpleNamespace(is_owner_reply=False, text="Another", like_count=0, timestamp=now - timedelta(minutes=1)),
        SimpleNamespace(is_owner_reply=False, text="Older", like_count=0, timestamp=now - timedelta(minutes=2)),
    ]
    account = SimpleNamespace(
        instagram_user_id="ig-1",
        scopes=["instagram_business_manage_comments"],
        session_sync_error=None,
    )
    monkeypatch.setattr(instagram_api, "has_ai_processing_consent", lambda _user_id: False)
    monkeypatch.setattr(instagram_api, "stored_connection", lambda _user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: _CacheContent())
    monkeypatch.setattr(
        instagram_api, "load_tracked_items", lambda *args, **kwargs: ([item], {"tracked-one": comments})
    )
    monkeypatch.setattr(instagram_api, "instagram_comment_ingestion_enabled", lambda *args: True)

    audience = instagram_api.tracked_detail(
        "tracked-one", AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    )["analysis"]["audience_comments"]

    assert audience["state"] == "consent_required"
    assert [comment["text"] for comment in audience["items"]] == ["Recent", "Another", "Older"]


def test_account_insights_reads_cached_suggestion_once_without_generation(monkeypatch):
    now = datetime.now(UTC)
    items = [_api_item(str(index), now - timedelta(minutes=index), views=100 + index) for index in range(7)]
    content = _CacheContent({("user-1", "reflection:latest-post"): SimpleNamespace(text="Reflection: Stored text.")})
    account = SimpleNamespace(status="connected", session_sync_error=None)
    build_calls = []
    original_build = instagram_api.build_account_insights

    def counted_build(*args, **kwargs):
        build_calls.append((args, kwargs))
        return original_build(*args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("GET /insights/account must not generate a suggestion")

    monkeypatch.setattr(instagram_api, "stored_connection", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: content)
    monkeypatch.setattr(instagram_api, "load_tracked_items", lambda *args, **kwargs: (items, {}))
    monkeypatch.setattr(instagram_api, "build_account_insights", counted_build)
    monkeypatch.setattr(insight_texts, "next_post_suggestion", forbidden)

    user = AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    ready = instagram_api.account_insights(user)

    assert len(build_calls) == 1
    assert ready["next_post_suggestion"] == "Reflection: Stored text."
    assert ready["next_post_suggestion_status"] == "ready"

    content.caches.clear()
    pending = instagram_api.account_insights(user)
    assert pending["next_post_suggestion"] is None
    assert pending["next_post_suggestion_status"] == "pending"

    content.caches[("user-1", "reflection:latest-post")] = SimpleNamespace(text="")
    resolved_empty = instagram_api.account_insights(user)
    assert resolved_empty["next_post_suggestion_status"] == "none"


def test_account_insights_hides_cached_suggestion_when_consent_is_revoked(monkeypatch):
    now = datetime.now(UTC)
    items = [_api_item(str(index), now - timedelta(minutes=index), views=100 + index) for index in range(7)]
    content = _CacheContent({("user-1", "reflection:latest-post"): SimpleNamespace(text="Reflection: Old cache.")})
    account = SimpleNamespace(status="connected", session_sync_error=None)
    monkeypatch.setattr(instagram_api, "has_ai_processing_consent", lambda _user_id: False)
    monkeypatch.setattr(instagram_api, "stored_connection", lambda _user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: content)
    monkeypatch.setattr(instagram_api, "load_tracked_items", lambda *args, **kwargs: (items, {}))

    result = instagram_api.account_insights(
        AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash")
    )

    assert result["next_post_suggestion"] is None
    assert result["next_post_suggestion_status"] == "consent_required"


def test_manual_refresh_schedules_cached_insight_generation(monkeypatch):
    tracked = SimpleNamespace(id="tracked-one", media_id="media-one")
    media = SimpleNamespace(id="media-one", instagram_media_id="provider-one", media_type="IMAGE")
    account = SimpleNamespace(id="account-one")
    refreshed = []

    monkeypatch.setattr(
        instagram_api,
        "_tracked_item",
        lambda user_id, tracked_id: {"tracking": tracked, "media": media, "latest": None},
    )
    monkeypatch.setattr(instagram_api, "_active_account", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "usable_token", lambda value: "token")
    monkeypatch.setattr(instagram_api, "refresh_one_post", lambda *args, **kwargs: refreshed.append(args))
    monkeypatch.setattr(instagram_api, "tracked_detail", lambda tracked_id, user: {"id": tracked_id})

    background_tasks = BackgroundTasks()
    result = instagram_api.refresh_tracking(
        "tracked-one",
        AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash"),
        background_tasks,
    )

    assert result == {"id": "tracked-one"}
    assert len(refreshed) == 1
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is instagram_api.refresh_cached_insights
    assert background_tasks.tasks[0].args == ("user-1", "tracked-one", True)


def test_recent_manual_refresh_still_schedules_cached_insight_generation(monkeypatch):
    tracked = SimpleNamespace(id="tracked-one", media_id="media-one")
    media = SimpleNamespace(id="media-one", instagram_media_id="provider-one", media_type="IMAGE")
    account = SimpleNamespace(id="account-one")

    monkeypatch.setattr(
        instagram_api,
        "_tracked_item",
        lambda user_id, tracked_id: {
            "tracking": tracked,
            "media": media,
            "latest": SimpleNamespace(captured_at=datetime.now(UTC)),
        },
    )
    monkeypatch.setattr(instagram_api, "_active_account", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "refresh_one_post", lambda *args, **kwargs: pytest.fail("must stay throttled"))
    monkeypatch.setattr(instagram_api, "tracked_detail", lambda tracked_id, user: {"id": tracked_id})

    background_tasks = BackgroundTasks()
    result = instagram_api.refresh_tracking(
        "tracked-one",
        AuthenticatedUser(id="user-1", email="user@example.test", token_hash="hash"),
        background_tasks,
    )

    assert result == {"id": "tracked-one"}
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is instagram_api.refresh_cached_insights
    assert background_tasks.tasks[0].args == ("user-1", "tracked-one", True)
