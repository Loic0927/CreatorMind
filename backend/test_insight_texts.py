from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
    published_at = datetime(2026, 10, 1, tzinfo=UTC)
    return {
        "tracked_post_id": identifier,
        "has_metrics": True,
        "mature": mature,
        "format_key": "video" if media_type == "REELS" else "image",
        "media_type": media_type,
        "media_type_label": "Reel" if media_type == "REELS" else "Image",
        "caption": f"caption-{identifier}",
        "published_at": published_at.isoformat(),
        "latest_captured_at": (published_at + timedelta(days=20)).isoformat(),
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


def test_next_post_suggestion_reflects_the_latest_post_against_high_performing_history(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"history-{index}", index * 100) for index in range(1, 7)]
    latest = _post("latest", 10_000)
    latest["published_at"] = datetime(2026, 11, 1, tzinfo=UTC).isoformat()
    posts.append(latest)
    captured = {}

    def generate(prompt: str) -> str:
        captured["data"] = _prompt_data(prompt)
        return "The latest post is performing strongly against comparable history. Keep the clear action premise."

    result = insight_texts.next_post_suggestion("user", posts, {}, generator=generate)

    assert (
        result
        == "Reflection: The latest post is performing strongly against comparable history. Keep the clear action premise."
    )
    assert captured["data"]["latest_post"]["role"] == "latest"
    assert captured["data"]["latest_post"]["outcome"] == "stronger_than_history"
    assert captured["data"]["latest_post"]["caption"] == "caption-latest"
    assert len(captured["data"]["historical_examples"]) == 2
    assert all(item["role"] == "historical_high_performer" for item in captured["data"]["historical_examples"])
    assert all("performance_signals" in item for item in captured["data"]["historical_examples"])


def test_next_post_suggestion_requires_six_historical_posts_with_rate_signals(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"post-{index}", index * 100, mature=index < 6) for index in range(1, 7)]

    assert insight_texts.next_post_suggestion("user", posts, {}, generator=lambda _: "unused") is None


def test_next_post_suggestion_includes_video_watch_time_bucket_when_available(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"video-{index}", index * 100, media_type="REELS") for index in range(1, 8)]
    posts[-1]["published_at"] = datetime(2026, 11, 1, tzinfo=UTC).isoformat()
    captured = {}

    def generate(prompt: str) -> str:
        captured["items"] = _prompt_data(prompt)
        return "Reflection: The latest sequence is holding attention well. Keep its clear progression."

    insight_texts.next_post_suggestion("video-user", posts, {}, generator=generate)

    assert captured["items"]["latest_post"]["format"] == "Reel"
    assert captured["items"]["latest_post"]["performance_signals"]["average_watch_time"] in {
        "higher",
        "lower",
        "usual",
    }


def test_next_post_suggestion_uses_video_watch_time_when_reach_is_missing(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"video-{index}", index * 100, media_type="REELS") for index in range(1, 8)]
    posts[-1]["published_at"] = datetime(2026, 11, 1, tzinfo=UTC).isoformat()
    for post in posts:
        post["metrics"].pop("reach")
    captured = {}

    def generate(prompt: str) -> str:
        captured["items"] = _prompt_data(prompt)
        return "Reflection: The latest viewing pattern is distinct from history. Consider one clearer visual sequence."

    assert insight_texts.next_post_suggestion("video-user", posts, {}, generator=generate)
    assert captured["items"]["latest_post"]["performance_signals"]["average_watch_time"] in {
        "higher",
        "lower",
        "usual",
    }


def test_next_post_suggestion_uses_same_age_history_for_a_newest_young_post(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    published = datetime(2026, 11, 1, tzinfo=UTC)
    posts = []
    for index in range(6):
        post = _post(f"history-{index}", 100 + index * 100)
        historic_published = published - timedelta(days=30 + index)
        post["published_at"] = historic_published.isoformat()
        post["history"] = [
            {
                "captured_at": (historic_published + timedelta(hours=24)).isoformat(),
                "metrics": post["metrics"],
            }
        ]
        posts.append(post)
    latest = _post("latest", 1_000, mature=False)
    latest["published_at"] = published.isoformat()
    latest["latest_captured_at"] = (published + timedelta(hours=24)).isoformat()
    posts.append(latest)
    captured = {}

    def generate(prompt: str) -> str:
        captured["data"] = _prompt_data(prompt)
        return "Reflection: The newest post is stronger than its same-age history. Keep its direct premise."

    result = insight_texts.next_post_suggestion(
        "user",
        posts,
        {},
        generator=generate,
    )

    assert result is not None
    assert captured["data"]["latest_post"]["comparison_basis"] == "same_age"


def test_next_post_suggestion_uses_mature_rate_history_when_same_age_snapshots_are_missing(monkeypatch):
    repository = _TextCacheRepository()
    monkeypatch.setattr(insight_texts, "get_content_repository", lambda: repository)
    posts = [_post(f"history-{index}", 100 + index * 100) for index in range(6)]
    latest = _post("latest", 1_000, mature=False)
    latest["published_at"] = datetime(2026, 11, 1, tzinfo=UTC).isoformat()
    latest["latest_captured_at"] = datetime(2026, 11, 2, tzinfo=UTC).isoformat()
    posts.append(latest)
    captured = {}

    def generate(prompt: str) -> str:
        captured["data"] = _prompt_data(prompt)
        return "Reflection: The latest response is stronger than its mature history. Keep the direct premise."

    assert insight_texts.next_post_suggestion("user", posts, {}, generator=generate)
    assert captured["data"]["latest_post"]["comparison_basis"] == "latest_response_rates"


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
    posts = [_post(f"post-{index}", index * 100) for index in range(1, 8)]
    posts[-1]["published_at"] = datetime(2026, 11, 1, tzinfo=UTC).isoformat()

    first = insight_texts.next_post_suggestion(
        "user",
        posts,
        {},
        generator=lambda _: "Reflection: Keep the clearer opening, while treating the result cautiously.",
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
    assert repository.get_text_cache("user", insight_texts.REFLECTION_CACHE_KEY).text == first


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
