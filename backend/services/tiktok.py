"""TikTok Login Kit, token lifecycle, and Content Posting API helpers."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken

from backend.storage.tiktok_repository import TikTokRepositoryError, get_tiktok_repository

TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_TOKEN_URL = f"{TIKTOK_API_BASE}/v2/oauth/token/"
TIKTOK_REVOKE_URL = f"{TIKTOK_API_BASE}/v2/oauth/revoke/"
TIKTOK_USER_INFO_URL = f"{TIKTOK_API_BASE}/v2/user/info/"
TIKTOK_VIDEO_LIST_URL = f"{TIKTOK_API_BASE}/v2/video/list/"
TIKTOK_CREATOR_INFO_URL = f"{TIKTOK_API_BASE}/v2/post/publish/creator_info/query/"
TIKTOK_VIDEO_INIT_URL = f"{TIKTOK_API_BASE}/v2/post/publish/video/init/"
TIKTOK_PHOTO_INIT_URL = f"{TIKTOK_API_BASE}/v2/post/publish/content/init/"
TIKTOK_STATUS_URL = f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/"


class TikTokServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise TikTokServiceError("tiktok_not_configured", f"TikTok configuration is missing: {name}.", 503)
    return value


def tiktok_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in (
            "POSTBRIDGE_TIKTOK_CLIENT_KEY",
            "POSTBRIDGE_TIKTOK_CLIENT_SECRET",
            "POSTBRIDGE_TIKTOK_REDIRECT_URI",
            "POSTBRIDGE_TOKEN_ENCRYPTION_KEY",
        )
    )


def _safe_provider_error(payload: object, http_status: int) -> TikTokServiceError:
    value = payload if isinstance(payload, dict) else {}
    nested = value.get("error") if isinstance(value.get("error"), dict) else {}
    provider_code = str(nested.get("code") or value.get("error") or "").strip()
    if provider_code in {"access_token_invalid", "invalid_grant"} or http_status == 401:
        return TikTokServiceError("tiktok_token_invalid", "TikTok must be reconnected.", 401)
    if provider_code == "scope_not_authorized" or http_status == 403:
        return TikTokServiceError("tiktok_permission_required", "TikTok publishing permission is required.", 403)
    if provider_code == "rate_limit_exceeded" or http_status == 429:
        return TikTokServiceError("tiktok_rate_limited", "TikTok is temporarily rate limiting requests.", 429)
    if http_status < 500:
        return TikTokServiceError("tiktok_request_rejected", "TikTok rejected the request.", 400)
    return TikTokServiceError("tiktok_upstream_error", "TikTok could not complete the request.", 502)


def _request_json(
    method: str,
    url: str,
    *,
    query: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    access_token: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    if query:
        url = f"{url}?{urlencode(query)}"
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    body: bytes | None = None
    if form is not None:
        body = urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=UTF-8"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        raise _safe_provider_error(payload, exc.code) from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        raise TikTokServiceError("tiktok_upstream_error", "TikTok could not complete the request.", 502) from None
    if not isinstance(payload, dict):
        raise TikTokServiceError("tiktok_upstream_error", "TikTok returned an invalid response.", 502)
    error = payload.get("error")
    if isinstance(error, dict) and str(error.get("code") or "ok") != "ok":
        raise _safe_provider_error(payload, 400)
    if isinstance(error, str) and error:
        raise _safe_provider_error(payload, 400)
    return payload


def create_oauth_state(user_id: str, *, client: str = "web", lifetime_seconds: int = 600) -> str:
    if client != "web":
        raise TikTokServiceError("tiktok_invalid_client", "TikTok connection client is invalid.", 400)
    nonce = secrets.token_urlsafe(32)
    try:
        get_tiktok_repository().create_oauth_state(
            nonce,
            user_id,
            client,
            datetime.now(UTC) + timedelta(seconds=lifetime_seconds),
        )
    except TikTokRepositoryError:
        raise TikTokServiceError(
            "tiktok_storage_unavailable", "TikTok connection storage is unavailable.", 503
        ) from None
    return nonce


def consume_oauth_state(state: str) -> tuple[str, str]:
    if not state:
        raise TikTokServiceError("invalid_oauth_state", "TikTok connection request is invalid or expired.", 400)
    try:
        result = get_tiktok_repository().consume_oauth_state(state, datetime.now(UTC))
    except TikTokRepositoryError:
        raise TikTokServiceError(
            "tiktok_storage_unavailable", "TikTok connection storage is unavailable.", 503
        ) from None
    if result is None:
        raise TikTokServiceError("invalid_oauth_state", "TikTok connection request is invalid or expired.", 400)
    return result


def build_authorization_url(state: str) -> str:
    scopes = os.getenv("POSTBRIDGE_TIKTOK_SCOPES", "user.info.basic,video.list,video.publish")
    return f"{TIKTOK_AUTHORIZE_URL}?{urlencode({'client_key': _required_env('POSTBRIDGE_TIKTOK_CLIENT_KEY'), 'response_type': 'code', 'scope': scopes, 'redirect_uri': _required_env('POSTBRIDGE_TIKTOK_REDIRECT_URI'), 'state': state})}"


def exchange_authorization_code(code: str) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        TIKTOK_TOKEN_URL,
        form={
            "client_key": _required_env("POSTBRIDGE_TIKTOK_CLIENT_KEY"),
            "client_secret": _required_env("POSTBRIDGE_TIKTOK_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _required_env("POSTBRIDGE_TIKTOK_REDIRECT_URI"),
        },
    )
    if not all(
        isinstance(payload.get(name), str) and payload[name] for name in ("access_token", "refresh_token", "open_id")
    ):
        raise TikTokServiceError("tiktok_token_exchange_failed", "TikTok token exchange failed.", 502)
    return payload


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        TIKTOK_TOKEN_URL,
        form={
            "client_key": _required_env("POSTBRIDGE_TIKTOK_CLIENT_KEY"),
            "client_secret": _required_env("POSTBRIDGE_TIKTOK_CLIENT_SECRET"),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if not all(isinstance(payload.get(name), str) and payload[name] for name in ("access_token", "refresh_token")):
        raise TikTokServiceError("tiktok_token_refresh_failed", "TikTok token refresh failed.", 502)
    return payload


def revoke_access_token(access_token: str) -> None:
    _request_json(
        "POST",
        TIKTOK_REVOKE_URL,
        form={
            "client_key": _required_env("POSTBRIDGE_TIKTOK_CLIENT_KEY"),
            "client_secret": _required_env("POSTBRIDGE_TIKTOK_CLIENT_SECRET"),
            "token": access_token,
        },
    )


def token_expiry(payload: dict[str, Any], field: str) -> datetime | None:
    seconds = payload.get(field)
    if not isinstance(seconds, (int, float)):
        return None
    return datetime.fromtimestamp(time.time() + float(seconds), UTC)


def granted_scopes(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("scope")
    if not isinstance(raw, str):
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def encrypt_token(token: str) -> str:
    try:
        return Fernet(_required_env("POSTBRIDGE_TOKEN_ENCRYPTION_KEY").encode()).encrypt(token.encode()).decode()
    except (ValueError, TypeError) as exc:
        raise TikTokServiceError("tiktok_not_configured", "TikTok token encryption is not configured.", 503) from exc


def decrypt_token(token: str) -> str:
    try:
        return Fernet(_required_env("POSTBRIDGE_TOKEN_ENCRYPTION_KEY").encode()).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise TikTokServiceError("tiktok_token_invalid", "TikTok must be reconnected.", 401) from exc


def fetch_user_info(access_token: str) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        TIKTOK_USER_INFO_URL,
        query={"fields": "open_id,union_id,avatar_url,display_name"},
        access_token=access_token,
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    if not user.get("open_id") or not user.get("display_name"):
        raise TikTokServiceError("tiktok_profile_failed", "TikTok profile could not be loaded.", 502)
    return user


def fetch_user_videos(access_token: str, *, max_count: int = 20) -> list[dict[str, Any]]:
    """Return recent public videos using TikTok's Display API."""
    fields = "id,create_time,cover_image_url,share_url,video_description,duration,title"
    payload = _request_json(
        "POST",
        TIKTOK_VIDEO_LIST_URL,
        query={"fields": fields},
        json_body={"max_count": max(1, min(max_count, 20))},
        access_token=access_token,
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    videos = data.get("videos")
    return [item for item in videos if isinstance(item, dict)] if isinstance(videos, list) else []


def fetch_creator_info(access_token: str) -> dict[str, Any]:
    payload = _request_json("POST", TIKTOK_CREATOR_INFO_URL, json_body={}, access_token=access_token)
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("privacy_level_options"), list):
        raise TikTokServiceError("tiktok_creator_info_failed", "TikTok creator settings could not be loaded.", 502)
    return data


