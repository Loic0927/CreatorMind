"""Instagram new-media detection, milestone collection, and token worker."""
from __future__ import annotations

import argparse, json, logging, os, signal, time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.services.instagram import InstagramServiceError, engagement_rate, fetch_instagram_media, fetch_instagram_media_insights, safe_raw_metrics
from backend.services.instagram_sync import usable_token
from backend.storage.content_repository import get_content_repository
from backend.storage.instagram_repository import get_instagram_repository
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia
from backend.storage.tracking_repository import get_tracking_repository

LOGGER = logging.getLogger("postbridge.tracking_worker")
STOP_REQUESTED = False

def _request_stop(signum, frame):  # pragma: no cover
    del signum, frame
    global STOP_REQUESTED
    STOP_REQUESTED = True

def _aware(value): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def _timestamp(value):
    if isinstance(value, str):
        try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError: pass
    return datetime.now(timezone.utc)

def detect_new_media(now: datetime | None = None) -> dict[str, int]:
    current = _aware(now or datetime.now(timezone.utc))
    instagram = get_instagram_repository(); content = get_content_repository(); queue = get_tracking_repository()
    counts = {"accounts": 0, "detected": 0, "duplicates": 0, "failed": 0}
    for account in instagram.list_connections():
        if account.status != "connected": continue
        counts["accounts"] += 1
        try:
            token = usable_token(account); upstream = fetch_instagram_media(token)
            items = [InstagramMedia(id=f"instagram:{item['id']}", account_id=account.id,
                instagram_media_id=str(item["id"]), media_type=str(item.get("media_type", "UNKNOWN")),
                media_url=item.get("media_url"), thumbnail_url=item.get("thumbnail_url"), permalink=item.get("permalink"),
                caption=str(item.get("caption", "")), published_at=_timestamp(item.get("timestamp")), last_synced_at=current)
                for item in upstream if item.get("id")]
            content.upsert_media(items)
            known = {row.media_id for row in content.tracked(account.user_id, active_only=False)}
            boundary = _aware(account.tracking_start_at or account.connected_at)
            for media in items:
                if _aware(media.published_at) <= boundary: continue
                if media.id in known:
                    counts["duplicates"] += 1; continue
                tracked = content.create_tracked(account.user_id, media.id)
                queue.ensure_jobs_for_tracking(tracked.id, current); known.add(media.id); counts["detected"] += 1
                LOGGER.info("new_media_detected account_id=%s tracked_post_id=%s", account.id, tracked.id)
        except InstagramServiceError as exc:
            counts["failed"] += 1
            if exc.code in {"instagram_token_invalid", "connection_expired"}:
                instagram.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
                queue.block_reconnect(account.user_id, current)
            LOGGER.warning("new_media_detection_failed account_id=%s code=%s", account.id, exc.code)
    LOGGER.info("new_media_detection_cycle accounts=%s detected=%s duplicates=%s failed=%s", counts["accounts"], counts["detected"], counts["duplicates"], counts["failed"])
    return counts

def collect_due(now: datetime | None = None, worker_id: str | None = None) -> dict[str, int]:
    current = _aware(now or datetime.now(timezone.utc)); worker = worker_id or f"worker-{os.getpid()}"
    queue = get_tracking_repository(); instagram = get_instagram_repository()
    counts = {"claimed": 0, "captured": 0, "retried": 0, "blocked": 0, "missed": 0}
    jobs = queue.claim_due(worker, now=current); counts["claimed"] = len(jobs)
    for claimed in jobs:
        context = queue.context(claimed.id, worker)
        if not context: continue
        job, media = context["job"], context["media"]
        account = None
        try:
            account = instagram.get_connection(job.user_id)
            if not account or account.status != "connected":
                queue.block_reconnect(job.user_id, current); counts["blocked"] += 1
                LOGGER.info("milestone_blocked_reconnect tracked_post_id=%s milestone=%s", job.tracked_post_id, job.milestone_hours); continue
            metrics = fetch_instagram_media_insights(usable_token(account), media.instagram_media_id, media.media_type)
            captured = datetime.now(timezone.utc)
            snapshot = InstagramInsightSnapshot(id=str(uuid4()), media_id=job.media_id, captured_at=captured,
                likes=metrics.get("likes"), comments=metrics.get("comments"), saves=metrics.get("saves"), shares=metrics.get("shares"),
                reach=metrics.get("reach"), views=metrics.get("views"), engagement_rate=engagement_rate(metrics),
                average_watch_time_ms=metrics.get("average_watch_time_ms"), total_watch_time_ms=metrics.get("total_watch_time_ms"),
                raw_metrics=safe_raw_metrics(metrics), metric_status=dict(metrics.get("_metric_status") or {}),
                scheduled_for=_aware(job.due_at), milestone_hours=job.milestone_hours, source="api",
                lateness_seconds=max(0, int((captured - _aware(job.due_at)).total_seconds())))
            if queue.complete(job.id, worker, snapshot, captured):
                counts["captured"] += 1
                LOGGER.info("milestone_captured tracked_post_id=%s milestone=%s lateness_seconds=%s", job.tracked_post_id, job.milestone_hours, snapshot.lateness_seconds)
            else:
                counts["missed"] += 1; LOGGER.info("milestone_missed tracked_post_id=%s milestone=%s", job.tracked_post_id, job.milestone_hours)
        except InstagramServiceError as exc:
            if exc.code in {"instagram_token_invalid", "connection_expired"}:
                if account: instagram.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
                queue.block_reconnect(job.user_id, current); counts["blocked"] += 1
                LOGGER.info("milestone_blocked_reconnect tracked_post_id=%s milestone=%s", job.tracked_post_id, job.milestone_hours)
            else:
                delay = min(300, 2 ** min(job.attempt_count, 8)); queue.retry(job.id, worker, exc.code, delay, current)
                counts["retried"] += 1; LOGGER.info("milestone_retry tracked_post_id=%s milestone=%s code=%s delay_seconds=%s", job.tracked_post_id, job.milestone_hours, exc.code, delay)
    return counts

