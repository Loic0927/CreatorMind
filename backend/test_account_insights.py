from datetime import datetime, timedelta, timezone

from backend.services.account_insights import RECOMMENDED_SAMPLE_SIZE, build_account_insights
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia, TrackedPostAnalysis


NOW = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)


def _item(
    index: int,
    score: int,
    *,
    topic: str,
    hashtag: str = "",
    hour: int = 12,
    cta: str = "None",
    complete_24h: bool = False,
    media_type: str = "VIDEO",
):
    published = NOW.replace(hour=hour) - timedelta(days=index + 2)
    media = InstagramMedia(
        id=f"media-{index}", account_id="account-1", instagram_media_id=str(index), media_type=media_type,
        media_url=None, caption=f"{topic} tutorial {hashtag}".strip(), published_at=published,
        last_synced_at=NOW,
    )
    analysis = TrackedPostAnalysis(
        id=f"analysis-{index}", user_id="user-1", tracked_post_id=f"tracked-{index}",
        source_snapshot_id=f"snapshot-{index}", model_name="test", created_at=NOW,
        output_payload={
            "score": {"overall": score},
            "content_attributes": {
                "topic": topic, "caption_style": "Short", "cta_usage": cta,
            },
        },
    )
    snapshots = []
    if complete_24h:
        snapshots.append(InstagramInsightSnapshot(
            id=f"snapshot-{index}", media_id=media.id, captured_at=published + timedelta(hours=24),
            likes=20 + index, comments=2, saves=3, shares=2, reach=200,
            views=250, engagement_rate=round(8 + index / 10, 2),
            collection_type="milestone", target_hour=24,
            scheduled_for=published + timedelta(hours=24),
        ))
    return {"media": media, "analyses": [analysis], "snapshots": snapshots}


def test_small_sample_is_visible_but_explicitly_low_confidence():
    result = build_account_insights([
        _item(1, 80, topic="Magic Tricks", hashtag="#magic"),
        _item(2, 70, topic="Magic Tricks", hashtag="#magic"),
    ])

    assert RECOMMENDED_SAMPLE_SIZE == 10
    assert result["sample_size"] == 2
    assert result["enough_data"] is False
    assert result["heading"] == "Patterns to validate"
    assert result["progress"] == {"patterns": 2, "posting_times": 0}
    assert result["patterns"][0]["confidence"] == "LOW"
    assert "limited sample" in result["patterns"][0]["confidence_label"].lower()
    assert result["tested_combination"] is None


def test_insights_rank_only_repeated_account_evidence_and_label_benchmark():
    items = [
        _item(
            index,
            90 if index < 6 else 60,
            topic="Magic Tricks" if index < 6 else "Tutorials",
            hashtag="#magic" if index < 6 else "#tutorial",
            hour=19 if index < 6 else 12,
            cta="Question" if index < 6 else "None",
            complete_24h=True,
        )
        for index in range(10)
    ]
    result = build_account_insights(items)

    assert result["sample_size"] == 10
    assert result["enough_data"] is True
    magic = next(row for row in result["patterns"] if row["label"] == "Magic Tricks")
    assert magic["posts"] == 6
    assert magic["confidence"] == "MEDIUM"
    assert magic["benchmark"] == "All analyzed posts in this account"
    assert "hashtag_insights" not in result
    assert "hashtag_recommendations" not in result
    assert result["posting_time_insights"][0]["metric_label"] == "24-hour engagement rate"
    assert result["posting_time_metadata"]["complete_posts"] == 10
    assert result["tested_combination"]["difference_from_baseline"] > 0
    assert "winning_formula" not in result
    forbidden = {"reach", "views", "likes", "comments", "saves", "shares", "engagement_rate"}
    assert forbidden.isdisjoint(result)


def test_incomplete_24_hour_tracking_is_not_used_for_time_rankings():
    items = [
        _item(index, 70, topic="Tutorials", hashtag="#tutorial", hour=12, complete_24h=False)
        for index in range(4)
    ]
    result = build_account_insights(items)

    assert result["posting_time_insights"] == []
    assert result["tracking_24h"]["available"] is False
    assert result["tracking_24h"]["automatic_collection"] is False
    assert result["posting_time_metadata"]["incomplete_posts"] == 4
    assert result["content_opportunities"][0]["title"] == "Collect a comparable 24-hour baseline"


