import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.post_analysis import PostAnalysisError, analyze_post
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def _media(media_type: str = "IMAGE") -> InstagramMedia:
    return InstagramMedia(
        id="instagram:media-1",
        account_id="account-1",
        instagram_media_id="media-1",
        media_type=media_type,
        media_url="https://scontent.cdninstagram.com/post.jpg",
        thumbnail_url=None,
        caption="A practical tutorial about tying a knot.",
        published_at=NOW - timedelta(days=2),
        last_synced_at=NOW,
    )


def _snapshot(identifier: str, minutes: int, reach: int, likes: int) -> InstagramInsightSnapshot:
    return InstagramInsightSnapshot(
        id=identifier,
        media_id="instagram:media-1",
        captured_at=NOW + timedelta(minutes=minutes),
        reach=reach,
        views=reach + 100,
        likes=likes,
        comments=4,
        saves=3,
        shares=2,
        engagement_rate=8.5,
    )


def test_analysis_uses_content_metrics_history_and_image_without_predictions():
    received = {}

    def generator(prompt: str, **kwargs):
        received["prompt"] = prompt
        received.update(kwargs)
        return json.dumps(
            {
                "summary": "The tutorial earned additional reach and saves.",
                "strengths": ["Clear educational subject."],
                "concerns": ["Comments remained flat."],
                "recommendations": ["Show the finished knot in the opening frame."],
                "missing_inputs": [],
            }
        )

    result = analyze_post(
        _media(),
        [_snapshot("snapshot-1", 0, 100, 10), _snapshot("snapshot-2", 30, 160, 18)],
        generator=generator,
        image_loader=lambda url: (b"image", "image/jpeg"),
        model_name="test-model",
    )

    assert result.source_snapshot_ids == ["snapshot-1", "snapshot-2"]
    assert result.observed_metrics["reach"] == 160
    assert result.metric_deltas["reach"] == 60
    assert result.content_payload["visual_context_used"] is True
    assert received["image_bytes"] == b"image"
    assert received["image_mime_type"] == "image/jpeg"
    assert "predict views" in received["prompt"]
    assert "A practical tutorial" in received["prompt"]
    assert result.output_payload["recommendations"] == [
        "Show the finished knot in the opening frame."
    ]


def test_analysis_marks_missing_metrics_and_unavailable_visual_context():
    snapshot = _snapshot("snapshot-1", 0, 100, 10).model_copy(
        update={"saves": None, "shares": None}
    )
    result = analyze_post(
        _media("VIDEO"),
        [snapshot],
        generator=lambda prompt, **kwargs: json.dumps(
            {
                "summary": "Only available evidence was considered.",
                "strengths": [],
                "concerns": [],
                "recommendations": ["Refresh metrics later."],
                "missing_inputs": [],
            }
        ),
        image_loader=lambda url: None,
        model_name="test-model",
    )
    assert result.metric_deltas["reach"] is None
    assert any("saves is unavailable" in item for item in result.output_payload["missing_inputs"])
    assert any("Visual content was unavailable" in item for item in result.output_payload["missing_inputs"])


def test_analysis_rejects_missing_snapshot_and_invalid_model_output():
    with pytest.raises(PostAnalysisError):
        analyze_post(_media(), [], model_name="test-model")
    with pytest.raises(PostAnalysisError):
        analyze_post(
            _media(),
            [_snapshot("snapshot-1", 0, 100, 10)],
            generator=lambda prompt, **kwargs: "not json",
            image_loader=lambda url: None,
            model_name="test-model",
        )
