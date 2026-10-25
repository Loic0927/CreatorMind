import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.account_context import AccountContextFields, serialize_account_context
from backend.services.post_analysis import PostAnalysisError, analyze_post
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def _media(identifier: str = "media-1", media_type: str = "IMAGE") -> InstagramMedia:
    return InstagramMedia(
        id=f"instagram:{identifier}", account_id="account-1", instagram_media_id=identifier,
        media_type=media_type, media_url="https://scontent.cdninstagram.com/post.jpg",
        caption="A practical tutorial about tying a knot? #magic #learn #creator #tips #tutorial",
        published_at=NOW - timedelta(days=2), last_synced_at=NOW,
    )


def _snapshot(identifier: str, minutes: int, reach: int, likes: int, *, views: int | None = None,
              comments: int | None = 4, saves: int | None = 3, shares: int | None = 2,
              engagement_rate: float = 8.5) -> InstagramInsightSnapshot:
    return InstagramInsightSnapshot(
        id=identifier, media_id="instagram:media-1", captured_at=NOW + timedelta(minutes=minutes),
        reach=reach, views=views if views is not None else reach + 100, likes=likes, comments=comments,
        saves=saves, shares=shares, engagement_rate=engagement_rate,
    )


def _peer(index: int, *, media_type: str = "IMAGE", reach: int = 100, views: int = 180,
          engagement_rate: float = 6.0, saves: int | None = 1, shares: int | None = 1) -> dict:
    return {
        "media_type": media_type,
        "published_at": (NOW - timedelta(days=index + 3)).isoformat(),
        "captured_at": (NOW - timedelta(days=index)).isoformat(),
        "metrics": {"reach": reach, "views": views, "likes": 10, "comments": 8,
                    "saves": saves, "shares": shares, "engagement_rate": engagement_rate},
    }


def _model_output() -> str:
    return json.dumps({
        "why_it_worked": [{
            "title": "Possible utility signal",
            "evidence": "Saves are above the comparison baseline.",
            "interpretation": "The tutorial may have offered reusable value; this is not a proven cause.",
            "why_it_matters": "Repeat one comparable test before treating it as a pattern.",
        }],
        "recommendations": [{"action": "Test one CTA wording change.",
                             "reason": "Comments are below the comparison baseline.",
                             "expected_outcome": "Observe whether comment rate changes."}],
    })


def test_analysis_reports_limited_sample_median_basis_and_real_data_range():
    received = {}

    def generator(prompt: str, **kwargs):
        received["prompt"] = prompt
        return _model_output()

    result = analyze_post(
        _media(), [_snapshot("snapshot-1", 0, 100, 10), _snapshot("snapshot-2", 30, 160, 18)],
        peer_metrics=[_peer(1, reach=100), _peer(2, reach=300)], account_context="Beginner-friendly magic education",
        generator=generator,
        image_loader=lambda url: (b"image", "image/jpeg"), model_name="test-model",
    )
    assert result.schema_version == "post-analysis-v3"
    baseline = result.output_payload["baseline"]
    assert baseline["sample_size"] == 2
    assert baseline["limited_sample"] is True
    assert baseline["group"] == "overall_account"
    assert baseline["published_range"]["start"]
    reach = next(item for item in result.output_payload["benchmarks"] if item["metric"] == "reach")
    assert reach["median"] == 200
    assert reach["average"] == 200
    assert reach["percent_change"] == -20
    assert "limited sample" in baseline["sample_notice"].lower()
    assert "audience retention" in received["prompt"].lower()
    assert "beginner-friendly magic education" in received["prompt"].lower()
    assert result.content_payload["account_context_used"] is True
    assert result.content_payload["account_context_relevance"] == "related"


def test_analysis_ignores_account_context_when_post_is_unrelated():
    prompts = []
    context = serialize_account_context(AccountContextFields(
        account_theme="Landscape photography",
        about_this_account="Mountain travel photography",
        target_audience="Outdoor photography enthusiasts",
    ))

    result = analyze_post(
        _media(), [_snapshot("snapshot-1", 0, 100, 10)],
        account_context=context,
        generator=lambda prompt, **kwargs: prompts.append(prompt) or _model_output(),
        image_loader=lambda url: None,
        model_name="test-model",
    )

    assert result.content_payload["account_context_used"] is False
    assert result.content_payload["account_context_relevance"] == "none"
    assert "Landscape photography" not in prompts[0]


