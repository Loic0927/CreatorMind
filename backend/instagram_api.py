import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedUser, has_ai_processing_consent, require_user
from backend.services.account_insights import build_account_insights, build_post_analysis
from backend.services.comments import audience_comment_state
from backend.services.insight_refresh import refresh_cached_insights
from backend.services.instagram import (
    InstagramServiceError,
    aggregate_seven_days,
    build_app_return_url,
    build_authorization_url,
    consume_oauth_state_context,
    create_oauth_state,
    decrypt_access_token,
    encrypt_access_token,
    exchange_authorization_code,
    exchange_long_lived_token,
    fetch_instagram_media,
    fetch_instagram_profile,
    granted_instagram_scopes,
    instagram_comment_ingestion_enabled,
    instagram_configured,
    publish_instagram_image,
    publish_instagram_reel,
    token_expiry,
)
from backend.services.instagram_sync import refresh_one_post, usable_token
from backend.services.publishing import (
    InstagramPublishingAdapter,
    PublishingAdapterRegistry,
    PublishInput,
    UnavailablePublishingAdapter,
)
from backend.services.tracked_items import load_tracked_items
from backend.storage.content_repository import get_content_repository
from backend.storage.instagram_repository import (
    InstagramRepository,
    InstagramRepositoryError,
    get_instagram_repository,
)
from backend.storage.models import InstagramAccount, InstagramMedia
from backend.storage.oci_object_storage import upload_bytes_with_temporary_read_url

router = APIRouter()
LOGGER = logging.getLogger("postbridge.instagram_api")
META_SIGNED_REQUEST_ALGORITHM = "HMAC-SHA256"


def upsert_instagram_media(items: list[InstagramMedia]) -> list[InstagramMedia]:
    """Compatibility boundary retained for tests and local integrations."""
    return get_content_repository().upsert_media(items)


def current_user(user: AuthenticatedUser | str) -> str:
    value = user.id if isinstance(user, AuthenticatedUser) else user.strip()
    if not value:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Authentication is required."},
        )
    return value


def service_error(exc: InstagramServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def repository_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "instagram_storage_unavailable",
            "message": "Instagram connection storage is unavailable.",
        },
    )


def repository() -> InstagramRepository:
    try:
        return get_instagram_repository()
    except InstagramRepositoryError:
        raise repository_error() from None


def stored_connection(user_id: str) -> InstagramAccount | None:
    try:
        return repository().get_connection(user_id)
    except InstagramRepositoryError:
        raise repository_error() from None


def public_account(account: InstagramAccount | None) -> dict:
    if not account:
        return {
            "connected": False,
            "configured": instagram_configured(),
            "status": "not_connected",
            "comment_ingestion": {"enabled": False, "permission_granted": False},
        }
    return {
        "connected": account.status == "connected",
        "configured": instagram_configured(),
        "status": account.status,
        "id": account.instagram_user_id,
        "username": account.username,
        "profile_picture_url": account.profile_picture_url,
        "account_type": account.account_type,
        "media_count": account.media_count,
        "last_synced_at": account.last_synced_at,
        "session_synced_at": account.session_synced_at,
        "sync_error": account.session_sync_error,
        "comment_ingestion": {
            "enabled": instagram_comment_ingestion_enabled(account.user_id, account.instagram_user_id),
            "permission_granted": "instagram_business_manage_comments" in account.scopes,
        },
    }


def _active_account(user_id: str) -> InstagramAccount:
    account = stored_connection(user_id)
    if account and account.status in {"expired", "reconnect_required"}:
        raise HTTPException(
            status_code=401,
            detail={"code": "reconnect_required", "message": "Instagram must be reconnected."},
        )
    if not account or account.status != "connected":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "instagram_not_connected",
                "message": "Instagram is not connected.",
            },
        )
    return account


def _access_token(account: InstagramAccount) -> str:
    try:
        encrypted_token = repository().get_encrypted_token(account.id)
    except InstagramRepositoryError:
        raise repository_error() from None
    if not encrypted_token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "connection_expired",
                "message": "Instagram must be reconnected.",
            },
        )
    try:
        return decrypt_access_token(encrypted_token)
    except InstagramServiceError as exc:
        raise service_error(exc) from exc


