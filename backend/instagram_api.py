from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.services.instagram import (
    INSTAGRAM_SCOPES,
    InstagramServiceError,
    aggregate_seven_days,
    build_app_return_url,
    build_authorization_url,
    consume_oauth_state_context,
    create_oauth_state,
    decrypt_access_token,
    engagement_rate,
    encrypt_access_token,
    exchange_authorization_code,
    exchange_long_lived_token,
    fetch_instagram_media,
    fetch_instagram_media_insights,
    fetch_instagram_profile,
    instagram_configured,
    publish_instagram_image,
    safe_raw_metrics,
    token_expiry,
)
from backend.services.publishing import (
    InstagramPublishingAdapter,
    PublishInput,
    PublishingAdapterRegistry,
    UnavailablePublishingAdapter,
)
from backend.services.gemini import GeminiConfigurationError, GeminiUpstreamError
from backend.services.post_analysis import PostAnalysisError, analyze_post
from backend.services.account_insights import build_account_insights, generate_account_themes
from backend.auth import AuthenticatedUser, get_account_context, require_user
from backend.storage.content_repository import get_content_repository
from backend.storage.models import InstagramAccount, InstagramInsightSnapshot, InstagramMedia, TrackedPostAnalysis
from backend.storage.oci_object_storage import upload_bytes_with_temporary_read_url
from backend.storage.instagram_repository import (
    InstagramRepository,
    InstagramRepositoryError,
    SQLAlchemyInstagramRepository,
    get_instagram_repository,
)
from backend.storage.tracking_repository import get_tracking_repository


router = APIRouter()


def _automatic_tracking_available() -> bool:
    try:
        return isinstance(get_instagram_repository(), SQLAlchemyInstagramRepository)
    except InstagramRepositoryError:
        return False


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
    if _automatic_tracking_available():
        get_tracking_repository().block_user_for_reauthorization(account.user_id)


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
        return {"authorization_url": build_authorization_url(create_oauth_state(user_id, client=client))}
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
            scopes=list(INSTAGRAM_SCOPES),
            status="connected",
            connected_at=existing.connected_at if existing else now,
            last_synced_at=now,
            last_error=None,
        )
        try:
            account = repo.upsert_connection(
                account,
                encrypted_token=encrypted_token,
                scopes=list(INSTAGRAM_SCOPES),
            )
        except InstagramRepositoryError:
            raise repository_error() from None
        if isinstance(repo, SQLAlchemyInstagramRepository):
            get_tracking_repository().resume_user_jobs(user_id)
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
    if _automatic_tracking_available():
        get_tracking_repository().cancel_user_jobs(user_id)
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
    if _automatic_tracking_available():
        get_tracking_repository().ensure_jobs_for_tracking(tracked.id)
    return tracked


def _tracking_schedule(tracked_id: str, snapshots: list[InstagramInsightSnapshot] | None = None) -> dict:
    if not _automatic_tracking_available():
        return {
            "automatic_collection": False,
            "status": "scheduler_unavailable",
            "next_capture_at": None,
            "milestones": [],
        }
    jobs = sorted(
        get_tracking_repository().jobs_for_tracking(tracked_id),
        key=lambda item: item.target_hour,
    )
    by_id = {item.id: item for item in (snapshots or [])}
    milestones = []
    previous_snapshot = None
    for job in jobs:
        snapshot = by_id.get(job.snapshot_id) if job.snapshot_id else None
        views_since_previous_snapshot = None
        if snapshot is not None and previous_snapshot is not None:
            current_views = snapshot.views
            previous_views = previous_snapshot.views
            if (
                isinstance(current_views, int)
                and isinstance(previous_views, int)
                and current_views >= previous_views
            ):
                views_since_previous_snapshot = current_views - previous_views
        milestones.append({
            "target_hour": job.target_hour,
            "scheduled_for": job.due_at,
            "deadline_at": job.deadline_at,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "actual_captured_at": snapshot.captured_at if snapshot else None,
            "snapshot": snapshot,
            "views_since_previous_snapshot": views_since_previous_snapshot,
            "error_code": job.last_error_code,
        })
        if snapshot is not None:
            previous_snapshot = snapshot
    next_jobs = [job for job in jobs if job.status in {"pending", "retry", "running"}]
    blocked = next((job.status for job in jobs if job.status in {"blocked_reauthorization", "permission_required"}), None)
    return {
        "automatic_collection": True,
        "status": blocked or ("complete" if jobs and all(job.status in {"completed", "missed", "cancelled", "unavailable"} for job in jobs) else "tracking"),
        "next_capture_at": min((job.next_attempt_at for job in next_jobs), default=None),
        "milestones": milestones,
    }


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
    for item in payload:
        item["post_publish_tracking"] = _tracking_schedule(item["tracking"].id)
    return payload


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
    item["snapshots"] = sorted(
        [
            snapshot
            for snapshot in get_content_repository().snapshots([item["tracking"].media_id])
            if snapshot.media_id == item["tracking"].media_id
        ],
        key=lambda snapshot: snapshot.captured_at,
        reverse=True,
    )
    item["analyses"] = get_content_repository().analyses(user_id, tracked_id)
    item["post_publish_tracking"] = _tracking_schedule(tracked_id, item["snapshots"])
    return item


