from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.services.feedback as feedback
from backend.services.gemini import GeminiGeneration
from backend.storage.database import engine_for_url, session_factory_for_url

FACTS = [
    {
        "id": "growth_stage",
        "type": "growth_stage",
        "value": "still_growing",
        "evidence": {"snapshot_ids": ["one", "two"]},
        "qualifies": True,
    }
]
PAYLOAD = {
    "diagnosis": "The post was still accumulating attention across the observed checkpoints.",
    "evidence": [
        {
            "fact_id": "growth_stage",
            "statement": "The post was still accumulating attention across the observed checkpoints.",
        }
    ],
    "hypothesis": "Hypothesis: the observed pattern may reflect the presentation, but the facts do not establish a cause.",
    "experiment": "Experiment: change one presentation element in the next comparable post.",
    "measure": "Measure: compare the cited signal on the next comparable post.",
    "do_not_change": "Do not change multiple elements at once.",
}


def test_gemini_feedback_uses_sdk_timeout_json_mode_schema_and_system_instruction(monkeypatch):
    monkeypatch.setenv("FEEDBACK_REQUEST_TIMEOUT_SECONDS", "9")
    captured = {}

    def generate(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return GeminiGeneration(text=json.dumps(PAYLOAD), token_usage={"total_token_count": 42})

    result = feedback.GeminiFeedbackProvider(generator=generate).generate(FACTS, media_input=(b"image", "image/png"))

    assert result.payload == PAYLOAD
    assert result.token_usage == {"total_token_count": 42}
    assert captured["prompt"] == f"FACTS_JSON={json.dumps(FACTS, separators=(',', ':'))}"
    assert captured["kwargs"] == {
        "system_instruction": feedback.FEEDBACK_SYSTEM_INSTRUCTION,
        "temperature": feedback.FEEDBACK_TEMPERATURE,
        "max_output_tokens": feedback.FEEDBACK_MAX_OUTPUT_TOKENS,
        "response_mime_type": "application/json",
        "response_schema": feedback.FEEDBACK_RESPONSE_SCHEMA,
        "timeout_ms": 9000,
        "return_usage": True,
        "image_bytes": b"image",
        "image_mime_type": "image/png",
    }
    assert "Do not restate" not in captured["prompt"]
    assert set(feedback.FEEDBACK_RESPONSE_SCHEMA["properties"]) == {
        "diagnosis",
        "evidence",
        "hypothesis",
        "experiment",
        "measure",
        "do_not_change",
    }


def test_gemini_feedback_retries_invalid_json_without_thread_timeout():
    calls = []

    def generate(_prompt: str, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return "not json"
        return json.dumps(PAYLOAD)

    result = feedback.GeminiFeedbackProvider(generator=generate).generate(FACTS)

    assert result.payload == PAYLOAD
    assert len(calls) == 2


def test_gemini_feedback_preserves_upstream_error_after_retry():
    message = "Gemini request failed (HTTP 400): INVALID_ARGUMENT: response_schema rejected"
    calls = []

    def generate(_prompt: str, **_kwargs):
        calls.append(True)
        raise feedback.GeminiUpstreamError(message, status_code=400)

    with pytest.raises(feedback.GeminiUpstreamError, match="INVALID_ARGUMENT") as failure:
        feedback.GeminiFeedbackProvider(generator=generate).generate(FACTS)

    assert str(failure.value) == message
    assert failure.value.status_code == 400
    assert len(calls) == 2


def test_gemini_feedback_includes_untrusted_post_and_creator_context_when_supplied():
    captured = {}

    def generate(prompt: str, **_kwargs):
        captured["prompt"] = prompt
        return json.dumps(PAYLOAD)

    context = {
        "post_caption": "A fursuit magic reveal #furry",
        "creator_context": "About This Account: Short fursuit magic performances\nTarget Audience: Furry magic fans",
    }
    feedback.GeminiFeedbackProvider(generator=generate).generate(FACTS, analysis_context=context)

    assert "FACTS_JSON=" in captured["prompt"]
    marker = "\nUNTRUSTED_POST_AND_CREATOR_CONTEXT_JSON="
    assert marker in captured["prompt"]
    assert json.loads(captured["prompt"].split(marker, 1)[1]) == context


def test_gemini_feedback_accepts_a_json_object_wrapped_by_provider_presentation_text():
    wrapped = "Here is the requested JSON:\n```JSON\n" + json.dumps(PAYLOAD) + "\n```"

    result = feedback.GeminiFeedbackProvider(generator=lambda _prompt, **_kwargs: wrapped).generate(FACTS)

    assert result.payload == PAYLOAD


def test_generate_summary_persists_gemini_token_usage_in_generation_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class Provider:
        name = "gemini"
        model = "unit-test-model"

        def generate(self, facts, *, media_input=None, analysis_context=None):
            assert facts == FACTS
            assert media_input is None
            return feedback.FeedbackGeneration(payload=PAYLOAD, token_usage={"prompt_token_count": 7})

    log_calls = []
    database_url = f"sqlite:///{(tmp_path / 'feedback.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine_for_url(database_url)
    monkeypatch.setattr(feedback, "has_ai_processing_consent", lambda _user_id: True)
    monkeypatch.setattr(feedback, "_selection", lambda: ([Provider()], "gemini:unit-test-model"))
    monkeypatch.setattr(feedback, "_log", lambda *args, **kwargs: log_calls.append((args, kwargs)))

    result = feedback.generate_summary("usage-user", "usage-post", FACTS)

    assert PAYLOAD["diagnosis"] in result
    assert len(log_calls) == 1
    args, kwargs = log_calls[0]
    assert args[4] == "ok"
    assert args[7] == {"prompt_token_count": 7}
    assert kwargs == {}
    engine_for_url(database_url).dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()


def test_generate_summary_persists_gemini_error_details_in_generation_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    error_message = "Gemini request failed (HTTP 400): INVALID_ARGUMENT: response_schema rejected"

    class Provider:
        name = "gemini"
        model = "unit-test-model"

        def generate(self, facts, *, media_input=None, analysis_context=None):
            raise feedback.GeminiUpstreamError(error_message, status_code=400)

    log_calls = []
    database_url = f"sqlite:///{(tmp_path / 'feedback-error.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine_for_url(database_url)
    monkeypatch.setattr(feedback, "has_ai_processing_consent", lambda _user_id: True)
    monkeypatch.setattr(feedback, "_selection", lambda: ([Provider()], "gemini:unit-test-model"))
    monkeypatch.setattr(feedback, "_log", lambda *args, **kwargs: log_calls.append((args, kwargs)))

    result = feedback.generate_summary("error-user", "error-post", FACTS)

    assert result
    assert len(log_calls) == 1
    args, kwargs = log_calls[0]
    assert args[4] == "error"
    assert args[6] == error_message
    assert kwargs == {}
    engine_for_url(database_url).dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