def _mark_reconnect_required(account: InstagramAccount) -> None:
    updated = account.model_copy(
        update={
            "status": "reconnect_required",
            "last_error": "instagram_token_invalid",
            "last_synced_at": datetime.now(UTC),
        }
    )
    try:
        repository().upsert_connection(updated)
    except InstagramRepositoryError:
        raise repository_error() from None


def _handle_connected_service_error(account: InstagramAccount, exc: InstagramServiceError) -> HTTPException:
    if exc.code in {"instagram_token_invalid", "connection_expired"}:
        _mark_reconnect_required(account)
        return HTTPException(
            status_code=401,
            detail={"code": "reconnect_required", "message": "Instagram must be reconnected."},
        )
    return service_error(exc)


def _invalid_signed_request() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "invalid_signed_request", "message": "Instagram signed request is invalid."},
    )


def verify_meta_signed_request(signed_request: str) -> str:
    """Verify a Meta signed_request and return its app-scoped user id.

    Meta signs the encoded payload, rather than decoded JSON. The raw signed
    request is deliberately never logged or persisted.
    """
    secret = os.getenv("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={"code": "instagram_not_configured", "message": "Instagram is not configured."},
        )
    try:
        signature_encoded, payload_encoded = signed_request.split(".")
        if not signature_encoded or not payload_encoded:
            raise ValueError
        supplied_signature = base64.urlsafe_b64decode(signature_encoded + "=" * (-len(signature_encoded) % 4))
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload_encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(payload_encoded + "=" * (-len(payload_encoded) % 4)))
        if not isinstance(payload, dict) or payload.get("algorithm") != META_SIGNED_REQUEST_ALGORITHM:
            raise ValueError
        value = payload.get("user_id")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError
        instagram_user_id = str(value).strip()
        if not instagram_user_id:
            raise ValueError
        return instagram_user_id
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        raise _invalid_signed_request() from None


def _data_deletion_status_url(confirmation_code: str) -> str:
    """Build the public confirmation URL without trusting a request Host header."""
    base_url = os.getenv("POSTBRIDGE_PUBLIC_API_URL", "").strip().rstrip("/")
    if not base_url:
        redirect_uri = os.getenv("POSTBRIDGE_INSTAGRAM_REDIRECT_URI", "").strip()
        parsed = urlparse(redirect_uri)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
    if not base_url:
        # This branch is development-only. Production deployments already use
        # POSTBRIDGE_PUBLIC_API_URL for the browser and mobile clients.
        base_url = "http://localhost:8000"
    return f"{base_url}/api/instagram/data-deletion/status?{urlencode({'code': confirmation_code})}"


@router.get("/api/instagram/connection")
@router.get("/instagram/connection", include_in_schema=False)
def connection(user: AuthenticatedUser = Depends(require_user)):
    return public_account(stored_connection(current_user(user)))


@router.post("/api/instagram/deauthorize")
def deauthorize(signed_request: str = Form(...)):
    instagram_user_id = verify_meta_signed_request(signed_request)
    try:
        affected = repository().deauthorize_instagram_user(instagram_user_id)
    except InstagramRepositoryError:
        raise repository_error() from None
    return {"deauthorized": bool(affected)}


@router.post("/api/instagram/data-deletion")
def data_deletion(signed_request: str = Form(...)):
    instagram_user_id = verify_meta_signed_request(signed_request)
    confirmation_code = secrets.token_urlsafe(24)
    try:
        repository().delete_instagram_data(
            instagram_user_id,
            confirmation_code,
            datetime.now(UTC),
        )
    except InstagramRepositoryError:
        raise repository_error() from None
    return {
        "url": _data_deletion_status_url(confirmation_code),
        "confirmation_code": confirmation_code,
    }


@router.get("/api/instagram/data-deletion/status")
def data_deletion_status(code: str = Query(..., min_length=1)):
    try:
        request = repository().get_data_deletion_request(code)
    except InstagramRepositoryError:
        raise repository_error() from None
    if request is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "deletion_request_not_found", "message": "Deletion request was not found."},
        )
    return {
        "status": request.status,
        "created_at": request.created_at,
        "completed_at": request.completed_at,
    }


