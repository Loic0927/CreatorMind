"""Evidence-backed analysis for one post, relative to the same account."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import datetime
from statistics import mean, median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from backend.services.account_context import context_reference_for_content
from backend.services.gemini import GeminiConfigurationError, GeminiUpstreamError, generate_gemini_content
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia


ANALYSIS_SCHEMA_VERSION = "post-analysis-v4"
OBSERVED_METRICS = ("likes", "comments", "saves", "shares", "reach", "views", "engagement_rate")
COMPARISON_METRICS = ("reach", "views", "engagement_rate", "shares", "saves", "comments")
RATE_METRICS = {"engagement_rate"}
NOISE_RELATIVE_PERCENT = 10.0
NOISE_COUNT_UNITS = 5.0
NOISE_RATE_POINTS = 0.5
SIGNIFICANT_RELATIVE_PERCENT = 25.0
SIGNIFICANT_COUNT_UNITS = 10.0
SIGNIFICANT_RATE_POINTS = 1.0
MIN_RELIABLE_BASELINE_POSTS = 5
MIN_TREND_POINTS = 3
MIN_TREND_SPAN_HOURS = 6
MIN_TREND_INTERVAL_MINUTES = 30
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_IMAGE_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net", ".fbsbx.com")


class PostAnalysisError(RuntimeError):
    """Raised when a tracked post cannot be analyzed safely."""


class ImpactHypothesis(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    evidence: str = Field(..., min_length=1, max_length=220)
    interpretation: str = Field(..., min_length=1, max_length=280)
    why_it_matters: str = Field(..., min_length=1, max_length=280)


class ContentAttributes(BaseModel):
    thumbnail_style: str = Field(default="Unavailable", min_length=1, max_length=80)
    caption_style: str = Field(default="Standard", min_length=1, max_length=80)
    cta_usage: str = Field(default="None", min_length=1, max_length=80)


class PostAnalysisInterpretation(BaseModel):
    why_it_worked: list[ImpactHypothesis] = Field(default_factory=list, max_length=2)
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
    metrics = {name: getattr(snapshot, name) for name in OBSERVED_METRICS}
    if not snapshot.reach:
        metrics["engagement_rate"] = None
    return metrics


def calculate_metric_deltas(current: InstagramInsightSnapshot, previous: InstagramInsightSnapshot | None) -> dict[str, int | float | None]:
    if previous is None:
        return {name: None for name in OBSERVED_METRICS}
    return {
        name: round(getattr(current, name) - getattr(previous, name), 1 if name in RATE_METRICS else 0)
        if getattr(current, name) is not None and getattr(previous, name) is not None else None
        for name in OBSERVED_METRICS
    }


def _allowed_image_host(hostname: str) -> bool:
    extra = tuple(value.strip().lower() for value in os.getenv("POSTBRIDGE_ANALYSIS_IMAGE_HOSTS", "").split(",") if value.strip())
    hostname = hostname.lower()
    return hostname in extra or any(hostname.endswith(suffix) for suffix in DEFAULT_IMAGE_HOST_SUFFIXES)


def fetch_remote_image(url: str, max_bytes: int = 5 * 1024 * 1024) -> tuple[bytes, str] | None:
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
    caption_style = "Question-led" if "?" in caption else "Short" if len(caption) <= 100 else "Long" if len(caption) >= 250 else "Standard"
    cta_usage = "Question" if "?" in caption else "Explicit CTA" if re.search(r"\b(comment|share|save|follow|click|try|tell me|let me know)\b", lowered) else "None"
    return ContentAttributes(caption_style=caption_style, cta_usage=cta_usage)


def _fallback_interpretation(caption: str, benchmarks: list[dict[str, Any]]) -> PostAnalysisInterpretation:
    strongest = next((item for item in benchmarks if item.get("real_gap") and (item.get("percent_change") or 0) > 0), None)
    hypotheses = []
    if strongest:
        label = strongest["metric"].replace("_", " ")
        hypotheses.append(ImpactHypothesis(
            title=f"Possible explanation for {label}", evidence=strongest["comparison_text"],
            interpretation="The creative or caption may have contributed, but the observed metric does not establish a cause.",
            why_it_matters="Repeat one comparable test before treating the result as a pattern.",
        ))
    return PostAnalysisInterpretation(why_it_worked=hypotheses, content_attributes=_caption_attributes(caption))


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_hours(published_at: Any, captured_at: Any) -> float | None:
    published, captured = _as_datetime(published_at), _as_datetime(captured_at)
    if not published or not captured:
        return None
    if published.tzinfo is None and captured.tzinfo is not None:
        published = published.replace(tzinfo=captured.tzinfo)
    if captured.tzinfo is None and published.tzinfo is not None:
        captured = captured.replace(tzinfo=published.tzinfo)
    return max(0.0, (captured - published).total_seconds() / 3600)


def _maturity_hours(media_type: str) -> int:
    return 14 * 24 if media_type.upper() in {"VIDEO", "REELS"} else 7 * 24


def _normalise_peer_sample(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
    return {
        "metrics": {name: metrics.get(name) for name in OBSERVED_METRICS},
        "media_type": str(item.get("media_type") or "UNKNOWN").upper(),
        "published_at": item.get("published_at"), "captured_at": item.get("captured_at"),
        "age_hours": _age_hours(item.get("published_at"), item.get("captured_at")),
    }


def _baseline_for(media: InstagramMedia, latest: InstagramInsightSnapshot, peer_metrics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    media_type = media.media_type.upper()
    all_samples = [_normalise_peer_sample(item) for item in peer_metrics]
    same_format = [item for item in all_samples if item["media_type"] == media_type]
    current_age = _age_hours(media.published_at, latest.captured_at)
    maturity = _maturity_hours(media_type)
    if current_age is not None and current_age >= maturity:
        selected = [item for item in same_format if item["age_hours"] is not None and item["age_hours"] >= maturity]
        age_basis = f"mature lifetime totals ({maturity // 24}+ days old)"
    elif current_age is not None:
        tolerance = max(6.0, current_age * 0.5)
        selected = [item for item in same_format if item["age_hours"] is not None and item["age_hours"] < maturity and abs(item["age_hours"] - current_age) <= tolerance]
        age_basis = f"similar post age (about {current_age / 24:.1f} days old)"
    else:
        selected, age_basis = [], "post age unavailable"
    published = sorted(str(item["published_at"]) for item in selected if item.get("published_at"))
    captured = sorted(str(item["captured_at"]) for item in selected if item.get("captured_at"))
    sample_size = len(selected)
    coverage = sum(value is not None for item in selected for value in item["metrics"].values()) / (sample_size * len(OBSERVED_METRICS)) if sample_size else 0
    return selected, {
        "sample_size": sample_size, "available_account_posts": len(all_samples), "same_format_posts": len(same_format),
        "metric_coverage": round(coverage, 3), "group": "same_format_similar_age",
        "label": f"{media_type.replace('_', ' ').title()} posts, {age_basis}", "age_basis": age_basis,
        "current_post_age_hours": round(current_age, 1) if current_age is not None else None, "statistic": "median",
        "published_range": {"start": published[0] if published else None, "end": published[-1] if published else None},
        "snapshot_range": {"start": captured[0] if captured else None, "end": captured[-1] if captured else None},
        "limited_sample": sample_size < MIN_RELIABLE_BASELINE_POSTS,
        "sample_notice": f"Only {sample_size} comparable post{'s' if sample_size != 1 else ''}, treat as a hint." if sample_size < MIN_RELIABLE_BASELINE_POSTS else f"Compared with {sample_size} same-format posts on a comparable age basis.",
        "limitations": [] if sample_size else ["No same-format post with a comparable maturity was available."],
    }


def _round_metric(name: str, value: float | int | None) -> float | int | None:
    if value is None:
        return None
    return round(float(value), 1) if name in RATE_METRICS else int(round(float(value)))


def _absolute_threshold(name: str) -> float:
    return NOISE_RATE_POINTS if name in RATE_METRICS else NOISE_COUNT_UNITS


def _significant_absolute_threshold(name: str) -> float:
    return SIGNIFICANT_RATE_POINTS if name in RATE_METRICS else SIGNIFICANT_COUNT_UNITS


def _ordinal(value: int) -> str:
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _benchmarks(metrics: dict[str, int | float | None], peer_samples: list[dict[str, Any]], basis: str) -> list[dict[str, Any]]:
    result = []
    for name in COMPARISON_METRICS:
        current = metrics.get(name)
        values = [float(item["metrics"][name]) for item in peer_samples if item["metrics"].get(name) is not None]
        sample_size = len(values)
        average = mean(values) if values else None
        median_value = median(values) if values else None
        absolute = float(current) - median_value if current is not None and median_value is not None else None
        change = absolute / median_value * 100 if absolute is not None and median_value not in (None, 0) and sample_size > 0 else None
        noise = change is not None and absolute is not None and abs(change) < NOISE_RELATIVE_PERCENT and abs(absolute) < _absolute_threshold(name)
        real_gap = change is not None and not noise
        significant = bool(real_gap and abs(change) >= SIGNIFICANT_RELATIVE_PERCENT and abs(absolute or 0) >= _significant_absolute_threshold(name))
        all_values = values + ([float(current)] if current is not None else [])
        rank = 1 + sum(value > float(current) for value in values) if current is not None and values else None
        percentile = round(sum(value <= float(current) for value in all_values) / len(all_values) * 100) if current is not None and values else None
        if change is None:
            comparison_text = "Comparison unavailable because the median or sample is missing or zero."
        elif noise:
            comparison_text = "In line with your typical posts."
        else:
            adverb = "significantly " if significant else ""
            comparison_text = f"{abs(change):.1f}% {adverb}{'above' if change > 0 else 'below'} the comparison median."
        result.append({
            "metric": name, "current": _round_metric(name, current), "average": _round_metric(name, average),
            "median": _round_metric(name, median_value), "sample_size": sample_size,
            "percent_change": round(change, 1) if change is not None else None,
            "absolute_difference": _round_metric(name, absolute),
            "direction": "above" if change is not None and change > 0 else "below" if change is not None and change < 0 else "same" if change == 0 else "unavailable",
            "is_noise": noise, "real_gap": real_gap, "significant": significant, "comparison_text": comparison_text,
            "rank": rank, "group_size": len(all_values) if values and current is not None else 0,
            "percentile": percentile, "percentile_label": f"{_ordinal(percentile)} percentile" if percentile is not None else "Not ranked", "basis": basis,
        })
    return result


def _trend_assessment(snapshots: list[InstagramInsightSnapshot]) -> dict[str, Any]:
    ordered = sorted(snapshots, key=lambda item: item.captured_at)
    start, end = ordered[0].captured_at, ordered[-1].captured_at
    span_hours = round((end - start).total_seconds() / 3600, 2)
    intervals = [(current.captured_at - previous.captured_at).total_seconds() / 60 for previous, current in zip(ordered, ordered[1:])]
    metric = next((name for name in ("reach", "views") if all(getattr(item, name) is not None for item in ordered)), None)
    comparable = bool(len(ordered) >= MIN_TREND_POINTS and span_hours >= MIN_TREND_SPAN_HOURS and intervals and min(intervals) >= MIN_TREND_INTERVAL_MINUTES and metric)
    changes = {}
    if len(ordered) >= 2:
        for name in COMPARISON_METRICS:
            first, last = getattr(ordered[0], name), getattr(ordered[-1], name)
            changes[name] = _round_metric(name, last - first) if first is not None and last is not None else None
    if comparable:
        total_change = getattr(ordered[-1], metric) - getattr(ordered[0], metric)
        summary, status = f"Across {len(ordered)} snapshots over {span_hours:g} hours, cumulative {metric} changed by {total_change:+g}.", "comparable_post_history"
    else:
        summary, status = "Snapshot history is still too short or too closely spaced to establish a trend.", "insufficient_history"
    return {"scope": "post_cumulative_metrics", "status": status, "observation_count": len(ordered), "metric": metric, "start": start.isoformat(), "end": end.isoformat(), "span_hours": span_hours, "summary": summary, "metric_changes": changes, "minimum_requirements": {"observations": MIN_TREND_POINTS, "span_hours": MIN_TREND_SPAN_HOURS, "interval_minutes": MIN_TREND_INTERVAL_MINUTES}}


def _finding(item: dict[str, Any], tone: str, interpretation: str | None = None) -> dict[str, Any]:
    return {"metric": item["metric"], "title": item["metric"].replace("_", " ").title(), "evidence": item["comparison_text"], "interpretation": interpretation, "sample_size": item["sample_size"], "basis": item["basis"], "tone": tone}


def _summary(benchmarks: list[dict[str, Any]], baseline: dict[str, Any]) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    comparable = [item for item in benchmarks if item["percent_change"] is not None]
    if not comparable:
        return "There are not yet enough same-format, similarly mature posts for a reliable comparison.", None, [], []
    strongest = max(comparable, key=lambda item: item["percent_change"])
    positives = sorted((item for item in comparable if item["percent_change"] >= 0), key=lambda item: item["percent_change"], reverse=True)
    negatives = sorted((item for item in comparable if item["real_gap"] and item["percent_change"] < 0), key=lambda item: item["percent_change"])
    worked = [_finding(positives[0], "positive")] if positives else [_finding(strongest, "neutral")]
    worked.extend(_finding(item, "positive") for item in positives[1:2] if item["real_gap"])
    improve = [_finding(item, "improve") for item in negatives[:2]]
    if all(item["is_noise"] for item in comparable):
        conclusion = f"This post is in line with your typical {baseline['label'].lower()} across the available metrics."
    elif strongest["percent_change"] >= 0:
        conclusion = f"{strongest['metric'].replace('_', ' ').title()} is this post's strongest relative metric; {strongest['comparison_text'].lower()}"
    else:
        conclusion = f"No available metric is above the comparison median; {strongest['metric'].replace('_', ' ')} is the closest to your typical result."
    return conclusion, strongest, worked[:2], improve[:2]


def _experiment(media: InstagramMedia, benchmarks: list[dict[str, Any]], baseline: dict[str, Any]) -> list[dict[str, str]]:
    gaps = [item for item in benchmarks if item["real_gap"]]
    if not gaps:
        return []
    target = max(gaps, key=lambda item: abs(item["percent_change"]))
    metric = target["metric"]
    if metric in {"reach", "views"}:
        variable, action = "cover treatment", "Change only the cover treatment on the next comparable post."
    elif metric == "shares":
        variable, action = "share prompt wording", "Change only the share prompt wording on the next comparable post."
    elif metric == "saves":
        variable, action = "utility framing", "Change only how the reusable value is framed on the next comparable post."
    else:
        variable, action = "CTA wording", "Change only the CTA wording on the next comparable post."
    minimum = "0.5 percentage points" if metric in RATE_METRICS else "5 units"
    return [{"test_variable": variable, "metric_to_watch": metric.replace("_", " "), "action": action,
             "reason": target["comparison_text"],
             "comparison": f"Use another {media.media_type.lower()} post on the same maturity basis; keep the other creative and timing choices as similar as practical.",
             "decision_rule": f"Keep the change only if {metric.replace('_', ' ')} improves by at least 10% and at least {minimum} versus the {baseline['sample_size']}-post median; otherwise reject or retest it."}]


def _evidence_quality(metrics: dict[str, Any], image_available: bool, baseline: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    available = sum(value is not None for value in metrics.values())
    return {"level": "Strong" if baseline["sample_size"] >= 10 and available >= 6 else "Moderate" if baseline["sample_size"] >= 5 else "Limited",
            "plain_language": f"Only {baseline['sample_size']} comparable post{'s' if baseline['sample_size'] != 1 else ''}, treat as a hint." if baseline["sample_size"] < 5 else f"Based on {baseline['sample_size']} comparable posts.",
            "sample_size": baseline["sample_size"], "metric_fields": available, "snapshot_count": trend["observation_count"], "visual_available": image_available}


def analyze_post(media: InstagramMedia, snapshots: list[InstagramInsightSnapshot], *, peer_metrics: list[dict[str, Any]] | None = None,
                 historical_posts: list[dict[str, Any]] | None = None, account_context: str = "",
                 generator: Callable[..., str] = generate_gemini_content,
                 image_loader: Callable[[str], tuple[bytes, str] | None] = fetch_remote_image,
                 model_name: str | None = None) -> PostAnalysisComputation:
    del historical_posts
    if not snapshots:
        raise PostAnalysisError("At least one metric snapshot is required.")
    ordered = sorted(snapshots, key=lambda item: item.captured_at)
    source_snapshots = ordered[-10:]
    latest = source_snapshots[-1]
    previous = source_snapshots[-2] if len(source_snapshots) > 1 else None
    metrics = observed_metrics(latest)
    deltas = calculate_metric_deltas(latest, previous)
    visual_source = media.thumbnail_url or media.media_url
    loaded = image_loader(visual_source) if visual_source else None
    image_bytes, image_mime_type = loaded if loaded else (None, None)
    baseline_samples, baseline = _baseline_for(media, latest, peer_metrics or [])
    benchmarks = _benchmarks(metrics, baseline_samples, baseline["label"])
    trend = _trend_assessment(source_snapshots)
    conclusion, strongest, worked, improve = _summary(benchmarks, baseline)
    context_reference = context_reference_for_content(account_context, media.caption, mode="analysis")
    evidence = {"benchmarks": benchmarks, "caption": media.caption, "media_type": media.media_type}
    account_reference = f"\nACCOUNT CONTEXT (content reference only, never performance evidence):\n{context_reference.text}" if context_reference.used else ""
    prompt = (
        "Use only the supplied evidence and return JSON with why_it_worked (maximum 2 possible explanations, each with title, evidence, interpretation, why_it_matters) and content_attributes "
        "(thumbnail_style, caption_style, cta_usage). Do not create a topic label; account themes are generated separately from the full account corpus. "
        f"Treat a difference as noise when it is under {NOISE_RELATIVE_PERCENT:.0f}% relative AND under {NOISE_COUNT_UNITS:.0f} count units (or {NOISE_RATE_POINTS:.1f} percentage points for rates). "
        "For noise, say it is in line with typical posts and do not explain it or recommend an experiment. Use 'significantly' only when the deterministic evidence field significant is true. "
        "Do not infer retention, hook quality, pacing, or causation without the matching metric. Never invent metrics or predict views.\n"
        f"EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}{account_reference}"
    )
    resolved_model = model_name or os.getenv("GEMINI_MODEL", "").strip()
    interpretation = None
    used_model = resolved_model
    if resolved_model:
        try:
            interpretation = _parse_interpretation(generator(prompt, image_bytes=image_bytes, image_mime_type=image_mime_type, model_name=resolved_model))
        except (GeminiConfigurationError, GeminiUpstreamError, PostAnalysisError):
            interpretation = None
    if interpretation is None:
        interpretation = _fallback_interpretation(media.caption, benchmarks)
        used_model = "deterministic-fallback-v4"
    if worked and any(item["real_gap"] and (item["percent_change"] or 0) > 0 for item in benchmarks) and interpretation.why_it_worked:
        hypothesis = interpretation.why_it_worked[0]
        text = " ".join((hypothesis.title, hypothesis.evidence, hypothesis.interpretation, hypothesis.why_it_matters)).lower()
        if not any(term in text for term in ("retention", "drop-off", "dropoff", "pacing", "watch time")):
            worked[0]["interpretation"] = re.sub(r"\bsignificantly\b", "clearly", hypothesis.interpretation, flags=re.IGNORECASE) if not any(item["significant"] for item in benchmarks) else hypothesis.interpretation
    content_payload = {"platform": "Instagram", "media_type": media.media_type, "caption": media.caption,
                       "published_at": media.published_at.isoformat(), "visual_context_used": image_bytes is not None,
                       "visual_context_kind": "thumbnail" if media.media_type.upper() in {"VIDEO", "REELS"} else "image",
                       "account_context_used": context_reference.used, "account_context_relevance": context_reference.relevance}
    data_gaps = []
    if media.media_type.upper() in {"VIDEO", "REELS"} and latest.average_watch_time_ms is None:
        data_gaps.append("Average watch time is unavailable for this Reel/video snapshot.")
    output = {"conclusion": conclusion, "strongest_metric": strongest, "what_worked": worked[:2], "what_to_improve": improve[:2],
              "metric_comparisons": benchmarks, "benchmarks": benchmarks, "baseline": baseline,
              "experiment": _experiment(media, benchmarks, baseline), "trend": trend,
              "evidence_quality": _evidence_quality(metrics, image_bytes is not None, baseline, trend),
              "methodology": {"noise_rule": f"No explanation or experiment when both the relative difference is under {NOISE_RELATIVE_PERCENT:.0f}% and the absolute difference is under {NOISE_COUNT_UNITS:.0f} units ({NOISE_RATE_POINTS:.1f} points for rates).",
                              "significant_rule": f"'Significantly' requires at least {SIGNIFICANT_RELATIVE_PERCENT:.0f}% relative and {SIGNIFICANT_COUNT_UNITS:.0f} units ({SIGNIFICANT_RATE_POINTS:.1f} point for rates).",
                              "ranking_basis": baseline["label"]},
              "data_gaps": data_gaps, "content_attributes": interpretation.content_attributes.model_dump()}
    return PostAnalysisComputation(source_snapshot_ids=[item.id for item in source_snapshots], model_name=used_model,
                                   observed_metrics=metrics, metric_deltas=deltas, content_payload=content_payload, output_payload=output)
