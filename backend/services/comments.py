"""Privacy-safe states for the wireframe audience-comments card."""

from __future__ import annotations

from typing import Any

from backend.storage.models import InstagramComment

MIN_AUDIENCE_COMMENTS = 3
MAX_AUDIENCE_COMMENT_ITEMS = 20


def _audience_comment_items(comments: list[InstagramComment]) -> list[dict[str, Any]]:
    """Return the privacy-safe recent-comment payload exposed to clients."""
    audience = [item for item in comments if not item.is_owner_reply and item.text.strip()]
    audience.sort(key=lambda item: item.timestamp, reverse=True)
    return [
        {
            "text": item.text,
            "like_count": item.like_count,
            "timestamp": item.timestamp,
        }
        for item in audience[:MAX_AUDIENCE_COMMENT_ITEMS]
    ]


def audience_comment_state(
    comments: list[InstagramComment],
    *,
    feature_enabled: bool,
    permission_granted: bool,
    description: str | None = None,
    consent_required: bool = False,
    error: bool = False,
) -> dict[str, Any]:
    if not feature_enabled:
        return {"state": "feature_off", "message": "Audience comments are not available yet."}
    if not permission_granted:
        return {"state": "reconnect_needed", "message": "Reconnect Instagram to read audience comments."}
    items = _audience_comment_items(comments)
    if consent_required:
        return {
            "state": "consent_required",
            "message": "AI processing consent is required to summarize comments.",
            "items": items,
        }
    if error:
        return {"state": "error", "message": "Couldn't read comments.", "items": items}
    if len(items) < MIN_AUDIENCE_COMMENTS:
        return {"state": "too_few", "message": "Not enough comments yet", "items": items}
    if not description:
        return {"state": "error", "message": "Couldn't summarize comments.", "items": items}
    return {"state": "ready", "description": description, "items": items}
