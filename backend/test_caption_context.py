import base64

from backend import main
from backend.auth import AuthenticatedUser
from backend.services.account_context import AccountContextFields, serialize_account_context


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id="user-1", email="creator@example.test", token_hash="hash")


def _request(use_account_context: bool) -> main.MobileCaptionRequest:
    return main.MobileCaptionRequest(
        information="A short tutorial about a rope trick",
        goal="Educate",
        platform="Instagram",
        platforms=["Instagram"],
        use_account_context=use_account_context,
    )


def test_caption_uses_saved_account_context_when_enabled(monkeypatch):
    prompts = []
    stored = serialize_account_context(AccountContextFields(
        account_theme="Rope magic lessons",
        about_this_account="Short educational demonstrations of practical rope techniques.",
        target_audience="People learning beginner rope magic",
    ))
    monkeypatch.setattr(main, "get_account_context", lambda user_id: stored)
    monkeypatch.setattr(main, "generate_gemini_content", lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Try this trick\nHASHTAGS: #magic")

    result = main.mobile_caption(_request(True), _user())

    assert result.caption == "Try this trick"
    assert result.hashtags == "#magic"
    assert "HASHTAGS:" in prompts[0]
    assert "Rope magic lessons" in prompts[0]
    assert "People learning beginner rope magic" in prompts[0]


def test_caption_ignores_saved_account_context_when_disabled(monkeypatch):
    prompts = []
    monkeypatch.setattr(main, "get_account_context", lambda user_id: "Must not appear")
    monkeypatch.setattr(main, "generate_gemini_content", lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Standalone\nHASHTAGS: #post")

    main.mobile_caption(_request(False), _user())

    assert "Must not appear" not in prompts[0]


def test_caption_ignores_unrelated_account_context(monkeypatch):
    prompts = []
    stored = serialize_account_context(AccountContextFields(
        account_theme="Landscape photography",
        about_this_account="Mountain travel photos",
        target_audience="Outdoor photography enthusiasts",
    ))
    monkeypatch.setattr(main, "get_account_context", lambda user_id: stored)
    monkeypatch.setattr(main, "generate_gemini_content", lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Test\nHASHTAGS: #test")

    main.mobile_caption(_request(True), _user())

    assert "Landscape photography" not in prompts[0]
    assert "Outdoor photography enthusiasts" not in prompts[0]
    assert "Account context reference" not in prompts[0]


def test_caption_passes_short_video_to_model(monkeypatch):
    captured = {}
    request = _request(False).model_copy(update={
        "media": main.MobileCaptionMedia(
            mime_type="video/mp4",
            data=base64.b64encode(b"short-video").decode("ascii"),
            duration_seconds=42,
        )
    })
    monkeypatch.setattr(
        main,
        "generate_gemini_content",
        lambda prompt, **kwargs: captured.update(kwargs) or "CAPTION: Video caption\nHASHTAGS: #video #short",
    )

    result = main.mobile_caption(request, _user())

    assert captured["image_bytes"] == b"short-video"
    assert captured["image_mime_type"] == "video/mp4"
    assert result.hashtags == "#video #short"