def run_once(*, detect: bool = True) -> dict[str, object]:
    token_count = 0; repository = get_instagram_repository()
    for account in repository.list_connections():
        if account.status != "connected": continue
        try: usable_token(account); token_count += 1
        except InstagramServiceError as exc:
            if exc.code in {"instagram_token_invalid", "connection_expired"}:
                repository.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
                get_tracking_repository().block_reconnect(account.user_id)
            LOGGER.warning("instagram_token_maintenance_failed account_id=%s code=%s", account.id, exc.code)
    scheduled = get_tracking_repository().ensure_all_active_jobs()
    return {"tokens": token_count, "scheduled_posts": scheduled, "detection": detect_new_media() if detect else None, "collection": collect_due()}

def _write_health(path: str): Path(path).write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
def run_loop(poll_seconds: int, new_media_seconds: int, health_file: str):  # pragma: no cover
    signal.signal(signal.SIGTERM, _request_stop); signal.signal(signal.SIGINT, _request_stop); next_detection = 0.0
    while not STOP_REQUESTED:
        try:
            current = time.monotonic(); detect = current >= next_detection; run_once(detect=detect)
            if detect: next_detection = current + new_media_seconds
            _write_health(health_file)
        except Exception as exc: LOGGER.error("tracking_worker_cycle_failed error_type=%s", type(exc).__name__)
        deadline = time.monotonic() + poll_seconds
        while not STOP_REQUESTED and time.monotonic() < deadline: time.sleep(min(1, deadline - time.monotonic()))

def healthcheck(path: str, max_age_seconds: int) -> int:
    target = Path(path); return 0 if target.exists() and time.time() - target.stat().st_mtime <= max_age_seconds else 1
def _poll_seconds(value: int) -> int:
    if not 60 <= value <= 300:
        LOGGER.warning("invalid_tracking_poll_seconds configured=%s using=60 reason=milestone_grace_windows", value); return 60
    return value
def _new_media_seconds(value: int) -> int:
    if value < 300:
        LOGGER.warning("invalid_new_media_poll_seconds configured=%s using=300 reason=provider_rate_limits", value)
        return 300
    return value

def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PostBridge Instagram tracking worker"); sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("--poll-seconds", type=int, default=int(os.getenv("POSTBRIDGE_TRACKING_POLL_SECONDS", "60"))); run.add_argument("--new-media-poll-seconds", type=int, default=int(os.getenv("NEW_MEDIA_POLL_SECONDS", "600"))); run.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health")
    sub.add_parser("once"); health = sub.add_parser("healthcheck"); health.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health"); health.add_argument("--max-age-seconds", type=int, default=7200); sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "run": run_loop(_poll_seconds(args.poll_seconds), _new_media_seconds(args.new_media_poll_seconds), args.health_file)
    elif args.command == "once": print(json.dumps(run_once()))
    elif args.command == "healthcheck": return healthcheck(args.health_file, args.max_age_seconds)
    else: print(json.dumps(get_tracking_repository().status_counts(), sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
