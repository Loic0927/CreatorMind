"""Login-triggered Instagram sync with account locking and safe partial failure."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.services.account_insights import build_account_insights
from backend.services.insight_texts import audience_description, next_post_suggestion, post_summary
from backend.services.instagram import (
    INSTAGRAM_SCOPES,
    InstagramServiceError,
    decrypt_access_token,
    engagement_rate,
    encrypt_access_token,
    fetch_instagram_comments,
    fetch_instagram_media,
    fetch_instagram_media_insights,
    instagram_comment_ingestion_enabled,
    refresh_long_lived_token,
    safe_raw_metrics,
    token_expiry,
)
from backend.storage.content_repository import get_content_repository
from backend.storage.instagram_repository import get_instagram_repository
from backend.storage.models import InstagramComment, InstagramInsightSnapshot, InstagramMedia


SESSION_SYNC_COOLDOWN = timedelta(minutes=30)
TOKEN_REFRESH_WINDOW = timedelta(days=7)
SYNC_BATCH_SIZE = 5
MAX_ATTEMPTS = 3
_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo:
        return value
    return value.replace(tzinfo=timezone.utc)


def _lock_for(account_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(account_id, threading.Lock())


def _timestamp(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def usable_token(account) -> str:
    repository = get_instagram_repository()
    encrypted = repository.get_encrypted_token(account.id)
    if not encrypted:
        raise InstagramServiceError("instagram_token_invalid", "Instagram authorization is no longer valid.", 401)
    token = decrypt_access_token(encrypted)
    expires_at = _aware(account.token_expires_at)
    if expires_at and expires_at <= datetime.now(timezone.utc) + TOKEN_REFRESH_WINDOW:
        payload = refresh_long_lived_token(token)
        token = payload["access_token"]
        repository.upsert_connection(account.model_copy(update={
            "token_expires_at": token_expiry(payload), "status": "connected", "last_error": None,
        }), encrypted_token=encrypt_access_token(token), scopes=list(account.scopes or INSTAGRAM_SCOPES))
    return token


def _retry(callable_):
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return callable_()
        except InstagramServiceError as exc:
            last_error = exc
            if exc.code not in {"instagram_rate_limited", "instagram_upstream_error"} or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(max(exc.retry_after_seconds or 0, 2 ** attempt))
    raise last_error  # pragma: no cover


def _same_metrics(previous, metrics: dict[str, Any]) -> bool:
    if previous is None:
        return False
    names = ("likes", "comments", "saves", "shares", "reach", "views", "average_watch_time_ms", "total_watch_time_ms")
    return all(getattr(previous, name) == metrics.get(name) for name in names)


def refresh_one_post(user_id: str, tracked, media, token: str, *, refresh_comments: bool = True) -> bool:
    repository = get_content_repository()
    metrics = _retry(lambda: fetch_instagram_media_insights(token, media.instagram_media_id, media.media_type))
    existing = repository.snapshots([media.id])
    latest = max(existing, key=lambda item: _aware(item.captured_at)) if existing else None
    changed = not _same_metrics(latest, metrics)
    if changed:
        repository.append_snapshot(InstagramInsightSnapshot(
            id=str(uuid4()), media_id=media.id, captured_at=datetime.now(timezone.utc),
            likes=metrics.get("likes"), comments=metrics.get("comments"), saves=metrics.get("saves"),
            shares=metrics.get("shares"), reach=metrics.get("reach"), views=metrics.get("views"),
            engagement_rate=engagement_rate(metrics), raw_metrics=safe_raw_metrics(metrics),
            average_watch_time_ms=metrics.get("average_watch_time_ms"),
            total_watch_time_ms=metrics.get("total_watch_time_ms"),
            metric_status=dict(metrics.get("_metric_status") or {}),
        ))

    account = get_instagram_repository().get_connection(user_id)
    if refresh_comments and account and instagram_comment_ingestion_enabled(user_id, account.instagram_user_id) and "instagram_business_manage_comments" in account.scopes:
        upstream = _retry(lambda: fetch_instagram_comments(token, media.instagram_media_id))
        now = datetime.now(timezone.utc)
        stored = []
        for value in upstream:
            provider_id = str(value.get("id") or "")
            text = str(value.get("text") or "").strip()[:2000]
            if not provider_id or not text:
                continue
            stored.append(InstagramComment(
                id=str(uuid4()), provider_id=provider_id, user_id=user_id, tracked_post_id=tracked.id,
                text=text, like_count=max(0, int(value.get("like_count") or 0)),
                timestamp=_timestamp(value.get("timestamp")),
                is_owner_reply=str((value.get("from") or {}).get("id") or "") == account.instagram_user_id,
                fetched_at=now,
            ))
        repository.upsert_comments(user_id, tracked.id, stored)

    snapshots = repository.snapshots([media.id])
    post_summary(user_id, tracked.id, snapshots)
    audience_description(user_id, tracked.id, repository.comments(user_id, tracked.id))
    return changed


def run_account_sync(user_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    current = _aware(now or datetime.now(timezone.utc))
    instagram_repository = get_instagram_repository()
    account = instagram_repository.get_connection(user_id)
    if not account or account.status != "connected":
        return {"status": "not_connected", "refreshed": 0, "failed": 0}
    last_success = _aware(account.session_synced_at)
    if last_success and current - last_success < SESSION_SYNC_COOLDOWN:
        return {"status": "skipped", "refreshed": 0, "failed": 0}
    lock = _lock_for(account.id)
    if not lock.acquire(blocking=False):
        return {"status": "already_running", "refreshed": 0, "failed": 0}
    try:
        token = usable_token(account)
        upstream = _retry(lambda: fetch_instagram_media(token))
        media = [InstagramMedia(
            id=f"instagram:{item['id']}", account_id=account.id, instagram_media_id=str(item["id"]),
            media_type=str(item.get("media_type", "UNKNOWN")), media_url=item.get("media_url"),
            thumbnail_url=item.get("thumbnail_url"), permalink=item.get("permalink"),
            caption=str(item.get("caption", "")), published_at=_timestamp(item.get("timestamp")), last_synced_at=current,
        ) for item in upstream if item.get("id")]
        content = get_content_repository()
        content.upsert_media(media)
        media_by_id = {item.id: item for item in media}
        for item in media:
            content.create_tracked(user_id, item.id)
        tracked = content.tracked(user_id, active_only=True)
        refreshed = failed = 0
        for index, tracked_post in enumerate(tracked):
            media_item = media_by_id.get(tracked_post.media_id)
            if media_item is None:
                stored = [item for item in content.media_for_account(account.id) if item.id == tracked_post.media_id]
                media_item = stored[0] if stored else None
            if media_item is None:
                failed += 1
                continue
            try:
                refresh_one_post(user_id, tracked_post, media_item, token)
                refreshed += 1
            except InstagramServiceError as exc:
                failed += 1
                if exc.code in {"instagram_token_invalid", "connection_expired"}:
                    instagram_repository.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
                    break
            if (index + 1) % SYNC_BATCH_SIZE == 0 and index + 1 < len(tracked):
                time.sleep(1)

        items = []
        stored_media = {item.id: item for item in content.media_for_account(account.id)}
        for tracked_post in content.tracked(user_id, active_only=False):
            snapshots = content.snapshots([tracked_post.media_id])
            items.append({"tracking": tracked_post, "media": stored_media.get(tracked_post.media_id),
                          "latest": max(snapshots, key=lambda value: _aware(value.captured_at)) if snapshots else None,
                          "snapshots": snapshots})
        post_payload = build_account_insights(items)["performance_posts"]
        internal_posts = []
        for post in post_payload:
            source = next((item for item in items if item["tracking"].id == post["tracked_post_id"]), None)
            internal_posts.append({**post, "caption": source["media"].caption if source and source.get("media") else ""})
        next_post_suggestion(user_id, internal_posts, {item["tracking"].id: content.comments(user_id, item["tracking"].id) for item in items})

        if failed:
            instagram_repository.mark_session_sync(user_id, None, "partial_failure")
            return {"status": "partial_failure", "refreshed": refreshed, "failed": failed}
        instagram_repository.mark_session_sync(user_id, current, None)
        return {"status": "complete", "refreshed": refreshed, "failed": 0}
    except InstagramServiceError as exc:
        if exc.code in {"instagram_token_invalid", "connection_expired"}:
            instagram_repository.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
            instagram_repository.mark_session_sync(user_id, None, "reconnect_required")
            return {"status": "reconnect_required", "refreshed": 0, "failed": 1}
        instagram_repository.mark_session_sync(user_id, None, "update_failed")
        return {"status": "failed", "refreshed": 0, "failed": 1}
    finally:
        lock.release()


def request_account_sync(user_id: str) -> dict[str, Any]:
    """BackgroundTasks entry point; kept separate for direct tests."""
    return run_account_sync(user_id)
