from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.services.account_insights import build_post_analysis, performance_posts

NOW = datetime(2026, 10, 30, tzinfo=UTC)


def item(index, views, *, reach=None, engagement=5.0, hours_old=1):
    media = SimpleNamespace(
        id=f"m{index}",
        instagram_media_id=f"ig{index}",
        media_type="IMAGE",
        thumbnail_url=None,
        media_url=None,
        published_at=NOW - timedelta(days=20),
    )
    tracking = SimpleNamespace(id=f"t{index}")
    snapshot = SimpleNamespace(
        captured_at=NOW - timedelta(hours=hours_old),
        views=views,
        reach=reach if reach is not None else views,
        engagement_rate=engagement,
        shares=10,
        saves=12,
        comments=8,
        likes=30,
    )
    return {"media": media, "tracking": tracking, "latest": snapshot, "snapshots": [snapshot]}


def analysis(selected, peers):
    return build_post_analysis(
        selected, [selected, *peers], summary=None, audience_comments={"state": "too_few"}, now=NOW
    )


def test_not_enough_comparable_posts_hides_all_range_sections():
    result = analysis(item(0, 100), [item(i, 200 + i) for i in range(1, 6)])
    assert result["comparable"] is False
    assert result["comparison_basis"] == "lifetime"
    assert result["not_comparable_reason"] == "too_few_posts"
    assert result["stands_out"] == result["weaker"] == result["usual_ranges"] == []


def test_stands_out_and_weaker_use_account_range():
    peers = [item(i, 100 + i * 10) for i in range(1, 7)]
    high = analysis(item(0, 1000), peers)
    low = analysis(item(0, 1), peers)
    assert {row["metric"] for row in high["stands_out"]} >= {"views", "reach"}
    assert {row["metric"] for row in low["weaker"]} >= {"views", "reach"}


def test_weaker_only_contains_metrics_below_the_usual_range():
    peers = [item(i, 100 + i * 10) for i in range(1, 7)]
    result = analysis(item(0, 115), peers)
    assert result["weaker"] == []


def _history_item(index, published_at, snapshots):
    media = SimpleNamespace(
        id=f"history-m{index}",
        instagram_media_id=f"history-ig{index}",
        media_type="IMAGE",
        thumbnail_url=None,
        media_url=None,
        published_at=published_at,
    )
    return {
        "media": media,
        "tracking": SimpleNamespace(id=f"history-t{index}"),
        "latest": max(snapshots, key=lambda snapshot: snapshot.captured_at),
        "snapshots": snapshots,
    }


def _history_snapshot(identifier, captured_at, views):
    return SimpleNamespace(
        id=identifier,
        captured_at=captured_at,
        views=views,
        reach=views,
        engagement_rate=5.0,
        shares=10,
        saves=12,
        comments=8,
        likes=30,
    )


def test_young_posts_compare_with_same_age_snapshots_including_young_peers():
    selected_published = NOW - timedelta(hours=26)
    selected = _history_item(
        0,
        selected_published,
        [_history_snapshot("selected", NOW - timedelta(hours=2), 100)],
    )
    peers = []
    for index in range(6):
        published = NOW - timedelta(days=30) if index < 5 else NOW - timedelta(days=2)
        snapshots = [_history_snapshot(f"p{index}-same-age", published + timedelta(hours=23), 90 + index * 5)]
        if index < 5:
            snapshots.extend(
                [
                    _history_snapshot(f"p{index}-early", published + timedelta(hours=2), 1),
                    _history_snapshot(f"p{index}-lifetime", NOW, 10_000),
                ]
            )
        peers.append(_history_item(index + 1, published, snapshots))

    result = build_post_analysis(
        selected, [selected, *peers], summary=None, audience_comments={"state": "too_few"}, now=NOW
    )

    views = next(row for row in result["usual_ranges"] if row["metric"] == "views")
    assert result["comparable"] is True
    assert result["comparison_basis"] == "same_age"
    assert result["not_comparable_reason"] is None
    assert result["comparable_count"] == 6
    assert (views["usual_min"], views["usual_max"]) == (90, 115)


def test_young_posts_report_too_early_when_too_few_same_age_peers_qualify():
    selected_published = NOW - timedelta(hours=26)
    selected = _history_item(
        0,
        selected_published,
        [_history_snapshot("selected", NOW - timedelta(hours=2), 100)],
    )
    peers = [
        _history_item(
            index,
            NOW - timedelta(days=2),
            [_history_snapshot(f"p{index}", NOW - timedelta(days=2) + timedelta(hours=24), 100)],
        )
        for index in range(1, 6)
    ]

    result = build_post_analysis(
        selected, [selected, *peers], summary=None, audience_comments={"state": "too_few"}, now=NOW
    )

    assert result["comparable"] is False
    assert result["comparison_basis"] == "same_age"
    assert result["not_comparable_reason"] == "too_early"
    assert result["stands_out"] == result["weaker"] == result["usual_ranges"] == []


def test_refresh_flag_uses_single_24_hour_constant_and_only_metric_posts_are_listed():
    fresh, stale = item(1, 10, hours_old=24), item(2, 20, hours_old=25)
    empty = item(3, None, hours_old=1)
    for name in ("reach", "engagement_rate", "shares", "saves", "comments"):
        setattr(empty["latest"], name, None)
    posts = performance_posts([fresh, stale, empty], now=NOW)
    assert {post["tracked_post_id"] for post in posts} == {"t1", "t2"}
    assert next(post for post in posts if post["tracked_post_id"] == "t1")["needs_refresh"] is False
    assert next(post for post in posts if post["tracked_post_id"] == "t2")["needs_refresh"] is True
