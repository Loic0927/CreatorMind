"""Authenticated TikTok connection and publishing-support endpoints."""

import os
from datetime import UTC, datetime, timedelta
from threading import Lock
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedUser, require_user
from backend.services.tiktok import (
    TikTokServiceError,
    build_authorization_url,
    consume_oauth_state,
    create_oauth_state,
    decrypt_token,
    encrypt_token,
    exchange_authorization_code,
    fetch_creator_info,
    fetch_publish_status,
    fetch_user_info,
    fetch_user_videos,
    fetch_videos_by_ids,
    granted_scopes,
    refresh_access_token,
    revoke_access_token,
    tiktok_configured,
    token_expiry,
    verify_media_token,
)
from backend.storage.models import TikTokConnection
from backend.storage.oci_object_storage import OCIStorageConfigurationError, download_private_bytes
from backend.storage.tiktok_repository import TikTokRepositoryError, get_tiktok_repository

router = APIRouter(prefix="/api/tiktok", tags=["tiktok"])
_TOKEN_REFRESH_LOCK = Lock()


class TikTokStatusRequest(BaseModel):
    publish_id: str = Field(..., min_length=4, max_length=255)


class TikTokTrackRequest(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=255)


def _service_error(exc: TikTokServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})


def _repository_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "tiktok_storage_unavailable", "message": "TikTok connection storage is unavailable."},
    )


_TIKTOK_ANALYSIS_METRICS = ("views", "likes", "engagement_rate", "shares", "comments")


def _tiktok_analysis(selected: dict, items: list[dict]) -> dict:
    peers = [item for item in items if item["id"] != selected["id"]]
    ranges = []
    for metric in _TIKTOK_ANALYSIS_METRICS:
        value = selected.get(metric)
        peer_values = [float(item[metric]) for item in peers if item.get(metric) is not None]
        if value is None or len(peer_values) < 2:
            continue
        low, high = min(peer_values), max(peer_values)
        numeric = float(value)
        status = "above" if numeric > high else "below" if numeric < low else "inside"
        all_values = [numeric, *peer_values]
        ranked = sorted(all_values, reverse=True)
        total_min, total_max = min(all_values), max(all_values)
        marker = 50.0 if total_min == total_max else (numeric - total_min) / (total_max - total_min) * 100
        band_start = 50.0 if total_min == total_max else (low - total_min) / (total_max - total_min) * 100
        band_end = 50.0 if total_min == total_max else (high - total_min) / (total_max - total_min) * 100
        ranges.append(
            {
                "metric": metric,
                "value": numeric,
                "usual_min": low,
                "usual_max": high,
                "status": status,
                "rank": ranked.index(numeric) + 1,
                "group_size": len(all_values),
                "band_start": max(0.0, min(100.0, band_start)),
                "band_end": max(0.0, min(100.0, band_end)),
                "marker": max(0.0, min(100.0, marker)),
            }
        )
    views = selected.get("views")
    likes = selected.get("likes")
    engagement = selected.get("engagement_rate")
    summary = (
        f"This TikTok has {views:,} views and {likes:,} likes with a {engagement:.1f}% engagement rate."
        if views is not None and likes is not None and engagement is not None
        else "TikTok public performance data is still being collected for this post."
    )
    view_range = next((row for row in ranges if row["metric"] == "views"), None)
    if view_range:
        comparison = {"above": "above", "below": "below", "inside": "within"}[view_range["status"]]
        summary += f" Its views are {comparison} the usual range across your other tracked TikTok posts."
    published_at = selected.get("published_at")
    published = published_at if isinstance(published_at, datetime) else None
    if published and published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return {
        "comparable": bool(ranges),
        "comparable_count": len(peers),
        "summary": summary,
        "stands_out": [row for row in ranges if row["status"] == "above"],
        "weaker": [row for row in ranges if row["status"] == "below"],
        "usual_ranges": ranges,
        "age_days": max(0, (datetime.now(UTC) - published).days) if published else 0,
        "media_format": "Video",
        "audience_comments": {
            "state": "unavailable",
            "message": "TikTok Display API provides the public comment count, but not comment text.",
        },
    }


def stored_connection(user_id: str) -> TikTokConnection | None:
    try:
        return get_tiktok_repository().get_connection(user_id)
    except TikTokRepositoryError:
        raise _repository_error() from None


