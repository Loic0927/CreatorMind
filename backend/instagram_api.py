import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

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
    instagram_configured,
    instagram_comment_ingestion_enabled,
    instagram_scopes,
    publish_instagram_image,
    token_expiry,
)
from backend.services.publishing import (
    InstagramPublishingAdapter,
    PublishInput,
    PublishingAdapterRegistry,
    UnavailablePublishingAdapter,
)
from backend.services.comments import audience_comment_state
from backend.services.account_insights import build_account_insights, build_post_analysis
from backend.services.insight_texts import audience_description, next_post_suggestion, post_feedback
from backend.services.instagram_sync import refresh_one_post, usable_token
from backend.auth import AuthenticatedUser, require_user
from backend.storage.content_repository import get_content_repository
from backend.storage.models import InstagramAccount, InstagramMedia
from backend.storage.oci_object_storage import upload_bytes_with_temporary_read_url
from backend.storage.instagram_repository import (
    InstagramRepository,
    InstagramRepositoryError,
    get_instagram_repository,
)


router = APIRouter()


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
            "last_synced_at": datetime.now(timezone.utc),
        }
    )
    try:
        repository().upsert_connection(updated)
    except InstagramRepositoryError:
        raise repository_error() from None


def _handle_connected_service_error(
    account: InstagramAccount, exc: InstagramServiceError
) -> HTTPException:
    if exc.code in {"instagram_token_invalid", "connection_expired"}:
        _mark_reconnect_required(account)
        return HTTPException(
            status_code=401,
            detail={"code": "reconnect_required", "message": "Instagram must be reconnected."},
        )
    return service_error(exc)


@router.get("/api/instagram/connection")
@router.get("/instagram/connection", include_in_schema=False)
def connection(user: AuthenticatedUser = Depends(require_user)):
    return public_account(stored_connection(current_user(user)))


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
                build_app_return_url(
                    "error", "instagram_authorization_denied", client
                ),
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
        now = datetime.now(timezone.utc)
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
                "last_synced_at": datetime.now(timezone.utc),
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
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


@router.get("/api/instagram/media")
@router.get("/instagram/media", include_in_schema=False)
def media(user: AuthenticatedUser = Depends(require_user)):
    account = _active_account(current_user(user))
    try:
        upstream = fetch_instagram_media(_access_token(account))
        now = datetime.now(timezone.utc)
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


class PublishImage(BaseModel):
    mime_type: str
    data: str = Field(..., min_length=4)


class PublishRequest(BaseModel):
    platforms: list[str] = Field(..., min_length=1, max_length=5)
    caption: str = Field(..., min_length=1, max_length=2200)
    hashtags: str = Field(default="", max_length=1000)
    image: PublishImage


def publishing_registry() -> PublishingAdapterRegistry:
    return PublishingAdapterRegistry([
        InstagramPublishingAdapter(
            account_loader=_active_account,
            token_loader=_access_token,
            repository_loader=get_content_repository,
            uploader=upload_bytes_with_temporary_read_url,
            provider_publisher=publish_instagram_image,
        ),
        *[
            UnavailablePublishingAdapter(platform)
            for platform in ("Twitter", "Facebook", "Threads", "YouTube")
        ],
    ])


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
        raise HTTPException(status_code=422, detail={"code": "unsupported_platform", "message": f"Unsupported platform: {unknown[0]}"})
    request = PublishInput(
        caption=payload.caption, hashtags=payload.hashtags,
        mime_type=payload.image.mime_type, encoded_media=payload.image.data,
    )
    results = [registry.get(platform).publish(user_id, request).as_dict() for platform in platforms]
    return {"results": results}


