"""Evidence-backed creator intelligence for one tracked social post."""

import json
import os
import re
from collections import defaultdict
from collections.abc import Callable
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from backend.services.gemini import GeminiConfigurationError, GeminiUpstreamError, generate_gemini_content
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia


ANALYSIS_SCHEMA_VERSION = "post-analysis-v2"
METRIC_NAMES = ("likes", "comments", "saves", "shares", "reach", "views", "engagement_rate")
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_IMAGE_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net", ".fbsbx.com")


class PostAnalysisError(RuntimeError):
    """Raised when a tracked post cannot be analyzed safely."""


class ImpactHypothesis(BaseModel):
    factor: str = Field(..., min_length=1, max_length=80)
    estimated_impact: str = Field(..., min_length=1, max_length=40)
    explanation: str = Field(..., min_length=1, max_length=280)


class ActionRecommendation(BaseModel):
    action: str = Field(..., min_length=1, max_length=220)
    reason: str = Field(..., min_length=1, max_length=280)
    expected_impact: str = Field(..., min_length=1, max_length=100)


class ContentAttributes(BaseModel):
    topic: str = Field(default="Unclassified", min_length=1, max_length=80)
    thumbnail_style: str = Field(default="Unavailable", min_length=1, max_length=80)
    caption_style: str = Field(default="Standard", min_length=1, max_length=80)
    cta_usage: str = Field(default="None", min_length=1, max_length=80)


class PostAnalysisInterpretation(BaseModel):
    why_it_worked: list[ImpactHypothesis] = Field(default_factory=list, max_length=3)
    recommendations: list[ActionRecommendation] = Field(default_factory=list, max_length=3)
    content_attributes: ContentAttributes = Field(default_factory=ContentAttributes)


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


def calculate_metric_deltas(current: InstagramInsightSnapshot, previous: InstagramInsightSnapshot | None) -> dict[str, int | float | None]:
    if previous is None:
        return {name: None for name in METRIC_NAMES}
    return {
        name: (round(getattr(current, name) - getattr(previous, name), 4)
               if getattr(current, name) is not None and getattr(previous, name) is not None else None)
        for name in METRIC_NAMES
    }


def _allowed_image_host(hostname: str) -> bool:
    extra = tuple(value.strip().lower() for value in os.getenv("POSTBRIDGE_ANALYSIS_IMAGE_HOSTS", "").split(",") if value.strip())
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
            return (body, mime_type) if body and len(body) <= max_bytes else None
    except (HTTPError, URLError, OSError, ValueError):
        return None


def _parse_interpretation(raw: str) -> PostAnalysisInterpretation:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        return PostAnalysisInterpretation.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise PostAnalysisError("Gemini returned an invalid post analysis.") from exc


def _caption_attributes(caption: str) -> ContentAttributes:
    lowered = caption.lower()
    topic = "Tutorials" if re.search(r"\b(how to|tutorial|guide|steps?|tips?|learn)\b", lowered) else \
        "Magic" if re.search(r"\b(magic|trick|illusion)\b", lowered) else \
        "Comedy" if re.search(r"\b(comedy|funny|joke|skit)\b", lowered) else \
        "Product" if re.search(r"\b(product|launch|shop|buy|review)\b", lowered) else "Unclassified"
    caption_style = "Question-led" if "?" in caption else "Short" if len(caption) <= 100 else "Long" if len(caption) >= 250 else "Standard"
    cta_usage = "Question" if "?" in caption else "Explicit CTA" if re.search(r"\b(comment|share|save|follow|click|try|tell me|let me know)\b", lowered) else "None"
    return ContentAttributes(topic=topic, thumbnail_style="Unavailable", caption_style=caption_style, cta_usage=cta_usage)


