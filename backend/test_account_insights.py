from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.services.account_insights import build_post_analysis, performance_posts

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)

def item(index, views, *, reach=None, engagement=5.0, hours_old=1):
    media = SimpleNamespace(id=f"m{index}", instagram_media_id=f"ig{index}", media_type="IMAGE", thumbnail_url=None, media_url=None, published_at=NOW - timedelta(days=20))
    tracking = SimpleNamespace(id=f"t{index}")
    snapshot = SimpleNamespace(captured_at=NOW - timedelta(hours=hours_old), views=views, reach=reach if reach is not None else views, engagement_rate=engagement, shares=10, saves=12, comments=8, likes=30)
    return {"media": media, "tracking": tracking, "latest": snapshot, "snapshots": [snapshot]}

def analysis(selected, peers):
    return build_post_analysis(selected, [selected, *peers], summary=None, audience_comments={"state": "too_few"}, now=NOW)

def test_not_enough_comparable_posts_hides_all_range_sections():
    result = analysis(item(0, 100), [item(i, 200 + i) for i in range(1, 6)])
    assert result["comparable"] is False
    assert result["stands_out"] == result["weaker"] == result["usual_ranges"] == []

def test_stands_out_and_weaker_use_account_range():
    peers = [item(i, 100 + i * 10) for i in range(1, 7)]
    high = analysis(item(0, 1000), peers)
    low = analysis(item(0, 1), peers)
    assert {row["metric"] for row in high["stands_out"]} >= {"views", "reach"}
    assert {row["metric"] for row in low["weaker"]} >= {"views", "reach"}

def test_weaker_falls_back_to_lower_half_when_nothing_is_below_range():
    peers = [item(i, 100 + i * 10) for i in range(1, 7)]
    result = analysis(item(0, 115), peers)
    assert result["weaker"]
    assert all(row["rank"] > row["group_size"] / 2 for row in result["weaker"])

def test_refresh_flag_uses_single_24_hour_constant_and_only_metric_posts_are_listed():
    fresh, stale = item(1, 10, hours_old=24), item(2, 20, hours_old=25)
    empty = item(3, None, hours_old=1)
    for name in ("reach", "engagement_rate", "shares", "saves", "comments"):
        setattr(empty["latest"], name, None)
    posts = performance_posts([fresh, stale, empty], now=NOW)
    assert {post["tracked_post_id"] for post in posts} == {"t1", "t2"}
    assert next(post for post in posts if post["tracked_post_id"] == "t1")["needs_refresh"] is False
    assert next(post for post in posts if post["tracked_post_id"] == "t2")["needs_refresh"] is True
