import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken

from backend.storage.instagram_repository import (
    InstagramRepositoryError,
    get_instagram_repository,
)


INSTAGRAM_AUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH_URL = "https://graph.instagram.com"
INSTAGRAM_REFRESH_PATH = "/refresh_access_token"
INSTAGRAM_SCOPES = (
    "instagram_business_basic",
    "instagram_business_manage_insights",
    "instagram_business_content_publish",
)


class InstagramServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise InstagramServiceError(
            "instagram_not_configured",
            f"Missing required Instagram configuration: {name}.",
            503,
        )
    return value


def instagram_configured() -> bool:
    required = (
        "POSTBRIDGE_INSTAGRAM_CLIENT_ID",
        "POSTBRIDGE_INSTAGRAM_CLIENT_SECRET",
        "POSTBRIDGE_INSTAGRAM_REDIRECT_URI",
        "POSTBRIDGE_INSTAGRAM_APP_RETURN_URI",
        "POSTBRIDGE_TOKEN_ENCRYPTION_KEY",
        "POSTBRIDGE_OAUTH_STATE_SECRET",
    )
    return all(os.getenv(name) for name in required)


def instagram_app_return_uri(requested_uri: Optional[str] = None) -> str:
    """Return the single server-controlled mobile OAuth destination.

    A caller may supply a URI only for equality validation. It can never select an
    arbitrary destination, which keeps the callback from becoming an open redirect.
    """
    configured = _required_env("POSTBRIDGE_INSTAGRAM_APP_RETURN_URI")
    parsed = urlparse(configured)
    if parsed.scheme not in {"postbridge", "creatormind"} or parsed.netloc != "instagram-connected":
        raise InstagramServiceError(
            "instagram_invalid_app_return_uri",
            "Instagram mobile return URI is not configured safely.",
            503,
        )
    if requested_uri is not None and requested_uri != configured:
        raise InstagramServiceError(
            "instagram_return_uri_not_allowed",
            "Instagram mobile return URI is not allowed.",
            400,
        )
    return configured


def build_app_return_url(status: str, code: Optional[str] = None, client: str = "mobile") -> str:
    query = {"status": status}
    if code:
        query["code"] = code
    if client == "web":
        frontend = _required_env("FRONTEND_BASE_URL").rstrip("/")
        web_query = {"instagram": status}
        if code:
            web_query["code"] = code
        return f"{frontend}/dashboard?{urlencode(web_query)}"
    return f"{instagram_app_return_uri()}?{urlencode(query)}"


def create_oauth_state(user_id: str, lifetime_seconds: int = 600, client: str = "mobile") -> str:
    if client not in {"mobile", "web"}:
        raise InstagramServiceError("instagram_invalid_client", "Instagram connection client is invalid.", 400)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=lifetime_seconds)
    payload = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(18),
        "exp": int(expires_at.timestamp()),
        "client": client,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(
        _required_env("POSTBRIDGE_OAUTH_STATE_SECRET").encode(),
        encoded,
        hashlib.sha256,
    ).digest()
    try:
        get_instagram_repository().create_oauth_state(
            payload["nonce"], user_id, expires_at
        )
    except InstagramRepositoryError:
        raise InstagramServiceError(
            "instagram_storage_unavailable",
            "Instagram connection storage is unavailable.",
            503,
        ) from None
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def consume_oauth_state_context(state: str) -> tuple[str, str]:
    try:
        encoded, supplied_signature = state.split(".", 1)
        expected = hmac.new(
            _required_env("POSTBRIDGE_OAUTH_STATE_SECRET").encode(),
            encoded.encode(),
            hashlib.sha256,
        ).digest()
        supplied = base64.urlsafe_b64decode(
            supplied_signature + "=" * (-len(supplied_signature) % 4)
        )
        if not hmac.compare_digest(expected, supplied):
            raise ValueError
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        nonce = str(payload["nonce"])
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        expected_user_id = str(payload["user_id"])
        try:
            stored_user_id = get_instagram_repository().consume_oauth_state(
                nonce, datetime.now(timezone.utc)
            )
        except InstagramRepositoryError:
            raise InstagramServiceError(
                "instagram_storage_unavailable",
                "Instagram connection storage is unavailable.",
                503,
            ) from None
        if stored_user_id != expected_user_id:
            raise ValueError
        client = str(payload.get("client", "mobile"))
        if client not in {"mobile", "web"}:
            raise ValueError
        return expected_user_id, client
    except InstagramServiceError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InstagramServiceError(
            "invalid_oauth_state",
            "Instagram connection request is invalid or expired.",
            400,
        ) from exc


