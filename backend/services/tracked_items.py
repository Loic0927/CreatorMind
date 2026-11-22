"""Bulk loaders for a user's tracked Instagram posts.

The dashboard reads several views of the same tracked-post collection.  Keeping
the loading here makes it much harder for an otherwise innocent API change to
reintroduce one snapshots/comments query per post.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from backend.storage.content_repository import ContentRepository, get_content_repository


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def load_tracked_items(
    user_id: str,
    *,
    account: Any | None = None,
    active_only: bool = True,
    include_comments: bool = False,
    repository: ContentRepository | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[Any]]]:
    """Load tracked posts, snapshots, and optionally comments in bulk.

    ``account`` is deliberately an argument rather than being fetched here so
    callers that already authenticated the connection do not need another
    storage lookup.  The returned item shape is shared with the analysis and
    summary services.
    """

    content = repository or get_content_repository()
    tracked = content.tracked(user_id, active_only=active_only)
    media_ids = list(dict.fromkeys(item.media_id for item in tracked))
    media_by_id: dict[str, Any] = {}
    if account is not None:
        media_by_id = {item.id: item for item in content.media_for_account(account.id)}

    snapshots_by_media: dict[str, list[Any]] = defaultdict(list)
    for snapshot in content.snapshots(media_ids):
        snapshots_by_media[snapshot.media_id].append(snapshot)
    for snapshots in snapshots_by_media.values():
        snapshots.sort(key=lambda item: _aware(item.captured_at))

    comments_by_tracked: dict[str, list[Any]] = defaultdict(list)
    if include_comments:
        for comment in content.comments(user_id, None):
            comments_by_tracked[comment.tracked_post_id].append(comment)

    items = []
    for tracking in tracked:
        snapshots = snapshots_by_media.get(tracking.media_id, [])
        items.append(
            {
                "tracking": tracking,
                "media": media_by_id.get(tracking.media_id),
                "latest": snapshots[-1] if snapshots else None,
                "snapshots": snapshots,
            }
        )
    return items, dict(comments_by_tracked)
