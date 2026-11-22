"""Wireframe-facing, account-relative Instagram insight payloads."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

MIN_COMPARABLE_POSTS = 6
PERCENTILE_RANGE_AT = 15
NEEDS_REFRESH_AFTER = timedelta(hours=24)
METRIC_ORDER = ("views", "reach", "engagement_rate", "shares", "saves", "comments")
SAME_AGE_TOLERANCE_FRACTION = 0.25
SAME_AGE_MINIMUM_TOLERANCE = timedelta(hours=3)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _format_key(media_type: str) -> str:
    return "video" if str(media_type or "").upper() in {"VIDEO", "REELS"} else str(media_type or "IMAGE").lower()


def _format_label(media_type: str) -> str:
    value = _format_key(media_type)
    return "Reel" if value == "video" else "Carousel" if value == "carousel_album" else "Image"


def _mature(media: Any, now: datetime) -> bool:
    threshold = 14 if _format_key(media.media_type) == "video" else 7
    return (now - _aware(media.published_at)).total_seconds() >= threshold * 86400


def _latest(item: dict[str, Any]) -> Any | None:
    values = list(item.get("snapshots") or [])
    if item.get("latest") is not None:
        values.append(item["latest"])
    return max(values, key=lambda value: _aware(value.captured_at)) if values else None


def _snapshots(item: dict[str, Any]) -> list[Any]:
    """Return a post's snapshots, retaining a separately supplied latest value."""
    values = list(item.get("snapshots") or [])
    latest = item.get("latest")
    if latest is not None and not any(value is latest for value in values):
        values.append(latest)
    return values


def _rate(snapshot: Any | None) -> float | None:
    if snapshot is None:
        return None
    if snapshot.engagement_rate is not None:
        return round(float(snapshot.engagement_rate), 1)
    if not snapshot.reach:
        return None
    values = [
        value for value in (snapshot.likes, snapshot.comments, snapshot.saves, snapshot.shares) if value is not None
    ]
    return round(sum(values) / snapshot.reach * 100, 1) if values else None


def _metrics(snapshot: Any | None) -> dict[str, int | float | None]:
    return {
        "views": snapshot.views if snapshot else None,
        "reach": snapshot.reach if snapshot else None,
        "engagement_rate": _rate(snapshot),
        "shares": snapshot.shares if snapshot else None,
        "saves": snapshot.saves if snapshot else None,
        "comments": snapshot.comments if snapshot else None,
        "likes": snapshot.likes if snapshot else None,
    }


