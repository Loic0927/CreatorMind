from types import SimpleNamespace

import pytest

import backend.services.gemini as gemini
from backend.services.gemini import (
    GeminiConfigurationError,
    GeminiGeneration,
    GeminiUpstreamError,
    generate_gemini_content,
)


class FakeModels:
    def __init__(self, response_text: str = "Generated strategy"):
        self.response_text = response_text
        self.calls: list[dict] = []

    def generate_content(self, *, model: str, contents):
        self.calls.append({"model": model, "contents": contents})
        return SimpleNamespace(text=self.response_text)


class FakeClient:
    def __init__(self, response_text: str = "Generated strategy"):
        self.models = FakeModels(response_text)


def test_normal_response_is_parsed_and_trimmed():
    client = FakeClient("  Generated strategy\n")

    result = generate_gemini_content(
        "Analyze this post",
        api_key="unit-test-key",
        model_name="unit-test-model",
        client_factory=lambda api_key, model_name: client,
    )

    assert result == "Generated strategy"


def test_prompt_and_configuration_are_passed_to_client():
    client = FakeClient()
    received = {}

    def factory(api_key: str, model_name: str):
        received.update(api_key=api_key, model_name=model_name)
        return client

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
    assert client.models.calls == [{"model": "configured-model", "contents": prompt}]


def test_image_and_prompt_are_passed_as_multimodal_content():
    client = FakeClient()
    image_part = object()

    generate_gemini_content(
        "Describe this image",
        image_bytes=b"image-bytes",
        image_mime_type="image/png",
        api_key="unit-test-key",
        model_name="configured-model",
        client_factory=lambda api_key, model_name: client,
        image_part_factory=lambda data, mime_type: image_part,
    )

    assert client.models.calls == [
        {
            "model": "configured-model",
            "contents": [image_part, "Describe this image"],
        }
    ]


def test_upstream_error_is_safely_wrapped():
    class FailingModels:
        def generate_content(self, *, model: str, contents):
            raise RuntimeError("provider response containing sensitive diagnostics")

    class FailingClient:
        models = FailingModels()

    with pytest.raises(GeminiUpstreamError) as failure:
        generate_gemini_content(
            "private prompt",
            api_key="private-api-key",
            model_name="configured-model",
            client_factory=lambda api_key, model_name: FailingClient(),
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
            client_factory=lambda api_key, model_name: FakeClient(),
        )

    assert str(failure.value) == "GEMINI_API_KEY is not configured."


def test_model_name_comes_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "environment-selected-model")
    received = {}

    def factory(api_key: str, model_name: str):
        received["model_name"] = model_name
        return FakeClient()

    generate_gemini_content("Analyze this post", client_factory=factory)

    assert received["model_name"] == "environment-selected-model"


def test_generation_options_and_token_usage_are_exposed_without_breaking_text_callers(monkeypatch):
    response = SimpleNamespace(
        text="Structured response",
        usage_metadata=SimpleNamespace(prompt_token_count=11, candidates_token_count=5, total_token_count=16),
    )
    calls = []

    class ConfigModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return response

    client = SimpleNamespace(models=ConfigModels())
    config = object()
    received = {}

    def configuration(**kwargs):
        received.update(kwargs)
        return config

    monkeypatch.setattr(gemini, "_generation_config", configuration)
    result = generate_gemini_content(
        "Return JSON",
        api_key="unit-test-key",
        model_name="configured-model",
        client_factory=lambda api_key, model_name: client,
        system_instruction="Follow the schema.",
        temperature=0.2,
        max_output_tokens=80,
        response_mime_type="application/json",
        response_schema={"type": "object"},
        timeout_ms=12_000,
        return_usage=True,
    )

    assert isinstance(result, GeminiGeneration)
    assert result.text == "Structured response"
    assert result.token_usage == {
        "prompt_token_count": 11,
        "candidates_token_count": 5,
        "total_token_count": 16,
    }
    assert received == {
        "system_instruction": "Follow the schema.",
        "temperature": 0.2,
        "max_output_tokens": 80,
        "response_mime_type": "application/json",
        "response_schema": {"type": "object"},
    }
    assert calls == [{"model": "configured-model", "contents": "Return JSON", "config": config}]
