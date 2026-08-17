from types import SimpleNamespace

import pytest

from backend.services.gemini import (
    GeminiConfigurationError,
    GeminiUpstreamError,
    generate_gemini_content,
)


class FakeModel:
    def __init__(self, response_text: str = "Generated strategy"):
        self.response_text = response_text
        self.prompts: list[str] = []

    def generate_content(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.response_text)


def test_normal_response_is_parsed_and_trimmed():
    model = FakeModel("  Generated strategy\n")

    result = generate_gemini_content(
        "Analyze this post",
        api_key="unit-test-key",
        model_name="unit-test-model",
        client_factory=lambda api_key, model_name: model,
    )

    assert result == "Generated strategy"


def test_prompt_and_configuration_are_passed_to_client():
    model = FakeModel()
    received = {}

    def factory(api_key: str, model_name: str):
        received.update(api_key=api_key, model_name=model_name)
        return model

    prompt = "Improve the first two seconds of this video"
    generate_gemini_content(
        prompt,
        api_key="unit-test-key",
        model_name="configured-model",
        client_factory=factory,
    )

    assert received == {
        "api_key": "unit-test-key",
        "model_name": "configured-model",
    }
    assert model.prompts == [prompt]


def test_upstream_error_is_safely_wrapped():
    class FailingModel:
        def generate_content(self, prompt: str):
            raise RuntimeError("provider response containing sensitive diagnostics")

    with pytest.raises(GeminiUpstreamError) as failure:
        generate_gemini_content(
            "private prompt",
            api_key="private-api-key",
            model_name="configured-model",
            client_factory=lambda api_key, model_name: FailingModel(),
        )

    assert str(failure.value) == "Gemini could not complete the request."
    assert "private-api-key" not in str(failure.value)
    assert "private prompt" not in str(failure.value)
    assert failure.value.__cause__ is None


def test_missing_api_key_has_explicit_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(GeminiConfigurationError) as failure:
        generate_gemini_content(
            "Analyze this post",
            model_name="configured-model",
            client_factory=lambda api_key, model_name: FakeModel(),
        )

    assert str(failure.value) == "GEMINI_API_KEY is not configured."


def test_model_name_comes_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "environment-selected-model")
    received = {}

    def factory(api_key: str, model_name: str):
        received["model_name"] = model_name
        return FakeModel()

    generate_gemini_content("Analyze this post", client_factory=factory)

    assert received["model_name"] == "environment-selected-model"