def _post(item: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    media = item.get("media")
    tracked = item.get("tracking")
    if media is None or tracked is None:
        return None
    latest = _latest(item)
    values = _metrics(latest)
    has_metrics = any(values[name] is not None for name in METRIC_ORDER)
    stale = latest is None or now - _aware(latest.captured_at) > NEEDS_REFRESH_AFTER
    return {
        "tracked_post_id": tracked.id,
        "instagram_media_id": media.instagram_media_id,
        "thumbnail_url": media.thumbnail_url or media.media_url,
        "published_at": _aware(media.published_at).isoformat(),
        "media_type": str(media.media_type or "IMAGE").upper(),
        "media_type_label": _format_label(media.media_type),
        "format_key": _format_key(media.media_type),
        "mature": _mature(media, now),
        "has_metrics": has_metrics,
        "needs_refresh": not has_metrics or stale,
        "metrics": values,
        "rank": None,
        "comparison_size": 0,
    }


def performance_posts(items: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    current = _aware(now or datetime.now(UTC))
    posts = [post for item in items if (post := _post(item, current)) is not None and post["has_metrics"]]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if post["mature"] and post["metrics"]["views"] is not None:
            groups[post["format_key"]].append(post)
    for group in groups.values():
        if len(group) < MIN_COMPARABLE_POSTS:
            continue
        ordered = sorted(group, key=lambda post: post["metrics"]["views"], reverse=True)
        for rank, post in enumerate(ordered, start=1):
            post["rank"] = rank
            post["comparison_size"] = len(ordered)
    return sorted(posts, key=lambda post: post["published_at"], reverse=True)


def _highlights(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if post["mature"]:
            groups[post["format_key"]].append(post)
    eligible = [group for group in groups.values() if len(group) >= MIN_COMPARABLE_POSTS]
    if not eligible:
        return []
    group = max(eligible, key=len)
    reach = [post for post in group if post["metrics"]["reach"] is not None]
    engagement = [post for post in group if post["metrics"]["engagement_rate"] is not None]
    if len(reach) < MIN_COMPARABLE_POSTS or len(engagement) < MIN_COMPARABLE_POSTS:
        return []

    def item(label: str, post: dict[str, Any], metric: str) -> dict[str, Any]:
        return {
            "label": label,
            "tracked_post_id": post["tracked_post_id"],
            "thumbnail_url": post["thumbnail_url"],
            "published_at": post["published_at"],
            "metric": metric,
            "value": post["metrics"][metric],
        }

    return [
        item("Highest reach", max(reach, key=lambda post: post["metrics"]["reach"]), "reach"),
        item("Lowest reach", min(reach, key=lambda post: post["metrics"]["reach"]), "reach"),
        item(
            "Highest engagement",
            max(engagement, key=lambda post: post["metrics"]["engagement_rate"]),
            "engagement_rate",
        ),
        item(
            "Lowest engagement", min(engagement, key=lambda post: post["metrics"]["engagement_rate"]), "engagement_rate"
        ),
    ]


def build_account_insights(
    items: list[dict[str, Any]],
    *,
    suggestion: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    posts = performance_posts(items, now=now)
    return {
        "highlights": _highlights(posts),
        "next_post_suggestion": suggestion if len(posts) >= MIN_COMPARABLE_POSTS else None,
        "performance_posts": posts,
        "needs_refresh_after_hours": int(NEEDS_REFRESH_AFTER.total_seconds() // 3600),
    }


def _percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * proportion
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _rounded(metric: str, value: float) -> int | float:
    return round(value, 1) if metric == "engagement_rate" else int(round(value))


def _range_positions(current: float, lower: float, upper: float) -> tuple[float, float, float]:
    span = max(1.0, upper - lower)
    domain_low = min(0.0, current, lower - span * 0.25)
    domain_high = max(current, upper + span * 0.25)
    domain_span = max(1.0, domain_high - domain_low)

    def position(value: float) -> float:
        return max(0.0, min(100.0, (value - domain_low) / domain_span * 100))

    return position(lower), position(upper), position(current)


def build_post_analysis(
    selected: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    summary: str | None,
    audience_comments: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = _aware(now or datetime.now(UTC))
    media = selected["media"]
    latest = _latest(selected)
    current_metrics = _metrics(latest)
    selected_is_mature = _mature(media, current_time)
    comparison_basis = "lifetime" if selected_is_mature else "same_age"
    peer_snapshots: list[Any] = []
    selected_age = _aware(latest.captured_at) - _aware(media.published_at) if latest is not None else None
    same_age_tolerance = (
        max(SAME_AGE_MINIMUM_TOLERANCE, selected_age * SAME_AGE_TOLERANCE_FRACTION)
        if selected_age is not None
        else None
    )
    for item in items:
        if item.get("tracking") is None or item["tracking"].id == selected["tracking"].id or item.get("media") is None:
            continue
        if _format_key(item["media"].media_type) != _format_key(media.media_type):
            continue
        if selected_is_mature:
            if not _mature(item["media"], current_time):
                continue
            peer_latest = _latest(item)
            if peer_latest is not None:
                peer_snapshots.append(peer_latest)
            continue

        if selected_age is None or same_age_tolerance is None:
            continue
        peer_published = _aware(item["media"].published_at)
        candidates = [snapshot for snapshot in _snapshots(item) if _aware(snapshot.captured_at) >= peer_published]
        if not candidates:
            continue
        closest = min(
            candidates,
            key=lambda snapshot: abs((_aware(snapshot.captured_at) - peer_published) - selected_age),
        )
        peer_age = _aware(closest.captured_at) - peer_published
        if abs(peer_age - selected_age) <= same_age_tolerance:
            peer_snapshots.append(closest)

    rows: list[dict[str, Any]] = []
    if len(peer_snapshots) >= MIN_COMPARABLE_POSTS and latest is not None:
        for metric in METRIC_ORDER:
            current_value = current_metrics.get(metric)
            peer_values = [
                float(value) for snapshot in peer_snapshots if (value := _metrics(snapshot).get(metric)) is not None
            ]
            if current_value is None or len(peer_values) < MIN_COMPARABLE_POSTS:
                continue
            if len(peer_values) >= PERCENTILE_RANGE_AT:
                lower = _percentile(peer_values, 0.10)
                upper = _percentile(peer_values, 0.90)
            else:
                lower, upper = min(peer_values), max(peer_values)
            status = "above" if current_value > upper else "below" if current_value < lower else "inside"
            rank_values = sorted([*peer_values, float(current_value)], reverse=True)
            rank = rank_values.index(float(current_value)) + 1
            band_start, band_end, marker = _range_positions(float(current_value), lower, upper)
            rows.append(
                {
                    "metric": metric,
                    "value": _rounded(metric, float(current_value)),
                    "usual_min": _rounded(metric, lower),
                    "usual_max": _rounded(metric, upper),
                    "status": status,
                    "rank": rank,
                    "group_size": len(rank_values),
                    "band_start": round(band_start, 2),
                    "band_end": round(band_end, 2),
                    "marker": round(marker, 2),
                }
            )

    stands_out = [row for row in rows if row["status"] == "above"]
    weaker = [row for row in rows if row["status"] == "below"]
    comparable = len(peer_snapshots) >= MIN_COMPARABLE_POSTS and bool(rows)
    not_comparable_reason = None
    if not comparable:
        not_comparable_reason = "too_few_posts" if selected_is_mature else "too_early"

    published = _aware(media.published_at)
    return {
        "comparable": comparable,
        "comparable_count": len(peer_snapshots),
        "comparison_basis": comparison_basis,
        "not_comparable_reason": not_comparable_reason,
        "summary": summary,
        "stands_out": stands_out,
        "weaker": weaker,
        "usual_ranges": rows,
        "audience_comments": audience_comments,
        "age_days": round(max(0.0, (current_time - published).total_seconds() / 86400), 1),
        "media_format": _format_label(media.media_type),
    }
