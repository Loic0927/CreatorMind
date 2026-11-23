"""Background cache generation for tracking insights.

This module is intentionally called only by background/manual collection
workflows.  Read endpoints consume the resulting caches and never invoke a
model or download media.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.auth import get_account_context
from backend.services.account_insights import build_account_insights
from backend.services.feedback import refresh_summary_for_user
from backend.services.insight_texts import audience_description, next_post_suggestion
from backend.services.instagram import instagram_comment_ingestion_enabled
from backend.services.tracked_items import load_tracked_items
from backend.storage.instagram_repository import get_instagram_repository

LOGGER = logging.getLogger("postbridge.insight_refresh")


def _internal_posts(items: list[dict[str, Any]], performance_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tracking_id = {item["tracking"].id: item for item in items}
    result = []
    for post in performance_posts:
        source = by_tracking_id.get(post["tracked_post_id"], {})
        media = source.get("media")
        latest = source.get("latest")
        snapshots = list(source.get("snapshots") or [])
        if latest is not None and not any(snapshot is latest for snapshot in snapshots):
            snapshots.append(latest)

        def snapshot_metrics(snapshot: Any) -> dict[str, Any]:
            return {
                "reach": getattr(snapshot, "reach", None),
                "views": getattr(snapshot, "views", None),
                "saves": getattr(snapshot, "saves", None),
                "shares": getattr(snapshot, "shares", None),
                "comments": getattr(snapshot, "comments", None),
                "average_watch_time_ms": getattr(snapshot, "average_watch_time_ms", None),
            }

        # Watch time is generator-only context: exposing it in the account
        # response would require a separate public contract change. The
        # private history lets the Reflection make a same-age comparison when
        # the newest post is still young, without changing that public shape.
        metrics = {
            **(post.get("metrics") or {}),
            "average_watch_time_ms": getattr(latest, "average_watch_time_ms", None),
        }
        result.append(
            {
                **post,
                "metrics": metrics,
                "caption": str(media.caption) if media else "",
                "latest_captured_at": getattr(latest, "captured_at", None),
                "history": [
                    {"captured_at": getattr(snapshot, "captured_at", None), "metrics": snapshot_metrics(snapshot)}
                    for snapshot in snapshots
                ],
            }
        )
    return result


def refresh_cached_insights(user_id: str, tracked_post_id: str | None = None) -> None:
    """Refresh generated text after a write-side collection event.

    Individual failures are isolated so a transient model/configuration issue
    cannot turn a completed metric capture into a failed tracking operation.
    """

    account = get_instagram_repository().get_connection(user_id)
    if account is None:
        return
    items, comments_by_tracking = load_tracked_items(user_id, account=account, active_only=False, include_comments=True)
    if not items:
        return

    comments_enabled = instagram_comment_ingestion_enabled(user_id, account.instagram_user_id)
    comments_permitted = comments_enabled and "instagram_business_manage_comments" in account.scopes
    if comments_permitted:
        for item in items:
            tracking_id = item["tracking"].id
            if tracked_post_id and tracking_id != tracked_post_id:
                continue
            try:
                audience_description(user_id, tracking_id, comments_by_tracking.get(tracking_id, []))
            except Exception as exc:  # pragma: no cover - provider-specific logging path
                LOGGER.warning(
                    "audience_refresh_failed user_id=%s tracked_post_id=%s error_type=%s",
                    user_id,
                    tracking_id,
                    type(exc).__name__,
                )

    try:
        account_insights = build_account_insights(items)
        next_post_suggestion(
            user_id,
            _internal_posts(items, account_insights["performance_posts"]),
            comments_by_tracking,
            account_context=get_account_context(user_id),
        )
    except Exception as exc:  # pragma: no cover - provider-specific logging path
        LOGGER.warning("suggestion_refresh_failed user_id=%s error_type=%s", user_id, type(exc).__name__)

    try:
        refresh_summary_for_user(user_id, tracked_post_id)
    except Exception as exc:  # pragma: no cover - provider-specific logging path
        LOGGER.warning(
            "summary_refresh_failed user_id=%s tracked_post_id=%s error_type=%s",
            user_id,
            tracked_post_id,
            type(exc).__name__,
        )
