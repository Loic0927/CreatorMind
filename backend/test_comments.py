from datetime import UTC, datetime, timedelta

from backend.services.comments import audience_comment_state
from backend.storage.models import InstagramComment


def comment(index, text="hello", owner=False, *, timestamp=None, like_count=0):
    value = timestamp or datetime.now(UTC)
    return InstagramComment(
        id=str(index),
        provider_id=f"p{index}",
        user_id="u",
        tracked_post_id="t",
        text=text,
        like_count=like_count,
        timestamp=value,
        is_owner_reply=owner,
        fetched_at=value,
    )


def test_audience_comment_states_are_explicit_and_too_few_has_exact_copy():
    assert audience_comment_state([], feature_enabled=False, permission_granted=False)["state"] == "feature_off"
    assert audience_comment_state([], feature_enabled=True, permission_granted=False)["state"] == "reconnect_needed"
    assert audience_comment_state([], feature_enabled=True, permission_granted=True, error=True)["state"] == "error"
    assert (
        audience_comment_state([comment(1), comment(2)], feature_enabled=True, permission_granted=True)["message"]
        == "Not enough comments yet"
    )
    comments = [comment(1), comment(2), comment(3)]
    ready = audience_comment_state(
        comments,
        feature_enabled=True,
        permission_granted=True,
        description="Viewers compared the examples.",
    )
    assert ready == {
        "state": "ready",
        "description": "Viewers compared the examples.",
        "items": [
            {"text": item.text, "like_count": item.like_count, "timestamp": item.timestamp}
            for item in sorted(comments, key=lambda item: item.timestamp, reverse=True)
        ],
    }


def test_audience_items_are_recent_bounded_and_never_expose_comment_identifiers():
    now = datetime(2026, 11, 22, tzinfo=UTC)
    comments = [
        comment(index, f"Comment {index}", timestamp=now + timedelta(seconds=index), like_count=index)
        for index in range(25)
    ]
    comments.extend(
        [
            comment(30, "Owner reply", owner=True, timestamp=now + timedelta(seconds=30)),
            comment(31, "   ", timestamp=now + timedelta(seconds=31)),
        ]
    )

    state = audience_comment_state(
        comments,
        feature_enabled=True,
        permission_granted=True,
        description="Viewers compared the examples.",
    )

    assert state["state"] == "ready"
    assert len(state["items"]) == 20
    assert [item["text"] for item in state["items"]] == [f"Comment {index}" for index in range(24, 4, -1)]
    assert all(set(item) == {"text", "like_count", "timestamp"} for item in state["items"])


def test_audience_items_are_available_in_the_too_few_state():
    latest = datetime(2026, 11, 22, tzinfo=UTC)
    state = audience_comment_state(
        [
            comment(1, "Older", timestamp=latest - timedelta(minutes=1)),
            comment(2, "Newest", timestamp=latest),
            comment(3, "Owner", owner=True, timestamp=latest + timedelta(minutes=1)),
        ],
        feature_enabled=True,
        permission_granted=True,
    )

    assert state["state"] == "too_few"
    assert [item["text"] for item in state["items"]] == ["Newest", "Older"]