def _fallback_interpretation(caption: str, benchmarks: list[dict[str, Any]]) -> PostAnalysisInterpretation:
    ranked = sorted(
        (item for item in benchmarks if item.get("percent_change") is not None),
        key=lambda item: abs(float(item["percent_change"])), reverse=True,
    )
    strongest = next((item for item in ranked if item["percent_change"] > 0), None)
    weakest = next((item for item in ranked if item["percent_change"] < 0), None)
    why = [] if strongest is None else [ImpactHypothesis(
        factor=strongest["metric"].replace("_", " ").title(), estimated_impact="Positive signal",
        explanation=f"This signal is {abs(strongest['percent_change']):.0f}% above the tracked-post average.",
    )]
    recommendations = [ActionRecommendation(
        action="Repeat the strongest content structure in the next post." if strongest else "Analyze more posts to establish a reliable baseline.",
        reason=(f"{strongest['metric'].replace('_', ' ').title()} is the clearest positive signal." if strongest else "There is not enough comparative evidence yet."),
        expected_impact="Test whether the observed pattern repeats.",
    )]
    if weakest:
        recommendations.append(ActionRecommendation(
            action=f"Test one change aimed at {weakest['metric'].replace('_', ' ')}.",
            reason=f"This signal is {abs(weakest['percent_change']):.0f}% below the tracked-post average.",
            expected_impact="Improve the weakest observed response.",
        ))
    return PostAnalysisInterpretation(
        why_it_worked=why, recommendations=recommendations,
        content_attributes=_caption_attributes(caption),
    )


def _clamp(value: float) -> int:
    return round(max(0, min(100, value)))


def _relative_score(current: float | None, average: float | None) -> int:
    if current is None:
        return 0
    if average is None:
        return 50
    if average <= 0:
        return 75 if current > 0 else 50
    return _clamp(50 + ((current / average) - 1) * 100)


