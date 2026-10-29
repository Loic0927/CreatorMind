"""Account-specific themes and maturity-safe Instagram insights."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any


RECOMMENDED_SAMPLE_SIZE = 10
MIN_PATTERN_POSTS = 3
TRACKING_TARGET_HOURS = (24,)
COMPLETE_24H_MIN_HOURS = 23
COMPLETE_24H_MAX_HOURS = 26


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value else None


def _analysis(item: dict[str, Any]) -> Any | None:
    analyses = item.get("analyses") or []
    return analyses[0] if analyses else None


def _format_label(media_type: str) -> str:
    value = str(media_type or "UNKNOWN").upper()
    return "Reel / video" if value in {"VIDEO", "REELS"} else "Carousel" if value == "CAROUSEL_ALBUM" else "Image"


def _structural_attributes(item: dict[str, Any]) -> dict[str, str]:
    media = item["media"]
    caption = media.caption or ""
    words = len(re.findall(r"\b\w+\b", re.sub(r"(?<!\w)[#@][\w'-]+", " ", caption)))
    length = "Short caption" if words <= 20 else "Long caption" if words > 60 else "Medium caption"
    has_cta = bool(re.search(r"\b(comment|share|save|follow|click|tap|try|tell me|let me know|send|visit)\b", caption.lower()))
    return {"format": _format_label(media.media_type), "length": length, "cta": "CTA" if has_cta else "No CTA"}


def _theme_labels_for_item(item: dict[str, Any]) -> tuple[str, str, str]:
    attrs = _structural_attributes(item)
    return (
        f"{attrs['format']} · {attrs['length']}",
        f"{attrs['format']} · {attrs['cta']}",
        f"{attrs['length']} · {attrs['cta']}",
    )


def generate_account_themes(items: list[dict[str, Any]]) -> list[str]:
    """Choose one structural 3-5 group partition; never name themes from caption subjects."""
    eligible = [item for item in items if item.get("media") and _analysis(item)]
    for scheme_index in range(3):
        labels = [_theme_labels_for_item(item)[scheme_index] for item in eligible]
        counts = Counter(labels)
        if 3 <= len(counts) <= 5 and all(count >= 2 for count in counts.values()):
            return sorted(counts, key=lambda label: (-counts[label], label))
    return []


def account_themes_meet_constraints(items: list[dict[str, Any]], themes: list[str]) -> bool:
    if not 3 <= len(themes) <= 5 or len(set(themes)) != len(themes):
        return False
    eligible = [item for item in items if item.get("media") and _analysis(item)]
    assigned = [assign_account_theme(item, themes) for item in eligible]
    counts = Counter(assigned)
    return bool(eligible) and "Theme unavailable" not in counts and all(counts[theme] >= 2 for theme in themes)


def assign_account_theme(item: dict[str, Any], themes: list[str]) -> str:
    if not themes or not item.get("media"):
        return "Theme unavailable"
    return next((label for label in _theme_labels_for_item(item) if label in themes), "Theme unavailable")


def _caption_attributes(item: dict[str, Any]) -> dict[str, str]:
    analysis = _analysis(item)
    stored = (analysis.output_payload.get("content_attributes") if analysis else {}) or {}
    caption = item["media"].caption or ""
    lowered = caption.lower()
    return {
        "caption": str(stored.get("caption_style") or ("Question-led" if "?" in caption else "Short" if len(caption) <= 100 else "Long" if len(caption) >= 250 else "Standard")),
        "cta": str(stored.get("cta_usage") or ("Question" if "?" in caption else "Explicit CTA" if re.search(r"\b(comment|share|save|follow|click|try|tell me|let me know)\b", lowered) else "None")),
    }


def _local_datetime(published_at: datetime, timezone_offset_minutes: int) -> datetime:
    return _aware(published_at) - timedelta(minutes=timezone_offset_minutes)


def _posting_window(published_at: datetime, timezone_offset_minutes: int) -> str:
    hour = _local_datetime(published_at, timezone_offset_minutes).hour
    start, end = (hour // 2) * 2, ((hour // 2) * 2 + 2) % 24
    label = lambda value: f"{value % 12 or 12} {'AM' if value < 12 else 'PM'}"
    return f"{label(start)} - {label(end)}"


def _timezone_label(offset_minutes: int) -> str:
    total = -offset_minutes
    sign = "+" if total >= 0 else "-"
    hours, minutes = divmod(abs(total), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _snapshot_engagement_rate(snapshot: Any) -> float | None:
    if not snapshot or not snapshot.reach or snapshot.reach <= 0:
        return None
    if snapshot.engagement_rate is not None:
        return round(float(snapshot.engagement_rate), 1)
    available = [value for value in (snapshot.likes, snapshot.comments, snapshot.saves, snapshot.shares) if value is not None]
    return round(sum(available) / snapshot.reach * 100, 1) if available else None


def _snapshot_at_24h(item: dict[str, Any]) -> Any | None:
    published = _aware(item["media"].published_at)
    candidates = []
    for snapshot in item.get("snapshots") or []:
        if getattr(snapshot, "collection_type", "manual_current") != "milestone" or getattr(snapshot, "target_hour", None) != 24:
            continue
        hours = (_aware(snapshot.captured_at) - published).total_seconds() / 3600
        if COMPLETE_24H_MIN_HOURS <= hours <= COMPLETE_24H_MAX_HOURS:
            candidates.append((abs(hours - 24), snapshot))
    return min(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _latest_snapshot(item: dict[str, Any]) -> Any | None:
    snapshots = item.get("snapshots") or []
    return max(snapshots, key=lambda value: _aware(value.captured_at)) if snapshots else item.get("latest")


def _maturity_days(media_type: str) -> int:
    return 14 if media_type.upper() in {"VIDEO", "REELS"} else 7


def _post_age_days(media: Any, snapshot: Any = None, now: datetime | None = None) -> float | None:
    """Return the post's current age, never the age of its latest snapshot."""
    del snapshot
    published_at = getattr(media, "published_at", None)
    if published_at is None:
        return None
    current = _aware(now or datetime.now(timezone.utc))
    return max(0.0, (current - _aware(published_at)).total_seconds() / 86400)


