import json
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from backend.storage.json_store import (
    delete_social_connection,
    get_social_connection,
    get_social_connections,
    upsert_social_connection,
)
from backend.storage.models import SocialConnection


logger = logging.getLogger(__name__)

YOUTUBE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
_PENDING_STATES: dict[str, dict[str, str | datetime]] = {}


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    hostname = parsed.netloc.lower()

    if "youtu.be" in hostname:
        video_id = parsed.path.strip("/")
        if video_id:
            return video_id

    if "youtube.com" in hostname:
        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/")[-1].strip("/")
            if video_id:
                return video_id

        query = parse_qs(parsed.query)
        if "v" in query and query["v"]:
            return query["v"][0]

    raise ValueError("Invalid YouTube URL. Provide a standard video or Shorts URL.")


def get_youtube_connection(user_id: str) -> SocialConnection | None:
    connection = get_social_connection("YouTube", user_id)
    if connection and connection.status == "connected":
        return connection
    return None


def get_youtube_api_key() -> str | None:
    return os.getenv("YOUTUBE_API_KEY")


def get_google_client_id() -> str | None:
    return os.getenv("GOOGLE_CLIENT_ID")


def get_google_client_secret() -> str | None:
    return os.getenv("GOOGLE_CLIENT_SECRET")


def get_youtube_oauth_redirect_uri() -> str:
    return os.getenv(
        "YOUTUBE_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/youtube/callback",
    )


def get_frontend_base_url() -> str:
    return os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")


def _cleanup_pending_states() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    expired = [
        state
        for state, payload in _PENDING_STATES.items()
        if isinstance(payload.get("created_at"), datetime) and payload["created_at"] < cutoff
    ]
    for state in expired:
        _PENDING_STATES.pop(state, None)


def create_youtube_oauth_state(user_id: str) -> str:
    _cleanup_pending_states()
    state = uuid4().hex
    _PENDING_STATES[state] = {
        "created_at": datetime.now(timezone.utc),
        "user_id": user_id,
    }
    return state


def consume_youtube_oauth_state(state: str) -> str | None:
    _cleanup_pending_states()
    payload = _PENDING_STATES.pop(state, None)
    if not payload:
        return None
    user_id = payload.get("user_id")
    return str(user_id) if user_id else None


def build_youtube_oauth_url(state: str) -> str:
    client_id = get_google_client_id()
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured.")

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": get_youtube_oauth_redirect_uri(),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(YOUTUBE_OAUTH_SCOPES),
            "state": state,
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def exchange_youtube_oauth_code(code: str) -> dict:
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    if not client_id or not client_secret:
        raise ValueError("Google OAuth client credentials are not configured.")

    payload = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": get_youtube_oauth_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    request = Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_youtube_account_profile(access_token: str) -> dict | None:
    query = urlencode({"part": "snippet", "mine": "true"})
    request = Request(
        f"https://www.googleapis.com/youtube/v3/channels?{query}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    items = payload.get("items") or []
    if not items:
        return None

    item = items[0]
    snippet = item.get("snippet") or {}
    return {
        "channel_id": item.get("id"),
        "account_name": snippet.get("title") or "YouTube Account",
    }


def store_youtube_connection(user_id: str, token_payload: dict) -> SocialConnection:
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")
    expires_in = token_payload.get("expires_in")
    scope = token_payload.get("scope")
    if not access_token:
        raise ValueError("Google OAuth token exchange did not return an access token.")

    profile = fetch_youtube_account_profile(access_token) or {}
    now = datetime.now(timezone.utc)
    expires_at = None
    if expires_in:
        try:
            expires_at = now + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    existing = get_youtube_connection(user_id)
    connection = SocialConnection(
        id=existing.id if existing else uuid4().hex,
        user_id=user_id,
        platform="YouTube",
        account_name=str(profile.get("account_name") or (existing.account_name if existing else "YouTube Account")),
        status="connected",
        connected_at=existing.connected_at if existing and existing.connected_at else now,
        last_sync_at=now,
        external_account_id=str(profile.get("channel_id") or (existing.external_account_id if existing else "")) or None,
        access_token=access_token,
        refresh_token=refresh_token or (existing.refresh_token if existing else None),
        token_scope=scope or (existing.token_scope if existing else None),
        token_expires_at=expires_at,
    )
    return upsert_social_connection(connection)


def disconnect_youtube_connection(user_id: str) -> bool:
    return delete_social_connection("YouTube", user_id)


def fetch_youtube_public_video_data(video_id: str) -> dict | None:
    api_key = get_youtube_api_key()
    if not api_key:
        logger.warning("YouTube Data API key is missing. Set YOUTUBE_API_KEY to fetch public video data.")
        return None

    query = urlencode(
        {
            "part": "snippet,statistics",
            "id": video_id,
            "key": api_key,
        }
    )
    endpoint = f"https://www.googleapis.com/youtube/v3/videos?{query}"
    logger.info("Fetching YouTube public video data for video_id=%s", video_id)

    try:
        with urlopen(endpoint, timeout=10) as response:
            raw_response = response.read().decode("utf-8")
            logger.info("YouTube Data API raw response: %s", raw_response)
            payload = json.loads(raw_response)
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        logger.error("YouTube Data API HTTP error for video_id=%s: %s", video_id, raw_error)
        return None
    except URLError as exc:
        logger.error("YouTube Data API network error for video_id=%s: %s", video_id, exc)
        return None
    except (TimeoutError, json.JSONDecodeError) as exc:
        logger.error("YouTube Data API parse/timeout error for video_id=%s: %s", video_id, exc)
        return None

    items = payload.get("items") or []
    if not items:
        logger.warning("YouTube Data API returned no items for video_id=%s", video_id)
        return None

    item = items[0]
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    thumbnails = snippet.get("thumbnails") or {}
    thumbnail = (
        thumbnails.get("maxres")
        or thumbnails.get("standard")
        or thumbnails.get("high")
        or thumbnails.get("medium")
        or thumbnails.get("default")
        or {}
    )

    def parse_optional_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "published_at": snippet.get("publishedAt"),
        "channel_title": snippet.get("channelTitle"),
        "thumbnail_url": thumbnail.get("url"),
        "views": parse_optional_int(statistics.get("viewCount")),
        "likes": parse_optional_int(statistics.get("likeCount")),
        "comments": parse_optional_int(statistics.get("commentCount")),
    }


def fetch_youtube_public_video_data_from_url(url: str) -> dict | None:
    video_id = extract_youtube_video_id(url)
    return fetch_youtube_public_video_data(video_id)


def fetch_youtube_analytics(video_id: str) -> dict | None:
    # OAuth-backed YouTube Analytics API data such as averageViewDuration
    # still requires an authorized user flow and is not fabricated here.
    _ = video_id
    return None


def fetch_youtube_advanced_analytics(user_id: str, video_id: str) -> dict | None:
    # Placeholder for future YouTube Analytics API integration using the stored
    # OAuth connection and refresh token flow.
    _ = video_id
    connection = get_youtube_connection(user_id)
    if connection is None or not connection.access_token:
        return None
    return None
