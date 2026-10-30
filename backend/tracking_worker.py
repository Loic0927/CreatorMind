"""Instagram token-maintenance worker.

Metrics and new-post discovery are login-triggered. This deployment process now has
one scheduled responsibility: refresh connected Instagram tokens near expiry.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.services.instagram import InstagramServiceError
from backend.services.instagram_sync import usable_token
from backend.storage.instagram_repository import get_instagram_repository


LOGGER = logging.getLogger("postbridge.tracking_worker")
STOP_REQUESTED = False


def _request_stop(signum, frame) -> None:  # pragma: no cover
    del signum, frame
    global STOP_REQUESTED
    STOP_REQUESTED = True


def run_once() -> int:
    refreshed = 0
    repository = get_instagram_repository()
    for account in repository.list_connections():
        if account.status != "connected":
            continue
        try:
            usable_token(account)
            refreshed += 1
        except InstagramServiceError as exc:
            if exc.code in {"instagram_token_invalid", "connection_expired"}:
                repository.upsert_connection(account.model_copy(update={"status": "reconnect_required", "last_error": exc.code}))
            LOGGER.warning("instagram_token_maintenance_failed account_id=%s code=%s", account.id, exc.code)
    return refreshed


def _write_health(path: str) -> None:
    Path(path).write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def run_loop(poll_seconds: int, health_file: str) -> None:  # pragma: no cover
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    while not STOP_REQUESTED:
        try:
            run_once()
            _write_health(health_file)
        except Exception as exc:
            LOGGER.error("token_worker_cycle_failed error_type=%s", type(exc).__name__)
        remaining = max(1, poll_seconds)
        while remaining and not STOP_REQUESTED:
            time.sleep(min(1, remaining))
            remaining -= 1


def healthcheck(path: str, max_age_seconds: int) -> int:
    target = Path(path)
    return 0 if target.exists() and time.time() - target.stat().st_mtime <= max_age_seconds else 1


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PostBridge Instagram token worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--poll-seconds", type=int, default=int(os.getenv("POSTBRIDGE_TRACKING_POLL_SECONDS", "3600")))
    run_parser.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health")
    subparsers.add_parser("once")
    health_parser = subparsers.add_parser("healthcheck")
    health_parser.add_argument("--health-file", default="/tmp/postbridge-tracking-worker.health")
    health_parser.add_argument("--max-age-seconds", type=int, default=7200)
    subparsers.add_parser("status")
    arguments = parser.parse_args()
    if arguments.command == "run":
        run_loop(max(60, arguments.poll_seconds), arguments.health_file)
    elif arguments.command == "once":
        run_once()
    elif arguments.command == "healthcheck":
        return healthcheck(arguments.health_file, arguments.max_age_seconds)
    else:
        print(json.dumps({"scheduled_work": "instagram_token_refresh"}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