def consume_oauth_state(state: str) -> str:
    return consume_oauth_state_context(state)[0]


def build_authorization_url(state: str) -> str:
    return INSTAGRAM_AUTH_URL + "?" + urlencode(
        {
            "client_id": _required_env("POSTBRIDGE_INSTAGRAM_CLIENT_ID"),
            "redirect_uri": _required_env("POSTBRIDGE_INSTAGRAM_REDIRECT_URI"),
            "response_type": "code",
            "scope": ",".join(INSTAGRAM_SCOPES),
            "state": state,
        }
    )


def _request_json(
    method: str,
    url: str,
    *,
    form: Optional[dict[str, str]] = None,
    query: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    if query:
        url = f"{url}?{urlencode(query)}"
    body = urlencode(form).encode() if form else None
    request = Request(url, data=body, method=method)
    if form:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        retry_after = None
        try:
            retry_after = int(exc.headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            pass
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            provider_error = error_payload.get("error", {})
            error_code = provider_error.get("code")
            if isinstance(error_code, str) and error_code.isdigit():
                error_code = int(error_code)
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            error_code = None
        if error_code == 190:
            raise InstagramServiceError(
                "instagram_token_invalid",
                "Instagram authorization is no longer valid.",
                401,
            ) from None
        if exc.code == 429 or error_code in {4, 17, 32, 613}:
            raise InstagramServiceError(
                "instagram_rate_limited",
                "Instagram is temporarily rate limiting insight requests.",
                429,
                retry_after_seconds=retry_after,
            ) from None
        if error_code in {10, 200}:
            raise InstagramServiceError(
                "instagram_permission_required",
                "Instagram insight permission is required.",
                403,
            ) from None
        if exc.code == 404:
            raise InstagramServiceError(
                "instagram_media_unavailable",
                "This Instagram post is no longer accessible.",
                404,
            ) from None
        if exc.code < 500:
            raise InstagramServiceError(
                "instagram_request_rejected",
                "Instagram did not provide this field for the post.",
                400,
            ) from None
        raise InstagramServiceError(
            "instagram_upstream_error",
            "Instagram could not complete the request.",
            502,
        ) from None
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise InstagramServiceError(
            "instagram_upstream_error",
            "Instagram could not complete the request.",
            502,
        ) from None
    if not isinstance(payload, dict):
        raise InstagramServiceError(
            "instagram_upstream_error",
            "Instagram returned an invalid response.",
            502,
        )
    return payload


def _token_from_payload(payload: dict[str, Any], error_code: str) -> str:
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise InstagramServiceError(
            error_code,
            "Instagram token exchange failed.",
            502,
        )
    return token


def exchange_authorization_code(code: str) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        INSTAGRAM_TOKEN_URL,
        form={
            "client_id": _required_env("POSTBRIDGE_INSTAGRAM_CLIENT_ID"),
            "client_secret": _required_env("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET"),
            "grant_type": "authorization_code",
            "redirect_uri": _required_env("POSTBRIDGE_INSTAGRAM_REDIRECT_URI"),
            "code": code,
        },
    )
    _token_from_payload(payload, "instagram_short_token_exchange_failed")
    return payload


def exchange_long_lived_token(short_lived_token: str) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        f"{INSTAGRAM_GRAPH_URL}/access_token",
        query={
            "grant_type": "ig_exchange_token",
            "client_secret": _required_env("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET"),
            "access_token": short_lived_token,
        },
    )
    _token_from_payload(payload, "instagram_long_token_exchange_failed")
    return payload


def refresh_long_lived_token(long_lived_token: str) -> dict[str, Any]:
    """Refresh a valid long-lived Instagram token.

    This is an on-demand interface only. A future durable scheduler should invoke it
    before expiry (target: seven days before ``token_expires_at``), persist the new
    encrypted token atomically, and retry transient failures without duplicate jobs.
    """
    payload = _request_json(
        "GET",
        f"{INSTAGRAM_GRAPH_URL}{INSTAGRAM_REFRESH_PATH}",
        query={
            "grant_type": "ig_refresh_token",
            "access_token": long_lived_token,
        },
    )
    _token_from_payload(payload, "instagram_token_refresh_failed")
    return payload


