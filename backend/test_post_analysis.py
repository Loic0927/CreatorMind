from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from backend.services.insight_texts import post_feedback, post_summary

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
def snapshot(hours, views):
    return SimpleNamespace(captured_at=NOW + timedelta(hours=hours), views=views, reach=views, engagement_rate=5.0, shares=1, saves=1, comments=1)

def test_summary_is_hidden_for_one_snapshot_without_calling_model():
    called = False
    def generator(_):
        nonlocal called
        called = True
        return "filler"
    assert post_summary("u", "t", [snapshot(0, 10)], generator=generator) is None
    assert called is False

def test_summary_is_hidden_when_history_has_no_non_obvious_movement():
    assert post_summary("u", "t", [snapshot(0, 10), snapshot(1, 10)], generator=lambda _: "filler") is None


def test_post_feedback_is_capped_at_three_sentences_and_uses_no_comment_content(monkeypatch):
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    prompts = []
    media = SimpleNamespace(caption="A quick rope tutorial", media_type="REELS")
    latest = snapshot(2, 150)
    analysis = {
        "media_format": "Reel",
        "usual_ranges": [{"metric": "reach", "status": "above"}],
        "stands_out": [{"metric": "reach"}],
        "weaker": [],
    }

    result = post_feedback(
        "user-feedback",
        "tracked-feedback",
        media,
        latest,
        analysis,
        generator=lambda prompt: prompts.append(prompt) or "Strong opening. Clear payoff. Worth adapting. Extra sentence.",
    )

    assert result == "Strong opening. Clear payoff. Worth adapting."
    assert "A quick rope tutorial" in prompts[0]
    assert "audience_comments" not in prompts[0]


def test_post_feedback_passes_available_video_content_to_model(monkeypatch):
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    captured = {}
    media = SimpleNamespace(id="media-video", caption="A visual trick", media_type="REELS")
    analysis = {"media_format": "Reel", "usual_ranges": [], "stands_out": [], "weaker": []}

    result = post_feedback(
        "user-video-feedback",
        "tracked-video-feedback",
        media,
        snapshot(2, 150),
        analysis,
        generator=lambda prompt, **kwargs: captured.update(kwargs) or "The visual sequence is easy to follow.",
        media_loader=lambda: (b"video-content", "video/mp4"),
    )

    assert result == "The visual sequence is easy to follow."
    assert captured == {"image_bytes": b"video-content", "image_mime_type": "video/mp4"}
