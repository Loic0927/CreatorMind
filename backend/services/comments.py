"""Privacy-safe states for the wireframe audience-comments card."""

from __future__ import annotations

from typing import Any

from backend.storage.models import InstagramComment


MIN_AUDIENCE_COMMENTS = 3


def audience_comment_state(
    comments: list[InstagramComment],
    *,
    feature_enabled: bool,
    permission_granted: bool,
    description: str | None = None,
    error: bool = False,
) -> dict[str, Any]:
    if not feature_enabled:
        return {"state": "feature_off", "message": "Audience comments are not available yet."}
    if not permission_granted:
        return {"state": "reconnect_needed", "message": "Reconnect Instagram to read audience comments."}
    if error:
        return {"state": "error", "message": "Couldn't read comments."}
    audience = [item for item in comments if not item.is_owner_reply and item.text.strip()]
    if len(audience) < MIN_AUDIENCE_COMMENTS:
        return {"state": "too_few", "message": "Not enough comments yet"}
    if not description:
        return {"state": "error", "message": "Couldn't summarize comments."}
    return {"state": "ready", "description": description}
