from datetime import datetime, timedelta, timezone

from backend.services.account_insights import build_account_insights
from backend.storage.models import InstagramMedia, TrackedPostAnalysis


NOW = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)


def _item(index: int, score: int, *, topic: str, hashtag: str, hour: int):
    media = InstagramMedia(
        id=f"media-{index}", account_id="account-1", instagram_media_id=str(index), media_type="VIDEO",
        media_url=None, caption=f"{topic} tutorial? {hashtag}", published_at=NOW.replace(hour=hour) - timedelta(days=index),
        last_synced_at=NOW,
    )
    analysis = TrackedPostAnalysis(
        id=f"analysis-{index}", user_id="user-1", tracked_post_id=f"tracked-{index}",
        source_snapshot_id=f"snapshot-{index}", model_name="test", created_at=NOW,
        output_payload={
            "score": {"overall": score},
            "content_attributes": {
                "topic": topic, "caption_style": "Short", "cta_usage": "Question",
            },
        },
    )
    return {"media": media, "analyses": [analysis]}


def test_insights_require_ten_analyzed_posts_and_report_progress():
    result = build_account_insights([
        _item(1, 80, topic="Magic Tricks", hashtag="#magic", hour=19),
        _item(2, 70, topic="Tutorials", hashtag="#tutorial", hour=12),
    ])
    assert result["sample_size"] == 2
    assert result["progress"] == {"topics": 2, "hashtags": 2, "posting_times": 2}
    assert result["top_patterns"] == []
    assert result["winning_formula"] is None


def test_insights_rank_account_patterns_without_individual_post_metrics():
    items = [
        _item(index, 90 if index < 6 else 60,
              topic="Magic Tricks" if index < 6 else "Tutorials",
              hashtag="#magic" if index < 6 else "#tutorial",
              hour=19 if index < 6 else 12)
        for index in range(10)
    ]
    result = build_account_insights(items)
    assert result["sample_size"] == 10
    assert result["top_patterns"][0]["label"] == "Magic Tricks"
    assert result["top_hashtags"][0]["label"] == "#magic"
    assert result["best_posting_times"][0]["label"] == "6 PM - 8 PM"
    assert result["winning_formula"]["topic"] == "Magic Tricks"
    assert "thumbnail_insights" not in result
    assert "thumbnail" not in result["winning_formula"]
    forbidden = {"reach", "views", "likes", "comments", "saves", "shares", "engagement_rate"}
    assert forbidden.isdisjoint(result)
