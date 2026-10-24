"""Account-level pattern discovery across analyzed posts."""

import re
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any


REQUIRED_ANALYZED_POSTS = 10
MIN_PATTERN_POSTS = 2


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
        "caption": str(stored.get("caption_style") or ("Question-led" if "?" in caption else "Short" if len(caption) <= 100 else "Long" if len(caption) >= 250 else "Standard")),
        "cta": str(stored.get("cta_usage") or ("Question" if "?" in caption else "Explicit CTA" if re.search(r"\b(comment|share|save|follow|click|try|tell me|let me know)\b", lowered) else "None")),
        "category": "Video" if item["media"].media_type.upper() == "VIDEO" else "Image",
    }


def _posting_window(published_at: datetime, timezone_offset_minutes: int) -> str:
    local_hour = (published_at.hour - round(timezone_offset_minutes / 60)) % 24
    start = (local_hour // 2) * 2
    end = (start + 2) % 24
    def label(hour: int) -> str:
        suffix = "AM" if hour < 12 else "PM"
        value = hour % 12 or 12
        return f"{value} {suffix}"
    return f"{label(start)} - {label(end)}"


def _rank(groups: dict[str, list[int]], baseline: float) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "label": label,
                "average_score": round(mean(scores)),
                "posts": len(scores),
                "difference_from_baseline": round(mean(scores) - baseline),
            }
            for label, scores in groups.items()
            if label not in {"", "Unavailable", "Unclassified"} and len(scores) >= MIN_PATTERN_POSTS
        ),
        key=lambda item: (item["average_score"], item["posts"]),
        reverse=True,
    )


def build_account_insights(items: list[dict[str, Any]], timezone_offset_minutes: int = 0) -> dict[str, Any]:
    analyzed = []
    for item in items:
        analyses = item.get("analyses") or []
        analysis = next((value for value in analyses if value.output_payload.get("score", {}).get("overall") is not None), None)
        if analysis and item.get("media"):
            analyzed.append({"analysis": analysis, "media": item["media"]})

    sample_size = len(analyzed)
    attribute_rows = [(_attributes(item), int(item["analysis"].output_payload["score"]["overall"]), item) for item in analyzed]
    progress = {
        "topics": sum(attrs["topic"] != "Unclassified" for attrs, _, _ in attribute_rows),
        "hashtags": sum(bool(re.findall(r"#[\w]+", item["media"].caption or "")) for _, _, item in attribute_rows),
        "posting_times": sample_size,
    }
    base = {
        "sample_size": sample_size,
        "required_sample_size": REQUIRED_ANALYZED_POSTS,
        "progress": progress,
        "top_patterns": [], "top_hashtags": [],
        "best_posting_times": [], "winning_formula": None,
    }
    if sample_size < REQUIRED_ANALYZED_POSTS:
        return base

    baseline = mean(score for _, score, _ in attribute_rows)
    groups: dict[str, dict[str, list[int]]] = {
        name: defaultdict(list) for name in ("topic", "caption", "cta", "category", "time")
    }
    hashtags: dict[str, list[int]] = defaultdict(list)
    for attrs, score, item in attribute_rows:
        for name in ("topic", "caption", "cta", "category"):
            groups[name][attrs[name]].append(score)
        groups["time"][_posting_window(item["media"].published_at, timezone_offset_minutes)].append(score)
        for hashtag in set(value.lower() for value in re.findall(r"#[\w]+", item["media"].caption or "")):
            hashtags[hashtag].append(score)

    topic_rank = _rank(groups["topic"], baseline)
    caption_rank = _rank(groups["caption"], baseline)
    cta_rank = _rank(groups["cta"], baseline)
    category_rank = _rank(groups["category"], baseline)
    time_rank = _rank(groups["time"], baseline)
    top_patterns = []
    for category, rows in (("Topic", topic_rank), ("Caption", caption_rank), ("CTA", cta_rank), ("Content category", category_rank)):
        top_patterns.extend({**row, "category": category} for row in rows)
    top_patterns.sort(key=lambda item: (item["average_score"], item["posts"]), reverse=True)
    hashtag_rank = _rank(hashtags, baseline)
    meaningful_hashtags = [item for item in hashtag_rank if abs(item["difference_from_baseline"]) >= 5]

    def winner(rows: list[dict[str, Any]]) -> str | None:
        return rows[0]["label"] if rows else None

    formula_values = {
        "topic": winner(topic_rank), "caption": winner(caption_rank),
        "cta": winner(cta_rank), "posting_time": winner(time_rank),
    }
    available_formula_values = sum(value is not None for value in formula_values.values())
    winning_formula = None if available_formula_values < 3 else {
        **formula_values,
        "confidence": min(95, round(45 + min(sample_size, 20) * 2 + available_formula_values * 2)),
    }
    return {
        **base,
        "top_patterns": top_patterns[:8],
        "top_hashtags": meaningful_hashtags[:8],
        "best_posting_times": time_rank[:5],
        "winning_formula": winning_formula,
    }
