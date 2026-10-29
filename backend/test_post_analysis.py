import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.post_analysis import PostAnalysisError, analyze_post
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def _media(identifier: str = "media-1", media_type: str = "IMAGE", age_days: int = 2) -> InstagramMedia:
    return InstagramMedia(id=f"instagram:{identifier}", account_id="account-1", instagram_media_id=identifier,
                          media_type=media_type, media_url="https://scontent.cdninstagram.com/post.jpg",
                          caption="A practical guide for this account's audience", published_at=NOW - timedelta(days=age_days), last_synced_at=NOW)


def _snapshot(identifier: str = "snapshot-1", **values) -> InstagramInsightSnapshot:
    defaults = dict(reach=100, views=120, likes=10, comments=4, saves=3, shares=2, engagement_rate=19.0)
    defaults.update(values)
    captured_at = defaults.pop("captured_at", NOW)
    return InstagramInsightSnapshot(id=identifier, media_id="instagram:media-1", captured_at=captured_at, **defaults)


def _peer(index: int, *, media_type: str = "IMAGE", age_days: int = 3, **values) -> dict:
    metrics = dict(reach=100, views=120, likes=10, comments=4, saves=3, shares=2, engagement_rate=19.0)
    metrics.update(values)
    return {"media_type": media_type, "published_at": (NOW - timedelta(days=age_days)).isoformat(), "captured_at": NOW.isoformat(), "metrics": metrics}


def _model_output(text: str = "The caption may have helped.") -> str:
    return json.dumps({"why_it_worked": [{"title": "Possible content explanation", "evidence": "Reach is above the median.", "interpretation": text, "why_it_matters": "Repeat a comparable test."}], "content_attributes": {"thumbnail_style": "Unavailable", "caption_style": "Short", "cta_usage": "None", "on_screen_text_hook": "Start here"}})


