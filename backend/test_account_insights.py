from datetime import datetime, timedelta, timezone

from backend.services.account_insights import RECOMMENDED_SAMPLE_SIZE, account_themes_meet_constraints, assign_account_theme, build_account_insights, generate_account_themes
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia, TrackedPostAnalysis

NOW = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)


def _item(index: int, *, caption: str, media_type: str = "IMAGE", age_days: int = 10,
          reach: int = 200, views: int = 250, engagement_rate: float = 8.0,
          caption_style: str = "Short", cta: str = "None", complete_24h: bool = False):
    published = NOW - timedelta(days=age_days)
    media = InstagramMedia(id=f"media-{index}", account_id="account-1", instagram_media_id=str(index), media_type=media_type,
                           media_url=f"https://cdn.example/{index}.jpg", caption=caption, published_at=published, last_synced_at=NOW)
    analysis = TrackedPostAnalysis(id=f"analysis-{index}", user_id="user-1", tracked_post_id=f"tracked-{index}",
                                   source_snapshot_id=f"snapshot-{index}", model_name="test", created_at=NOW,
                                   output_payload={"conclusion": "Test", "content_attributes": {"caption_style": caption_style, "cta_usage": cta, "thumbnail_style": "Unavailable"}})
    snapshots = [InstagramInsightSnapshot(id=f"snapshot-{index}", media_id=media.id, captured_at=NOW,
                                          likes=10, comments=2, saves=3, shares=2, reach=reach, views=views, engagement_rate=engagement_rate)]
    if complete_24h:
        snapshots.append(InstagramInsightSnapshot(id=f"milestone-{index}", media_id=media.id, captured_at=published + timedelta(hours=24),
                                                  scheduled_for=published + timedelta(hours=24), collection_type="milestone", target_hour=24,
                                                  likes=5, comments=1, saves=1, shares=1, reach=80, views=100, engagement_rate=10.0))
    return {"media": media, "analyses": [analysis], "snapshots": snapshots, "tracking": type("Tracking", (), {"id": f"tracked-{index}"})()}


def test_themes_are_derived_from_account_corpus_and_each_post_gets_one():
    items = [
        _item(1, caption="short update"), _item(2, caption="another short update"),
        _item(3, caption="short clip", media_type="VIDEO"), _item(4, caption="another short clip", media_type="VIDEO"),
        _item(5, caption="short slides", media_type="CAROUSEL_ALBUM"), _item(6, caption="another short set", media_type="CAROUSEL_ALBUM"),
    ]
    themes = generate_account_themes(items)
    result = build_account_insights(items, themes=themes)
    assert 3 <= len(themes) <= 5
    assert account_themes_meet_constraints(items, themes)
    assert all("#" not in theme and "@" not in theme for theme in themes)
    assert all(post["theme"] in themes for post in result["performance_posts"])
    assert assign_account_theme(items[0], themes) in themes
    assert all(item["post_count"] == 2 for item in result["theme_stats"])


def test_themes_are_hidden_when_three_groups_of_two_cannot_be_formed():
    items = [_item(index, caption=f"same form {index}") for index in range(6)]
    result = build_account_insights(items)
    assert result["themes"] == []
    assert result["theme_stats"] == []
    assert all(post["theme"] == "Theme unavailable" for post in result["performance_posts"])


def test_mature_lifetime_is_default_and_rankings_never_mix_format_or_maturity():
    mature = [_item(index, caption=f"account subject {index}", age_days=10, views=700 - index * 50) for index in range(1, 7)]
    young = _item(7, caption="account subject young", age_days=1, views=9999)
    video = _item(8, caption="account subject video", media_type="VIDEO", age_days=20, views=9999)
    posts = build_account_insights([*mature, young, video])["performance_posts"]
    by_id = {post["instagram_media_id"]: post for post in posts}
    assert by_id["1"]["observation_kind"] == "Mature lifetime snapshot"
    assert by_id["1"]["comparison"]["rank"] == 1
    assert by_id["1"]["comparison"]["group_size"] == 6
    assert by_id["7"]["comparison"] is None
    assert by_id["8"]["comparison"] is None


