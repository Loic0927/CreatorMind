import base64
from pathlib import Path

import pytest

from backend import caption_api
from backend.auth import AuthenticatedUser
from backend.rate_limit import reset_rate_limits
from backend.services.account_context import AccountContextFields, serialize_account_context
from backend.storage.database import engine_for_url, session_factory_for_url


@pytest.fixture(autouse=True)
def _fresh_rate_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{(tmp_path / 'caption.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine_for_url(database_url)
    reset_rate_limits()
    monkeypatch.setattr(caption_api, "has_ai_processing_consent", lambda user_id: True)
    yield
    reset_rate_limits()
    engine_for_url(database_url).dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id="user-1", email="creator@example.test", token_hash="hash")


def _request(use_account_context: bool) -> caption_api.CaptionRequest:
    return caption_api.CaptionRequest(
        information="A short tutorial about a rope trick",
        goal="Educate",
        platform="Instagram",
        platforms=["Instagram"],
        use_account_context=use_account_context,
    )


def test_caption_uses_saved_account_context_when_enabled(monkeypatch):
    prompts = []
    stored = serialize_account_context(
        AccountContextFields(
            account_theme="Rope magic lessons",
            about_this_account="Short educational demonstrations of practical rope techniques.",
            target_audience="People learning beginner rope magic",
            preferred_hashtags=("#RopeMagic", "#Tutorial"),
        )
    )
    monkeypatch.setattr(caption_api, "get_account_context", lambda user_id: stored)
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Try this trick\nHASHTAGS: #magic",
    )

    result = caption_api.generate_caption(_request(True), _user())

    assert result.caption == "Try this trick"
    assert result.hashtags == "#magic"
    assert "HASHTAGS:" in prompts[0]
    assert "Rope magic lessons" in prompts[0]
    assert "People learning beginner rope magic" in prompts[0]
    assert "Preferred Hashtags (use only when relevant): #RopeMagic #Tutorial" in prompts[0]


def test_caption_ignores_saved_account_context_when_disabled(monkeypatch):
    prompts = []
    monkeypatch.setattr(caption_api, "get_account_context", lambda user_id: "Must not appear")
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Standalone\nHASHTAGS: #post",
    )

    caption_api.generate_caption(_request(False), _user())

    assert "Must not appear" not in prompts[0]


def test_caption_ignores_unrelated_account_context(monkeypatch):
    prompts = []
    stored = serialize_account_context(
        AccountContextFields(
            account_theme="Landscape photography",
            about_this_account="Mountain travel photos",
            target_audience="Outdoor photography enthusiasts",
        )
    )
    monkeypatch.setattr(caption_api, "get_account_context", lambda user_id: stored)
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Test\nHASHTAGS: #test",
    )

    caption_api.generate_caption(_request(True), _user())

    assert "Landscape photography" not in prompts[0]
    assert "Outdoor photography enthusiasts" not in prompts[0]
    assert "Account context reference" not in prompts[0]


def test_caption_passes_short_video_to_model(monkeypatch):
    captured = {}
    request = _request(False).model_copy(
        update={
            "media": caption_api.CaptionMedia(
                mime_type="video/mp4",
                data=base64.b64encode(b"short-video").decode("ascii"),
                duration_seconds=42,
            )
        }
    )
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: captured.update(kwargs) or "CAPTION: Video caption\nHASHTAGS: #video #short",
    )

    result = caption_api.generate_caption(request, _user())

    assert captured["image_bytes"] == b"short-video"
    assert captured["image_mime_type"] == "video/mp4"
    assert result.hashtags == "#video #short"


def test_caption_honours_requested_hashtag_limit_and_removes_duplicates(monkeypatch):
    prompts = []
    request = _request(False).model_copy(update={"hashtag_count": 2})
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Test\nHASHTAGS: #one #two #one #three",
    )

    result = caption_api.generate_caption(request, _user())

    assert result.hashtags == "#one #two"
    assert "exactly 2 concise" in prompts[0]


def test_caption_can_generate_without_hashtags(monkeypatch):
    request = _request(False).model_copy(update={"hashtag_count": 0})
    monkeypatch.setattr(
        caption_api,
        "generate_gemini_content",
        lambda prompt, **kwargs: "CAPTION: No tags\nHASHTAGS: #ignored",
    )

    assert caption_api.generate_caption(request, _user()).hashtags == ""


def test_caption_generation_is_rate_limited_per_user(monkeypatch):
    monkeypatch.setenv("POSTBRIDGE_CAPTION_LIMIT_PER_HOUR", "2")
    monkeypatch.setattr(caption_api, "generate_gemini_content", lambda prompt, **kwargs: "CAPTION: Hi\nHASHTAGS:")
    caption_api.generate_caption(_request(False), _user())
    caption_api.generate_caption(_request(False), _user())

    with pytest.raises(caption_api.HTTPException) as limited:
        caption_api.generate_caption(_request(False), _user())
    assert limited.value.status_code == 429

    other = AuthenticatedUser(id="user-2", email="other@example.test", token_hash="other")
    assert caption_api.generate_caption(_request(False), other).caption == "Hi"


def test_caption_requires_explicit_ai_processing_consent(monkeypatch):
    monkeypatch.setattr(caption_api, "has_ai_processing_consent", lambda user_id: False)

    with pytest.raises(caption_api.HTTPException) as rejected:
        caption_api.generate_caption(_request(False), _user())

    assert rejected.value.status_code == 403
    assert rejected.value.detail["code"] == "consent_required"
