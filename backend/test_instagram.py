from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from backend import instagram_api
from backend.services import instagram
from backend.services.instagram import (
    InstagramServiceError,
    aggregate_seven_days,
    consume_oauth_state,
    create_oauth_state,
    engagement_rate,
    exchange_authorization_code,
    exchange_long_lived_token,
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
    monkeypatch.setattr(json_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    from backend.storage import token_store

    monkeypatch.setattr(
        token_store, "TOKEN_STORE_PATH", tmp_path / "postbridge_tokens.local.json"
    )
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
    assert query["redirect_uri"] == [
        "https://example.test/api/instagram/connect/callback"
    ]


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


def _account(encrypted_token: str = "encrypted") -> InstagramAccount:
    return InstagramAccount(
        id="account-1",
        user_id="owner@example.test",
        instagram_user_id="ig-1",
        username="creator",
        account_type="BUSINESS",
        media_count=2,
        encrypted_access_token=encrypted_token,
        connected_at=datetime.now(timezone.utc),
    )


def test_callback_success_encrypts_before_storage_and_hides_tokens(
    monkeypatch, caplog, instagram_environment
):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(
        instagram_api,
        "exchange_authorization_code",
        lambda code: {"access_token": "short-sensitive"},
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
    response = instagram_api.connect_callback(
        state=state, error="access_denied"
    )
    assert response.headers["location"] == (
        "https://app.example.test/dashboard?"
        "instagram=error&code=instagram_authorization_denied"
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
    assert response.headers["location"].endswith(
        "?status=error&code=instagram_upstream_error"
    )
    assert "private-code" not in response.headers["location"]


def test_callback_profile_failure_redirects_with_safe_code(monkeypatch):
    state = create_oauth_state("owner@example.test")
    monkeypatch.setattr(instagram_api, "exchange_authorization_code", lambda code: {"access_token": "short-secret"})
    monkeypatch.setattr(instagram_api, "exchange_long_lived_token", lambda token: {"access_token": "long-secret"})
    monkeypatch.setattr(
        instagram_api,
        "fetch_instagram_profile",
        lambda token: (_ for _ in ()).throw(
            InstagramServiceError("instagram_profile_failed", "safe failure")
        ),
    )
    response = instagram_api.connect_callback(code="private-code", state=state)
    assert response.headers["location"].endswith(
        "?status=error&code=instagram_profile_failed"
    )
    assert "secret" not in response.headers["location"]


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
        lambda method, url, **kwargs: calls.append((method, url, kwargs))
        or {"access_token": "refreshed-secret", "expires_in": 3600},
    )
    result = refresh_long_lived_token("existing-secret")
    assert result["expires_in"] == 3600
    assert calls[0][2]["query"]["grant_type"] == "ig_refresh_token"


def test_revoked_token_marks_connection_reconnect_required(
    monkeypatch, instagram_environment
):
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
    instagram_environment.upsert_connection(
        existing, encrypted_token=existing.encrypted_access_token
    )
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
    assert engagement_rate({"reach": 0, "likes": 4}) == 0
    assert engagement_rate(
        {"reach": 100, "likes": 4, "comments": 1, "saves": None, "shares": 2}
    ) == 7
    assert safe_raw_metrics({"reach": 4, "access_token": "secret"}) == {"reach": 4}


def test_seven_day_aggregation_uses_latest_snapshot_and_unavailable_metrics():
    now = datetime.now(timezone.utc)
    media = [SimpleNamespace(id="media-1", published_at=now - timedelta(days=1))]
    snapshots = [
        SimpleNamespace(media_id="media-1", captured_at=now - timedelta(hours=2), reach=10, views=None, likes=1, comments=0, saves=None, shares=None),
        SimpleNamespace(media_id="media-1", captured_at=now - timedelta(hours=1), reach=20, views=None, likes=2, comments=1, saves=None, shares=None),
    ]
    result = aggregate_seven_days(media, snapshots, now)
    assert result["posts"] == 1
    assert result["metrics"]["reach"] == 20
    assert result["metrics"]["views"] is None
    assert result["metrics"]["engagement_rate"] == 15


def test_local_store_media_upsert_and_tracking(tmp_path, monkeypatch):
    monkeypatch.setattr(json_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    now = datetime.now(timezone.utc)
    account = _account()
    json_store.upsert_instagram_account(account)
    first = InstagramMedia(id="media-1", account_id=account.id, instagram_media_id="external-1", media_type="IMAGE", caption="First", published_at=now, last_synced_at=now)
    json_store.upsert_instagram_media([first])
    json_store.upsert_instagram_media([first.model_copy(update={"caption": "Updated"})])
    assert len(json_store.get_instagram_media(account.id)) == 1
    tracked_a = json_store.create_tracked_post("owner@example.test", first.id)
    tracked_b = json_store.create_tracked_post("owner@example.test", first.id)
    assert tracked_a.id == tracked_b.id
    snapshot = InstagramInsightSnapshot(id=str(uuid4()), media_id=first.id, captured_at=now, reach=10, engagement_rate=0)
    json_store.append_instagram_snapshot(snapshot)
    assert json_store.load_store().instagram_insight_snapshots == [snapshot]
