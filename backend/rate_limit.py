"""PostgreSQL-backed sliding-window limiter for expensive per-user actions."""

import time
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.storage.database import session_factory
from backend.storage.sql_models import RateLimitRecord


def _create_record_if_missing(session: Session, key: str, now: datetime) -> None:
    values = {"key": key, "hits": [], "updated_at": now}
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = (
            postgresql_insert(RateLimitRecord)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[RateLimitRecord.key])
        )
        session.execute(statement)
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(RateLimitRecord).values(**values).on_conflict_do_nothing(index_elements=[RateLimitRecord.key])
        )
        session.execute(statement)
    else:
        if session.get(RateLimitRecord, key) is None:
            session.add(RateLimitRecord(**values))
            session.flush()


def enforce_rate_limit_in_session(
    session: Session,
    key: str,
    limit: int,
    window_seconds: int = 3600,
    *,
    error_code: str = "rate_limited",
    error_message: str = "Too many requests. Please try again later.",
) -> None:
    if limit <= 0:
        return

    now_timestamp = time.time()
    now = datetime.now(UTC)
    _create_record_if_missing(session, key, now)
    record = session.scalar(select(RateLimitRecord).where(RateLimitRecord.key == key).with_for_update())
    if record is None:  # pragma: no cover - the insert/select transaction guarantees the row exists.
        raise RuntimeError("Rate-limit storage row was not created.")

    cutoff = now_timestamp - window_seconds
    hits = [float(hit) for hit in (record.hits or []) if float(hit) > cutoff]
    if len(hits) >= limit:
        raise HTTPException(
            status_code=429,
            detail={"code": error_code, "message": error_message},
        )
    record.hits = [*hits, now_timestamp]
    record.updated_at = now
    session.flush()


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 3600) -> None:
    with session_factory().begin() as session:
        enforce_rate_limit_in_session(session, key, limit, window_seconds)


def reset_rate_limits() -> None:
    with session_factory().begin() as session:
        session.execute(delete(RateLimitRecord))
