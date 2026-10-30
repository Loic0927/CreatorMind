from datetime import datetime, timezone
from backend.services.comments import audience_comment_state
from backend.storage.models import InstagramComment

def comment(index, text="hello", owner=False):
    return InstagramComment(id=str(index), provider_id=f"p{index}", user_id="u", tracked_post_id="t", text=text, like_count=0, timestamp=datetime.now(timezone.utc), is_owner_reply=owner, fetched_at=datetime.now(timezone.utc))

def test_audience_comment_states_are_explicit_and_too_few_has_exact_copy():
    assert audience_comment_state([], feature_enabled=False, permission_granted=False)["state"] == "feature_off"
    assert audience_comment_state([], feature_enabled=True, permission_granted=False)["state"] == "reconnect_needed"
    assert audience_comment_state([], feature_enabled=True, permission_granted=True, error=True)["state"] == "error"
    assert audience_comment_state([comment(1), comment(2)], feature_enabled=True, permission_granted=True)["message"] == "Not enough comments yet"
    ready = audience_comment_state([comment(1), comment(2), comment(3)], feature_enabled=True, permission_granted=True, description="Viewers compared the examples.")
    assert ready == {"state": "ready", "description": "Viewers compared the examples."}