def public_connection(connection: TikTokConnection | None) -> dict:
    if connection is None:
        return {"connected": False, "configured": tiktok_configured(), "status": "not_connected"}
    return {
        "connected": connection.status == "connected",
        "configured": tiktok_configured(),
        "status": connection.status,
        "display_name": connection.display_name,
        "avatar_url": connection.avatar_url,
        "scopes": connection.scopes,
        "updated_at": connection.updated_at,
    }


def active_connection(user_id: str) -> TikTokConnection:
    connection = stored_connection(user_id)
    if connection is None or connection.status == "disconnected":
        raise HTTPException(
            status_code=404,
            detail={"code": "tiktok_not_connected", "message": "TikTok is not connected."},
        )
    if connection.status != "connected":
        raise HTTPException(
            status_code=401,
            detail={"code": "tiktok_reconnect_required", "message": "TikTok must be reconnected."},
        )
    return connection


def access_token_for(connection: TikTokConnection) -> str:
    repository = get_tiktok_repository()
    try:
        tokens = repository.get_encrypted_tokens(connection.id)
    except TikTokRepositoryError:
        raise _repository_error() from None
    if not tokens or not all(tokens):
        raise HTTPException(
            status_code=401,
            detail={"code": "tiktok_reconnect_required", "message": "TikTok must be reconnected."},
        )
    now = datetime.now(UTC)
    if connection.access_token_expires_at is None or connection.access_token_expires_at > now + timedelta(minutes=15):
        try:
            return decrypt_token(tokens[0])
        except TikTokServiceError as exc:
            raise _service_error(exc) from None

    with _TOKEN_REFRESH_LOCK:
        refreshed_connection = stored_connection(connection.user_id)
        if (
            refreshed_connection
            and refreshed_connection.access_token_expires_at
            and refreshed_connection.access_token_expires_at > datetime.now(UTC) + timedelta(minutes=15)
        ):
            try:
                refreshed_tokens = repository.get_encrypted_tokens(refreshed_connection.id)
                if refreshed_tokens:
                    return decrypt_token(refreshed_tokens[0])
            except TikTokServiceError as exc:
                raise _service_error(exc) from None
            except TikTokRepositoryError:
                raise _repository_error() from None
        try:
            refresh_token = decrypt_token(tokens[1])
            payload = refresh_access_token(refresh_token)
            access_token = str(payload["access_token"])
            rotated_refresh_token = str(payload["refresh_token"])
            repository.update_tokens(
                connection.user_id,
                encrypted_access_token=encrypt_token(access_token),
                encrypted_refresh_token=encrypt_token(rotated_refresh_token),
                access_token_expires_at=token_expiry(payload, "expires_in"),
                refresh_token_expires_at=token_expiry(payload, "refresh_expires_in"),
                scopes=granted_scopes(payload) or connection.scopes,
            )
            return access_token
        except TikTokServiceError as exc:
            if exc.code in {"tiktok_token_invalid", "tiktok_token_refresh_failed"}:
                try:
                    repository.mark_reconnect_required(connection.user_id)
                except TikTokRepositoryError:
                    pass
            raise _service_error(exc) from None
        except TikTokRepositoryError:
            raise _repository_error() from None


def _frontend_redirect(status: str, code: str | None = None) -> RedirectResponse:
    base = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    query = {"tab": "settings", "tiktok": status}
    if code:
        query["code"] = code
    return RedirectResponse(f"{base}/dashboard?{urlencode(query)}", status_code=302)