def test_24_hour_snapshot_without_reach_is_not_treated_as_complete():
    item = _item(1, 70, topic="Tutorials", complete_24h=True)
    item["snapshots"][0] = item["snapshots"][0].model_copy(update={"reach": None, "engagement_rate": 0.0})

    result = build_account_insights([item])

    assert result["tracking_24h"]["complete_posts"] == 0
    assert result["posting_time_insights"] == []


def test_hashtags_in_captions_are_preserved_but_not_analyzed_or_recommended():
    items = [
        _item(index, 80, topic="Magic", hashtag="#magic", complete_24h=False)
        for index in range(3)
    ]
    result = build_account_insights(items)

    assert all("#magic" in item["media"].caption for item in items)
    assert not any("hashtag" in key.lower() for key in result)
    assert not any("hashtag" in opportunity["title"].lower() for opportunity in result["content_opportunities"])


def test_legacy_manual_snapshot_near_24_hours_is_not_a_24_hour_result():
    item = _item(1, 70, topic="Tutorials", complete_24h=True)
    item["snapshots"][0] = item["snapshots"][0].model_copy(update={
        "collection_type": "manual_current", "target_hour": None,
    })

    result = build_account_insights([item])

    assert result["tracking_24h"]["complete_posts"] == 0
    assert result["posting_time_insights"] == []
    assert all(milestone["scheduled_for"] is None for milestone in result["performance_posts"][0]["milestones"])


def test_zero_complete_24h_never_describes_24h_comments_as_existing_evidence():
    items = [_item(index, 70, topic="Tutorials", cta="None") for index in range(3)]

    result = build_account_insights(items)

    cta = next(item for item in result["content_opportunities"] if item["title"] == "CTA experiment")
    assert result["tracking_24h"]["complete_posts"] == 0
    assert "no completed comparable 24-hour comment snapshots" in cta["data_gap"].lower()
    assert "caption usage only" in cta["current_observation"].lower()
    assert "24-hour" not in cta["current_observation"].lower()
    assert "existing evidence" not in cta
    assert cta["effect_estimate"] is None
    assert cta["effect_estimate_label"] == "Impact cannot currently be estimated."


def test_pending_24h_job_is_reported_as_waiting_data_not_lifetime_evidence():
    item = _item(1, 72, topic="Tutorials")
    item["post_publish_tracking"] = {
        "automatic_collection": True,
        "milestones": [{
            "target_hour": 24,
            "status": "pending",
            "scheduled_for": item["media"].published_at + timedelta(hours=24),
        }],
    }

    result = build_account_insights([item])

    assert result["tracking_24h"]["pending_posts"] == 1
    assert "still waiting" in result["tracking_24h"]["message"].lower()
    assert result["content_opportunities"][0]["status"] == "DATA_GAP"
    assert "lifetime" not in result["content_opportunities"][0]["current_observation"].lower()


def test_performance_timeline_preserves_present_and_missing_views_reach_without_zero_fill():
    item = _item(1, 75, topic="Tutorials")
    published = item["media"].published_at
    item["snapshots"] = [
        InstagramInsightSnapshot(
            id="snapshot-1h", media_id=item["media"].id,
            captured_at=published + timedelta(hours=1, minutes=4),
            scheduled_for=published + timedelta(hours=1), collection_type="milestone", target_hour=1,
            views=120, reach=90, likes=10, comments=1,
            metric_status={"views": "available", "reach": "available"},
        ),
        InstagramInsightSnapshot(
            id="snapshot-3h", media_id=item["media"].id,
            captured_at=published + timedelta(hours=3, minutes=6),
            scheduled_for=published + timedelta(hours=3), collection_type="milestone", target_hour=3,
            views=None, reach=140, likes=14, comments=2,
            metric_status={"views": "unavailable", "reach": "available"},
        ),
    ]

    result = build_account_insights([item])
    milestones = result["performance_posts"][0]["milestones"]

    assert milestones[0]["metrics"]["views"] == 120
    assert milestones[0]["metrics"]["reach"] == 90
    assert milestones[0]["captured_at"].endswith("+00:00")
    assert milestones[1]["metrics"]["views"] is None
    assert milestones[1]["metric_status"]["views"] == "unavailable"
    assert milestones[1]["views_since_previous_snapshot"] is None
    assert milestones[2]["metrics"] is None