@router.post("/api/instagram/connect/start")
@router.post("/instagram/connect/start", include_in_schema=False)
def connect_start(client: str = Query("mobile"), user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    try:
        return {"authorization_url": build_authorization_url(create_oauth_state(user_id, client=client), user_id)}
    except InstagramServiceError as exc:
        raise service_error(exc) from exc


@router.get("/api/instagram/connect/callback")
@router.get("/instagram/connect/callback", include_in_schema=False)
def connect_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    client = "mobile"
    try:
        if error:
            if state:
                try:
                    _, client = consume_oauth_state_context(state)
                except InstagramServiceError:
                    pass
            return RedirectResponse(
                build_app_return_url("error", "instagram_authorization_denied", client),
                status_code=302,
            )
        if not code or not state:
            return RedirectResponse(
                build_app_return_url("error", "invalid_oauth_callback"),
                status_code=302,
            )
        user_id, client = consume_oauth_state_context(state)
        short_payload = exchange_authorization_code(code)
        granted_scopes = list(granted_instagram_scopes(short_payload))
        long_payload = exchange_long_lived_token(short_payload["access_token"])
        access_token = long_payload["access_token"]
        profile = fetch_instagram_profile(access_token)
        if str(profile.get("account_type", "")).upper() not in {"BUSINESS", "MEDIA_CREATOR"}:
            raise InstagramServiceError(
                "instagram_professional_account_required",
                "Connect an Instagram Business or Creator account.",
                403,
            )
        repo = repository()
        try:
            existing = repo.get_connection(user_id)
        except InstagramRepositoryError:
            raise repository_error() from None
        now = datetime.now(UTC)
        encrypted_token = encrypt_access_token(access_token)
        account = InstagramAccount(
            id=existing.id if existing else str(uuid4()),
            user_id=user_id,
            instagram_user_id=str(profile["id"]),
            username=str(profile["username"]),
            profile_picture_url=None,
            account_type=profile.get("account_type"),
            media_count=profile.get("media_count"),
            encrypted_access_token="",
            token_expires_at=token_expiry(long_payload),
            scopes=granted_scopes,
            session_synced_at=existing.session_synced_at if existing else None,
            session_sync_error=None,
            tracking_start_at=existing.tracking_start_at if existing and existing.tracking_start_at else now,
            status="connected",
            connected_at=existing.connected_at if existing else now,
            last_synced_at=now,
            last_error=None,
        )
        try:
            account = repo.upsert_connection(
                account,
                encrypted_token=encrypted_token,
                scopes=granted_scopes,
            )
        except InstagramRepositoryError:
            raise repository_error() from None
        return RedirectResponse(build_app_return_url("success", client=client), status_code=302)
    except InstagramServiceError as exc:
        return RedirectResponse(build_app_return_url("error", exc.code, client), status_code=302)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        safe_code = str(detail.get("code", "instagram_callback_failed"))
        return RedirectResponse(build_app_return_url("error", safe_code, client), status_code=302)


@router.get("/api/instagram/account")
def account(user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    stored = _active_account(user_id)
    try:
        profile = fetch_instagram_profile(_access_token(stored))
        updated = stored.model_copy(
            update={
                "instagram_user_id": str(profile["id"]),
                "username": str(profile["username"]),
                "account_type": profile.get("account_type"),
                "media_count": profile.get("media_count"),
                "last_synced_at": datetime.now(UTC),
                "last_error": None,
            }
        )
        try:
            updated = repository().upsert_connection(updated)
        except InstagramRepositoryError:
            raise repository_error() from None
        return public_account(updated)
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(stored, exc) from exc


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


@router.get("/api/instagram/media")
@router.get("/instagram/media", include_in_schema=False)
def media(user: AuthenticatedUser = Depends(require_user)):
    account = _active_account(current_user(user))
    try:
        upstream = fetch_instagram_media(_access_token(account))
        now = datetime.now(UTC)
        items = [
            InstagramMedia(
                id=f"instagram:{item['id']}",
                account_id=account.id,
                instagram_media_id=str(item["id"]),
                media_type=str(item.get("media_type", "UNKNOWN")),
                media_url=item.get("media_url"),
                thumbnail_url=item.get("thumbnail_url"),
                permalink=item.get("permalink"),
                caption=str(item.get("caption", "")),
                published_at=_parse_timestamp(item.get("timestamp")),
                last_synced_at=now,
            )
            for item in upstream
            if item.get("id")
        ]
        upsert_instagram_media(items)
        return {"status": account.status, "items": items}
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(account, exc) from exc


def _disconnect(user_id: str) -> dict:
    try:
        disconnected = repository().delete_connection(user_id)
    except InstagramRepositoryError:
        raise repository_error() from None
    if disconnected:
        get_content_repository().stop_all_tracked(user_id)
    return {"disconnected": disconnected}


@router.delete("/api/instagram/connection")
def delete_connection(user: AuthenticatedUser = Depends(require_user)):
    return _disconnect(current_user(user))


@router.post("/instagram/disconnect", include_in_schema=False)
def legacy_disconnect(user: AuthenticatedUser = Depends(require_user)):
    return _disconnect(current_user(user))


class TrackRequest(BaseModel):
    media_id: str


def _public_tracking(value) -> dict:
    return {
        "id": value.id,
        "media_id": value.media_id,
        "is_active": value.is_active,
        "started_at": value.started_at,
        "stopped_at": value.stopped_at,
    }


def _public_snapshot(value) -> dict | None:
    if value is None:
        return None
    return {
        name: getattr(value, name)
        for name in (
            "id",
            "media_id",
            "captured_at",
            "likes",
            "comments",
            "saves",
            "shares",
            "reach",
            "views",
            "engagement_rate",
            "average_watch_time_ms",
            "total_watch_time_ms",
            "raw_metrics",
            "metric_status",
        )
    }


def _public_tracked_item(item: dict) -> dict:
    result = dict(item)
    result["tracking"] = _public_tracking(item["tracking"])
    result["latest"] = _public_snapshot(item.get("latest"))
    if "snapshots" in item:
        result["snapshots"] = [_public_snapshot(value) for value in item["snapshots"]]
    return result


def _cached_text_with_status(
    content,
    user_id: str,
    cache_key: str,
    *,
    pending_when_missing: bool,
) -> tuple[str | None, str, bool]:
    """Read one generated-text cache without scheduling or generating it.

    A persisted empty value is an intentional resolved result (for example,
    when the available evidence cannot support a Summary), so it is distinct
    from a missing cache while a write-side refresh is still in progress.
    """

    cached = content.get_text_cache(user_id, cache_key)
    if cached is not None:
        text = str(cached.text or "").strip()
        return (text, "ready", True) if text else (None, "none", True)
    return (None, "pending", False) if pending_when_missing else (None, "none", False)


def _next_suggestion_can_be_generated(posts: list[dict]) -> bool:
    """Return whether the newest post has enough comparable history for Reflection.

    This is deliberately a local, deterministic availability check. It does
    not call the generator (or duplicate its scoring): a missing cache stays
    ``pending`` only while a background refresh could actually create one.
    """

    eligible: list[dict] = []
    for post in posts:
        metrics = post.get("metrics") or {}
        reach = metrics.get("reach")
        has_reach_signal = (
            isinstance(reach, (int, float))
            and reach > 0
            and (
                isinstance(metrics.get("views"), (int, float))
                or isinstance(metrics.get("comments"), (int, float))
                or (isinstance(metrics.get("saves"), (int, float)) and isinstance(metrics.get("shares"), (int, float)))
            )
        )
        format_key = str(post.get("format_key") or post.get("media_type") or "unknown").lower()
        is_video = format_key in {"video", "reel", "reels"}
        has_watch_signal = is_video and isinstance(metrics.get("average_watch_time_ms"), (int, float))
        if not (has_reach_signal or has_watch_signal):
            continue
        eligible.append(post)
    if not eligible:
        return False
    latest = max(
        eligible, key=lambda post: (str(post.get("published_at") or ""), str(post.get("tracked_post_id") or ""))
    )
    latest_format = str(latest.get("format_key") or latest.get("media_type") or "unknown").lower()
    historical_count = sum(
        1
        for post in eligible
        if post is not latest
        and post.get("mature")
        and str(post.get("format_key") or post.get("media_type") or "unknown").lower() == latest_format
    )
    return historical_count >= 6


class PublishImage(BaseModel):
    mime_type: str
    data: str = Field(..., min_length=4)
    duration_seconds: float | None = Field(default=None, gt=0, le=60.05)


class PublishRequest(BaseModel):
    platforms: list[str] = Field(..., min_length=1, max_length=5)
    caption: str = Field(..., min_length=1, max_length=2200)
    hashtags: str = Field(default="", max_length=1000)
    image: PublishImage | None = None
    media: PublishImage | None = None


def publishing_registry() -> PublishingAdapterRegistry:
    return PublishingAdapterRegistry(
        [
            InstagramPublishingAdapter(
                account_loader=_active_account,
                token_loader=_access_token,
                repository_loader=get_content_repository,
                uploader=upload_bytes_with_temporary_read_url,
                provider_publisher=publish_instagram_image,
                video_publisher=publish_instagram_reel,
            ),
            *[UnavailablePublishingAdapter(platform) for platform in ("Twitter", "Facebook", "Threads", "YouTube")],
        ]
    )


@router.get("/publishing/capabilities")
def publishing_capabilities(user: AuthenticatedUser = Depends(require_user)):
    capabilities = publishing_registry().capabilities(current_user(user))
    return {"items": [item.as_dict() for item in capabilities]}


@router.post("/publications")
def publish(payload: PublishRequest, user: AuthenticatedUser = Depends(require_user)):
    """Publish to supported selected platforms and report each result independently."""
    user_id = current_user(user)
    platforms = list(dict.fromkeys(payload.platforms))
    registry = publishing_registry()
    unknown = [item for item in platforms if registry.get(item) is None]
    if unknown:
        raise HTTPException(
            status_code=422, detail={"code": "unsupported_platform", "message": f"Unsupported platform: {unknown[0]}"}
        )
    if payload.image is not None and payload.media is not None:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_media", "message": "Provide either image or media, not both."}
        )
    supplied_media = payload.media or payload.image
    if supplied_media is None:
        raise HTTPException(
            status_code=422, detail={"code": "media_required", "message": "Publishable media is required."}
        )
    request = PublishInput(
        caption=payload.caption,
        hashtags=payload.hashtags,
        mime_type=supplied_media.mime_type,
        encoded_media=supplied_media.data,
        duration_seconds=supplied_media.duration_seconds,
    )
    results = [registry.get(platform).publish(user_id, request).as_dict() for platform in platforms]
    return {"results": results}


@router.post("/tracked-posts")
def track(
    payload: TrackRequest,
    user: AuthenticatedUser = Depends(require_user),
    background_tasks: BackgroundTasks = None,
):
    user_id = current_user(user)
    account = stored_connection(user_id)
    content = get_content_repository()
    media_by_id = {item.id: item for item in content.media_for_account(account.id)} if account else {}
    media_item = media_by_id.get(payload.media_id)
    if media_item is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "media_not_found", "message": "Instagram post was not found."},
        )
    tracked = content.create_tracked(user_id, payload.media_id)
    # The existing picker is the only path for OLD posts. Fetch current lifetime
    # metrics immediately, then generate any AI caches outside the request.
    try:
        refresh_one_post(user_id, tracked, media_item, usable_token(account), refresh_comments=False)
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(account, exc) from exc
    if background_tasks is not None:
        background_tasks.add_task(refresh_cached_insights, user_id, tracked.id)
    return _public_tracking(tracked)


