import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.post_analysis import PostAnalysisError, analyze_post
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def _media(media_type: str = "IMAGE") -> InstagramMedia:
    return InstagramMedia(id="instagram:media-1", account_id="account-1", instagram_media_id="media-1",
                          media_type=media_type, media_url="https://scontent.cdninstagram.com/post.jpg",
                          caption="A practical tutorial about tying a knot? #magic #learn #creator #tips #tutorial",
                          published_at=NOW - timedelta(days=2), last_synced_at=NOW)


def _snapshot(identifier: str, minutes: int, reach: int, likes: int) -> InstagramInsightSnapshot:
    return InstagramInsightSnapshot(id=identifier, media_id="instagram:media-1", captured_at=NOW + timedelta(minutes=minutes),
                                    reach=reach, views=reach + 100, likes=likes, comments=4, saves=3, shares=2,
                                    engagement_rate=8.5)


def _model_output() -> str:
    return json.dumps({
        "why_it_worked": [{"factor": "Tutorial framing", "estimated_impact": "positive estimate", "explanation": "The useful format aligns with above-average saves."}],
        "recommendations": [{"action": "Ask one specific question.", "reason": "Comments trail the account average.", "expected_impact": "Likely higher comment participation."}],
    })


def test_analysis_builds_scores_benchmarks_patterns_and_confidence_without_predictions():
    received = {}
    def generator(prompt: str, **kwargs):
        received["prompt"] = prompt
        received.update(kwargs)
        return _model_output()

    peer = {"reach": 100, "views": 180, "likes": 10, "comments": 8, "saves": 1, "shares": 1, "engagement_rate": 6.0}
    result = analyze_post(_media(), [_snapshot("snapshot-1", 0, 100, 10), _snapshot("snapshot-2", 30, 160, 18)],
                          peer_metrics=[peer], historical_posts=[{"caption": _media().caption, "media_type": "IMAGE", "metrics": peer}],
                          generator=generator, image_loader=lambda url: (b"image", "image/jpeg"), model_name="test-model")
    assert result.schema_version == "post-analysis-v2"
    assert result.observed_metrics["reach"] == 160
    assert result.metric_deltas["reach"] == 60
    assert result.output_payload["score"]["overall"] >= 0
    assert next(item for item in result.output_payload["benchmarks"] if item["metric"] == "reach")["percent_change"] == 60.0
    assert result.output_payload["confidence"]["score"] > 80
    assert any(item["pattern"] == "Tutorial posts" for item in result.output_payload["content_patterns"])
    assert len(result.output_payload["recommendations"]) == 1
    assert "never predict views" in received["prompt"]
    assert received["image_bytes"] == b"image"


def test_analysis_marks_plateau_and_missing_inputs_in_confidence():
    snapshot = _snapshot("snapshot-1", 0, 100, 10).model_copy(update={"saves": None, "shares": None})
    second = snapshot.model_copy(update={"id": "snapshot-2", "captured_at": NOW + timedelta(minutes=10)})
    result = analyze_post(_media("VIDEO"), [snapshot, second], generator=lambda prompt, **kwargs: _model_output(),
                          image_loader=lambda url: None, model_name="test-model")
    assert any("stalled" in item for item in result.output_payload["risks"])
    unavailable = {item["name"]: item["available"] for item in result.output_payload["confidence"]["inputs"]}
    assert unavailable["Full Video"] is False
    assert unavailable["Watch Time"] is False


def test_analysis_rejects_missing_snapshot_and_falls_back_for_invalid_model_output():
    with pytest.raises(PostAnalysisError):
        analyze_post(_media(), [], model_name="test-model")
    result = analyze_post(_media(), [_snapshot("snapshot-1", 0, 100, 10)], generator=lambda prompt, **kwargs: "not json",
                          image_loader=lambda url: None, model_name="test-model")
    assert result.model_name == "deterministic-fallback-v2"
    assert result.output_payload["recommendations"]
    assert result.output_payload["content_attributes"]["topic"] == "Tutorials"


def test_analysis_works_without_a_configured_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    result = analyze_post(_media(), [_snapshot("snapshot-1", 0, 100, 10)],
                          generator=lambda *args, **kwargs: pytest.fail("generator should not run"),
                          image_loader=lambda url: None)
    assert result.model_name == "deterministic-fallback-v2"
    assert result.output_payload["score"]["overall"] >= 0