def test_patterns_require_three_posts_real_difference_and_dimension_variation():
    items = []
    for index in range(6):
        items.append(_item(index, caption=f"clay glazing method {index}", engagement_rate=12 if index < 3 else 5,
                           caption_style="Short" if index < 3 else "Long"))
    result = build_account_insights(items, themes=["Clay Glazing", "Studio Portrait", "Kiln Process"])
    assert any(row["category"] == "Caption style" and row["posts"] == 3 for row in result["patterns"])
    row = next(row for row in result["patterns"] if row["category"] == "Caption style")
    assert row["comparison_posts"] == 3
    assert row["baseline"] in {5.0, 12.0}
    assert not any(row["category"] == "Format" for row in result["patterns"])
    small_groups = build_account_insights(items[:2], themes=["Clay", "Studio", "Kiln"])
    assert small_groups["patterns"] == []


def test_small_pattern_differences_are_hidden():
    items = [_item(index, caption=f"account phrase {index}", engagement_rate=8.1 if index < 3 else 8.0,
                   caption_style="Short" if index < 3 else "Long") for index in range(6)]
    assert build_account_insights(items, themes=["Account Phrase", "Creative Notes", "Daily Work"])["patterns"] == []


def test_analyzed_progress_total_can_exceed_cap_but_required_cap_is_stable():
    items = [_item(index, caption=f"specific account theme word{index}") for index in range(11)]
    result = build_account_insights(items)
    assert RECOMMENDED_SAMPLE_SIZE == 10
    assert result["progress"]["patterns"] == 11
    assert result["required_sample_size"] == 10


def test_historical_tracking_is_collapsed_to_backfill_flag():
    item = _item(1, caption="specific historical post")
    item["post_publish_tracking"] = {"automatic_collection": True, "milestones": [
        {"target_hour": hour, "status": "missed", "error_code": "tracking_started_after_milestone"} for hour in (1, 3, 6, 12, 24)
    ]}
    post = build_account_insights([item])["performance_posts"][0]
    assert post["historical_backfill_unavailable"] is True


def test_optional_24h_view_never_substitutes_manual_lifetime_snapshot():
    item = _item(1, caption="specific account post", complete_24h=False)
    result = build_account_insights([item])
    assert result["tracking_24h"]["complete_posts"] == 0
    assert result["posting_time_insights"] == []
    assert "optional" in result["tracking_24h"]["message"].lower()


def test_metric_capabilities_match_implemented_watch_time_and_unavailable_account_data():
    capabilities = build_account_insights([_item(1, caption="specific account post")])["metric_capabilities"]
    by_key = {item["key"]: item for item in capabilities["advanced_metrics"]}
    assert capabilities["required_scope"] == "instagram_business_manage_insights"
    assert by_key["average_watch_time"]["status"] == "collected_when_available"
    assert by_key["total_watch_time"]["status"] == "collected_when_available"
    assert by_key["follower_non_follower_reach"]["status"] == "unavailable"
    assert by_key["audience_demographics"]["status"] == "unavailable"
    assert by_key["online_followers"]["status"] == "unavailable"
    assert build_account_insights([])["untested_posting_windows"] == []


def test_performance_summary_uses_one_mature_format_and_rank_threshold_is_six():
    five = [_item(index, caption=f"summary subject {index}", views=100 + index * 10, reach=100 + index * 10,
                  engagement_rate=12 if index == 0 else 6 + index) for index in range(5)]
    result = build_account_insights(five)
    assert result["performance_summary"]["sample_size"] == 5
    assert result["performance_summary"]["highest_reach"]["metric"] == "reach"
    assert result["performance_summary"]["lowest_engagement_rate"]["metric"] == "engagement_rate"
    assert result["performance_summary"]["lowest_reach"]["note"]
    assert all(post["comparison"] is None for post in result["performance_posts"])
    sixth = _item(5, caption="summary subject six", views=200)
    ranked = build_account_insights([*five, sixth])
    assert all(post["comparison"]["group_size"] == 6 for post in ranked["performance_posts"])


def test_cta_patterns_use_binary_groups_and_compare_against_other_posts():
    items = [
        _item(index, caption=f"cta subject {index}", engagement_rate=12, cta="Explicit CTA") for index in range(3)
    ] + [
        _item(index + 3, caption=f"plain subject {index}", engagement_rate=5, cta="None") for index in range(3)
    ]
    rows = build_account_insights(items)["patterns"]
    cta = next(row for row in rows if row["category"] == "CTA")
    assert cta["label"] in {"Has CTA", "No CTA"}
    assert cta["label"] != "None"
    assert cta["posts"] == cta["comparison_posts"] == 3