def tracked_payload(user_id: str, active_only: bool = True):
    account = stored_connection(user_id)
    items, _ = load_tracked_items(user_id, account=account, active_only=active_only)
    # The list endpoint historically returns only the latest snapshot. Keep the
    # bulk loader's history internal unless a caller explicitly needs it.
    return [{key: item.get(key) for key in ("tracking", "media", "latest")} for item in items]


def _tracked_item(user_id: str, tracked_id: str) -> dict:
    item = next(
        (candidate for candidate in tracked_payload(user_id) if candidate["tracking"].id == tracked_id),
        None,
    )
    if not item:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tracked_post_not_found",
                "message": "Tracked post was not found.",
            },
        )
    return item


def _find_tracked_item(items: list[dict], tracked_id: str) -> dict:
    item = next((candidate for candidate in items if candidate["tracking"].id == tracked_id), None)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tracked_post_not_found",
                "message": "Tracked post was not found.",
            },
        )
    return item


@router.get("/tracked-posts")
def tracked_posts(user: AuthenticatedUser = Depends(require_user)):
    return {"items": [_public_tracked_item(item) for item in tracked_payload(current_user(user))]}


@router.get("/tracked-posts/{tracked_id}")
def tracked_detail(tracked_id: str, user: AuthenticatedUser = Depends(require_user)):
    """Read one tracked post and its generated-text caches without side effects."""

    user_id = current_user(user)
    account = stored_connection(user_id)
    content = get_content_repository()
    all_items, comments_by_tracking = load_tracked_items(
        user_id,
        account=account,
        active_only=False,
        include_comments=True,
        repository=content,
    )
    selected_for_analysis = _find_tracked_item(all_items, tracked_id)
    if not selected_for_analysis["tracking"].is_active:
        # Match the pre-existing endpoint behavior: stopped posts are retained
        # for account-level comparisons but have no individually addressable
        # detail route.
        raise HTTPException(
            status_code=404,
            detail={"code": "tracked_post_not_found", "message": "Tracked post was not found."},
        )
    if selected_for_analysis.get("media") is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "media_not_found", "message": "Instagram post was not found."},
        )

    comments = comments_by_tracking.get(tracked_id, [])
    consented = has_ai_processing_consent(user_id)
    enabled = bool(account and instagram_comment_ingestion_enabled(user_id, account.instagram_user_id))
    permission = bool(account and "instagram_business_manage_comments" in account.scopes)
    audience_description, _, _ = _cached_text_with_status(
        content,
        user_id,
        f"audience:{tracked_id}",
        pending_when_missing=enabled and permission and len(comments) >= 3,
    )
    audience = audience_comment_state(
        comments,
        feature_enabled=enabled,
        permission_granted=permission,
        description=audience_description,
        consent_required=enabled and permission and not consented,
    )
    if account and account.session_sync_error == "comment_access_denied":
        audience = {
            "state": "access_denied",
            "message": "Instagram denied access to comments.",
            **({"items": audience["items"]} if enabled and permission else {}),
        }

    summary, summary_status, _ = _cached_text_with_status(
        content,
        user_id,
        f"summary:{tracked_id}",
        pending_when_missing=bool(selected_for_analysis.get("snapshots")),
    )
    if not consented:
        # A revoked account must not receive a stale AI cache even if cache
        # deletion races a read. Deterministic no-consent templates are safe
        # to retain and are written with the explicit template provider.
        summary_cache = content.get_text_cache(user_id, f"summary:{tracked_id}")
        if summary_cache is not None and getattr(summary_cache, "provider", "template") not in {"template", "none"}:
            summary = None
            summary_status = "pending" if selected_for_analysis.get("snapshots") else "none"
    analysis = build_post_analysis(
        selected_for_analysis,
        all_items,
        summary=summary,
        audience_comments=audience,
    )
    analysis["summary_status"] = summary_status
    item = {
        **selected_for_analysis,
        "snapshots": list(reversed(selected_for_analysis.get("snapshots") or [])),
        "analysis": analysis,
    }
    return _public_tracked_item(item)