def _maturity_key(media_type: str, age_days: float | None, snapshots: list[Any] | None = None,
                  external_insights: list[Any] | None = None) -> tuple[str, str, bool, float | None]:
    threshold = _maturity_days(media_type)
    # The day rule is the deterministic fallback and wins once reached. Growth
    # evidence is useful only for posts that are still inside that window.
    if age_days is not None and age_days >= threshold:
        return "mature", f"Mature by {threshold}-day rule", True, None
    viewed = sorted(
        [item for item in (snapshots or []) if isinstance(getattr(item, "views", None), (int, float))],
        key=lambda item: _aware(item.captured_at),
    )
    if len(viewed) >= 2:
        latest = viewed[-1]
        recent = [item for item in viewed[:-1] if (_aware(latest.captured_at) - _aware(item.captured_at)).total_seconds() <= 48 * 3600]
        if recent:
            earliest = recent[0]
            start, end = float(earliest.views), float(latest.views)
            if start > 0 and end >= start:
                growth = (end - start) / start * 100
                hours = (_aware(latest.captured_at) - _aware(earliest.captured_at)).total_seconds() / 3600
                mature = growth < 3
                return ("mature" if mature else "growing", f"Views grew {growth:.1f}% over {hours:.0f}h", mature, round(growth, 1))
    for record in external_insights or []:
        share = ((getattr(record, "payload", {}) or {}).get("curve") or {}).get("share_of_final_by_24h")
        if isinstance(share, (int, float)):
            mature = float(share) >= 97
            return ("mature" if mature else "growing", f"Screenshot curve: about {float(share):.1f}% reached by 24h", mature, None)
    if age_days is None:
        return "unknown", "Age unavailable", False, None
    if age_days >= threshold:
        return "mature", f"Mature by {threshold}-day fallback", True, None
    if age_days < 0.75:
        return "0-18h", "Early: under 18 hours", False, None
    if age_days < 1.5:
        return "18-36h", "Early: 18-36 hours", False, None
    if age_days < 2:
        return "36-48h", "Early: 36-48 hours", False, None
    return f"2-{threshold}d", f"Developing: 2-{threshold} days", False, None


def _snapshot_metrics(snapshot: Any) -> dict[str, Any]:
    status = dict(getattr(snapshot, "metric_status", {}) or {}) if snapshot else {}
    metrics: dict[str, Any] = {}
    for name in ("views", "reach", "likes", "comments", "saves", "shares", "average_watch_time_ms", "total_watch_time_ms"):
        value = getattr(snapshot, name, None) if snapshot else None
        metrics[name] = int(value) if isinstance(value, (int, float)) else None
        status.setdefault(name, "available" if isinstance(value, (int, float)) else "unavailable")
    metrics["engagement_rate"] = _snapshot_engagement_rate(snapshot)
    return {"metrics": metrics, "metric_status": status}


