"""Evidence-labelled account intelligence across analyzed Instagram posts."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

RECOMMENDED_SAMPLE_SIZE = 10
MIN_VISIBLE_PATTERN_POSTS = 2
MEDIUM_CONFIDENCE_POSTS = 5
HIGH_CONFIDENCE_POSTS = 10
TRACKING_TARGET_HOURS = (1, 3, 6, 12, 24)
COMPLETE_24H_MIN_HOURS = 23
COMPLETE_24H_MAX_HOURS = 26


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _attributes(item: dict[str, Any]) -> dict[str, str]:
    output = item["analysis"].output_payload
    stored = output.get("content_attributes") or {}
    caption = item["media"].caption or ""
    lowered = caption.lower()
    topic = stored.get("topic") or (
        "Tutorials" if re.search(r"\b(how to|tutorial|guide|steps?|tips?|learn)\b", lowered)
        else "Magic" if re.search(r"\b(magic|trick|illusion)\b", lowered)
        else "Comedy" if re.search(r"\b(comedy|funny|joke|skit)\b", lowered)
        else "Product" if re.search(r"\b(product|launch|shop|buy|review)\b", lowered)
        else "Unclassified"
    )
    return {
        "topic": str(topic),
        "caption": str(stored.get("caption_style") or (
            "Question-led" if "?" in caption else "Short" if len(caption) <= 100
            else "Long" if len(caption) >= 250 else "Standard"
        )),
        "cta": str(stored.get("cta_usage") or (
            "Question" if "?" in caption
            else "Explicit CTA" if re.search(r"\b(comment|share|save|follow|click|try|tell me|let me know)\b", lowered)
            else "None"
        )),
        "category": "Video" if item["media"].media_type.upper() == "VIDEO" else "Image",
    }


def _local_datetime(published_at: datetime, timezone_offset_minutes: int) -> datetime:
    # Browser getTimezoneOffset is UTC - local time.
    return _aware(published_at) - timedelta(minutes=timezone_offset_minutes)


def _posting_window(published_at: datetime, timezone_offset_minutes: int) -> str:
    local_hour = _local_datetime(published_at, timezone_offset_minutes).hour
    start = (local_hour // 2) * 2
    end = (start + 2) % 24

    def label(hour: int) -> str:
        suffix = "AM" if hour < 12 else "PM"
        return f"{hour % 12 or 12} {suffix}"

    return f"{label(start)} - {label(end)}"


def _timezone_label(offset_minutes: int) -> str:
    total = -offset_minutes
    sign = "+" if total >= 0 else "-"
    hours, minutes = divmod(abs(total), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _confidence(posts: int, total: int) -> tuple[str, str]:
    if posts >= HIGH_CONFIDENCE_POSTS and total >= RECOMMENDED_SAMPLE_SIZE:
        return "HIGH", "High confidence"
    if posts >= MEDIUM_CONFIDENCE_POSTS and total >= RECOMMENDED_SAMPLE_SIZE:
        return "MEDIUM", "Medium confidence"
    return "LOW", "Low confidence — limited sample"


def _score_rows(
    groups: dict[str, list[int]],
    baseline: float,
    total: int,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for label, scores in groups.items():
        if label in {"", "Unavailable", "Unclassified"} or len(scores) < MIN_VISIBLE_PATTERN_POSTS:
            continue
        confidence, confidence_label = _confidence(len(scores), total)
        average = round(mean(scores), 1)
        rows.append({
            "label": label,
            "category": category,
            "average_score": average,
            "posts": len(scores),
            "baseline_score": round(baseline, 1),
            "difference_from_baseline": round(average - baseline, 1),
            "benchmark": "All analyzed posts in this account",
            "confidence": confidence,
            "confidence_label": confidence_label,
            "evidence": f"Observed in {len(scores)} of {total} analyzed posts.",
            "metric_label": "Post Score",
        })
    return sorted(rows, key=lambda row: (row["average_score"], row["posts"]), reverse=True)


def _snapshot_engagement_rate(snapshot: Any) -> float | None:
    if snapshot.reach and snapshot.reach > 0:
        if snapshot.engagement_rate is not None:
            return float(snapshot.engagement_rate)
        available = [value for value in (snapshot.likes, snapshot.comments, snapshot.saves, snapshot.shares) if value is not None]
        if not available:
            return None
        interactions = sum(available)
        return round(interactions / snapshot.reach * 100, 2)
    return None


def _snapshot_near_24h(item: dict[str, Any]) -> Any | None:
    published_at = _aware(item["media"].published_at)
    candidates = []
    for snapshot in item.get("snapshots") or []:
        if getattr(snapshot, "collection_type", "manual_current") != "milestone" or getattr(snapshot, "target_hour", None) != 24:
            continue
        hours = (_aware(snapshot.captured_at) - published_at).total_seconds() / 3600
        if COMPLETE_24H_MIN_HOURS <= hours <= COMPLETE_24H_MAX_HOURS and _snapshot_engagement_rate(snapshot) is not None:
            candidates.append((abs(hours - 24), snapshot))
    return min(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _period(analyzed: list[dict[str, Any]]) -> dict[str, str | None]:
    if not analyzed:
        return {"start": None, "end": None}
    dates = sorted(_aware(item["media"].published_at) for item in analyzed)
    return {"start": dates[0].isoformat(), "end": dates[-1].isoformat()}


def _opportunity(
    title: str,
    evidence: str,
    sample_size: int,
    action: str,
    metric: str,
    decision: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "status": "HYPOTHESIS",
        "evidence": evidence,
        "sample_size": sample_size,
        "action": action,
        "metric_to_watch": metric,
        "success_criteria": decision,
        "potential_effect": None,
        "potential_effect_label": "Potential effect cannot be estimated with current data.",
    }


def _content_opportunities(
    attribute_rows: list[tuple[dict[str, str], int, dict[str, Any]]],
    complete_24h: int,
    untested_windows: list[str],
) -> list[dict[str, Any]]:
    total = len(attribute_rows)
    opportunities: list[dict[str, Any]] = []
    cta_posts = sum(attrs["cta"] not in {"", "None", "Unavailable"} for attrs, _, _ in attribute_rows)
    if total and cta_posts / total < 0.4:
        opportunities.append(_opportunity(
            "CTA experiment",
            f"A detectable CTA appears in {cta_posts} of {total} analyzed posts.",
            total,
            "Add one direct question to the next otherwise-comparable caption.",
            "Comments captured near 24 hours",
            "Compare 24-hour comments with a similar post without the question; repeat before adopting it.",
        ))
    if untested_windows:
        window = untested_windows[0]
        opportunities.append(_opportunity(
            "Untested posting window",
            f"No analyzed post was published in {window} in the selected timezone.",
            total,
            f"Publish one otherwise-comparable post in {window}.",
            "24-hour engagement rate",
            "Treat it as one trial and repeat in the same window before drawing a timing conclusion.",
        ))
    if complete_24h < RECOMMENDED_SAMPLE_SIZE:
        opportunities.append(_opportunity(
            "Build a comparable 24-hour baseline",
            f"Only {complete_24h} of {total} analyzed posts have a usable snapshot captured 23–26 hours after publishing.",
            complete_24h,
            "Refresh the next tracked post close to 24 hours after publishing.",
            "24-hour engagement rate",
            f"Continue until at least {RECOMMENDED_SAMPLE_SIZE} comparable 24-hour snapshots are available.",
        ))
    return opportunities[:4]


def build_account_insights(
    items: list[dict[str, Any]],
    timezone_offset_minutes: int = 0,
    account_context: str = "",
) -> dict[str, Any]:
    del account_context  # Retained for API compatibility; hashtags are not analyzed.
    analyzed = []
    for item in items:
        analyses = item.get("analyses") or []
        analysis = next((value for value in analyses if value.output_payload.get("score", {}).get("overall") is not None), None)
        if analysis and item.get("media"):
            analyzed.append({**item, "analysis": analysis})

    sample_size = len(analyzed)
    attribute_rows = [
        (_attributes(item), int(item["analysis"].output_payload["score"]["overall"]), item)
        for item in analyzed
    ]
    baseline = mean(score for _, score, _ in attribute_rows) if attribute_rows else 0

    groups: dict[str, dict[str, list[int]]] = {
        name: defaultdict(list) for name in ("topic", "caption", "cta", "category", "combination")
    }
    used_windows: set[str] = set()
    complete_time_groups: dict[str, list[float]] = defaultdict(list)
    complete_24h = 0

    for attrs, score, item in attribute_rows:
        for name in ("topic", "caption", "cta", "category"):
            groups[name][attrs[name]].append(score)
        window = _posting_window(item["media"].published_at, timezone_offset_minutes)
        used_windows.add(window)
        combination = " · ".join((attrs["topic"], attrs["caption"], attrs["cta"], window))
        groups["combination"][combination].append(score)
        snapshot = _snapshot_near_24h(item)
        if snapshot is not None:
            complete_24h += 1
            complete_time_groups[window].append(_snapshot_engagement_rate(snapshot))

    patterns = []
    for category, key in (("Topic", "topic"), ("Caption", "caption"), ("CTA", "cta"), ("Content category", "category")):
        patterns.extend(_score_rows(groups[key], baseline, sample_size, category=category))
    patterns.sort(key=lambda row: (row["average_score"], row["posts"]), reverse=True)

    posting_time_rows = []
    time_baseline_values = [value for values in complete_time_groups.values() for value in values]
    time_baseline = mean(time_baseline_values) if time_baseline_values else 0
    for label, values in complete_time_groups.items():
        if len(values) < MIN_VISIBLE_PATTERN_POSTS:
            continue
        confidence, confidence_label = _confidence(len(values), complete_24h)
        average_value = round(mean(values), 2)
        posting_time_rows.append({
            "label": label,
            "average_value": average_value,
            "average_score": average_value,
            "posts": len(values),
            "baseline_score": round(time_baseline, 2),
            "difference_from_baseline": round(average_value - time_baseline, 2),
            "benchmark": "All complete 24-hour snapshots in this account",
            "confidence": confidence,
            "confidence_label": confidence_label,
            "evidence": f"Based on {len(values)} posts with a snapshot captured 23–26 hours after publishing.",
            "metric_label": "24-hour engagement rate",
        })
    posting_time_rows.sort(key=lambda row: (row["average_value"], row["posts"]), reverse=True)

    candidate_windows = [
        f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'} - {(hour + 2) % 12 or 12} {'AM' if (hour + 2) % 24 < 12 else 'PM'}"
        for hour in range(6, 24, 2)
    ]
    untested_windows = [window for window in candidate_windows if window not in used_windows]

    combination_rows = _score_rows(groups["combination"], baseline, sample_size)
    tested_combination = next((row for row in combination_rows if row["posts"] >= 3 and row["difference_from_baseline"] > 0), None)
    if tested_combination:
        tested_combination = {
            **tested_combination,
            "label_type": "Pattern to validate",
            "caution": "These elements appeared together, but the association does not prove that the combination caused performance.",
        }

    progress = {
        "patterns": sample_size,
        "posting_times": complete_24h,
    }
    enough_data = sample_size >= RECOMMENDED_SAMPLE_SIZE
    period = _period(analyzed)
    return {
        "sample_size": sample_size,
        "required_sample_size": RECOMMENDED_SAMPLE_SIZE,
        "enough_data": enough_data,
        "heading": "Observed account patterns" if enough_data else "Patterns to validate",
        "sample_notice": (
            f"{sample_size} / {RECOMMENDED_SAMPLE_SIZE} analyzed posts. Results remain observational, not causal."
        ),
        "confidence_policy": {
            "low": f"Fewer than {MEDIUM_CONFIDENCE_POSTS} matching posts, or fewer than {RECOMMENDED_SAMPLE_SIZE} total posts",
            "medium": f"At least {MEDIUM_CONFIDENCE_POSTS} matching posts and {RECOMMENDED_SAMPLE_SIZE} total posts",
            "high": f"At least {HIGH_CONFIDENCE_POSTS} matching posts and {RECOMMENDED_SAMPLE_SIZE} total posts",
        },
        "observation_period": {**period, "timezone": _timezone_label(timezone_offset_minutes)},
        "progress": progress,
        "patterns": patterns[:10],
        "posting_time_insights": posting_time_rows[:6],
        "untested_posting_windows": untested_windows[:4],
        "posting_time_metadata": {
            "timezone": _timezone_label(timezone_offset_minutes),
            "period_start": period["start"],
            "period_end": period["end"],
            "metric": "Engagement rate from a cumulative snapshot captured 23–26 hours after publishing",
            "complete_posts": complete_24h,
            "incomplete_posts": max(0, sample_size - complete_24h),
        },
        "tracking_24h": {
            "available": complete_24h > 0,
            "complete_posts": complete_24h,
            "total_posts": sample_size,
            "target_hours": list(TRACKING_TARGET_HOURS),
            "automatic_collection": any(
                item.get("post_publish_tracking", {}).get("automatic_collection")
                for item in analyzed
            ),
            "status": "LIMITED" if complete_24h < RECOMMENDED_SAMPLE_SIZE else "AVAILABLE",
            "message": (
                "Only completed 24-hour milestone snapshots are compared. Older lifetime snapshots and missed "
                "milestones are not presented as 24-hour results."
            ),
        },
        "content_opportunities": _content_opportunities(attribute_rows, complete_24h, untested_windows),
        "tested_combination": tested_combination,
    }
