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
    assert any(item["title"] == "Build a comparable 24-hour baseline" for item in result["content_opportunities"])


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