def test_analysis_uses_mature_same_format_range_and_hides_rank_below_six_peers():
    result = analyze_post(_media(), [_snapshot("old", reach=50, captured_at=NOW - timedelta(days=1)), _snapshot("new")], peer_metrics=[_peer(1), _peer(2, media_type="VIDEO"), _peer(3, age_days=20)],
                          generator=lambda *args, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test")
    assert result.schema_version == "post-analysis-v6"
    assert "score" not in result.output_payload
    assert result.output_payload["baseline"]["sample_size"] == 1
    assert result.output_payload["baseline"]["group"] == "mature_same_format"
    reach = next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach["rank"] is None
    assert reach["percentile"] is None
    assert result.output_payload["what_worked"] == []
    assert result.output_payload["what_to_improve"] == []
    assert result.output_payload["comparison_notice"] == "Only 1 mature same-format post; no comparison yet."
    assert reach["basis"] == result.output_payload["baseline"]["label"]


def test_account_range_is_in_prompt_and_in_range_values_are_not_highlighted():
    received = {}
    def generator(prompt, **kwargs):
        received["prompt"] = prompt
        return _model_output()
    current = _snapshot(reach=104, views=124, likes=10, comments=4, saves=3, shares=2, engagement_rate=19.4)
    peers = [_peer(index, age_days=20, reach=value) for index, value in enumerate((90, 95, 100, 105, 110, 115))]
    previous = _snapshot("previous", reach=50, views=60, captured_at=NOW - timedelta(days=1))
    result = analyze_post(_media(), [previous, current], peer_metrics=peers,
                          generator=generator,
                          image_loader=lambda url: None, model_name="test")
    reach = next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach["range_status"] == "in_range"
    assert reach["rank"] is not None
    assert result.output_payload["experiment"] == []
    assert "mature same-format range" in received["prompt"]
    assert "under 10%" not in received["prompt"]


def test_range_and_rank_logic_marks_only_values_outside_account_distribution():
    peers = [_peer(index, age_days=20, reach=value, views=value) for index, value in enumerate((80, 90, 100, 110, 120, 130))]
    inside = analyze_post(_media(), [_snapshot(reach=105, views=105)], peer_metrics=peers, image_loader=lambda url: None)
    above = analyze_post(_media(), [_snapshot(reach=140, views=140)], peer_metrics=peers, image_loader=lambda url: None)
    reach = lambda result: next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach(inside)["range_status"] == "in_range"
    assert reach(inside)["comparison_text"].startswith("#")
    assert reach(above)["range_status"] == "above_range"
    assert reach(above)["comparison_text"].startswith("Above your usual range:")


def test_benchmark_comparison_hidden_for_zero_median_and_values_are_rounded():
    result = analyze_post(_media(), [_snapshot(reach=12, engagement_rate=3.26)], peer_metrics=[_peer(1, age_days=20, reach=0, engagement_rate=2.24)], image_loader=lambda url: None)
    reach = next(item for item in result.output_payload["benchmarks"] if item["metric"] == "reach")
    rate = next(item for item in result.output_payload["benchmarks"] if item["metric"] == "engagement_rate")
    assert reach["median"] == 0
    assert reach["percent_change"] is None
    assert rate["current"] == 3.3
    assert rate["median"] == 2.2


def test_metric_gap_without_account_condition_evidence_does_not_invent_an_experiment():
    snapshots = [_snapshot("previous", reach=80, views=90, captured_at=NOW - timedelta(days=1)), _snapshot(reach=160, views=180, shares=10, saves=0)]
    result = analyze_post(_media(), snapshots, peer_metrics=[_peer(index, age_days=20, saves=10) for index in range(6)],
                          generator=lambda *args, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test")
    assert result.output_payload["experiment"] == []
    assert result.output_payload["strongest_metric"]["rank"] == 1
    assert result.output_payload["what_worked"]


def test_usual_range_switches_to_percentiles_at_fifteen_peers():
    values = list(range(10, 25))
    fourteen = analyze_post(_media(), [_snapshot(reach=17)], peer_metrics=[_peer(index, age_days=20, reach=value) for index, value in enumerate(values[:14])], image_loader=lambda url: None)
    fifteen = analyze_post(_media(), [_snapshot(reach=17)], peer_metrics=[_peer(index, age_days=20, reach=value) for index, value in enumerate(values)], image_loader=lambda url: None)
    get_reach = lambda result: next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert get_reach(fourteen)["range_kind"] == "minimum-maximum"
    assert get_reach(fourteen)["minimum"] == 10
    assert get_reach(fifteen)["range_kind"] == "10th-90th percentile"
    assert get_reach(fifteen)["minimum"] == 11
    assert get_reach(fifteen)["maximum"] == 23


def test_unsupported_retention_explanation_is_removed():
    result = analyze_post(_media(media_type="VIDEO"), [_snapshot(reach=180)], peer_metrics=[_peer(index, media_type="VIDEO") for index in range(5)],
                          generator=lambda *args, **kwargs: _model_output("Retention proves the hook prevented drop-off."),
                          image_loader=lambda url: None, model_name="test")
    assert all("retention" not in (item.get("interpretation") or "").lower() for item in result.output_payload["what_worked"])
    assert "Average watch time is unavailable" in result.output_payload["data_gaps"][0]


def test_analysis_rejects_missing_snapshot_and_falls_back_for_invalid_model_output(monkeypatch):
    with pytest.raises(PostAnalysisError):
        analyze_post(_media(), [])
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    result = analyze_post(_media(), [_snapshot()], generator=lambda *args, **kwargs: pytest.fail("not called"), image_loader=lambda url: None)
    assert result.model_name == "deterministic-fallback-v6"
    assert "topic" not in result.output_payload["content_attributes"]


def test_plateaued_young_post_uses_only_the_mature_same_format_basis():
    peers = [_peer(index, age_days=20, reach=value) for index, value in enumerate((70, 80, 90, 100, 110, 120))]
    snapshots = [_snapshot("old", reach=125, captured_at=NOW - timedelta(days=1)), _snapshot("new", reach=127)]
    result = analyze_post(_media(age_days=2), snapshots, peer_metrics=peers, image_loader=lambda url: None)
    baseline = result.output_payload["baseline"]
    assert baseline["group"] == "mature_same_format"
    assert baseline["sample_size"] == 6
    assert result.output_payload["comparison_notice"] is None
    assert "above your usual range" in result.output_payload["verdict"]
    reach = next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach["range_status"] == "above_range"


def test_same_age_basis_is_not_used_until_growth_is_observed():
    peers = [_peer(index, age_days=20) for index in range(3)] + [_peer(index + 3, age_days=2) for index in range(3)]
    result = analyze_post(_media(age_days=2), [_snapshot()], peer_metrics=peers, image_loader=lambda url: None)
    assert result.output_payload["trend"]["growth_status"] == "growth status not established"
    assert result.output_payload["baseline"]["group"] == "mature_same_format"


def test_verdict_mentions_only_metrics_outside_the_usual_range():
    peers = [_peer(index, age_days=20, reach=100 + index, engagement_rate=10.0 + index / 10, saves=3) for index in range(6)]
    snapshots = [_snapshot("previous", reach=80, captured_at=NOW - timedelta(days=1)), _snapshot(reach=180, engagement_rate=5.0, saves=3)]
    result = analyze_post(_media(), snapshots, peer_metrics=peers, image_loader=lambda url: None)
    verdict = result.output_payload["verdict"].lower()
    assert "reach is above your usual range" in verdict
    assert "engagement rate is below your usual range" in verdict


def test_similar_posts_are_factual_and_theme_scoped_without_content_snapshot():
    history = [
        {"is_current": True, "theme": "Image · Short caption"},
        {"is_current": False, "theme": "Image · Short caption", "tracked_post_id": "peer-1", "media_type": "IMAGE",
         "caption": "Peer caption #hidden", "published_at": NOW.isoformat(), "thumbnail_url": "https://cdn.example/peer.jpg",
         "metrics": {"views": 321, "engagement_rate": 7.25}},
        {"is_current": False, "theme": "Reel / video · Long caption", "tracked_post_id": "peer-2", "media_type": "VIDEO",
         "caption": "Other theme", "published_at": NOW.isoformat(), "metrics": {"views": 999, "engagement_rate": 4.0}},
    ]
    result = analyze_post(_media(), [_snapshot()], historical_posts=history,
                          generator=lambda *args, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test")
    assert "content_snapshot" not in result.output_payload
    snapshot = {"on_screen_text_hook": "Start here", "cta": "Not present", "theme": history[0]["theme"]}
    assert snapshot["on_screen_text_hook"] == "Start here"
    assert snapshot["cta"] == "Not present"
    assert snapshot["theme"] == "Image · Short caption"
    assert result.output_payload["similar_posts"][0]["title"] == "Peer caption"
    assert result.output_payload["similar_posts"][0]["engagement_rate"] == 7.2
