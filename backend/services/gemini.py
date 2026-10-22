"""Gemini text and image generation boundary."""

import os
from collections.abc import Callable
from typing import Any


class GeminiConfigurationError(RuntimeError):
    """Raised when required server-side Gemini configuration is missing."""


class GeminiUpstreamError(RuntimeError):
    """Raised with a safe message when Gemini cannot complete a request."""


GeminiClientFactory = Callable[[str, str], Any]
GeminiImagePartFactory = Callable[[bytes, str], Any]


def _client_factory(api_key: str, model_name: str) -> Any:
    del model_name
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiConfigurationError(
            "The Gemini SDK is not installed on the backend."
        ) from exc

    return genai.Client(api_key=api_key)


def _image_part_factory(image_bytes: bytes, mime_type: str) -> Any:
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiConfigurationError(
            "The Gemini SDK is not installed on the backend."
        ) from exc

    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def generate_gemini_content(
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    client_factory: GeminiClientFactory | None = None,
    image_part_factory: GeminiImagePartFactory | None = None,
) -> str:
    """Generate content from text and an optional inline image."""

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    resolved_model = model_name or os.getenv("GEMINI_MODEL")
    if not resolved_model:
        raise GeminiConfigurationError("GEMINI_MODEL is not configured.")

    if (image_bytes is None) != (image_mime_type is None):
        raise GeminiConfigurationError(
            "Image bytes and MIME type must be provided together."
        )

    factory = client_factory or _client_factory
    try:
        client = factory(resolved_api_key, resolved_model)
        contents: str | list[Any] = prompt
        if image_bytes is not None and image_mime_type is not None:
            part_factory = image_part_factory or _image_part_factory
            contents = [
                part_factory(image_bytes, image_mime_type),
                prompt,
            ]
        response = client.models.generate_content(
            model=resolved_model,
            contents=contents,
        )
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