def fetch_instagram_profile(access_token: str) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        f"{INSTAGRAM_GRAPH_URL}/me",
        query={
            "fields": "id,username,account_type,media_count",
            "access_token": access_token,
        },
    )
    if not payload.get("id") or not payload.get("username"):
        raise InstagramServiceError(
            "instagram_profile_failed",
            "Instagram profile could not be loaded.",
            502,
        )
    return payload


def fetch_instagram_media(access_token: str) -> list[dict[str, Any]]:
    payload = _request_json(
        "GET",
        f"{INSTAGRAM_GRAPH_URL}/me/media",
        query={
            "fields": "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp",
            "access_token": access_token,
        },
    )
    items = payload.get("data")
    if not isinstance(items, list):
        raise InstagramServiceError(
            "instagram_media_failed",
            "Instagram media could not be loaded.",
            502,
        )
    return [item for item in items if isinstance(item, dict)]


def publish_instagram_image(
    access_token: str,
    instagram_user_id: str,
    image_url: str,
    caption: str,
) -> dict[str, Any]:
    """Publish one provider-readable JPEG through Instagram's official API."""
    container = _request_json(
        "POST",
        f"{INSTAGRAM_GRAPH_URL}/{instagram_user_id}/media",
        form={"image_url": image_url, "caption": caption, "access_token": access_token},
    )
    container_id = container.get("id")
    if not isinstance(container_id, str) or not container_id:
        raise InstagramServiceError("instagram_publish_failed", "Instagram did not create a media container.", 502)
    published = _request_json(
        "POST",
        f"{INSTAGRAM_GRAPH_URL}/{instagram_user_id}/media_publish",
        form={"creation_id": container_id, "access_token": access_token},
    )
    media_id = published.get("id")
    if not isinstance(media_id, str) or not media_id:
        raise InstagramServiceError("instagram_publish_failed", "Instagram did not publish the media container.", 502)
    return _request_json(
        "GET",
        f"{INSTAGRAM_GRAPH_URL}/{media_id}",
        query={
            "fields": "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp",
            "access_token": access_token,
        },
    )


def fetch_instagram_media_insights(
    access_token: str,
    instagram_media_id: str,
    media_type: str | None = None,
) -> dict[str, Any]:
    """Fetch the metrics supported for a media item without fabricating missing values."""
    metrics: dict[str, Any] = {}
    status = {name: "unavailable" for name in (
        "likes", "comments", "reach", "saves", "shares", "views",
        "average_watch_time_ms", "total_watch_time_ms",
    )}
    retryable_codes = {"instagram_token_invalid", "instagram_rate_limited", "instagram_upstream_error"}
    try:
        basic = _request_json(
            "GET",
            f"{INSTAGRAM_GRAPH_URL}/{instagram_media_id}",
            query={"fields": "like_count,comments_count", "access_token": access_token},
        )
        if isinstance(basic.get("like_count"), int):
            metrics["likes"] = basic["like_count"]
            status["likes"] = "available"
        if isinstance(basic.get("comments_count"), int):
            metrics["comments"] = basic["comments_count"]
            status["comments"] = "available"
    except InstagramServiceError as exc:
        if exc.code in retryable_codes:
            raise
        value = "permission_required" if exc.code == "instagram_permission_required" else "unavailable"
        status["likes"] = value
        status["comments"] = value

    for upstream_name, local_name in (("reach", "reach"), ("saved", "saves"), ("shares", "shares"), ("views", "views")):
        try:
            payload = _request_json(
                "GET",
                f"{INSTAGRAM_GRAPH_URL}/{instagram_media_id}/insights",
                query={"metric": upstream_name, "access_token": access_token},
            )
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                continue
            metric = data[0] if isinstance(data[0], dict) else {}
            value = metric.get("total_value", {}).get("value") if isinstance(metric.get("total_value"), dict) else None
            if value is None and isinstance(metric.get("values"), list) and metric["values"]:
                value = metric["values"][0].get("value")
            if isinstance(value, (int, float)):
                metrics[local_name] = int(value)
                status[local_name] = "available"
        except InstagramServiceError as exc:
            if exc.code in retryable_codes:
                raise
            status[local_name] = "permission_required" if exc.code == "instagram_permission_required" else "unavailable"
    if (media_type or "").upper() in {"VIDEO", "REELS"}:
        for upstream_name, local_name in (
            ("ig_reels_avg_watch_time", "average_watch_time_ms"),
            ("ig_reels_video_view_total_time", "total_watch_time_ms"),
        ):
            try:
                payload = _request_json(
                    "GET",
                    f"{INSTAGRAM_GRAPH_URL}/{instagram_media_id}/insights",
                    query={"metric": upstream_name, "access_token": access_token},
                )
                data = payload.get("data")
                if not isinstance(data, list) or not data:
                    continue
                metric = data[0] if isinstance(data[0], dict) else {}
                value = metric.get("total_value", {}).get("value") if isinstance(metric.get("total_value"), dict) else None
                if value is None and isinstance(metric.get("values"), list) and metric["values"]:
                    value = metric["values"][0].get("value")
                if isinstance(value, (int, float)):
                    metrics[local_name] = int(value)
                    status[local_name] = "available"
            except InstagramServiceError as exc:
                if exc.code in retryable_codes:
                    raise
                status[local_name] = "permission_required" if exc.code == "instagram_permission_required" else "unavailable"
    metrics["_metric_status"] = status
    metrics["_media_type"] = (media_type or "UNKNOWN").upper()
    if not any(isinstance(metrics.get(name), int) for name in status):
        if "permission_required" in status.values():
            raise InstagramServiceError("instagram_permission_required", "Instagram insight permission is required.", 403)
        raise InstagramServiceError("instagram_media_unavailable", "This Instagram post is no longer accessible or has no available insights.", 404)
    return metrics


