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
    return InstagramInsightSnapshot(id=identifier, media_id="instagram:media-1", captured_at=NOW, **defaults)


def _peer(index: int, *, media_type: str = "IMAGE", age_days: int = 3, **values) -> dict:
    metrics = dict(reach=100, views=120, likes=10, comments=4, saves=3, shares=2, engagement_rate=19.0)
    metrics.update(values)
    return {"media_type": media_type, "published_at": (NOW - timedelta(days=age_days)).isoformat(), "captured_at": NOW.isoformat(), "metrics": metrics}


def _model_output(text: str = "The caption may have helped.") -> str:
    return json.dumps({"why_it_worked": [{"title": "Possible content explanation", "evidence": "Reach is above the median.", "interpretation": text, "why_it_matters": "Repeat a comparable test."}], "content_attributes": {"thumbnail_style": "Unavailable", "caption_style": "Short", "cta_usage": "None"}})


def test_analysis_uses_same_format_and_similar_age_without_a_score():
    result = analyze_post(_media(), [_snapshot()], peer_metrics=[_peer(1), _peer(2, media_type="VIDEO"), _peer(3, age_days=20)],
                          generator=lambda *args, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test")
    assert result.schema_version == "post-analysis-v5"
    assert "score" not in result.output_payload
    assert result.output_payload["baseline"]["sample_size"] == 1
    assert result.output_payload["baseline"]["group"] == "same_format_similar_age"
    reach = next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach["rank"] is None
    assert reach["percentile"] is None
    assert result.output_payload["what_worked"] == []
    assert result.output_payload["what_to_improve"] == []
    assert result.output_payload["comparison_notice"] == "Only 1 comparable post; no comparison yet."
    assert reach["basis"] == result.output_payload["baseline"]["label"]


def test_noise_threshold_is_in_prompt_and_deterministically_suppresses_experiment():
    received = {}
    def generator(prompt, **kwargs):
        received["prompt"] = prompt
        return _model_output()
    current = _snapshot(reach=104, views=124, likes=10, comments=4, saves=3, shares=2, engagement_rate=19.4)
    peers = [_peer(index) for index in range(5)]
    result = analyze_post(_media(), [current], peer_metrics=peers,
                          generator=generator,
                          image_loader=lambda url: None, model_name="test")
    reach = next(item for item in result.output_payload["metric_comparisons"] if item["metric"] == "reach")
    assert reach["is_noise"] is True
    assert reach["comparison_text"] == "In line with your typical posts."
    assert result.output_payload["experiment"] == []
    assert "under 10% relative" in received["prompt"]
    assert "under 5 count units" in received["prompt"]


def test_benchmark_comparison_hidden_for_zero_median_and_values_are_rounded():
    result = analyze_post(_media(), [_snapshot(reach=12, engagement_rate=3.26)], peer_metrics=[_peer(1, reach=0, engagement_rate=2.24)], image_loader=lambda url: None)
    reach = next(item for item in result.output_payload["benchmarks"] if item["metric"] == "reach")
    rate = next(item for item in result.output_payload["benchmarks"] if item["metric"] == "engagement_rate")
    assert reach["median"] == 0
    assert reach["percent_change"] is None
    assert rate["current"] == 3.3
    assert rate["median"] == 2.2


def test_exactly_one_experiment_and_strongest_positive_metric_are_returned_for_real_gap():
    result = analyze_post(_media(), [_snapshot(reach=160, views=180, shares=10, saves=0)], peer_metrics=[_peer(index) for index in range(5)],
                          generator=lambda *args, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test")
    assert len(result.output_payload["experiment"]) == 1
    assert result.output_payload["strongest_metric"]["percent_change"] > 0
    assert result.output_payload["what_worked"]
    experiment = result.output_payload["experiment"][0]
    assert experiment["test_variable"]
    assert experiment["metric_to_watch"] == "saves"
    assert experiment["metric_to_watch"] != result.output_payload["strongest_metric"]["metric"]
    assert "Keep the change if" in experiment["decision_rule"]


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
    assert result.model_name == "deterministic-fallback-v5"
    assert "topic" not in result.output_payload["content_attributes"]


def test_young_post_reports_observed_mature_same_format_reference():
    peers = [_peer(index, age_days=20, reach=value) for index, value in enumerate((80, 100, 120))]
    result = analyze_post(_media(age_days=2), [_snapshot(reach=127)], peer_metrics=peers, image_loader=lambda url: None)
    reference = result.output_payload["mature_reference"]
    assert reference["sample_size"] == 3
    assert reference["percent_of_median"] == 127
    assert "still growing" not in reference["text"] or result.output_payload["trend"]["growth_status"] == "still growing"
    assert "127% of your mature Image median" in result.output_payload["verdict"]


def test_wider_reach_dilution_is_not_an_improvement_item_or_experiment():
    peers = [_peer(index, reach=100, engagement_rate=10.0, saves=3) for index in range(5)]
    result = analyze_post(_media(), [_snapshot(reach=180, engagement_rate=5.0, saves=3)], peer_metrics=peers, image_loader=lambda url: None)
    assert result.output_payload["diluted_by_wider_reach"] is True
    assert "diluted by wider reach" in result.output_payload["verdict"]
    assert all(item["metric"] != "engagement_rate" for item in result.output_payload["what_to_improve"])
    assert result.output_payload["experiment"] == []
