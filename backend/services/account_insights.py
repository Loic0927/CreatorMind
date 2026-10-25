"""Evidence-labelled account intelligence across analyzed Instagram posts."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median
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


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value else None


def _attributes(item: dict[str, Any]) -> dict[str, str]:
    analysis = item.get("analysis")
    output = analysis.output_payload if analysis else {}
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
    media_type = str(item["media"].media_type or "UNKNOWN").upper()
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
        "category": "Reel / video" if media_type in {"VIDEO", "REELS"} else "Carousel" if media_type == "CAROUSEL_ALBUM" else "Image",
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
        return "HIGH", "High sample sufficiency"
    if posts >= MEDIUM_CONFIDENCE_POSTS and total >= RECOMMENDED_SAMPLE_SIZE:
        return "MEDIUM", "Medium sample sufficiency"
    return "LOW", "Low sample sufficiency - limited sample"


def _difference_interpretation(difference: float, threshold: float) -> str:
    if abs(difference) < threshold:
        return "The difference is small, so there is no clear direction yet."
    if difference > 0:
        return "This group is above the account baseline, but the association is observational."
    return "This group is below the account baseline, but the association is observational."


def _score_rows(
    groups: dict[str, list[float]],
    baseline: float,
    total: int,
    *,
    category: str | None = None,
    metric_label: str = "Post Score",
    difference_threshold: float = 3.0,
    benchmark: str = "All analyzed posts in this account",
) -> list[dict[str, Any]]:
    rows = []
    for label, values in groups.items():
        if label in {"", "Unavailable", "Unclassified"} or len(values) < MIN_VISIBLE_PATTERN_POSTS:
            continue
        confidence, confidence_label = _confidence(len(values), total)
        digits = 2 if "engagement" in metric_label.lower() else 1
        average = round(mean(values), digits)
        difference = round(average - baseline, digits)
        rows.append({
            "label": label,
            "category": category,
            "average_score": average,
            "posts": len(values),
            "baseline_score": round(baseline, digits),
            "difference_from_baseline": difference,
            "benchmark": benchmark,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "confidence_meaning": "Sample sufficiency only; this is not the probability that the conclusion is correct.",
            "evidence": f"Observed in {len(values)} of {total} eligible posts.",
            "metric_label": metric_label,
            "distribution": {
                "minimum": round(min(values), digits),
                "median": round(median(values), digits),
                "maximum": round(max(values), digits),
            },
            "difference_interpretation": _difference_interpretation(difference, difference_threshold),
        })
    return sorted(rows, key=lambda row: (row["average_score"], row["posts"]), reverse=True)


def _snapshot_engagement_rate(snapshot: Any) -> float | None:
    if snapshot.reach and snapshot.reach > 0:
        if snapshot.engagement_rate is not None:
            return float(snapshot.engagement_rate)
        available = [value for value in (snapshot.likes, snapshot.comments, snapshot.saves, snapshot.shares) if value is not None]
        if not available:
            return None
        return round(sum(available) / snapshot.reach * 100, 2)
    return None


def _snapshot_at_24h(item: dict[str, Any]) -> Any | None:
    published_at = _aware(item["media"].published_at)
    candidates = []
    for snapshot in item.get("snapshots") or []:
        if getattr(snapshot, "collection_type", "manual_current") != "milestone" or getattr(snapshot, "target_hour", None) != 24:
            continue
        hours = (_aware(snapshot.captured_at) - published_at).total_seconds() / 3600
        if COMPLETE_24H_MIN_HOURS <= hours <= COMPLETE_24H_MAX_HOURS:
            candidates.append((abs(hours - 24), snapshot))
    return min(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _snapshot_near_24h(item: dict[str, Any]) -> Any | None:
    snapshot = _snapshot_at_24h(item)
    return snapshot if snapshot is not None and _snapshot_engagement_rate(snapshot) is not None else None


def _period(analyzed: list[dict[str, Any]]) -> dict[str, str | None]:
    if not analyzed:
        return {"start": None, "end": None}
    dates = sorted(_aware(item["media"].published_at) for item in analyzed)
    return {"start": dates[0].isoformat(), "end": dates[-1].isoformat()}


def _tracking_state(analyzed: list[dict[str, Any]], complete_24h: int) -> dict[str, Any]:
    automatic = any(item.get("post_publish_tracking", {}).get("automatic_collection") for item in analyzed)
    pending = blocked = unavailable = 0
    for item in analyzed:
        milestones = item.get("post_publish_tracking", {}).get("milestones") or []
        target = next((value for value in milestones if value.get("target_hour") == 24), None)
        status = target.get("status") if target else None
        if status in {"pending", "running", "retry"}:
            pending += 1
        elif status in {"blocked_reauthorization", "permission_required"}:
            blocked += 1
        elif status in {"missed", "cancelled", "unavailable"}:
            unavailable += 1

    if not automatic:
        reason = "Automatic milestone collection is unavailable; lifetime or manual snapshots are not substituted for 24-hour data."
    elif blocked:
        reason = f"{blocked} post(s) need Instagram reauthorization or Insights permission before collection can continue."
    elif pending:
        reason = f"{pending} post(s) are still waiting for their scheduled 24-hour capture."
    elif unavailable:
        reason = f"{unavailable} post(s) missed the window, were cancelled, or are no longer accessible."
    elif complete_24h == 0:
        reason = "No eligible post has a complete 24-hour milestone snapshot yet."
    else:
        reason = "Only completed 24-hour milestone snapshots are compared."
    return {"automatic_collection": automatic, "pending_posts": pending, "blocked_posts": blocked, "unavailable_posts": unavailable, "reason": reason}


def _opportunity(
    *, priority: int, title: str, current_observation: str, sample_size: int,
    period: dict[str, str | None], data_gap: str, suggested_test: str,
    primary_variable: str, tracking_metric: str, capture_timing: str,
    decision_method: str, repetitions_required: int,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "title": title,
        "status": "DATA_GAP" if priority == 1 else "HYPOTHESIS",
        "current_observation": current_observation,
        "sample_size": sample_size,
        "observation_period": period,
        "data_gap": data_gap,
        "suggested_test": suggested_test,
        "primary_variable": primary_variable,
        "tracking_metric": tracking_metric,
        "capture_timing": capture_timing,
        "decision_method": decision_method,
        "repetitions_required": repetitions_required,
        "effect_estimate": None,
        "effect_estimate_label": "Impact cannot currently be estimated.",
    }


def _content_opportunities(
    attribute_rows: list[tuple[dict[str, str], int, dict[str, Any]]],
    complete_24h: int,
    untested_windows: list[str],
    period: dict[str, str | None],
    tracking_state: dict[str, Any],
) -> list[dict[str, Any]]:
    total = len(attribute_rows)
    opportunities: list[dict[str, Any]] = []
    if complete_24h < RECOMMENDED_SAMPLE_SIZE:
        opportunities.append(_opportunity(
            priority=1,
            title="Collect a comparable 24-hour baseline",
            current_observation=f"{complete_24h} of {total} analyzed posts have a complete, comparable 24-hour milestone snapshot.",
            sample_size=complete_24h,
            period=period,
            data_gap=tracking_state["reason"],
            suggested_test="Enable tracking on the next eligible post and let the scheduled 1h, 3h, 6h, 12h and 24h captures complete.",
            primary_variable="Data collection only; do not change a content variable for this step.",
            tracking_metric="Views, reach, likes, comments, saves and shares actually returned by Instagram.",
            capture_timing="Separate milestone snapshots at 1h, 3h, 6h, 12h and 24h after publishing.",
            decision_method=f"Do not compare timing or creative performance until at least {RECOMMENDED_SAMPLE_SIZE} same-format 24-hour snapshots exist.",
            repetitions_required=RECOMMENDED_SAMPLE_SIZE,
        ))

    cta_posts = sum(attrs["cta"] not in {"", "None", "Unavailable"} for attrs, _, _ in attribute_rows)
    if total and cta_posts / total < 0.4:
        data_gap = (
            "There are no completed comparable 24-hour comment snapshots, so 24-hour comments are not existing evidence."
            if complete_24h == 0
            else "The available 24-hour posts do not yet form repeated matched CTA and non-CTA pairs."
        )
        opportunities.append(_opportunity(
            priority=2,
            title="CTA experiment",
            current_observation=f"A detectable CTA appears in {cta_posts} of {total} analyzed captions. This describes caption usage only, not CTA impact.",
            sample_size=total,
            period=period,
            data_gap=data_gap,
            suggested_test="On the next post, enable tracking and add one direct question while keeping the topic, media format and posting window as similar as practical.",
            primary_variable="Direct question in the caption.",
            tracking_metric="Comments from the completed 24-hour milestone snapshot.",
            capture_timing="Capture comments at 24 hours after publishing; earlier cumulative snapshots are context, not the decision metric.",
            decision_method="Compare with one otherwise-similar post without the question. Repeat at least three matched tests before deciding whether the CTA helps.",
            repetitions_required=3,
        ))

    if untested_windows:
        window = untested_windows[0]
        opportunities.append(_opportunity(
            priority=3,
            title="Test an unobserved posting window",
            current_observation=f"No analyzed post in the selected period was published in {window}.",
            sample_size=total,
            period=period,
            data_gap="This is a coverage gap only; there is no evidence that the untested window will perform better.",
            suggested_test=f"Publish one otherwise-comparable post in {window}, changing only the posting window.",
            primary_variable="Posting window.",
            tracking_metric="24-hour engagement rate and its returned component metrics.",
            capture_timing="Use the completed 24-hour milestone; do not compare it with lifetime or partial-window totals.",
            decision_method="Compare with the same media format and a similar topic from a tested window; repeat at least three times before interpreting direction.",
            repetitions_required=3,
        ))
    return sorted(opportunities, key=lambda value: value["priority"])[:4]


def _snapshot_metrics(snapshot: Any) -> dict[str, Any]:
    status = dict(getattr(snapshot, "metric_status", {}) or {})
    metrics = {}
    for name in ("views", "reach", "likes", "comments", "saves", "shares"):
        value = getattr(snapshot, name, None)
        metrics[name] = value if isinstance(value, int) else None
        status.setdefault(name, "available" if isinstance(value, int) else "unavailable")
    metrics["engagement_rate"] = _snapshot_engagement_rate(snapshot)
    return {"metrics": metrics, "metric_status": status}


def _performance_posts(items: list[dict[str, Any]], timezone_offset_minutes: int) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for item in items:
        media = item.get("media")
        if not media:
            continue
        analyses = item.get("analyses") or []
        analysis = next((value for value in analyses if value.output_payload.get("score", {}).get("overall") is not None), None)
        enriched = {**item, "analysis": analysis}
        attrs = _attributes(enriched)
        published = _aware(media.published_at)
        snapshots = sorted(item.get("snapshots") or [], key=lambda value: _aware(value.captured_at))
        milestone_by_hour: dict[int, Any] = {}
        for snapshot in snapshots:
            target_hour = getattr(snapshot, "target_hour", None)
            if getattr(snapshot, "collection_type", "manual_current") == "milestone" and target_hour in TRACKING_TARGET_HOURS:
                milestone_by_hour[target_hour] = snapshot
        schedule = item.get("post_publish_tracking") or {}
        jobs_by_hour = {value.get("target_hour"): value for value in schedule.get("milestones") or []}
        timeline = []
        previous_snapshot = None
        for target_hour in TRACKING_TARGET_HOURS:
            snapshot = milestone_by_hour.get(target_hour)
            job = jobs_by_hour.get(target_hour) or {}
            delta = None
            if snapshot is not None and previous_snapshot is not None:
                current_views = snapshot.views
                previous_views = previous_snapshot.views
                if isinstance(current_views, int) and isinstance(previous_views, int) and current_views >= previous_views:
                    delta = current_views - previous_views
            snapshot_values = _snapshot_metrics(snapshot) if snapshot is not None else {"metrics": None, "metric_status": {}}
            scheduled_for = getattr(snapshot, "scheduled_for", None) if snapshot is not None else None
            scheduled_for = scheduled_for or job.get("scheduled_for")
            status = job.get("status") or ("completed" if snapshot is not None else "scheduler_unavailable" if not schedule.get("automatic_collection") else "not_scheduled")
            timeline.append({
                "target_hour": target_hour,
                "status": status,
                "scheduled_for": _iso(scheduled_for),
                "captured_at": _iso(snapshot.captured_at) if snapshot is not None else None,
                "tracking_period_hours": round((_aware(snapshot.captured_at) - published).total_seconds() / 3600, 2) if snapshot is not None else None,
                **snapshot_values,
                "views_since_previous_snapshot": delta,
            })
            previous_snapshot = snapshot

        snapshot_24h = _snapshot_at_24h(enriched)
        latest = snapshots[-1] if snapshots else None
        observation = snapshot_24h or latest
        observation_payload = _snapshot_metrics(observation) if observation is not None else {"metrics": None, "metric_status": {}}
        observation_kind = "24-hour milestone" if snapshot_24h is not None else "Latest cumulative snapshot" if latest is not None else "No snapshot"
        posts.append({
            "tracked_post_id": getattr(item.get("tracking"), "id", None),
            "instagram_media_id": media.instagram_media_id,
            "permalink": media.permalink,
            "media_type": str(media.media_type or "UNKNOWN").upper(),
            "media_type_label": attrs["category"],
            "topic": attrs["topic"],
            "published_at": _iso(media.published_at),
            "posting_window": _posting_window(media.published_at, timezone_offset_minutes),
            "caption_excerpt": (media.caption or "")[:180],
            "observation_kind": observation_kind,
            "snapshot_captured_at": _iso(observation.captured_at) if observation is not None else None,
            "tracking_period_hours": round((_aware(observation.captured_at) - published).total_seconds() / 3600, 2) if observation is not None else None,
            **observation_payload,
            "milestones": timeline,
            "comparison": None,
        })

    by_media_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if post["observation_kind"] == "24-hour milestone":
            by_media_type[post["media_type"]].append(post)
    for media_type, candidates in by_media_type.items():
        metric = "views" if sum(post["metrics"].get("views") is not None for post in candidates) >= 2 else "reach"
        comparable = [post for post in candidates if post["metrics"].get(metric) is not None]
        if len(comparable) < 2:
            continue
        ordered = sorted(comparable, key=lambda post: post["metrics"][metric], reverse=True)
        for rank, post in enumerate(ordered, start=1):
            post["comparison"] = {"rank": rank, "group_size": len(ordered), "metric": metric, "group": f"{media_type} posts with a 24-hour milestone"}
    return sorted(posts, key=lambda post: (post["comparison"] is not None, -(post["comparison"]["rank"] if post["comparison"] else 9999), post["published_at"] or ""), reverse=True)


def build_account_insights(items: list[dict[str, Any]], timezone_offset_minutes: int = 0, account_context: str = "") -> dict[str, Any]:
    del account_context  # Retained for API compatibility; hashtags are not analyzed.
    analyzed = []
    for item in items:
        analyses = item.get("analyses") or []
        analysis = next((value for value in analyses if value.output_payload.get("score", {}).get("overall") is not None), None)
        if analysis and item.get("media"):
            analyzed.append({**item, "analysis": analysis})

    sample_size = len(analyzed)
    attribute_rows = [(_attributes(item), int(item["analysis"].output_payload["score"]["overall"]), item) for item in analyzed]
    baseline = mean(score for _, score, _ in attribute_rows) if attribute_rows else 0
    groups: dict[str, dict[str, list[float]]] = {name: defaultdict(list) for name in ("topic", "caption", "cta", "category", "combination")}
    used_windows: set[str] = set()
    complete_time_groups: dict[str, list[float]] = defaultdict(list)
    complete_24h = 0

    for attrs, score, item in attribute_rows:
        for name in ("topic", "caption", "cta", "category"):
            groups[name][attrs[name]].append(score)
        window = _posting_window(item["media"].published_at, timezone_offset_minutes)
        used_windows.add(window)
        groups["combination"][" | ".join((attrs["topic"], attrs["caption"], attrs["cta"], window))].append(score)
        snapshot = _snapshot_near_24h(item)
        if snapshot is not None:
            complete_24h += 1
            complete_time_groups[window].append(_snapshot_engagement_rate(snapshot))

    patterns = []
    for category, key in (("Topic", "topic"), ("Caption", "caption"), ("CTA", "cta"), ("Content category", "category")):
        patterns.extend(_score_rows(groups[key], baseline, sample_size, category=category))
    patterns.sort(key=lambda row: (row["average_score"], row["posts"]), reverse=True)

    time_baseline_values = [value for values in complete_time_groups.values() for value in values]
    time_baseline = mean(time_baseline_values) if time_baseline_values else 0
    posting_time_rows = _score_rows(complete_time_groups, time_baseline, complete_24h, metric_label="24-hour engagement rate", difference_threshold=0.5, benchmark="All complete 24-hour snapshots in this account")
    candidate_windows = [f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'} - {(hour + 2) % 12 or 12} {'AM' if (hour + 2) % 24 < 12 else 'PM'}" for hour in range(6, 24, 2)]
    untested_windows = [window for window in candidate_windows if window not in used_windows]
    combination_rows = _score_rows(groups["combination"], baseline, sample_size)
    tested_combination = next((row for row in combination_rows if row["posts"] >= 3 and row["difference_from_baseline"] >= 3), None)
    if tested_combination:
        tested_combination = {**tested_combination, "label_type": "Pattern to validate", "caution": "These elements appeared together, but the association does not prove that the combination caused performance."}

    enough_data = sample_size >= RECOMMENDED_SAMPLE_SIZE
    period = _period(analyzed)
    tracking_state = _tracking_state(analyzed, complete_24h)
    return {
        "sample_size": sample_size,
        "required_sample_size": RECOMMENDED_SAMPLE_SIZE,
        "enough_data": enough_data,
        "heading": "Observed account patterns" if enough_data else "Patterns to validate",
        "sample_notice": f"{sample_size} / {RECOMMENDED_SAMPLE_SIZE} analyzed posts. Results remain observational, not causal.",
        "confidence_explanation": "Confidence labels describe sample-size sufficiency only. They are not the probability that a conclusion is correct.",
        "confidence_policy": {"low": f"Fewer than {MEDIUM_CONFIDENCE_POSTS} matching posts, or fewer than {RECOMMENDED_SAMPLE_SIZE} total posts", "medium": f"At least {MEDIUM_CONFIDENCE_POSTS} matching posts and {RECOMMENDED_SAMPLE_SIZE} total posts", "high": f"At least {HIGH_CONFIDENCE_POSTS} matching posts and {RECOMMENDED_SAMPLE_SIZE} total posts"},
        "observation_period": {**period, "timezone": _timezone_label(timezone_offset_minutes)},
        "progress": {"patterns": sample_size, "posting_times": complete_24h},
        "patterns": patterns[:10],
        "posting_time_insights": posting_time_rows[:6],
        "untested_posting_windows": untested_windows[:4],
        "posting_time_metadata": {"timezone": _timezone_label(timezone_offset_minutes), "period_start": period["start"], "period_end": period["end"], "metric": "Engagement rate from a cumulative milestone captured 23-26 hours after publishing", "complete_posts": complete_24h, "incomplete_posts": max(0, sample_size - complete_24h)},
        "tracking_24h": {"available": complete_24h > 0, "complete_posts": complete_24h, "total_posts": sample_size, "target_hours": list(TRACKING_TARGET_HOURS), **tracking_state, "status": "LIMITED" if complete_24h < RECOMMENDED_SAMPLE_SIZE else "AVAILABLE", "message": tracking_state["reason"]},
        "metric_capabilities": {
            "account_requirement": "Instagram professional account (Business or Creator) connected through Instagram Login.",
            "required_scope": "instagram_business_manage_insights",
            "definitions": {"views": "Cumulative views returned by Instagram; may include repeat views by the same account.", "reach": "Cumulative unique accounts reached when Instagram returns the metric."},
            "currently_collected": ["views", "reach", "likes", "comments", "saves", "shares"],
            "advanced_metrics": [
                {"key": "average_watch_time", "status": "not_collected", "reason": "Not requested or persisted by the current Instagram integration."},
                {"key": "watch_time", "status": "not_collected", "reason": "Not requested or persisted by the current Instagram integration."},
                {"key": "retention", "status": "not_collected", "reason": "Not requested or persisted by the current Instagram integration."},
                {"key": "skip_rate", "status": "not_collected", "reason": "Not requested or persisted by the current Instagram integration."},
            ],
        },
        "performance_posts": _performance_posts(items, timezone_offset_minutes),
        "content_opportunities": _content_opportunities(attribute_rows, complete_24h, untested_windows, period, tracking_state),
        "tested_combination": tested_combination,
    }
