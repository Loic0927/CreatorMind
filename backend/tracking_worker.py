"""Restart-safe Instagram milestone worker, intentionally separate from Gunicorn."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from backend.services.instagram import (
    INSTAGRAM_SCOPES,
    InstagramServiceError,
    decrypt_access_token,
    engagement_rate,
    encrypt_access_token,
    fetch_instagram_media_insights,
    refresh_long_lived_token,
    safe_raw_metrics,
    token_expiry,
)
from backend.storage.instagram_repository import InstagramRepositoryError, get_instagram_repository
from backend.storage.models import InstagramInsightCollectionJob, InstagramInsightSnapshot
from backend.storage.tracking_repository import TrackingRepository, get_tracking_repository


LOGGER = logging.getLogger("postbridge.tracking_worker")
STOP_REQUESTED = False
REFRESH_BEFORE_EXPIRY = timedelta(days=7)


def _request_stop(signum, frame) -> None:  # pragma: no cover - OS integration
    del signum, frame
    global STOP_REQUESTED
    STOP_REQUESTED = True


def _retry_delay(job: InstagramInsightCollectionJob, provider_delay: int | None = None) -> int:
    base = min(3600, 60 * (2 ** max(0, job.attempt_count - 1)))
    jitter = sum(ord(value) for value in job.id) % max(1, base // 4)
    return max(provider_delay or 0, base + jitter)


def _mark_reconnect_required(user_id: str) -> None:
    repository = get_instagram_repository()
    account = repository.get_connection(user_id)
    if account is None:
        return
    repository.upsert_connection(account.model_copy(update={
        "status": "reconnect_required",
        "last_error": "instagram_token_invalid",
        "last_synced_at": datetime.now(timezone.utc),
    }))


def _usable_token(account_record) -> str:
    repository = get_instagram_repository()
    encrypted = repository.get_encrypted_token(account_record.id)
    if not encrypted:
        raise InstagramServiceError("instagram_token_invalid", "Instagram authorization is no longer valid.", 401)
    token = decrypt_access_token(encrypted)
    expires_at = account_record.token_expires_at
    if expires_at is not None:
        expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    if expires_at is not None and expires_at <= datetime.now(timezone.utc) + REFRESH_BEFORE_EXPIRY:
        payload = refresh_long_lived_token(token)
        token = payload["access_token"]
        account = repository.get_connection(account_record.user_id)
        if account is None:
            raise InstagramServiceError("instagram_token_invalid", "Instagram authorization is no longer valid.", 401)
        repository.upsert_connection(
            account.model_copy(update={
                "token_expires_at": token_expiry(payload),
                "status": "connected",
                "last_error": None,
                "last_synced_at": datetime.now(timezone.utc),
            }),
            encrypted_token=encrypt_access_token(token),
            scopes=list(account.scopes or INSTAGRAM_SCOPES),
        )
    return token


def process_job(repository: TrackingRepository, job: InstagramInsightCollectionJob, worker_id: str) -> str:
    context = repository.job_context(job.id, worker_id)
    if context is None:
        repository.fail_job(job.id, worker_id, "cancelled", "tracking_cancelled")
        return "cancelled"
    account = context["account"]
    media = context["media"]
    if account.status != "connected":
        repository.block_user_for_reauthorization(job.user_id)
        return "blocked_reauthorization"
    try:
        token = _usable_token(account)
        metrics = fetch_instagram_media_insights(token, media.instagram_media_id, media.media_type)
        captured_at = datetime.now(timezone.utc)
        snapshot = InstagramInsightSnapshot(
            id=str(uuid4()), media_id=job.media_id, captured_at=captured_at,
            likes=metrics.get("likes"), comments=metrics.get("comments"),
            saves=metrics.get("saves"), shares=metrics.get("shares"),
            reach=metrics.get("reach"), views=metrics.get("views"),
            engagement_rate=engagement_rate(metrics), raw_metrics=safe_raw_metrics(metrics),
            metric_status=dict(metrics.get("_metric_status") or {}),
            collection_type="milestone", target_hour=job.target_hour,
            scheduled_for=job.due_at,
        )
        return "completed" if repository.complete_job(job.id, worker_id, snapshot, captured_at) else "cancelled"
    except InstagramServiceError as exc:
        if exc.code in {"instagram_token_invalid", "connection_expired"}:
            try:
                _mark_reconnect_required(job.user_id)
            except InstagramRepositoryError:
                pass
            repository.block_user_for_reauthorization(job.user_id)
            return "blocked_reauthorization"
        if exc.code == "instagram_permission_required":
            repository.block_user_for_permission(job.user_id)
            return "permission_required"
        if exc.code == "instagram_media_unavailable":
            repository.fail_job(job.id, worker_id, "unavailable", "instagram_media_unavailable")
            repository.cancel_tracking_jobs(job.tracked_post_id)
            return "unavailable"
        repository.retry_job(
            job.id, worker_id, exc.code,
            _retry_delay(job, exc.retry_after_seconds),
        )
        return "retry"
    except InstagramRepositoryError:
        repository.retry_job(job.id, worker_id, "instagram_storage_unavailable", _retry_delay(job))
        return "retry"


def run_once(repository: TrackingRepository | None = None, worker_id: str | None = None, batch_size: int | None = None) -> int:
    repo = repository or get_tracking_repository()
    identity = worker_id or f"{socket.gethostname()}-{os.getpid()}"
    repo.ensure_all_active_jobs()
    jobs = repo.claim_due(identity, limit=batch_size or int(os.getenv("POSTBRIDGE_TRACKING_BATCH_SIZE", "5")))
    for job in jobs:
        result = process_job(repo, job, identity)
        LOGGER.info("tracking_job_result job_id=%s target_hour=%s result=%s", job.id, job.target_hour, result)
    return len(jobs)


def _write_health(path: str) -> None:
    target = Path(path)
    target.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def run_loop(poll_seconds: int, health_file: str) -> None:  # pragma: no cover - exercised by container
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    while not STOP_REQUESTED:
        try:
            run_once()
            _write_health(health_file)
        except Exception as exc:
            # Never render provider payloads, database URLs, or tokens in worker logs.
            LOGGER.error("tracking_worker_cycle_failed error_type=%s", type(exc).__name__)
        remaining = max(1, poll_seconds)
        while remaining and not STOP_REQUESTED:
            time.sleep(min(1, remaining))
            remaining -= 1


def healthcheck(path: str, max_age_seconds: int) -> int:
    target = Path(path)
    if not target.exists():
        return 1
    return 0 if time.time() - target.stat().st_mtime <= max_age_seconds else 1


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PostBridge Instagram tracking worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--poll-seconds", type=int, default=int(os.getenv("POSTBRIDGE_TRACKING_POLL_SECONDS", "60")))
    run_parser.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health")
    once_parser = subparsers.add_parser("once")
    once_parser.add_argument("--batch-size", type=int, default=int(os.getenv("POSTBRIDGE_TRACKING_BATCH_SIZE", "5")))
    health_parser = subparsers.add_parser("healthcheck")
    health_parser.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health")
    health_parser.add_argument("--max-age-seconds", type=int, default=180)
    subparsers.add_parser("status")
    arguments = parser.parse_args()
    if arguments.command == "run":
        run_loop(max(5, arguments.poll_seconds), arguments.health_file)
        return 0
    if arguments.command == "once":
        run_once(batch_size=arguments.batch_size)
        return 0
    if arguments.command == "healthcheck":
        return healthcheck(arguments.health_file, arguments.max_age_seconds)
    print(json.dumps(get_tracking_repository().status_counts(), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
