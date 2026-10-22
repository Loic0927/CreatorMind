"""Content-aware analysis for one tracked social post."""

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from backend.services.gemini import GeminiConfigurationError, generate_gemini_content
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia


ANALYSIS_SCHEMA_VERSION = "post-analysis-v1"
METRIC_NAMES = ("likes", "comments", "saves", "shares", "reach", "views", "engagement_rate")
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_IMAGE_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net", ".fbsbx.com")


class PostAnalysisError(RuntimeError):
    """Raised when a tracked post cannot be analyzed safely."""


class PostAnalysisInterpretation(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)
    strengths: list[str] = Field(default_factory=list, max_length=6)
    concerns: list[str] = Field(default_factory=list, max_length=6)
    recommendations: list[str] = Field(default_factory=list, max_length=8)
    missing_inputs: list[str] = Field(default_factory=list, max_length=8)


class PostAnalysisComputation(BaseModel):
    source_snapshot_ids: list[str]
    model_name: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION
    observed_metrics: dict[str, int | float | None]
    metric_deltas: dict[str, int | float | None]
    content_payload: dict[str, Any]
    output_payload: dict[str, Any]


def observed_metrics(snapshot: InstagramInsightSnapshot) -> dict[str, int | float | None]:
    return {name: getattr(snapshot, name) for name in METRIC_NAMES}


def calculate_metric_deltas(
    current: InstagramInsightSnapshot,
    previous: InstagramInsightSnapshot | None,
) -> dict[str, int | float | None]:
    if previous is None:
        return {name: None for name in METRIC_NAMES}
    deltas: dict[str, int | float | None] = {}
    for name in METRIC_NAMES:
        current_value = getattr(current, name)
        previous_value = getattr(previous, name)
        deltas[name] = (
            round(current_value - previous_value, 4)
            if current_value is not None and previous_value is not None
            else None
        )
    return deltas


def _allowed_image_host(hostname: str) -> bool:
    extra = tuple(
        value.strip().lower()
        for value in os.getenv("POSTBRIDGE_ANALYSIS_IMAGE_HOSTS", "").split(",")
        if value.strip()
    )
    hostname = hostname.lower()
    return hostname in extra or any(hostname.endswith(suffix) for suffix in DEFAULT_IMAGE_HOST_SUFFIXES)


def fetch_remote_image(url: str, max_bytes: int = 5 * 1024 * 1024) -> tuple[bytes, str] | None:
    """Download a provider-owned image without allowing arbitrary server-side URLs."""

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not _allowed_image_host(parsed.hostname):
        return None
    try:
        request = Request(url, headers={"User-Agent": "PostBridge/1.0"})
        with urlopen(request, timeout=12) as response:
            mime_type = response.headers.get_content_type().lower()
            if mime_type not in SUPPORTED_IMAGE_TYPES:
                return None
            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) > max_bytes:
                return None
            body = response.read(max_bytes + 1)
            if not body or len(body) > max_bytes:
                return None
            return body, mime_type
    except (HTTPError, URLError, OSError, ValueError):
        return None


def _parse_interpretation(raw: str) -> PostAnalysisInterpretation:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        return PostAnalysisInterpretation.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise PostAnalysisError("Gemini returned an invalid post analysis.") from exc


def analyze_post(
    media: InstagramMedia,
    snapshots: list[InstagramInsightSnapshot],
    *,
    generator: Callable[..., str] = generate_gemini_content,
    image_loader: Callable[[str], tuple[bytes, str] | None] = fetch_remote_image,
    model_name: str | None = None,
) -> PostAnalysisComputation:
    if not snapshots:
        raise PostAnalysisError("At least one metric snapshot is required.")

    ordered = sorted(snapshots, key=lambda item: item.captured_at)
    source_snapshots = ordered[-10:]
    latest = source_snapshots[-1]
    previous = source_snapshots[-2] if len(source_snapshots) > 1 else None
    metrics = observed_metrics(latest)
    deltas = calculate_metric_deltas(latest, previous)
    resolved_model = model_name or os.getenv("GEMINI_MODEL", "").strip()
    if not resolved_model:
        raise GeminiConfigurationError("GEMINI_MODEL is not configured.")

    image_bytes: bytes | None = None
    image_mime_type: str | None = None
    visual_source = media.thumbnail_url or media.media_url
    if visual_source:
        loaded = image_loader(visual_source)
        if loaded:
            image_bytes, image_mime_type = loaded

    missing_inputs = [
        f"{name} is unavailable from the provider."
        for name, value in metrics.items()
        if value is None
    ]
    if image_bytes is None:
        missing_inputs.append("Visual content was unavailable, so the analysis used caption and metrics only.")
    elif media.media_type.upper() == "VIDEO":
        missing_inputs.append("Only the video thumbnail was analyzed; the full video was not analyzed.")

    history = [
        {
            "snapshot_id": item.id,
            "captured_at": item.captured_at.isoformat(),
            "metrics": observed_metrics(item),
        }
        for item in source_snapshots
    ]
    content_payload = {
        "platform": "Instagram",
        "media_type": media.media_type,
        "caption": media.caption,
        "published_at": media.published_at.isoformat(),
        "visual_context_used": image_bytes is not None,
        "visual_context_kind": "thumbnail" if media.media_type.upper() == "VIDEO" else "image",
    }
    prompt = (
        "Analyze one Instagram post using only the supplied post content and observed provider metrics. "
        "Do not predict views, assign a viral score, invent unavailable metrics, or claim causation. "
        "Separate evidence from interpretation. Explain what the content and metric changes suggest, "
        "then recommend concrete improvements for the next post. Return only a JSON object with exactly "
        "these keys: summary (string), strengths (array of strings), concerns (array of strings), "
        "recommendations (array of strings), missing_inputs (array of strings).\n"
        f"POST CONTENT: {json.dumps(content_payload, ensure_ascii=False)}\n"
        f"LATEST OBSERVED METRICS: {json.dumps(metrics)}\n"
        f"CHANGES FROM PREVIOUS SNAPSHOT: {json.dumps(deltas)}\n"
        f"SNAPSHOT HISTORY: {json.dumps(history)}"
    )
    raw = generator(
        prompt,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
        model_name=resolved_model,
    )
    interpretation = _parse_interpretation(raw)
    interpretation.missing_inputs = list(
        dict.fromkeys([*missing_inputs, *interpretation.missing_inputs])
    )
    return PostAnalysisComputation(
        source_snapshot_ids=[item.id for item in source_snapshots],
        model_name=resolved_model,
        observed_metrics=metrics,
        metric_deltas=deltas,
        content_payload=content_payload,
        output_payload=interpretation.model_dump(),
    )
