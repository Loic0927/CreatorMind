from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from backend.services.insight_texts import post_summary

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
def snapshot(hours, views):
    return SimpleNamespace(captured_at=NOW + timedelta(hours=hours), views=views, reach=views, engagement_rate=5.0, shares=1, saves=1, comments=1)

def test_summary_is_hidden_for_one_snapshot_without_calling_model():
    called = False
    def generator(_):
        nonlocal called
        called = True
        return "filler"
    assert post_summary("u", "t", [snapshot(0, 10)], generator=generator) is None
    assert called is False

def test_summary_is_hidden_when_history_has_no_non_obvious_movement():
    assert post_summary("u", "t", [snapshot(0, 10), snapshot(1, 10)], generator=lambda _: "filler") is None
