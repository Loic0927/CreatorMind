"""Durable, account-scoped first-24-hour milestone queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.storage.database import session_factory
from backend.storage.models import InstagramInsightSnapshot
from backend.storage.sql_models import (
    InstagramConnectionRecord, InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord, InstagramMediaRecord, TrackedPostRecord,
)

MILESTONES = (1, 3, 6, 12, 24)
GRACE_MINUTES = {1: 30, 3: 30, 6: 60, 12: 60, 24: 60}
FINAL_STATUSES = {"completed", "missed"}
LEASE = timedelta(minutes=10)
LOGGER = logging.getLogger("postbridge.tracking_queue")


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class TrackingRepository:
    def __init__(self, factory=None):
        self.factory = factory or session_factory()

    def ensure_jobs_for_tracking(self, tracked_id: str, now: datetime | None = None) -> list[InstagramInsightCollectionJobRecord]:
        current = _utc(now or datetime.now(timezone.utc))
        with self.factory.begin() as session:
            row = session.execute(
                select(TrackedPostRecord, InstagramMediaRecord)
                .join(InstagramMediaRecord, InstagramMediaRecord.id == TrackedPostRecord.media_id)
                .where(TrackedPostRecord.id == tracked_id)
            ).one_or_none()
            if not row:
                return []
            tracked, media = row
            existing_jobs = list(session.scalars(select(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id).order_by(
                    InstagramInsightCollectionJobRecord.milestone_hours)))
            if existing_jobs:
                self._refresh_post_status(session, tracked_id)
                return existing_jobs
            published = _utc(media.published_at)
            if current > published + timedelta(hours=24):
                tracked.first_24h_status = "unavailable"
                tracked.first_24h_reason = "added_after_24h"
                return []

            values = []
            missed_any = False
            for milestone in MILESTONES:
                due = published + timedelta(hours=milestone)
                deadline = due + timedelta(minutes=GRACE_MINUTES[milestone])
                missed = current > deadline
                missed_any = missed_any or missed
                values.append({
                    "id": str(uuid4()), "user_id": tracked.user_id,
                    "tracked_post_id": tracked.id, "media_id": tracked.media_id,
                    "milestone_hours": milestone, "due_at": due, "deadline_at": deadline,
                    "next_attempt_at": max(current, due), "attempt_count": 0,
                    "status": "missed" if missed else "pending",
                    "snapshot_id": None, "reason": "tracking_started_late" if missed else None,
                    "locked_at": None, "locked_by": None,
                    "completed_at": current if missed else None,
                    "created_at": current, "updated_at": current,
                })
            table = InstagramInsightCollectionJobRecord.__table__
            if session.bind.dialect.name == "postgresql":
                session.execute(postgresql_insert(table).values(values).on_conflict_do_nothing(
                    constraint="uq_instagram_insight_job_milestone"))
            elif session.bind.dialect.name == "sqlite":
                session.execute(sqlite_insert(table).values(values).on_conflict_do_nothing(
                    index_elements=["tracked_post_id", "milestone_hours"]))
            else:  # pragma: no cover - supported deployments use PostgreSQL/SQLite
                for value in values:
                    exists = session.scalar(select(InstagramInsightCollectionJobRecord.id).where(
                        InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id,
                        InstagramInsightCollectionJobRecord.milestone_hours == value["milestone_hours"]))
                    if not exists:
                        session.add(InstagramInsightCollectionJobRecord(**value))
            tracked.first_24h_status = "partial" if missed_any else "collecting"
            tracked.first_24h_reason = "tracking_started_late" if missed_any else None
            session.flush()
            jobs = list(session.scalars(select(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id).order_by(
                    InstagramInsightCollectionJobRecord.milestone_hours)))
            LOGGER.info("milestone_scheduling tracked_post_id=%s total=%s missed=%s", tracked_id, len(jobs), sum(job.status == "missed" for job in jobs))
            return jobs

    def ensure_all_active_jobs(self, now: datetime | None = None) -> int:
        with self.factory() as session:
            ids = list(session.scalars(select(TrackedPostRecord.id).where(TrackedPostRecord.is_active.is_(True))))
        for tracked_id in ids:
            self.ensure_jobs_for_tracking(tracked_id, now)
        return len(ids)

    def claim_due(self, worker_id: str, limit: int = 20, now: datetime | None = None):
        current = _utc(now or datetime.now(timezone.utc))
        with self.factory.begin() as session:
            # Expired leases become claimable after restart; past-deadline work is never captured.
            session.execute(update(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.status == "running",
                InstagramInsightCollectionJobRecord.locked_at < current - LEASE,
            ).values(status="retry", locked_at=None, locked_by=None, next_attempt_at=current, updated_at=current))
            overdue = list(session.scalars(select(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.status.in_({"pending", "retry", "blocked_reconnect"}),
                InstagramInsightCollectionJobRecord.deadline_at < current)))
            for job in overdue:
                job.status = "missed"; job.reason = "collection_window_missed"
                job.completed_at = current; job.updated_at = current; job.locked_at = None; job.locked_by = None
                LOGGER.info("milestone_miss tracked_post_id=%s milestone=%s reason=collection_window_missed", job.tracked_post_id, job.milestone_hours)

            statement = (
                select(InstagramInsightCollectionJobRecord)
                .join(InstagramConnectionRecord, InstagramConnectionRecord.user_id == InstagramInsightCollectionJobRecord.user_id)
                .where(
                    InstagramInsightCollectionJobRecord.status.in_({"pending", "retry", "blocked_reconnect"}),
                    InstagramInsightCollectionJobRecord.next_attempt_at <= current,
                    InstagramInsightCollectionJobRecord.deadline_at >= current,
                    InstagramConnectionRecord.status == "connected",
                ).order_by(InstagramInsightCollectionJobRecord.next_attempt_at).limit(limit)
            )
            if session.bind.dialect.name == "postgresql":
                statement = statement.with_for_update(skip_locked=True)
            jobs = list(session.scalars(statement))
            for job in jobs:
                job.status = "running"; job.attempt_count += 1
                job.locked_at = current; job.locked_by = worker_id; job.updated_at = current
            session.flush()
            for job in [*overdue, *jobs]:
                self._refresh_post_status(session, job.tracked_post_id)
            return jobs

    def context(self, job_id: str, worker_id: str):
        with self.factory() as session:
            row = session.execute(
                select(InstagramInsightCollectionJobRecord, InstagramMediaRecord, InstagramConnectionRecord)
                .join(InstagramMediaRecord, InstagramMediaRecord.id == InstagramInsightCollectionJobRecord.media_id)
                .join(InstagramConnectionRecord, InstagramConnectionRecord.id == InstagramMediaRecord.account_id)
                .where(InstagramInsightCollectionJobRecord.id == job_id,
                       InstagramInsightCollectionJobRecord.status == "running",
                       InstagramInsightCollectionJobRecord.locked_by == worker_id)
            ).one_or_none()
            return {"job": row[0], "media": row[1], "account": row[2]} if row else None

    def complete(self, job_id: str, worker_id: str, snapshot: InstagramInsightSnapshot, now: datetime | None = None) -> bool:
        current = _utc(now or datetime.now(timezone.utc))
        with self.factory.begin() as session:
            job = session.scalar(select(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.id == job_id).with_for_update())
            if not job or job.status != "running" or job.locked_by != worker_id or current > _utc(job.deadline_at):
                if job and job.status == "running" and job.locked_by == worker_id:
                    self._finish(job, "missed", "collection_window_missed", current)
                    self._refresh_post_status(session, job.tracked_post_id)
                return False
            existing = session.scalar(select(InstagramInsightSnapshotRecord).where(
                InstagramInsightSnapshotRecord.media_id == job.media_id,
                InstagramInsightSnapshotRecord.milestone_hours == job.milestone_hours))
            if existing is None:
                session.add(InstagramInsightSnapshotRecord(**snapshot.model_dump()))
                job.snapshot_id = snapshot.id
            else:
                job.snapshot_id = existing.id
            self._finish(job, "completed", None, current)
            session.flush()
            self._refresh_post_status(session, job.tracked_post_id)
            return True

    def retry(self, job_id: str, worker_id: str, reason: str, delay_seconds: int, now: datetime | None = None) -> bool:
        current = _utc(now or datetime.now(timezone.utc))
        with self.factory.begin() as session:
            job = session.scalar(select(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.id == job_id,
                InstagramInsightCollectionJobRecord.status == "running",
                InstagramInsightCollectionJobRecord.locked_by == worker_id).with_for_update())
            if not job:
                return False
            next_attempt = current + timedelta(seconds=max(1, delay_seconds))
            if next_attempt > _utc(job.deadline_at):
                self._finish(job, "missed", "collection_window_missed", current)
            else:
                job.status = "retry"; job.reason = reason; job.next_attempt_at = next_attempt
                job.locked_at = None; job.locked_by = None; job.updated_at = current
            self._refresh_post_status(session, job.tracked_post_id)
            return True

    def block_reconnect(self, user_id: str, now: datetime | None = None) -> int:
        current = _utc(now or datetime.now(timezone.utc))
        with self.factory.begin() as session:
            result = session.execute(update(InstagramInsightCollectionJobRecord).where(
                InstagramInsightCollectionJobRecord.user_id == user_id,
                InstagramInsightCollectionJobRecord.status.in_({"pending", "retry", "running"}),
            ).values(status="blocked_reconnect", reason="reconnect_required", locked_at=None, locked_by=None, updated_at=current))
            return int(result.rowcount or 0)

    def status_counts(self) -> dict[str, dict[str, int]]:
        with self.factory() as session:
            jobs = {str(status): int(count) for status, count in session.execute(
                select(InstagramInsightCollectionJobRecord.status, func.count()).group_by(InstagramInsightCollectionJobRecord.status))}
            posts = {str(status): int(count) for status, count in session.execute(
                select(TrackedPostRecord.first_24h_status, func.count()).group_by(TrackedPostRecord.first_24h_status))}
        return {"milestone_status": jobs, "first_24h_status": posts}

    @staticmethod
    def _finish(job, status: str, reason: str | None, current: datetime) -> None:
        job.status = status; job.reason = reason; job.completed_at = current
        job.locked_at = None; job.locked_by = None; job.updated_at = current

    @staticmethod
    def _refresh_post_status(session, tracked_id: str) -> None:
        tracked = session.get(TrackedPostRecord, tracked_id)
        if not tracked or tracked.first_24h_status == "unavailable":
            return
        jobs = list(session.scalars(select(InstagramInsightCollectionJobRecord).where(
            InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id)))
        if len(jobs) == len(MILESTONES) and all(job.status == "completed" for job in jobs):
            tracked.first_24h_status = "complete"; tracked.first_24h_reason = None
        elif any(job.status in {"pending", "retry", "running", "blocked_reconnect"} for job in jobs):
            if any(job.status == "missed" for job in jobs):
                tracked.first_24h_status = "partial"
                tracked.first_24h_reason = next(job.reason for job in jobs if job.status == "missed")
            else:
                tracked.first_24h_status = "collecting"; tracked.first_24h_reason = None
        elif jobs:
            tracked.first_24h_status = "partial"
            missed = next((job for job in jobs if job.status == "missed"), None)
            tracked.first_24h_reason = missed.reason if missed else "collection_incomplete"


def get_tracking_repository() -> TrackingRepository:
    return TrackingRepository()