@router.get("/tracked-posts/{tracked_id}/analyses")
def tracked_analyses(tracked_id: str, user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    _tracked_item(user_id, tracked_id)
    return {"items": get_content_repository().analyses(user_id, tracked_id)}


@router.get("/insights/patterns")
def account_pattern_insights(
    timezone_offset_minutes: int = Query(0, ge=-840, le=840),
    user: AuthenticatedUser = Depends(require_user),
):
    user_id = current_user(user)
    account = stored_connection(user_id)
    items = []
    for item in tracked_payload(user_id, active_only=False):
        snapshots = get_content_repository().snapshots([item["tracking"].media_id])
        items.append({
            **item,
            "analyses": get_content_repository().analyses(user_id, item["tracking"].id),
            "snapshots": snapshots,
            "post_publish_tracking": _tracking_schedule(item["tracking"].id, snapshots),
        })
    themes = list(account.insight_themes) if account else []
    if account and not themes:
        themes = generate_account_themes(items)
        if themes:
            get_instagram_repository().set_insight_themes(user_id, themes)
    return build_account_insights(
        items,
        timezone_offset_minutes,
        account_context=get_account_context(user_id),
        themes=themes,
    )


@router.post("/insights/themes/regenerate")
def regenerate_insight_themes(user: AuthenticatedUser = Depends(require_user)):
    user_id = current_user(user)
    account = stored_connection(user_id)
    if account is None:
        raise HTTPException(status_code=409, detail={"code": "instagram_not_connected", "message": "Connect Instagram before regenerating themes."})
    items = []
    for item in tracked_payload(user_id, active_only=False):
        items.append({**item, "analyses": get_content_repository().analyses(user_id, item["tracking"].id)})
    themes = generate_account_themes(items)
    get_instagram_repository().set_insight_themes(user_id, themes)
    return {"themes": themes}


@router.post("/tracked-posts/{tracked_id}/analyses")
def analyze_tracking(tracked_id: str, user: AuthenticatedUser = Depends(require_user), use_account_context: bool = True):
    user_id = current_user(user)
    item = _tracked_item(user_id, tracked_id)
    media_item = item.get("media")
    if media_item is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "media_not_found", "message": "Instagram post was not found."},
        )
    snapshots = get_content_repository().snapshots([item["tracking"].media_id])
    if not snapshots:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "metrics_required",
                "message": "Refresh this post's metrics before running an analysis.",
            },
        )
    peer_metrics = []
    historical_posts = []
    for candidate in tracked_payload(user_id):
        candidate_latest = candidate.get("latest")
        candidate_media = candidate.get("media")
        if candidate_latest is None or candidate_media is None:
            continue
        candidate_metrics = {
            name: getattr(candidate_latest, name)
            for name in ("likes", "comments", "saves", "shares", "reach", "views", "engagement_rate")
        }
        historical_posts.append(
            {
                "tracked_post_id": candidate["tracking"].id,
                "caption": candidate_media.caption,
                "media_type": candidate_media.media_type,
                "published_at": candidate_media.published_at.isoformat(),
                "captured_at": candidate_latest.captured_at.isoformat(),
                "metrics": candidate_metrics,
            }
        )
        if candidate["tracking"].id != tracked_id:
            peer_metrics.append(
                {
                    "media_type": candidate_media.media_type,
                    "published_at": candidate_media.published_at.isoformat(),
                    "captured_at": candidate_latest.captured_at.isoformat(),
                    "metrics": candidate_metrics,
                }
            )
    try:
        computed = analyze_post(
            media_item,
            snapshots,
            peer_metrics=peer_metrics,
            historical_posts=historical_posts,
            account_context=get_account_context(user_id) if use_account_context else "",
        )
    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "analysis_not_configured", "message": str(exc)},
        ) from None
    except (GeminiUpstreamError, PostAnalysisError):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "analysis_failed",
                "message": "PostBridge could not analyze this post. Please try again.",
            },
        ) from None

    analysis = TrackedPostAnalysis(
        id=str(uuid4()),
        user_id=user_id,
        tracked_post_id=tracked_id,
        source_snapshot_id=computed.source_snapshot_ids[-1],
        source_snapshot_ids=computed.source_snapshot_ids,
        model_name=computed.model_name,
        schema_version=computed.schema_version,
        observed_metrics=computed.observed_metrics,
        metric_deltas=computed.metric_deltas,
        content_payload=computed.content_payload,
        output_payload=computed.output_payload,
        created_at=datetime.now(timezone.utc),
    )
    return get_content_repository().append_analysis(analysis)


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
    if _automatic_tracking_available():
        get_tracking_repository().cancel_tracking_jobs(tracked_id)
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
    try:
        metrics = fetch_instagram_media_insights(
            _access_token(account), media_item.instagram_media_id, media_item.media_type
        )
    except InstagramServiceError as exc:
        raise _handle_connected_service_error(account, exc) from exc
    snapshot = InstagramInsightSnapshot(
        id=str(uuid4()), media_id=media_item.id, captured_at=datetime.now(timezone.utc),
        likes=metrics.get("likes"), comments=metrics.get("comments"), saves=metrics.get("saves"),
        shares=metrics.get("shares"), reach=metrics.get("reach"), views=metrics.get("views"),
        engagement_rate=engagement_rate(metrics), raw_metrics=safe_raw_metrics(metrics),
        average_watch_time_ms=metrics.get("average_watch_time_ms"),
        total_watch_time_ms=metrics.get("total_watch_time_ms"),
        metric_status=dict(metrics.get("_metric_status") or {}),
        collection_type="manual_current", target_hour=None, scheduled_for=None,
    )
    get_content_repository().append_snapshot(snapshot)
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