def _upload_video(upload_url: str, body: bytes, mime_type: str) -> None:
    request = Request(
        upload_url,
        data=body,
        headers={
            "Content-Type": mime_type,
            "Content-Length": str(len(body)),
            "Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}",
        },
        method="PUT",
    )
    try:
        with urlopen(request, timeout=120) as response:
            if response.status not in {200, 201, 206}:
                raise TikTokServiceError("tiktok_upload_failed", "TikTok media upload failed.", 502)
    except HTTPError as exc:
        raise _safe_provider_error({}, exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise TikTokServiceError("tiktok_upload_failed", "TikTok media upload failed.", 502) from None


def initialize_video_post(
    access_token: str,
    *,
    title: str,
    post_info: dict[str, Any],
    media_url: str | None = None,
    media_bytes: bytes | None = None,
    mime_type: str = "video/mp4",
) -> str:
    if bool(media_url) == bool(media_bytes):
        raise ValueError("Provide exactly one TikTok video source.")
    source_info: dict[str, Any]
    if media_url:
        source_info = {"source": "PULL_FROM_URL", "video_url": media_url}
    else:
        size = len(media_bytes or b"")
        source_info = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    payload = _request_json(
        "POST",
        TIKTOK_VIDEO_INIT_URL,
        json_body={"post_info": {"title": title, **post_info}, "source_info": source_info},
        access_token=access_token,
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    publish_id = data.get("publish_id")
    if not isinstance(publish_id, str) or not publish_id:
        raise TikTokServiceError("tiktok_publish_failed", "TikTok did not initialize the video post.", 502)
    if media_bytes is not None:
        upload_url = data.get("upload_url")
        if not isinstance(upload_url, str) or not upload_url:
            raise TikTokServiceError("tiktok_publish_failed", "TikTok did not provide an upload URL.", 502)
        _upload_video(upload_url, media_bytes, mime_type)
    return publish_id


def initialize_photo_post(
    access_token: str,
    *,
    description: str,
    post_info: dict[str, Any],
    media_url: str,
    is_aigc: bool = False,
) -> str:
    payload = _request_json(
        "POST",
        TIKTOK_PHOTO_INIT_URL,
        json_body={
            "media_type": "PHOTO",
            "post_mode": "DIRECT_POST",
            "post_info": {"description": description, **post_info},
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_images": [media_url],
                "photo_cover_index": 0,
            },
            "is_aigc": is_aigc,
        },
        access_token=access_token,
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    publish_id = data.get("publish_id")
    if not isinstance(publish_id, str) or not publish_id:
        raise TikTokServiceError("tiktok_publish_failed", "TikTok did not initialize the photo post.", 502)
    return publish_id


def fetch_publish_status(access_token: str, publish_id: str) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        TIKTOK_STATUS_URL,
        json_body={"publish_id": publish_id},
        access_token=access_token,
    )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        raise TikTokServiceError("tiktok_status_failed", "TikTok post status could not be loaded.", 502)
    return data


def create_media_token(object_name: str, mime_type: str, *, lifetime_seconds: int = 4200) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"object_name": object_name, "mime_type": mime_type, "exp": int(time.time()) + lifetime_seconds},
            separators=(",", ":"),
        ).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(
        _required_env("POSTBRIDGE_TIKTOK_MEDIA_URL_SECRET").encode("utf-8"), payload, hashlib.sha256
    ).digest()
    return f"{payload.decode('ascii')}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def verify_media_token(token: str) -> tuple[str, str]:
    try:
        encoded, supplied = token.split(".", 1)
        payload = encoded.encode("ascii")
        expected = hmac.new(
            _required_env("POSTBRIDGE_TIKTOK_MEDIA_URL_SECRET").encode("utf-8"), payload, hashlib.sha256
        ).digest()
        supplied_bytes = base64.urlsafe_b64decode(supplied + "=" * (-len(supplied) % 4))
        if not hmac.compare_digest(expected, supplied_bytes):
            raise ValueError
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        object_name = decoded.get("object_name")
        mime_type = decoded.get("mime_type")
        expires_at = decoded.get("exp")
        if (
            not isinstance(object_name, str)
            or not object_name.startswith(("draft-assets/", "publication-assets/"))
            or not isinstance(mime_type, str)
            or not isinstance(expires_at, int)
            or expires_at < int(time.time())
        ):
            raise ValueError
        return object_name, mime_type
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise TikTokServiceError("tiktok_media_url_invalid", "TikTok media URL is invalid or expired.", 404) from None


def create_media_url(object_name: str, mime_type: str) -> str:
    base_url = _required_env("POSTBRIDGE_PUBLIC_API_URL").rstrip("/")
    return f"{base_url}/api/tiktok/media/{create_media_token(object_name, mime_type)}"


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2
