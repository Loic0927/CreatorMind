"""Gemini text generation boundary.

The legacy ``google.generativeai`` SDK is imported lazily so unit tests and pytest
collection never require credentials or network access. Migrating this adapter to
``google.genai`` is intentionally deferred to a separate change.
"""

import os
from collections.abc import Callable
from typing import Any


class GeminiConfigurationError(RuntimeError):
    """Raised when required server-side Gemini configuration is missing."""


class GeminiUpstreamError(RuntimeError):
    """Raised with a safe message when Gemini cannot complete a request."""


GeminiClientFactory = Callable[[str, str], Any]


def _legacy_client_factory(api_key: str, model_name: str) -> Any:
    # TODO: Migrate this isolated adapter from google.generativeai to google.genai
    # in a dedicated SDK migration change.
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiConfigurationError(
            "The Gemini SDK is not installed on the backend."
        ) from exc

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def generate_gemini_content(
    prompt: str,
    *,
    api_key: str | None = None,
    model_name: str | None = None,
    client_factory: GeminiClientFactory | None = None,
) -> str:
    """Generate text without exposing provider errors or credentials."""

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    resolved_model = model_name or os.getenv("GEMINI_MODEL")
    if not resolved_model:
        raise GeminiConfigurationError("GEMINI_MODEL is not configured.")

    factory = client_factory or _legacy_client_factory
    try:
        model = factory(resolved_api_key, resolved_model)
        response = model.generate_content(prompt)
        text = response.text
    except GeminiConfigurationError:
        raise
    except Exception:
        raise GeminiUpstreamError(
            "Gemini could not complete the request."
        ) from None

    if not isinstance(text, str) or not text.strip():
        raise GeminiUpstreamError("Gemini returned an empty response.")
    return text.strip()
