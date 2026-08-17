from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from backend.services.instagram import (
    InstagramServiceError,
    aggregate_seven_days,
    build_authorization_url,
    consume_oauth_state,
    create_oauth_state,
    decrypt_access_token,
    encrypt_access_token,
    exchange_authorization_code,
    exchange_long_lived_token,
    fetch_instagram_media,
    fetch_instagram_profile,
    instagram_configured,
    token_expiry,
)
from backend.storage.json_store import (
    create_tracked_post,
    get_instagram_account,
    get_instagram_media as get_stored_instagram_media,
    get_tracked_posts,
    load_store,
    stop_tracked_post,
    update_store,
    upsert_instagram_account,
    upsert_instagram_media,
)
from backend.storage.models import InstagramAccount, InstagramMedia
from backend.storage.token_store import (
    delete_encrypted_token,
    get_encrypted_token,
    save_encrypted_token,
)


router = APIRouter()


def current_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    value = x_user_id.strip()
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
    account = get_instagram_account(user_id)
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
    encrypted_token = get_encrypted_token(account.id)
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


@router.get("/api/instagram/connection")
@router.get("/instagram/connection", include_in_schema=False)
def connection(user_id: str = Header(..., alias="X-User-Id")):
    return public_account(get_instagram_account(current_user(user_id)))


@router.post("/api/instagram/connect/start")
@router.post("/instagram/connect/start", include_in_schema=False)
def connect_start(user_id: str = Header(..., alias="X-User-Id")):
    user_id = current_user(user_id)
    try:
        return {"authorization_url": build_authorization_url(create_oauth_state(user_id))}
    except InstagramServiceError as exc:
        raise service_error(exc) from exc


@router.get("/api/instagram/connect/callback")
@router.get("/instagram/connect/callback", include_in_schema=False)
def connect_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "instagram_authorization_denied",
                "message": "Instagram authorization was not completed.",
            },
        )
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_oauth_callback",
                "message": "Instagram callback is missing required parameters.",
            },
        )
    try:
        user_id = consume_oauth_state(state)
        short_payload = exchange_authorization_code(code)
        long_payload = exchange_long_lived_token(short_payload["access_token"])
        access_token = long_payload["access_token"]
        profile = fetch_instagram_profile(access_token)
        existing = get_instagram_account(user_id)
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
            status="connected",
            connected_at=existing.connected_at if existing else now,
            last_synced_at=now,
            last_error=None,
        )
        save_encrypted_token(account.id, encrypted_token)
        try:
            upsert_instagram_account(account)
        except Exception:
            delete_encrypted_token(account.id)
            raise
        return {"connected": True, "account": public_account(account)}
    except InstagramServiceError as exc:
        raise service_error(exc) from exc


@router.get("/api/instagram/account")
def account(user_id: str = Header(..., alias="X-User-Id")):
    user_id = current_user(user_id)
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
        upsert_instagram_account(updated)
        return public_account(updated)
    except InstagramServiceError as exc:
        raise service_error(exc) from exc


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


@router.get("/api/instagram/media")
@router.get("/instagram/media", include_in_schema=False)
def media(user_id: str = Header(..., alias="X-User-Id")):
    account = _active_account(current_user(user_id))
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
        raise service_error(exc) from exc


def _disconnect(user_id: str) -> dict:
    existing = get_instagram_account(user_id)
    def mutate(store):
        account = next(
            (item for item in store.instagram_accounts if item.user_id == user_id),
            None,
        )
        if not account:
            return False
        account.status = "disconnected"
        account.encrypted_access_token = ""
        account.last_error = None
        for tracked in store.tracked_posts:
            if tracked.user_id == user_id and tracked.is_active:
                tracked.is_active = False
                tracked.stopped_at = datetime.now(timezone.utc)
        return True

    disconnected = update_store(mutate)
    if existing:
        delete_encrypted_token(existing.id)
    return {"disconnected": disconnected}


@router.delete("/api/instagram/connection")
def delete_connection(user_id: str = Header(..., alias="X-User-Id")):
    return _disconnect(current_user(user_id))


@router.post("/instagram/disconnect", include_in_schema=False)
def legacy_disconnect(user_id: str = Header(..., alias="X-User-Id")):
    return _disconnect(current_user(user_id))


class TrackRequest(BaseModel):
    media_id: str


@router.post("/tracked-posts")
def track(payload: TrackRequest, user_id: str = Header(..., alias="X-User-Id")):
    user_id = current_user(user_id)
    account = get_instagram_account(user_id)
    owned_ids = (
        {item.id for item in get_stored_instagram_media(account.id)} if account else set()
    )
    if payload.media_id not in owned_ids:
        raise HTTPException(
            status_code=404,
            detail={"code": "media_not_found", "message": "Instagram post was not found."},
        )
    return create_tracked_post(user_id, payload.media_id)


def tracked_payload(user_id: str):
    store = load_store()
    media_by_id = {item.id: item for item in store.instagram_media}
    snapshots_by_media = {}
    for item in store.instagram_insight_snapshots:
        if (
            item.media_id not in snapshots_by_media
            or item.captured_at > snapshots_by_media[item.media_id].captured_at
        ):
            snapshots_by_media[item.media_id] = item
    return [
        {
            "tracking": tracked,
            "media": media_by_id.get(tracked.media_id),
            "latest": snapshots_by_media.get(tracked.media_id),
        }
        for tracked in get_tracked_posts(user_id)
    ]


@router.get("/tracked-posts")
def tracked_posts(user_id: str = Header(..., alias="X-User-Id")):
    return {"items": tracked_payload(current_user(user_id))}


@router.get("/tracked-posts/{tracked_id}")
def tracked_detail(tracked_id: str, user_id: str = Header(..., alias="X-User-Id")):
    user_id = current_user(user_id)
    item = next(
        (
            item
            for item in tracked_payload(user_id)
            if item["tracking"].id == tracked_id
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
    store = load_store()
    item["snapshots"] = [
        snapshot
        for snapshot in store.instagram_insight_snapshots
        if snapshot.media_id == item["tracking"].media_id
    ]
    return item


@router.delete("/tracked-posts/{tracked_id}")
def stop_tracking(tracked_id: str, user_id: str = Header(..., alias="X-User-Id")):
    if not stop_tracked_post(current_user(user_id), tracked_id):
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
    tracked_id: str, user_id: str = Header(..., alias="X-User-Id")
):
    user_id = current_user(user_id)
    if not any(
        item["tracking"].id == tracked_id for item in tracked_payload(user_id)
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tracked_post_not_found",
                "message": "Tracked post was not found.",
            },
        )
    raise HTTPException(
        status_code=503,
        detail={
            "code": "instagram_insights_not_implemented",
            "message": "Live Instagram Insights refresh is not implemented yet.",
        },
    )


@router.get("/insights/instagram")
def insights(
    period: str = Query("7d"), user_id: str = Header(..., alias="X-User-Id")
):
    user_id = current_user(user_id)
    if period != "7d":
        raise HTTPException(
            status_code=400,
            detail={"code": "unsupported_period", "message": "Only 7d is supported."},
        )
    account = get_instagram_account(user_id)
    if not account:
        return {"status": "not_connected", "period": "7d"}
    if account.status != "connected":
        return {"status": account.status, "period": "7d"}
    store = load_store()
    stored_media = [
        item for item in store.instagram_media if item.account_id == account.id
    ]
    result = aggregate_seven_days(stored_media, store.instagram_insight_snapshots)
    result["status"] = "connected"
    result["top_posts"] = []
    result["trend"] = []
    return result
