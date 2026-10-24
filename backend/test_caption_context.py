from backend import main
from backend.auth import AuthenticatedUser


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
    monkeypatch.setattr(main, "get_account_context", lambda user_id: "Beginner-friendly magic lessons")
    monkeypatch.setattr(main, "generate_gemini_content", lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Try this trick\nHASHTAGS: #magic")

    result = main.mobile_caption(_request(True), _user())

    assert result.caption == "Try this trick"
    assert "Beginner-friendly magic lessons" in prompts[0]


def test_caption_ignores_saved_account_context_when_disabled(monkeypatch):
    prompts = []
    monkeypatch.setattr(main, "get_account_context", lambda user_id: "Must not appear")
    monkeypatch.setattr(main, "generate_gemini_content", lambda prompt, **kwargs: prompts.append(prompt) or "CAPTION: Standalone\nHASHTAGS: #post")

    main.mobile_caption(_request(False), _user())

    assert "Must not appear" not in prompts[0]