def _has_metrics(metrics: dict[str, Any]) -> bool:
    return any(isinstance(value, (int, float)) for key, value in metrics.items() if key != "skip_rate_pct")


def _performance_posts(items: list[dict[str, Any]], timezone_offset_minutes: int, themes: list[str]) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for item in items:
        media = item.get("media")
        if not media:
            continue
        latest = _latest_snapshot(item)
        age_days = _post_age_days(media, latest)
        snapshots = sorted(item.get("snapshots") or [], key=lambda value: _aware(value.captured_at))
        external = item.get("external_insights") or []
        key, basis, mature, growth_pct = _maturity_key(str(media.media_type or "UNKNOWN"), age_days, snapshots, external)
        payload = _snapshot_metrics(latest)
        screenshot_payload = (external[0].payload if external else {}) or {}
        payload["metrics"]["skip_rate_pct"] = screenshot_payload.get("skip_rate_pct")
        payload["metric_status"]["skip_rate_pct"] = "available" if screenshot_payload.get("skip_rate_pct") is not None else "unavailable"
        attrs = _caption_attributes(item)
        has_metrics = _has_metrics(payload["metrics"])
        captured_at = _aware(latest.captured_at) if latest else None
        stale = bool(captured_at and datetime.now(timezone.utc) - captured_at > timedelta(hours=48))
        if not has_metrics:
            status_label = "No data"
        elif stale:
            status_label = "Needs refresh"
        else:
            status_label = "Mature" if mature else "Growing"
        published_label = _aware(media.published_at).strftime("%d %b %Y")
        format_label = _format_label(media.media_type)
        posts.append({
            "tracked_post_id": getattr(item.get("tracking"), "id", None), "instagram_media_id": media.instagram_media_id,
            "permalink": media.permalink, "thumbnail_url": media.thumbnail_url or media.media_url,
            "media_type": str(media.media_type or "UNKNOWN").upper(),
            "media_type_label": _format_label(media.media_type),
            "theme": assign_account_theme(item, themes), "published_at": _iso(media.published_at),
            "posting_window": _posting_window(media.published_at, timezone_offset_minutes), "caption_excerpt": (media.caption or "")[:180],
            "display_title": f"{format_label} · {published_label}",
            "observation_kind": "Mature lifetime snapshot" if mature else "Latest cumulative snapshot" if latest else "No snapshot",
            "comparison_basis": basis, "maturity_key": key, "mature": mature, "age_days": round(age_days, 1) if age_days is not None else None,
            "snapshot_captured_at": _iso(latest.captured_at) if latest else None, **payload,
            "has_metrics": has_metrics, "status_label": status_label,
            "metrics_unavailable_reason": None if has_metrics else "Instagram has not returned supported metrics for this post yet.",
            "metric_sources": {name: ("From your screenshot" if name == "skip_rate_pct" else "Instagram API") for name, value in payload["metrics"].items() if value is not None},
            "first_24_hours": item.get("first_24_hours"),
            "comparison": None, "caption_style": attrs["caption"], "cta_style": attrs["cta"],
            "exclude_from_comparisons": bool(getattr(item.get("tracking"), "exclude_from_comparisons", False)),
            "maturity_growth_pct": growth_pct,
        })
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if post["has_metrics"] and post["mature"] and not post["exclude_from_comparisons"]:
            groups[(post["media_type"], post["maturity_key"])].append(post)
    for (media_type, _), candidates in groups.items():
        metric = "views" if sum(post["metrics"].get("views") is not None for post in candidates) >= 2 else "reach"
        comparable = [post for post in candidates if post["metrics"].get(metric) is not None]
        if len(comparable) < 6:
            continue
        for rank, post in enumerate(sorted(comparable, key=lambda value: value["metrics"][metric], reverse=True), start=1):
            post["comparison"] = {"rank": rank, "group_size": len(comparable), "metric": metric,
                                  "group": f"{media_type} posts · {post['comparison_basis']}"}
    return sorted(posts, key=lambda post: post["published_at"] or "", reverse=True)