@router.get("/insights/account")
def account_insights(user: AuthenticatedUser = Depends(require_user)):
    """Return stored metric and suggestion caches without calling providers."""

    user_id = current_user(user)
    account = stored_connection(user_id)
    content = get_content_repository()
    items, _ = load_tracked_items(
        user_id,
        account=account,
        active_only=False,
        repository=content,
    )
    consented = has_ai_processing_consent(user_id)
    suggestion, suggestion_status, suggestion_resolved = _cached_text_with_status(
        content,
        user_id,
        "reflection:latest-post",
        pending_when_missing=False,
    )
    # Build this once: it is pure, and includes both highlights and the
    # performance rows used to decide whether a missing cache can be pending.
    result = build_account_insights(items, suggestion=suggestion)
    if not consented:
        # Revocation clears caches, but never expose a stale text if a request
        # races that cleanup. The client can turn this state into its consent
        # explainer instead of treating it as a failed generation.
        result["next_post_suggestion"] = None
        suggestion_status = (
            "consent_required" if _next_suggestion_can_be_generated(result["performance_posts"]) else "none"
        )
    elif result["next_post_suggestion"] is None:
        if suggestion_resolved:
            suggestion_status = "none"
        elif _next_suggestion_can_be_generated(result["performance_posts"]):
            suggestion_status = "pending"
        else:
            suggestion_status = "none"
    result["next_post_suggestion_status"] = suggestion_status
    result["sync_status"] = (
        "reconnect_required"
        if account and account.status == "reconnect_required"
        else "failed"
        if account and account.session_sync_error
        else "ok"
    )
    return result