def test_adjacent_snapshot_view_increase_is_labelled_data_not_hourly_estimate():
    item = _item(1, 75, topic="Tutorials")
    published = item["media"].published_at
    item["snapshots"] = [
        InstagramInsightSnapshot(id="one", media_id=item["media"].id, captured_at=published + timedelta(hours=1), scheduled_for=published + timedelta(hours=1), collection_type="milestone", target_hour=1, views=100),
        InstagramInsightSnapshot(id="three", media_id=item["media"].id, captured_at=published + timedelta(hours=3), scheduled_for=published + timedelta(hours=3), collection_type="milestone", target_hour=3, views=175),
    ]

    milestones = build_account_insights([item])["performance_posts"][0]["milestones"]

    assert milestones[1]["views_since_previous_snapshot"] == 75


def test_post_ranking_never_mixes_media_types_or_observation_windows():
    video_a = _item(1, 80, topic="Tutorials", complete_24h=True, media_type="VIDEO")
    video_b = _item(2, 75, topic="Tutorials", complete_24h=True, media_type="VIDEO")
    image = _item(3, 90, topic="Tutorials", complete_24h=True, media_type="IMAGE")
    partial_video = _item(4, 85, topic="Tutorials", media_type="VIDEO")
    partial_video["snapshots"] = [InstagramInsightSnapshot(
        id="partial", media_id=partial_video["media"].id,
        captured_at=partial_video["media"].published_at + timedelta(hours=12),
        scheduled_for=partial_video["media"].published_at + timedelta(hours=12),
        collection_type="milestone", target_hour=12, views=9999, reach=9999,
    )]
    video_a["snapshots"][0] = video_a["snapshots"][0].model_copy(update={"views": 400})
    video_b["snapshots"][0] = video_b["snapshots"][0].model_copy(update={"views": 300})

    posts = build_account_insights([video_a, video_b, image, partial_video])["performance_posts"]
    by_id = {post["instagram_media_id"]: post for post in posts}

    assert by_id["1"]["comparison"]["rank"] == 1
    assert by_id["1"]["comparison"]["group_size"] == 2
    assert by_id["2"]["comparison"]["rank"] == 2
    assert by_id["3"]["comparison"] is None
    assert by_id["4"]["comparison"] is None


def test_small_score_gap_is_neutral_even_when_total_sample_is_large():
    items = [
        _item(index, 71 if index < 5 else 70, topic="Tutorials" if index < 5 else "Magic")
        for index in range(10)
    ]

    result = build_account_insights(items)
    tutorials = next(row for row in result["patterns"] if row["label"] == "Tutorials")

    assert tutorials["confidence"] == "MEDIUM"
    assert "no clear direction" in tutorials["difference_interpretation"].lower()
    assert tutorials["distribution"] == {"minimum": 71, "median": 71, "maximum": 71}
    assert "not the probability" in result["confidence_explanation"].lower()


def test_untested_window_is_explicitly_only_a_coverage_gap():
    result = build_account_insights([_item(1, 70, topic="Tutorials", hour=12)])

    opportunity = next(item for item in result["content_opportunities"] if item["title"] == "Test an unobserved posting window")
    assert "coverage gap only" in opportunity["data_gap"].lower()
    assert "no evidence" in opportunity["data_gap"].lower()


def test_advanced_video_metrics_are_not_claimed_when_integration_does_not_collect_them():
    capabilities = build_account_insights([_item(1, 70, topic="Tutorials")])["metric_capabilities"]

    assert capabilities["required_scope"] == "instagram_business_manage_insights"
    assert {item["key"] for item in capabilities["advanced_metrics"]} == {
        "average_watch_time", "watch_time", "retention", "skip_rate",
    }
    assert all(item["status"] == "not_collected" for item in capabilities["advanced_metrics"])