def encrypt_access_token(token: str) -> str:
    key = _required_env("POSTBRIDGE_TOKEN_ENCRYPTION_KEY")
    try:
        return Fernet(key.encode()).encrypt(token.encode()).decode()
    except (ValueError, TypeError) as exc:
        raise InstagramServiceError(
            "instagram_not_configured",
            "Instagram token encryption is not configured.",
            503,
        ) from exc


def decrypt_access_token(encrypted_token: str) -> str:
    key = _required_env("POSTBRIDGE_TOKEN_ENCRYPTION_KEY")
    try:
        return Fernet(key.encode()).decrypt(encrypted_token.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise InstagramServiceError(
            "connection_expired",
            "Instagram connection has expired.",
            401,
        ) from exc


def token_expiry(payload: dict[str, Any]) -> Optional[datetime]:
    expires_in = payload.get("expires_in")
    if not isinstance(expires_in, (int, float)):
        return None
    return datetime.fromtimestamp(time.time() + float(expires_in), timezone.utc)


def engagement_rate(metrics: dict[str, Any]) -> float | None:
    """Return observed interactions / reach, excluding unavailable components.

    At least one actual interaction count and a positive reach value are required.
    Missing values are never converted to zero.
    """
    reach = metrics.get("reach")
    if not isinstance(reach, (int, float)) or reach <= 0:
        return None
    values = [metrics.get(name) for name in ("likes", "comments", "saves", "shares")]
    available = [value for value in values if isinstance(value, (int, float))]
    if not available:
        return None
    interactions = sum(available)
    return round(interactions / reach * 100, 2)


def safe_raw_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "likes", "comments", "saves", "shares", "reach", "views", "impressions",
        "average_watch_time_ms", "total_watch_time_ms",
    }
    return {key: value for key, value in metrics.items() if key in allowed}


def aggregate_seven_days(
    media: list[Any], snapshots: list[Any], now: Optional[datetime] = None
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    start_timestamp = current.timestamp() - 7 * 24 * 60 * 60
    recent_media = [
        item
        for item in media
        if item.published_at.replace(tzinfo=item.published_at.tzinfo or timezone.utc).timestamp()
        >= start_timestamp
    ]
    latest: dict[str, Any] = {}
    for snapshot in snapshots:
        if snapshot.media_id in {item.id for item in recent_media} and (
            snapshot.media_id not in latest
            or snapshot.captured_at > latest[snapshot.media_id].captured_at
        ):
            latest[snapshot.media_id] = snapshot
    totals: dict[str, Optional[int]] = {
        name: 0 for name in ("reach", "views", "likes", "comments", "saves", "shares")
    }
    for name in totals:
        values = [
            getattr(item, name)
            for item in latest.values()
            if getattr(item, name) is not None
        ]
        totals[name] = sum(values) if values else None
    totals["engagement_rate"] = engagement_rate(totals)
    return {
        "period": "7d",
        "start": datetime.fromtimestamp(start_timestamp, timezone.utc).isoformat(),
        "end": current.isoformat(),
        "posts": len(recent_media),
        "metrics": totals,
    }