@router.delete("/tracked-posts/{tracked_id}")
def stop_tracking(tracked_id: str, user: AuthenticatedUser = Depends(require_user)):
    if not get_content_repository().stop_tracked(current_user(user), tracked_id):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tracked_post_not_found",
                "message": "Tracked post was not found.",
            },
        )
    return {"stopped": True}


@router.post("/tracked-posts/{tracked_id}/refresh")
def refresh_tracking(
    tracked_id: str,
    user: AuthenticatedUser = Depends(require_user),
    background_tasks: BackgroundTasks = None,
):
    user_id = current_user(user)
    tracked_item = _tracked_item(user_id, tracked_id)
    account = _active_account(user_id)
    media_item = tracked_item.get("media")
    if media_item is None:
        raise HTTPException(
            status_code=404, detail={"code": "media_not_found", "message": "Instagram post was not found."}
        )
    latest = tracked_item.get("latest")
    if latest and datetime.now(UTC) - (
        latest.captured_at if latest.captured_at.tzinfo else latest.captured_at.replace(tzinfo=UTC)
    ) < timedelta(minutes=1):
        # A manual refresh can also be used to recover a missing derived-text
        # cache.  Keep the one-minute metrics throttle, but still enqueue the
        # write-side cache refresh rather than making the GET-style response
        # path responsible for generation.
        if background_tasks is not None:
            background_tasks.add_task(refresh_cached_insights, user_id, tracked_id)
        return tracked_detail(tracked_id, user)
    try:
        refresh_one_post(user_id, tracked_item["tracking"], media_item, usable_token(account))
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(account, exc) from exc
    if background_tasks is not None:
        background_tasks.add_task(refresh_cached_insights, user_id, tracked_id)
    return tracked_detail(tracked_id, user)


@router.get("/insights/instagram")
def insights(period: str = Query("7d"), user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    if period != "7d":
        raise HTTPException(
            status_code=400,
            detail={"code": "unsupported_period", "message": "Only 7d is supported."},
        )
    account = stored_connection(user_id)
    if not account:
        return {"status": "not_connected", "period": "7d"}
    if account.status != "connected":
        return {"status": account.status, "period": "7d"}
    stored_media = get_content_repository().media_for_account(account.id)
    snapshots = get_content_repository().snapshots([item.id for item in stored_media])
    result = aggregate_seven_days(stored_media, snapshots)
    result["status"] = "connected"
    tracked = tracked_payload(user_id)
    result["top_posts"] = sorted(
        [item for item in tracked if item.get("latest")],
        key=lambda item: item["latest"].engagement_rate,
        reverse=True,
    )[:3]
    daily: dict[str, int] = {}
    for snapshot in snapshots:
        day = snapshot.captured_at.date().isoformat()
        daily[day] = daily.get(day, 0) + (snapshot.reach or snapshot.views or 0)
    result["trend"] = [{"date": day, "value": value} for day, value in sorted(daily.items())[-7:]]
    return result