@router.post("/tracked-posts")
def track(payload: TrackRequest, user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    account = stored_connection(user_id)
    owned_ids = (
        {item.id for item in get_content_repository().media_for_account(account.id)} if account else set()
    )
    if payload.media_id not in owned_ids:
        raise HTTPException(
            status_code=404,
            detail={"code": "media_not_found", "message": "Instagram post was not found."},
        )
    tracked = get_content_repository().create_tracked(user_id, payload.media_id)
    return tracked


def tracked_payload(user_id: str, active_only: bool = True):
    account = stored_connection(user_id)
    media = get_content_repository().media_for_account(account.id) if account else []
    media_by_id = {item.id: item for item in media}
    snapshots_by_media = {}
    for item in get_content_repository().snapshots(list(media_by_id)):
        if (
            item.media_id not in snapshots_by_media
            or item.captured_at > snapshots_by_media[item.media_id].captured_at
        ):
            snapshots_by_media[item.media_id] = item
    payload = [
        {
            "tracking": tracked,
            "media": media_by_id.get(tracked.media_id),
            "latest": snapshots_by_media.get(tracked.media_id),
        }
        for tracked in get_content_repository().tracked(user_id, active_only=active_only)
    ]
    return payload


def _feedback_media(media) -> tuple[bytes, str] | None:
    """Fetch only bounded media URLs previously supplied by Meta."""
    media_type = str(media.media_type or "").upper()
    url = media.media_url if media_type in {"VIDEO", "REELS"} else media.thumbnail_url or media.media_url
    if not url:
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    allowed_host = hostname == "instagram.com" or hostname.endswith((".instagram.com", ".cdninstagram.com", ".fbcdn.net"))
    if parsed.scheme != "https" or not allowed_host:
        return None
    maximum = int(os.getenv("POSTBRIDGE_FEEDBACK_MEDIA_BYTES", str(10 * 1024 * 1024)))
    request = Request(url, headers={"User-Agent": "PostBridge/1.0"})
    try:
        with urlopen(request, timeout=8) as response:
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            allowed_types = {
                "image/jpeg", "image/png", "image/webp",
                "video/mp4", "video/webm", "video/quicktime",
            }
            if content_type not in allowed_types:
                return None
            length = response.headers.get("Content-Length")
            if length and int(length) > maximum:
                return None
            content = response.read(maximum + 1)
    except (HTTPError, URLError, OSError, ValueError):
        return None
    return (content, content_type) if content and len(content) <= maximum else None


def _tracked_item(user_id: str, tracked_id: str) -> dict:
    item = next(
        (
            candidate
            for candidate in tracked_payload(user_id)
            if candidate["tracking"].id == tracked_id
        ),
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


@router.get("/tracked-posts")
def tracked_posts(user: AuthenticatedUser = Depends(require_user)):
    return {"items": tracked_payload(current_user(user))}


@router.get("/tracked-posts/{tracked_id}")
def tracked_detail(tracked_id: str, user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    item = _tracked_item(user_id, tracked_id)
    repository = get_content_repository()
    snapshots = sorted(repository.snapshots([item["tracking"].media_id]), key=lambda value: value.captured_at)
    item["snapshots"] = list(reversed(snapshots))
    all_items = []
    for candidate in tracked_payload(user_id, active_only=False):
        candidate_snapshots = repository.snapshots([candidate["tracking"].media_id])
        all_items.append({**candidate, "snapshots": candidate_snapshots})
    account = stored_connection(user_id)
    comments = repository.comments(user_id, tracked_id)
    enabled = bool(account and instagram_comment_ingestion_enabled(user_id, account.instagram_user_id))
    permission = bool(account and "instagram_business_manage_comments" in account.scopes)
    description = audience_description(user_id, tracked_id, comments) if enabled and permission else None
    audience = audience_comment_state(comments, feature_enabled=enabled, permission_granted=permission, description=description)
    if account and account.session_sync_error == "comment_access_denied":
        audience = {"state": "access_denied", "message": "Instagram denied access to comments."}
    selected_for_analysis = next(value for value in all_items if value["tracking"].id == tracked_id)
    analysis = build_post_analysis(selected_for_analysis, all_items, summary=None, audience_comments=audience)
    analysis["summary"] = post_feedback(
        user_id,
        tracked_id,
        item["media"],
        item.get("latest"),
        analysis,
        media_loader=lambda: _feedback_media(item["media"]),
    )
    item["analysis"] = analysis
    return item


@router.get("/insights/account")
def account_insights(user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    account = stored_connection(user_id)
    repository = get_content_repository()
    items = []
    for item in tracked_payload(user_id, active_only=False):
        items.append({**item, "snapshots": repository.snapshots([item["tracking"].media_id])})
    base = build_account_insights(items)
    internal_posts = []
    for post in base["performance_posts"]:
        source = next((item for item in items if item["tracking"].id == post["tracked_post_id"]), None)
        internal_posts.append({**post, "caption": source["media"].caption if source and source.get("media") else ""})
    suggestion = next_post_suggestion(
        user_id,
        internal_posts,
        {item["tracking"].id: repository.comments(user_id, item["tracking"].id) for item in items},
    )
    result = build_account_insights(items, suggestion=suggestion)
    result["sync_status"] = (
        "reconnect_required" if account and account.status == "reconnect_required"
        else "failed" if account and account.session_sync_error
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
    tracked_id: str, user: AuthenticatedUser = Depends(require_user)
):
    user_id = current_user(user)
    tracked_item = _tracked_item(user_id, tracked_id)
    account = _active_account(user_id)
    media_item = tracked_item.get("media")
    if media_item is None:
        raise HTTPException(status_code=404, detail={"code": "media_not_found", "message": "Instagram post was not found."})
    latest = tracked_item.get("latest")
    if latest and datetime.now(timezone.utc) - (latest.captured_at if latest.captured_at.tzinfo else latest.captured_at.replace(tzinfo=timezone.utc)) < timedelta(minutes=1):
        return tracked_detail(tracked_id, user)
    try:
        refresh_one_post(user_id, tracked_item["tracking"], media_item, usable_token(account))
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(account, exc) from exc
    return tracked_detail(tracked_id, user)


@router.get("/insights/instagram")
def insights(
    period: str = Query("7d"), user: AuthenticatedUser = Depends(require_user)
):
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