@router.get("/connection")
def connection(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return public_connection(stored_connection(user.id))


@router.post("/connect/start")
def connect_start(
    client: str = Query(default="web"),
    user: AuthenticatedUser = Depends(require_user),
) -> dict:
    try:
        return {"authorization_url": build_authorization_url(create_oauth_state(user.id, client=client))}
    except TikTokServiceError as exc:
        raise _service_error(exc) from None


@router.get("/connect/callback")
def connect_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    del error_description
    try:
        user_id, _client = consume_oauth_state(state or "")
        if error or not code:
            return _frontend_redirect("error", "tiktok_authorization_denied" if error else "invalid_oauth_callback")
        token_payload = exchange_authorization_code(code)
        access_token = str(token_payload["access_token"])
        refresh_token = str(token_payload["refresh_token"])
        profile = fetch_user_info(access_token)
        open_id = str(token_payload["open_id"])
        if str(profile.get("open_id")) != open_id:
            raise TikTokServiceError("tiktok_profile_mismatch", "TikTok profile verification failed.", 502)
        now = datetime.now(UTC)
        existing = stored_connection(user_id)
        connection_value = TikTokConnection(
            id=existing.id if existing else str(uuid4()),
            user_id=user_id,
            open_id=open_id,
            union_id=str(profile["union_id"]) if profile.get("union_id") else None,
            display_name=str(profile["display_name"]),
            avatar_url=str(profile["avatar_url"]) if profile.get("avatar_url") else None,
            access_token_expires_at=token_expiry(token_payload, "expires_in"),
            refresh_token_expires_at=token_expiry(token_payload, "refresh_expires_in"),
            scopes=granted_scopes(token_payload),
            status="connected",
            connected_at=existing.connected_at if existing else now,
            updated_at=now,
        )
        get_tiktok_repository().upsert_connection(
            connection_value,
            encrypted_access_token=encrypt_token(access_token),
            encrypted_refresh_token=encrypt_token(refresh_token),
        )
        return _frontend_redirect("connected")
    except TikTokServiceError as exc:
        return _frontend_redirect("error", exc.code)
    except TikTokRepositoryError:
        return _frontend_redirect("error", "tiktok_storage_unavailable")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return _frontend_redirect("error", str(detail.get("code", "tiktok_connection_failed")))


@router.delete("/connection")
def disconnect(user: AuthenticatedUser = Depends(require_user)) -> dict:
    connection_value = stored_connection(user.id)
    if connection_value and connection_value.status == "connected":
        try:
            revoke_access_token(access_token_for(connection_value))
        except (HTTPException, TikTokServiceError):
            # Local disconnection must remain available when TikTok is temporarily
            # unavailable or the provider token has already expired.
            pass
    try:
        return {"disconnected": get_tiktok_repository().disconnect(user.id)}
    except TikTokRepositoryError:
        raise _repository_error() from None


@router.get("/creator-info")
def creator_info(user: AuthenticatedUser = Depends(require_user)) -> dict:
    connection_value = active_connection(user.id)
    try:
        return fetch_creator_info(access_token_for(connection_value))
    except TikTokServiceError as exc:
        raise _service_error(exc) from None


@router.get("/media")
def media(user: AuthenticatedUser = Depends(require_user)) -> dict:
    """List recent public videos for the authenticated creator."""
    connection_value = active_connection(user.id)
    try:
        videos = fetch_user_videos(access_token_for(connection_value))
    except TikTokServiceError as exc:
        raise _service_error(exc) from None
    return {
        "items": [
            {
                "id": str(item["id"]),
                "caption": str(item.get("video_description") or item.get("title") or "TikTok post"),
                "thumbnail_url": item.get("cover_image_url"),
                "permalink": item.get("share_url"),
                "published_at": item.get("create_time"),
                "likes": item.get("like_count"),
                "comments": item.get("comment_count"),
                "shares": item.get("share_count"),
                "views": item.get("view_count"),
            }
            for item in videos
            if item.get("id")
        ]
    }


@router.get("/tracked")
def tracked_posts(user: AuthenticatedUser = Depends(require_user)) -> dict:
    try:
        repository = get_tiktok_repository()
        items = repository.tracked_posts(user.id)
    except TikTokRepositoryError:
        raise _repository_error() from None
    connection_value = stored_connection(user.id)
    stale = [
        item
        for item in items
        if item.get("metrics_updated_at") is None
        or datetime.now(UTC) - item["metrics_updated_at"] > timedelta(minutes=15)
    ]
    if stale and connection_value and connection_value.status == "connected":
        try:
            videos = fetch_videos_by_ids(
                access_token_for(connection_value),
                [item["video_id"] for item in stale],
            )
            by_id = {str(item.get("id")): item for item in videos if item.get("id")}
            for item in stale:
                video = by_id.get(item["video_id"])
                if video:
                    repository.refresh_tracked_post(user.id, item["id"], video)
            items = repository.tracked_posts(user.id)
        except (TikTokServiceError, TikTokRepositoryError, HTTPException):
            # Serve the last stored values when TikTok is temporarily unavailable.
            pass
    return {"items": items}


@router.post("/tracked")
def track_post(payload: TikTokTrackRequest, user: AuthenticatedUser = Depends(require_user)) -> dict:
    connection_value = active_connection(user.id)
    try:
        videos = fetch_user_videos(access_token_for(connection_value))
        video = next((item for item in videos if str(item.get("id")) == payload.video_id), None)
        if video is None:
            raise HTTPException(
                status_code=404, detail={"code": "tiktok_video_not_found", "message": "TikTok post was not found."}
            )
        return get_tiktok_repository().track_post(user.id, video)
    except TikTokServiceError as exc:
        raise _service_error(exc) from None
    except TikTokRepositoryError:
        raise _repository_error() from None


@router.get("/tracked/{tracked_id}")
def tracked_post(tracked_id: str, user: AuthenticatedUser = Depends(require_user)) -> dict:
    try:
        repository = get_tiktok_repository()
        post = repository.get_tracked_post(user.id, tracked_id)
    except TikTokRepositoryError:
        raise _repository_error() from None
    if post is None:
        raise HTTPException(
            status_code=404, detail={"code": "tiktok_tracked_post_not_found", "message": "TikTok post was not found."}
        )
    try:
        items = repository.tracked_posts(user.id)
    except TikTokRepositoryError:
        raise _repository_error() from None
    return {**post, "analysis": _tiktok_analysis(post, items)}


@router.post("/tracked/{tracked_id}/refresh")
def refresh_tracked_post(tracked_id: str, user: AuthenticatedUser = Depends(require_user)) -> dict:
    connection_value = active_connection(user.id)
    repository = get_tiktok_repository()
    try:
        stored = repository.get_tracked_post(user.id, tracked_id)
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "tiktok_tracked_post_not_found", "message": "TikTok post was not found."},
            )
        videos = fetch_videos_by_ids(access_token_for(connection_value), [stored["video_id"]])
        if not videos:
            raise HTTPException(
                status_code=404,
                detail={"code": "tiktok_video_not_found", "message": "TikTok post was not found."},
            )
        refreshed = repository.refresh_tracked_post(user.id, tracked_id, videos[0])
        if refreshed is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "tiktok_tracked_post_not_found", "message": "TikTok post was not found."},
            )
        items = repository.tracked_posts(user.id)
        return {**refreshed, "analysis": _tiktok_analysis(refreshed, items)}
    except TikTokServiceError as exc:
        raise _service_error(exc) from None
    except TikTokRepositoryError:
        raise _repository_error() from None