def test_evidence_quality_drops_for_missing_retention_history_and_metrics():
    snapshot = _snapshot("snapshot-1", 0, 100, 10, saves=None, shares=None)
    unsupported_claim = json.dumps({
        "why_it_worked": [{
            "title": "Strong hook",
            "evidence": "The opening caused viewers to stay.",
            "interpretation": "Retention proves there was no drop-off.",
            "why_it_matters": "Keep the pacing.",
        }],
        "recommendations": [],
    })
    result = analyze_post(
        _media(media_type="VIDEO"), [snapshot], peer_metrics=[_peer(1)],
        generator=lambda prompt, **kwargs: unsupported_claim, image_loader=lambda url: None, model_name="test-model",
    )
    quality = result.output_payload["evidence_quality"]
    assert quality["label"] == "Evidence quality"
    assert "not the probability" in quality["meaning"]
    assert quality["level"] == "Limited"
    assert "Average watch time" in quality["missing_evidence"]
    assert "Audience retention" in quality["missing_evidence"]
    assert any("cannot diagnose hook, pacing, or drop-off" in item for item in result.output_payload["data_gaps"])
    assert result.output_payload["why_it_worked"] == []
    assert "shareability" not in result.output_payload["score"]["categories"]


def test_two_snapshots_are_described_neutrally_not_as_a_stalled_growth_trend():
    first = _snapshot("snapshot-1", 0, 100, 10)
    second = first.model_copy(update={"id": "snapshot-2", "captured_at": NOW + timedelta(minutes=60)})
    result = analyze_post(
        _media(), [first, second], peer_metrics=[_peer(index) for index in range(1, 6)],
        generator=lambda prompt, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test-model",
    )
    trend = result.output_payload["trend"]
    assert trend["status"] == "insufficient_history"
    assert trend["observation_count"] == 2
    assert "changed little" in trend["summary"]
    rendered = json.dumps(result.output_payload).lower()
    assert "stalled" not in rendered
    assert "plateau" not in rendered
    assert "enough history" in trend["summary"]


def test_low_reach_high_interaction_post_keeps_dimensions_visible_and_score_explainable():
    peers = [_peer(index, reach=1000, views=1200, engagement_rate=5, saves=10, shares=5) for index in range(1, 6)]
    low_reach = analyze_post(
        _media("low"), [_snapshot("low-1", 0, 300, 20, views=400, saves=15, shares=10, engagement_rate=15)],
        peer_metrics=peers, generator=lambda prompt, **kwargs: _model_output(), image_loader=lambda url: None,
        model_name="test-model",
    ).output_payload["score"]
    higher_reach = analyze_post(
        _media("high"), [_snapshot("high-1", 0, 1200, 20, views=1400, saves=6, shares=4, engagement_rate=3)],
        peer_metrics=peers, generator=lambda prompt, **kwargs: _model_output(), image_loader=lambda url: None,
        model_name="test-model",
    ).output_payload["score"]
    assert low_reach["categories"]["exposure"] < higher_reach["categories"]["exposure"]
    assert low_reach["categories"]["interaction_quality"] > higher_reach["categories"]["interaction_quality"]
    # The low-reach post can still rank higher because both quality dimensions
    # are much stronger; the exposed category scores make that tradeoff visible.
    assert low_reach["overall"] > higher_reach["overall"]
    expected = round((low_reach["categories"]["exposure"] * 50
                      + low_reach["categories"]["interaction_quality"] * 35
                      + low_reach["categories"]["shareability"] * 15) / 100)
    assert low_reach["overall"] == expected
    assert low_reach["weights"] == {"exposure": 50, "interaction_quality": 35, "shareability": 15}
    assert "extreme values have less influence" in low_reach["method"]


def test_same_media_type_baseline_is_used_only_with_enough_comparable_posts():
    peers = [_peer(index, media_type="IMAGE", reach=100 + index) for index in range(1, 4)]
    peers += [_peer(index + 10, media_type="VIDEO", reach=1000) for index in range(3)]
    result = analyze_post(
        _media(media_type="IMAGE"), [_snapshot("snapshot-1", 0, 150, 10)], peer_metrics=peers,
        generator=lambda prompt, **kwargs: _model_output(), image_loader=lambda url: None, model_name="test-model",
    )
    assert result.output_payload["baseline"]["group"] == "same_media_type"
    assert result.output_payload["baseline"]["sample_size"] == 3
    assert next(item for item in result.output_payload["benchmarks"] if item["metric"] == "reach")["median"] == 102


def test_analysis_rejects_missing_snapshot_and_falls_back_for_invalid_model_output():
    with pytest.raises(PostAnalysisError):
        analyze_post(_media(), [], model_name="test-model")
    result = analyze_post(
        _media(), [_snapshot("snapshot-1", 0, 100, 10)], generator=lambda prompt, **kwargs: "not json",
        image_loader=lambda url: None, model_name="test-model",
    )
    assert result.model_name == "deterministic-fallback-v3"
    assert result.output_payload["recommendations"]
    assert result.output_payload["content_attributes"]["topic"] == "Tutorials"


def test_analysis_works_without_a_configured_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    result = analyze_post(
        _media(), [_snapshot("snapshot-1", 0, 100, 10)],
        generator=lambda *args, **kwargs: pytest.fail("generator should not run"), image_loader=lambda url: None,
    )
    assert result.model_name == "deterministic-fallback-v3"
    assert result.output_payload["score"]["overall"] >= 0