def _pattern_rows(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [post for post in posts if post["mature"] and post["has_metrics"] and not post["exclude_from_comparisons"] and post["metrics"].get("engagement_rate") is not None]
    if not eligible:
        return []
    dimensions = {"Theme": "theme", "Caption style": "caption_style", "CTA": "cta_style", "Format": "media_type_label"}
    rows = []
    for dimension, field in dimensions.items():
        groups: dict[str, list[float]] = defaultdict(list)
        for post in eligible:
            label = "Has CTA" if dimension == "CTA" and post[field] != "None" else "No CTA" if dimension == "CTA" else post[field]
            groups[label].append(post["metrics"]["engagement_rate"])
        if len(groups) < 2:
            continue
        dimension_rows = []
        for label, values in groups.items():
            other_values = [value for other_label, group in groups.items() if other_label != label for value in group]
            if len(values) < MIN_PATTERN_POSTS or len(other_values) < MIN_PATTERN_POSTS:
                continue
            average = mean(values)
            other_average = mean(other_values)
            absolute = average - other_average
            relative = absolute / other_average * 100 if other_average else None
            if relative is None or absolute == 0:
                continue
            dimension_rows.append({"label": label, "category": dimension, "value": round(average, 1), "posts": len(values),
                                   "baseline": round(other_average, 1), "comparison_posts": len(other_values), "difference": round(absolute, 1),
                                   "metric_label": "mature lifetime engagement rate", "basis": f"{len(values)} vs {len(other_values)} mature posts",
                                   "sample_note": f"Compared with {len(other_values)} posts in the other groups",
                                   "distribution": {"minimum": round(min(values), 1), "median": round(median(values), 1), "maximum": round(max(values), 1)}})
        if dimension_rows:
            rows.append(max(dimension_rows, key=lambda row: abs(row["difference"])))
    return sorted(rows, key=lambda row: abs(row["difference"]), reverse=True)


def _performance_summary(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if post["mature"] and post.get("has_metrics") and not post["exclude_from_comparisons"]:
            groups[post["media_type"]].append(post)
    candidates = [(media_type, group) for media_type, group in groups.items() if len(group) >= MIN_PATTERN_POSTS]
    if not candidates:
        return None
    media_type, group = max(candidates, key=lambda pair: len(pair[1]))
    reach_posts = [post for post in group if post["metrics"].get("reach") is not None]
    rate_posts = [post for post in group if post["metrics"].get("engagement_rate") is not None]
    if len(reach_posts) < MIN_PATTERN_POSTS or len(rate_posts) < MIN_PATTERN_POSTS:
        return None
    reach_median = median(post["metrics"]["reach"] for post in reach_posts)
    rate_median = median(post["metrics"]["engagement_rate"] for post in rate_posts)
    label = _format_label(media_type)

    def item(kind: str, post: dict[str, Any], metric: str, typical: float) -> dict[str, Any]:
        value = float(post["metrics"][metric])
        note = None
        if kind == "lowest_reach" and post["metrics"].get("engagement_rate") is not None and post["metrics"]["engagement_rate"] > rate_median:
            note = f"Engagement rate is above the {rate_median:.1f}% group median."
        return {"kind": kind, "title": post["display_title"], "thumbnail_url": post["thumbnail_url"],
                "published_at": post["published_at"], "media_type_label": post["media_type_label"],
                "value": round(value, 1) if metric == "engagement_rate" else int(round(value)),
                "difference": round(value - typical, 1) if metric == "engagement_rate" else int(round(value - typical)), "metric": metric, "note": note}

    return {
        "media_type": media_type, "media_type_label": label, "sample_size": len(group),
        "source": "Instagram API",
        "reach_sample_size": len(reach_posts), "engagement_rate_sample_size": len(rate_posts),
        "reach_median": int(round(reach_median)), "engagement_rate_median": round(rate_median, 1),
        "highest_reach": item("highest_reach", max(reach_posts, key=lambda post: post["metrics"]["reach"]), "reach", reach_median),
        "lowest_reach": item("lowest_reach", min(reach_posts, key=lambda post: post["metrics"]["reach"]), "reach", reach_median),
        "highest_engagement_rate": item("highest_engagement_rate", max(rate_posts, key=lambda post: post["metrics"]["engagement_rate"]), "engagement_rate", rate_median),
        "lowest_engagement_rate": item("lowest_engagement_rate", min(rate_posts, key=lambda post: post["metrics"]["engagement_rate"]), "engagement_rate", rate_median),
    }


def _theme_stats(posts: list[dict[str, Any]], themes: list[str]) -> list[dict[str, Any]]:
    if not themes:
        return []
    result = []
    for theme in themes:
        members = [post for post in posts if post["theme"] == theme]
        views = [post["metrics"]["views"] for post in members if not post["exclude_from_comparisons"] and post.get("metrics") and post["metrics"].get("views") is not None]
        if len(members) < 2:
            return []
        result.append({"name": theme, "post_count": len(members), "median_views": int(round(median(views))) if views else None})
    return result


def _posting_time_rows(items: list[dict[str, Any]], timezone_offset_minutes: int) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for item in items:
        snapshot = _snapshot_at_24h(item) if item.get("media") else None
        rate = _snapshot_engagement_rate(snapshot)
        if rate is not None:
            groups[_posting_window(item["media"].published_at, timezone_offset_minutes)].append(rate)
    values = [value for group in groups.values() for value in group]
    if not values or len(groups) < 2:
        return []
    baseline = mean(values)
    rows = []
    for label, group in groups.items():
        if len(group) < MIN_PATTERN_POSTS:
            continue
        difference = mean(group) - baseline
        relative = difference / baseline * 100 if baseline else None
        if relative is None or difference == 0:
            continue
        rows.append({"label": label, "category": "Posting window", "value": round(mean(group), 1), "posts": len(group),
                     "baseline": round(baseline, 1), "difference": round(difference, 1), "metric_label": "24-hour engagement rate",
                     "basis": f"{len(values)} completed 24-hour snapshots", "sample_note": f"Only {len(group)} posts, treat as a hint",
                     "distribution": {"minimum": round(min(group), 1), "median": round(median(group), 1), "maximum": round(max(group), 1)}})
    return sorted(rows, key=lambda row: abs(row["difference"]), reverse=True)


def _tracking_state(items: list[dict[str, Any]], complete: int) -> dict[str, Any]:
    automatic = any((item.get("first_24_hours") or {}).get("api_capture_status") != "scheduler_unavailable" for item in items)
    pending = blocked = unavailable = 0
    for item in items:
        status = (item.get("first_24_hours") or {}).get("api_capture_status")
        pending += status in {"pending", "running", "retry"}
        blocked += status in {"blocked_reauthorization", "permission_required"}
        unavailable += status in {"missed", "cancelled", "unavailable"}
    reason = "24-hour tracking is optional; mature lifetime comparisons are the default."
    return {"automatic_collection": automatic, "pending_posts": pending, "blocked_posts": blocked, "unavailable_posts": unavailable, "reason": reason,
            "available": complete > 0, "complete_posts": complete, "total_posts": len(items), "target_hours": [24],
            "status": "AVAILABLE" if complete >= RECOMMENDED_SAMPLE_SIZE else "LIMITED", "message": reason}


def build_account_insights(items: list[dict[str, Any]], timezone_offset_minutes: int = 0, account_context: str = "", themes: list[str] | None = None) -> dict[str, Any]:
    del account_context
    analyzed = [item for item in items if item.get("media") and _analysis(item)]
    supplied_themes = list(themes or [])
    theme_list = supplied_themes if account_themes_meet_constraints(analyzed, supplied_themes) else generate_account_themes(analyzed)
    posts = _performance_posts(items, timezone_offset_minutes, theme_list)
    theme_stats = _theme_stats(posts, theme_list)
    if not theme_stats:
        theme_list = []
        for post in posts:
            post["theme"] = "Theme unavailable"
    patterns = _pattern_rows(posts)
    performance_summary = _performance_summary(posts)
    posting_times = _posting_time_rows(analyzed, timezone_offset_minutes)
    complete_24h = sum(_snapshot_engagement_rate(_snapshot_at_24h(item)) is not None for item in analyzed)
    dates = sorted(_aware(item["media"].published_at) for item in analyzed)
    period = {"start": dates[0].isoformat() if dates else None, "end": dates[-1].isoformat() if dates else None}
    mature_count = sum(post["mature"] for post in posts)
    posts_with_metrics = [post for post in posts if post.get("has_metrics")]
    watch_time_count = sum(post["metrics"].get("average_watch_time_ms") is not None for post in posts_with_metrics)
    show_average_watch_time = bool(posts_with_metrics) and watch_time_count > len(posts_with_metrics) / 2
    skip_rate_count = sum(post["metrics"].get("skip_rate_pct") is not None for post in posts_with_metrics)
    show_skip_rate = bool(posts_with_metrics) and skip_rate_count > len(posts_with_metrics) / 2
    peak_shares = []
    for item in items:
        records = item.get("external_insights") or []
        if not records:
            continue
        share = ((records[0].payload or {}).get("curve") or {}).get("share_of_final_by_24h")
        if isinstance(share, (int, float)):
            peak_shares.append(float(share))
    peak_summary = ({"sample_size": len(peak_shares), "median_share_of_final_by_24h": round(median(peak_shares), 1),
                     "source": "Estimated from your screenshots"} if len(peak_shares) >= 3 else None)
    opportunities = []
    if mature_count < MIN_PATTERN_POSTS:
        opportunities.append({"title": "Build a mature same-format baseline", "priority": 1, "status": "DATA_GAP",
                              "current_observation": f"{mature_count} mature posts are available across the connected account.",
                              "sample_size": mature_count, "observation_period": period,
                              "data_gap": "At least 3 mature posts in a repeated group are needed before showing a content pattern.",
                              "suggested_test": "Keep collecting lifetime metrics; do not change strategy from this sample yet.",
                              "primary_variable": "None — data collection only", "tracking_metric": "Lifetime reach, views and engagement rate",
                              "capture_timing": "After 7 days for images/carousels and 14 days for video/Reels.",
                              "decision_method": "Review again when at least 3 comparable mature posts exist.", "repetitions_required": 3})
    return {
        "sample_size": len(analyzed), "required_sample_size": RECOMMENDED_SAMPLE_SIZE, "enough_data": len(analyzed) >= RECOMMENDED_SAMPLE_SIZE,
        "heading": "Account insights", "sample_notice": f"{len(analyzed)} analyzed posts total; {mature_count} currently qualify for mature lifetime comparison.",
        "observation_period": {**period, "timezone": _timezone_label(timezone_offset_minutes)},
        "progress": {"patterns": len(analyzed), "posting_times": complete_24h, "mature_posts": mature_count},
        "themes": theme_list, "theme_stats": theme_stats,
        "theme_method": "Derived from repeated content formats and purposes in this account; each visible theme has at least 2 posts.",
        "patterns": patterns, "posting_time_insights": posting_times, "untested_posting_windows": [],
        "posting_time_metadata": {"timezone": _timezone_label(timezone_offset_minutes), "period_start": period["start"], "period_end": period["end"],
                                  "metric": "Optional advanced view: engagement rate from a completed 24-hour milestone", "complete_posts": complete_24h,
                                  "incomplete_posts": max(0, len(analyzed) - complete_24h)},
        "tracking_24h": _tracking_state(analyzed, complete_24h),
        "metric_capabilities": {
            "account_requirement": "Instagram professional account (Business or Creator).", "required_scope": "instagram_business_manage_insights",
            "definitions": {"views": "Cumulative views returned by Instagram; repeat views may be included.", "reach": "Unique accounts reached when Instagram returns this estimated metric."},
            "currently_collected": ["views", "reach", "likes", "comments", "saves", "shares", "Reels average watch time", "Reels total watch time"],
            "advanced_metrics": [
                {"key": "average_watch_time", "status": "collected_when_available", "reason": "Requested for video/Reels and shown as unavailable when Meta does not return it."},
                {"key": "total_watch_time", "status": "collected_when_available", "reason": "Requested for video/Reels and shown as unavailable when Meta does not return it."},
                {"key": "follower_non_follower_reach", "status": "unavailable", "reason": "Meta exposes follow-type breakdowns at account-insight level, not as this per-media lifetime metric; PostBridge does not infer a split."},
                {"key": "audience_demographics", "status": "unavailable", "reason": "Not collected yet; availability is account-level and threshold-dependent."},
                {"key": "online_followers", "status": "unsupported", "reason": "The current Instagram API with Instagram Login does not expose online_followers for this integration. You can optionally upload the account-level Audience most-active-times chart instead."},
            ],
        },
        "performance_posts": posts, "performance_summary": performance_summary,
        "show_average_watch_time": show_average_watch_time,
        "show_skip_rate": show_skip_rate, "how_fast_posts_peak": peak_summary,
        "content_opportunities": opportunities, "tested_combination": None,
        "methodology": {"default_basis": "Lifetime comparisons use posts at least 7 days old, or 14 days old for video and Reels, grouped by media format.",
                        "pattern_rule": "Patterns need at least 3 posts, real variation, and a difference above the noise threshold.",
                        "advanced_basis": "The single 24-hour API capture and confirmed screenshots keep visible source labels and are never mixed silently."},
    }
