"""Gemini text and multimodal generation boundary.

This module deliberately owns the SDK-specific knobs so product services can
declare a small, typed generation contract without reaching into ``google-genai``
directly.  The default return value remains a string for existing callers;
callers which need auditing information can opt into :class:`GeminiGeneration`.
"""

import copy
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger("postbridge.gemini")


class GeminiConfigurationError(RuntimeError):
    """Raised when required server-side Gemini configuration is missing."""


class GeminiUpstreamError(RuntimeError):
    """Raised with safe upstream diagnostics when Gemini cannot complete a request."""

    def __init__(self, message: str, *, status_code: int | str | None = None):
        super().__init__(message)
        self.status_code = status_code


GeminiClientFactory = Callable[..., Any]
GeminiMediaPartFactory = Callable[[bytes, str], Any]
# Backward-compatible name retained for existing test and integration callers.
GeminiImagePartFactory = GeminiMediaPartFactory


@dataclass(frozen=True)
class GeminiGeneration:
    text: str
    token_usage: dict[str, Any] | None = None


def _client_factory(api_key: str, model_name: str, *, timeout_ms: int | None = None) -> Any:
    del model_name
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GeminiConfigurationError("The Gemini SDK is not installed on the backend.") from exc

    options = types.HttpOptions(timeout=timeout_ms) if timeout_ms is not None else None
    return genai.Client(api_key=api_key, http_options=options)


def _media_part_factory(media_bytes: bytes, mime_type: str) -> Any:
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiConfigurationError("The Gemini SDK is not installed on the backend.") from exc

    return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)


def _generation_config(
    *,
    system_instruction: str | None,
    temperature: float | None,
    max_output_tokens: int | None,
    response_mime_type: str | None,
    response_schema: Any | None,
) -> Any | None:
    if all(
        value is None
        for value in (system_instruction, temperature, max_output_tokens, response_mime_type, response_schema)
    ):
        return None
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiConfigurationError("The Gemini SDK is not installed on the backend.") from exc
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type=response_mime_type,
        response_schema=response_schema,
    )


def _sanitized_response_schema(response_schema: Any | None) -> Any | None:
    """Copy a response schema and remove fields unsupported by Gemini."""
    sanitized = copy.deepcopy(response_schema)

    def strip(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("additionalProperties", None)
            for nested in value.values():
                strip(nested)
        elif isinstance(value, list):
            for nested in value:
                strip(nested)

    strip(sanitized)
    return sanitized


def _upstream_status_code(exc: Exception) -> int | str | None:
    for name in ("status_code", "code"):
        value = getattr(exc, name, None)
        if value is None:
            continue
        enum_value = getattr(value, "value", value)
        if isinstance(enum_value, (int, str)):
            return enum_value
    return None


def _safe_upstream_message(exc: Exception, api_key: str) -> str:
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(exc)
    message = message.strip() or type(exc).__name__
    return message.replace(api_key, "[REDACTED]")


def _token_usage(response: Any) -> dict[str, Any] | None:
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return None
    if hasattr(metadata, "model_dump"):
        value = metadata.model_dump(exclude_none=True)
        return value if isinstance(value, dict) else None
    if isinstance(metadata, dict):
        return {key: value for key, value in metadata.items() if value is not None}
    values = {
        name: getattr(metadata, name)
        for name in (
            "prompt_token_count",
            "candidates_token_count",
            "total_token_count",
            "cached_content_token_count",
            "thoughts_token_count",
        )
        if getattr(metadata, name, None) is not None
    }
    return values or None


def generate_gemini_content(
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    client_factory: GeminiClientFactory | None = None,
    image_part_factory: GeminiImagePartFactory | None = None,
    system_instruction: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    response_mime_type: str | None = None,
    response_schema: Any | None = None,
    timeout_ms: int | None = None,
    return_usage: bool = False,
) -> str | GeminiGeneration:
    """Generate content from text and optional inline image or video bytes."""

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    resolved_model = model_name or os.getenv("GEMINI_MODEL")
    if not resolved_model:
        raise GeminiConfigurationError("GEMINI_MODEL is not configured.")

    if (image_bytes is None) != (image_mime_type is None):
        raise GeminiConfigurationError("Image bytes and MIME type must be provided together.")

    config = _generation_config(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type=response_mime_type,
        response_schema=_sanitized_response_schema(response_schema),
    )
    factory = client_factory or _client_factory
    try:
        if client_factory is None:
            client = factory(resolved_api_key, resolved_model, timeout_ms=timeout_ms)
        else:
            # Test and integration factories historically accepted two positional
            # arguments.  Preserve that boundary while production clients receive
            # the SDK HTTP timeout above.
            client = factory(resolved_api_key, resolved_model)
        contents: str | list[Any] = prompt
        if image_bytes is not None and image_mime_type is not None:
            part_factory = image_part_factory or _media_part_factory
            contents = [
                part_factory(image_bytes, image_mime_type),
                prompt,
            ]
        request: dict[str, Any] = {"model": resolved_model, "contents": contents}
        if config is not None:
            request["config"] = config
        response = client.models.generate_content(**request)
        text = response.text
    except GeminiConfigurationError:
        raise
    except Exception as exc:
        status_code = _upstream_status_code(exc)
        upstream_message = _safe_upstream_message(exc, resolved_api_key)
        status_label = f" (HTTP {status_code})" if status_code is not None else ""
        message = f"Gemini request failed{status_label}: {upstream_message}"
        LOGGER.error(
            "gemini_request_failed status_code=%s message=%s",
            status_code if status_code is not None else "unknown",
            upstream_message,
        )
        raise GeminiUpstreamError(message, status_code=status_code) from exc

    if not isinstance(text, str) or not text.strip():
        raise GeminiUpstreamError("Gemini returned an empty response.")
    result = GeminiGeneration(text=text.strip(), token_usage=_token_usage(response))
    return result if return_usage else result.text
