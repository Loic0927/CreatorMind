"""In-process sliding-window limiter for expensive per-user actions.

Each Gunicorn worker keeps its own window, so the effective limit is
``limit * POSTBRIDGE_GUNICORN_WORKERS``.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 3600) -> None:
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "message": "Too many requests. Please try again later."},
            )
        hits.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()
