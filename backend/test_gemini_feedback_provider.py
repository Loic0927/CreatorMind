from __future__ import annotations

import json

import backend.services.feedback as feedback
from backend.services.gemini import GeminiGeneration

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
    "sentences": [
        {
            "text": "Attention was still accumulating across the observed checkpoints.",
            "kind": "observation",
            "fact_ids": ["growth_stage"],
        }
    ]
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
    assert feedback.FEEDBACK_RESPONSE_SCHEMA["properties"]["sentences"]["items"]["properties"] == {
        "text": {"type": "string"},
        "kind": {"type": "string", "enum": ["observation", "suggestion"]},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
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


def test_generate_summary_persists_gemini_token_usage_in_generation_log(monkeypatch):
    class Provider:
        name = "gemini"
        model = "unit-test-model"

        def generate(self, facts, *, media_input=None, analysis_context=None):
            assert facts == FACTS
            assert media_input is None
            return feedback.FeedbackGeneration(payload=PAYLOAD, token_usage={"prompt_token_count": 7})

    log_calls = []
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    monkeypatch.setattr(feedback, "has_ai_processing_consent", lambda _user_id: True)
    monkeypatch.setattr(feedback, "_selection", lambda: ([Provider()], "gemini:unit-test-model"))
    monkeypatch.setattr(feedback, "_log", lambda *args, **kwargs: log_calls.append((args, kwargs)))

    result = feedback.generate_summary("usage-user", "usage-post", FACTS)

    assert result == PAYLOAD["sentences"][0]["text"]
    assert len(log_calls) == 1
    args, kwargs = log_calls[0]
    assert args[4] == "ok"
    assert args[7] == {"prompt_token_count": 7}
    assert kwargs == {}