@router.delete("/tracked/{tracked_id}")
def delete_tracked_post(tracked_id: str, user: AuthenticatedUser = Depends(require_user)) -> dict:
    try:
        deleted = get_tiktok_repository().delete_tracked_post(user.id, tracked_id)
    except TikTokRepositoryError:
        raise _repository_error() from None
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "tiktok_tracked_post_not_found", "message": "TikTok post was not found."},
        )
    return {"stopped": True}


@router.post("/publishing/status")
def publishing_status(payload: TikTokStatusRequest, user: AuthenticatedUser = Depends(require_user)) -> dict:
    connection_value = active_connection(user.id)
    try:
        data = fetch_publish_status(access_token_for(connection_value), payload.publish_id)
    except TikTokServiceError as exc:
        raise _service_error(exc) from None
    provider_status = str(data.get("status", ""))
    normalized = (
        "published"
        if provider_status == "PUBLISH_COMPLETE"
        else "failed"
        if provider_status == "FAILED"
        else "publishing"
    )
    return {
        "publish_id": payload.publish_id,
        "status": normalized,
        "provider_status": provider_status,
        "post_ids": data.get("publicaly_available_post_id") or [],
        "fail_reason": data.get("fail_reason") if normalized == "failed" else None,
    }


@router.get("/media/{token}", include_in_schema=False)
def provider_media(token: str) -> Response:
    try:
        object_name, mime_type = verify_media_token(token)
        body = download_private_bytes(object_name)
    except TikTokServiceError as exc:
        raise _service_error(exc) from None
    except OCIStorageConfigurationError:
        raise HTTPException(status_code=503, detail="TikTok media storage is unavailable.") from None
    except Exception:
        raise HTTPException(status_code=404, detail="TikTok media was not found.") from None
    return Response(
        content=body,
        media_type=mime_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
