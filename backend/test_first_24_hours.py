from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.services.first_24_hours import first_24_hour_state, screenshot_validation


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def test_first_24_hour_state_hides_upload_until_the_post_is_24_hours_old():
    young = first_24_hour_state(NOW - timedelta(hours=23), now=NOW)
    old = first_24_hour_state(NOW - timedelta(hours=25), now=NOW)
    assert young["state"] == "not_ready"
    assert young["upload_allowed"] is False
    assert old["state"] == "upload_available"
    assert old["upload_allowed"] is True


def test_first_24_hour_state_labels_api_and_screenshot_sources():
    api = SimpleNamespace(views=120, reach=100, average_watch_time_ms=9500, captured_at=NOW)
    api_state = first_24_hour_state(NOW - timedelta(days=2), now=NOW, api_snapshot=api)
    screenshot = SimpleNamespace(payload={"views": 118, "curve": {"estimated_views_at_24h": 90}}, confirmed_at=NOW)
    screenshot_state = first_24_hour_state(NOW - timedelta(days=2), now=NOW, api_snapshot=api, screenshot_record=screenshot)
    assert api_state["record"]["source_label"] == "Instagram API"
    assert api_state["record"]["payload"]["avg_watch_time_seconds"] == 9.5
    assert screenshot_state["record"]["source_label"] == "From your screenshot"


def test_screenshot_validation_warns_only_above_ten_percent_mismatch():
    assert screenshot_validation(109, 100)["possible_wrong_post"] is False
    warning = screenshot_validation(111, 100)
    assert warning["possible_wrong_post"] is True
    assert warning["mismatch_pct"] == 11.0
    assert "right post" in warning["warning"]
