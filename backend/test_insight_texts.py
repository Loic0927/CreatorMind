from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import backend.services.insight_texts as insight_texts
from backend.services.gemini import GeminiUpstreamError


class _TextCacheRepository:
    def __init__(self) -> None:
        self.cache = {}
        self.writes = []

    def get_text_cache(self, user_id, cache_key):
        return self.cache.get((user_id, cache_key))

    def upsert_text_cache(self, item):
        self.cache[(item.user_id, item.cache_key)] = item
        self.writes.append(item)
        return item


@pytest.fixture(autouse=True)
def ai_processing_consent(monkeypatch):
    monkeypatch.setattr(insight_texts, "has_ai_processing_consent", lambda _user_id: True)


def _comment(text: str, *, owner: bool = False):
    return SimpleNamespace(
        text=text,
        is_owner_reply=owner,
        like_count=0,
        timestamp=datetime(2026, 11, 1, tzinfo=UTC),
    )


def _post(identifier: str, rate: int, *, mature: bool = True, media_type: str = "IMAGE"):
    return {
        "tracked_post_id": identifier,
        "has_metrics": True,
        "mature": mature,
        "format_key": "video" if media_type == "REELS" else "image",
        "media_type": media_type,
        "media_type_label": "Reel" if media_type == "REELS" else "Image",
        "caption": f"caption-{identifier}",
        "metrics": {
            "reach": 1000,
            "views": rate,
            "saves": rate // 10,
            "shares": rate // 20,
            "comments": rate // 25,
            "average_watch_time_ms": rate * 10 if media_type == "REELS" else None,
        },
    }


def _prompt_data(prompt: str) -> list[dict]:
    _, marker, serialized = prompt.partition("UNTRUSTED_POST_DATA_JSON=")
    assert marker
    return json.loads(serialized)


def test_next_post_suggestion_uses_mature_rate_ranked_distinct_top_and_bottom_posts(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"post-{index}", index * 100) for index in range(1, 7)]
    # An immature outlier must not displace one of the mature comparison posts.
    posts.append(_post("young-outlier", 100_000, mature=False))
    comments = {
        "post-6": [_comment("viewer comment") for _ in range(8)] + [_comment("owner reply", owner=True)],
    }
    captured = {}

    def generate(prompt: str) -> str:
        captured["items"] = _prompt_data(prompt)
        return "Compare a clear opening with a slower one, although the sample is limited. Try a clearer opening."

    result = insight_texts.next_post_suggestion("user", posts, comments, generator=generate)

    assert (
        result
        == "Suggestion: Compare a clear opening with a slower one, although the sample is limited. Try a clearer opening."
    )
    items = captured["items"]
    assert [item["role"] for item in items] == ["top", "top", "top", "bottom", "bottom"]
    assert len({item["caption"] for item in items}) == 5
    assert "caption-young-outlier" not in {item["caption"] for item in items}
    assert all(item["format"] == "Image" for item in items)
    assert all("caption_length" in item and "rate_signals" in item for item in items)
    assert all("metrics" not in item for item in items)
    assert len(items[0]["audience_comments"]) == 8
    assert "owner reply" not in items[0]["audience_comments"]


def test_next_post_suggestion_requires_six_mature_posts_with_rate_signals(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"post-{index}", index * 100, mature=index < 6) for index in range(1, 7)]

    assert insight_texts.next_post_suggestion("user", posts, {}, generator=lambda _: "unused") is None


def test_next_post_suggestion_includes_video_watch_time_bucket_when_available(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"video-{index}", index * 100, media_type="REELS") for index in range(1, 7)]
    captured = {}

    def generate(prompt: str) -> str:
        captured["items"] = _prompt_data(prompt)
        return "Suggestion: Compare the clearest sequence, with uncertainty. Consider testing a clearer sequence."

    insight_texts.next_post_suggestion("video-user", posts, {}, generator=generate)

    assert all(item["format"] == "Reel" for item in captured["items"])
    assert all(item["average_watch_time_bucket"] in {"higher", "lower", "usual"} for item in captured["items"])


def test_next_post_suggestion_uses_video_watch_time_when_reach_is_missing(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"video-{index}", index * 100, media_type="REELS") for index in range(1, 7)]
    for post in posts:
        post["metrics"].pop("reach")
    captured = {}

    def generate(prompt: str) -> str:
        captured["items"] = _prompt_data(prompt)
        return "Suggestion: Test one clearer visual sequence, while treating this pattern as uncertain."

    assert insight_texts.next_post_suggestion("video-user", posts, {}, generator=generate)
    assert all(item["average_watch_time_bucket"] in {"higher", "lower", "usual"} for item in captured["items"])


def test_audience_cache_keeps_the_last_good_text_when_generation_fails_after_inputs_change(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    comments = [_comment("Love the tutorial"), _comment("Helpful explanation"), _comment("Please make another")]

    first = insight_texts.audience_description(
        "user", "tracked", comments, generator=lambda _: "Viewers repeatedly asked for another explanation."
    )
    changed_comments = [*comments, _comment("What is the next step?")]
    second = insight_texts.audience_description(
        "user",
        "tracked",
        changed_comments,
        generator=lambda _: (_ for _ in ()).throw(GeminiUpstreamError("unavailable")),
    )

    assert second == first
    assert len(repository.writes) == 1
    assert repository.get_text_cache("user", "audience:tracked").text == first


def test_next_post_cache_keeps_the_last_good_text_when_generation_fails_after_inputs_change(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"post-{index}", index * 100) for index in range(1, 7)]

    first = insight_texts.next_post_suggestion(
        "user", posts, {}, generator=lambda _: "Suggestion: Test a clearer opening, with uncertainty."
    )
    posts[-1]["caption"] = "changed caption changes the cache input"
    second = insight_texts.next_post_suggestion(
        "user",
        posts,
        {},
        generator=lambda _: (_ for _ in ()).throw(GeminiUpstreamError("unavailable")),
    )

    assert second == first
    assert len(repository.writes) == 1
    assert repository.get_text_cache("user", "next-post-suggestion").text == first


def test_cached_text_keeps_the_last_good_text_when_validation_rejects_new_output(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)

    first = insight_texts._cached_text(
        "user",
        "next-post-suggestion",
        None,
        {"version": 1},
        "prompt",
        maximum_sentences=2,
        generator=lambda _: "Suggestion: Try one focused change.",
        validator=lambda _: True,
    )
    second = insight_texts._cached_text(
        "user",
        "next-post-suggestion",
        None,
        {"version": 2},
        "changed prompt",
        maximum_sentences=2,
        generator=lambda _: "invalid output",
        validator=lambda _: False,
    )

    assert second == first
    assert len(repository.writes) == 1


def test_audience_and_next_post_generation_require_ai_processing_consent(monkeypatch):
    repository = _TextCacheRepository()
    posts = [_post(f"post-{index}", index * 100) for index in range(1, 7)]
    comments = [_comment("One"), _comment("Two"), _comment("Three")]
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    monkeypatch.setattr(insight_texts, "has_ai_processing_consent", lambda _user_id: False)

    def forbidden(_prompt):
        raise AssertionError("generation must not run without consent")

    assert insight_texts.audience_description("user", "tracked", comments, generator=forbidden) is None
    assert insight_texts.next_post_suggestion("user", posts, {}, generator=forbidden) is None
    assert repository.writes == []