def _average(values: list[int | float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return round(mean(available), 4) if available else None


def _benchmark(metrics: dict[str, int | float | None], peer_metrics: list[dict[str, int | float | None]]) -> list[dict[str, Any]]:
    result = []
    for name in METRIC_NAMES:
        current = metrics.get(name)
        average = _average([item.get(name) for item in peer_metrics])
        change = round((float(current) - average) / average * 100, 1) if current is not None and average not in (None, 0) else None
        result.append({"metric": name, "current": current, "average": average, "percent_change": change,
                       "direction": "above" if change is not None and change > 0 else "below" if change is not None and change < 0 else "same" if change == 0 else "unavailable"})
    return result


def _shareability_rate(metrics: dict[str, int | float | None]) -> float | None:
    reach = metrics.get("reach")
    if not reach:
        return None
    return round(((metrics.get("saves") or 0) + (metrics.get("shares") or 0)) / float(reach) * 100, 4)


def _growth_rate(current: dict[str, int | float | None], previous: InstagramInsightSnapshot | None) -> float | None:
    if previous is None or current.get("reach") is None or not previous.reach:
        return None
    return round((float(current["reach"]) - previous.reach) / previous.reach * 100, 4)


def _score(metrics: dict[str, int | float | None], peer_metrics: list[dict[str, int | float | None]], previous: InstagramInsightSnapshot | None) -> dict[str, Any]:
    categories = {
        "reach": _relative_score(metrics.get("reach"), _average([item.get("reach") for item in peer_metrics])),
        "engagement": _relative_score(metrics.get("engagement_rate"), _average([item.get("engagement_rate") for item in peer_metrics])),
        "shareability": _relative_score(_shareability_rate(metrics), _average([_shareability_rate(item) for item in peer_metrics])),
        "growth": _clamp(50 + (_growth_rate(metrics, previous) or 0) * 5) if previous else 50,
    }
    available = [value for key, value in categories.items() if key != "growth" or previous is not None]
    overall = round(mean(available)) if available else 0
    grade = "A+" if overall >= 90 else "A" if overall >= 80 else "B" if overall >= 65 else "C"
    return {"overall": overall, "grade": grade, "categories": categories}


def _top_insights(benchmarks: list[dict[str, Any]], deltas: dict[str, int | float | None]) -> list[dict[str, str]]:
    candidates: list[tuple[float, dict[str, str]]] = []
    labels = {"reach": "Reach", "engagement_rate": "Engagement rate", "saves": "Save activity", "shares": "Share activity", "comments": "Comments"}
    for item in benchmarks:
        change = item["percent_change"]
        if item["metric"] in labels and change is not None and abs(change) >= 8:
            status = "strong" if change > 0 else "attention"
            candidates.append((abs(change), {"status": status, "text": f"{labels[item['metric']]} is {abs(change):.0f}% {item['direction']} your tracked-post average."}))
    interaction_growth = sum(float(deltas.get(name) or 0) for name in ("likes", "comments", "saves", "shares"))
    if deltas.get("reach") == 0 and interaction_growth == 0:
        candidates.append((1000, {"status": "attention", "text": "Growth has plateaued since the previous metrics snapshot."}))
    return [item for _, item in sorted(candidates, key=lambda value: value[0], reverse=True)[:3]] or [{"status": "neutral", "text": "More tracked posts are needed before PostBridge can identify an unusual result."}]


def _risks(benchmarks: list[dict[str, Any]], deltas: dict[str, int | float | None]) -> list[str]:
    risks = []
    by_name = {item["metric"]: item for item in benchmarks}
    for name, label in (("comments", "Comment participation"), ("shares", "Share activity"), ("saves", "Save activity")):
        change = by_name[name]["percent_change"]
        if change is not None and change <= -15:
            risks.append(f"{label} is {abs(change):.0f}% below your tracked-post average.")
    if deltas.get("reach") == 0 and all((deltas.get(name) or 0) == 0 for name in ("likes", "comments", "saves", "shares")):
        risks.insert(0, "Growth momentum has stalled since the previous snapshot.")
    return risks[:3]


def _patterns_for_caption(caption: str, media_type: str) -> list[str]:
    lowered = caption.lower()
    patterns = ["Video posts" if media_type.upper() == "VIDEO" else "Image posts"]
    if "?" in caption:
        patterns.append("Question-driven posts")
    if re.search(r"\b(how to|tutorial|guide|steps?|tips?|learn)\b", lowered):
        patterns.append("Tutorial posts")
    if len(re.findall(r"#\w+", caption)) >= 5:
        patterns.append("Hashtag-rich posts")
    if len(caption) <= 100:
        patterns.append("Short-caption posts")
    elif len(caption) >= 250:
        patterns.append("Long-caption posts")
    return patterns


def _content_patterns(historical_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not historical_posts:
        return []
    metrics = [item["metrics"] for item in historical_posts]
    avg_reach = _average([item.get("reach") for item in metrics])
    avg_engagement = _average([item.get("engagement_rate") for item in metrics])
    groups: dict[str, list[int]] = defaultdict(list)
    for item in historical_posts:
        performance = round(mean([_relative_score(item["metrics"].get("reach"), avg_reach), _relative_score(item["metrics"].get("engagement_rate"), avg_engagement)]))
        for pattern in _patterns_for_caption(item.get("caption", ""), item.get("media_type", "IMAGE")):
            groups[pattern].append(performance)
    overall = mean([round(mean([_relative_score(item["metrics"].get("reach"), avg_reach), _relative_score(item["metrics"].get("engagement_rate"), avg_engagement)])) for item in historical_posts])
    return sorted(({"pattern": name, "sample_size": len(values), "average_score": round(mean(values)), "difference_from_baseline": round(mean(values) - overall)} for name, values in groups.items()), key=lambda item: (item["average_score"], item["sample_size"]), reverse=True)[:5]


def _confidence(media: InstagramMedia, metrics: dict[str, int | float | None], image_available: bool) -> dict[str, Any]:
    metric_coverage = sum(value is not None for value in metrics.values()) / len(metrics)
    score = _clamp(35 + metric_coverage * 35 + (10 if media.caption.strip() else 0) + (20 if image_available else 0))
    is_video = media.media_type.upper() == "VIDEO"
    return {"score": score, "inputs": [
        {"name": "Thumbnail", "available": image_available}, {"name": "Caption", "available": bool(media.caption.strip())},
        {"name": "Metrics", "available": metric_coverage > 0},
        {"name": "Full Video", "available": False, "detail": "Only the thumbnail is analyzed." if is_video and image_available else None},
        {"name": "Audio Analysis", "available": False}, {"name": "Watch Time", "available": False},
        {"name": "Retention Curve", "available": False},
    ]}


def analyze_post(media: InstagramMedia, snapshots: list[InstagramInsightSnapshot], *,
                 peer_metrics: list[dict[str, int | float | None]] | None = None,
                 historical_posts: list[dict[str, Any]] | None = None,
                 generator: Callable[..., str] = generate_gemini_content,
                 image_loader: Callable[[str], tuple[bytes, str] | None] = fetch_remote_image,
                 model_name: str | None = None) -> PostAnalysisComputation:
    if not snapshots:
        raise PostAnalysisError("At least one metric snapshot is required.")
    ordered = sorted(snapshots, key=lambda item: item.captured_at)
    source_snapshots = ordered[-10:]
    latest = source_snapshots[-1]
    previous = source_snapshots[-2] if len(source_snapshots) > 1 else None
    metrics = observed_metrics(latest)
    deltas = calculate_metric_deltas(latest, previous)
    peers = peer_metrics or []
    history_posts = historical_posts or []
    resolved_model = model_name or os.getenv("GEMINI_MODEL", "").strip()

    visual_source = media.thumbnail_url or media.media_url
    loaded = image_loader(visual_source) if visual_source else None
    image_bytes, image_mime_type = loaded if loaded else (None, None)
    benchmarks = _benchmark(metrics, peers)
    score = _score(metrics, peers, previous)
    patterns = _content_patterns(history_posts)
    content_payload = {"platform": "Instagram", "media_type": media.media_type, "caption": media.caption,
                       "published_at": media.published_at.isoformat(), "visual_context_used": image_bytes is not None,
                       "visual_context_kind": "thumbnail" if media.media_type.upper() == "VIDEO" else "image"}
    evidence = {"score": score, "benchmarks": benchmarks, "metric_deltas": deltas,
                "content_patterns": patterns, "caption": media.caption, "media_type": media.media_type}
    prompt = (
        "Act as a creator strategist. Use only the supplied evidence. Return only JSON with exactly "
        "why_it_worked (maximum 3 objects with factor, estimated_impact, explanation), recommendations "
        "(maximum 3 objects with action, reason, expected_impact). Treat factors as hypotheses, label impact "
        "as an estimate, never invent metrics, never predict views or viral potential, and make every action "
        "specific to the evidence. Also return content_attributes with topic, thumbnail_style, caption_style, "
        "and cta_usage. Use 'Unavailable' when visual evidence does not support a thumbnail label. Expected "
        "impact may be a cautious directional estimate or range, not a guarantee.\n"
        f"EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}"
    )
    interpretation = None
    used_model = resolved_model
    if resolved_model:
        try:
            raw = generator(prompt, image_bytes=image_bytes, image_mime_type=image_mime_type, model_name=resolved_model)
            interpretation = _parse_interpretation(raw)
        except (GeminiConfigurationError, GeminiUpstreamError, PostAnalysisError):
            interpretation = None
    if interpretation is None:
        interpretation = _fallback_interpretation(media.caption, benchmarks)
        used_model = "deterministic-fallback-v2"
    output = {"score": score, "top_insights": _top_insights(benchmarks, deltas),
              "why_it_worked": [item.model_dump() for item in interpretation.why_it_worked[:3]],
              "benchmarks": benchmarks, "risks": _risks(benchmarks, deltas),
              "recommendations": [item.model_dump() for item in interpretation.recommendations[:3]],
              "confidence": _confidence(media, metrics, image_bytes is not None), "content_patterns": patterns,
              "content_attributes": interpretation.content_attributes.model_dump()}
    return PostAnalysisComputation(source_snapshot_ids=[item.id for item in source_snapshots], model_name=used_model,
                                   observed_metrics=metrics, metric_deltas=deltas, content_payload=content_payload,
                                   output_payload=output)
