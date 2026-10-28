"""Durable PostgreSQL queue for Instagram post-publish milestone snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from backend.storage.database import session_factory
from backend.storage.models import InstagramInsightCollectionJob, InstagramInsightSnapshot
from backend.storage.sql_models import (
    InstagramConnectionRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    TrackedPostRecord,
)


TRACKING_TARGET_HOURS = (24,)
FINAL_STATUSES = {"completed", "missed", "cancelled", "permission_required", "unavailable"}
CLAIMABLE_STATUSES = {"pending", "retry"}
LEASE_MINUTES = 10


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _deadline(due_at: datetime, target_hour: int) -> datetime:
    # The single API capture allows two hours for transient provider recovery.
    return due_at + timedelta(minutes=120)


class TrackingRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def ensure_jobs_for_tracking(self, tracked_id: str, now: datetime | None = None) -> list[InstagramInsightCollectionJob]:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            row = session.execute(
                select(TrackedPostRecord, InstagramMediaRecord)
                .join(InstagramMediaRecord, InstagramMediaRecord.id == TrackedPostRecord.media_id)
                .where(TrackedPostRecord.id == tracked_id)
            ).one_or_none()
            if row is None:
                return []
            tracked, media = row
            if not tracked.is_active:
                return self._jobs_in_session(session, tracked_id)
            values = []
            started_at = _utc(tracked.started_at) or current
            published_at = _utc(media.published_at) or current
            for target_hour in TRACKING_TARGET_HOURS:
                due_at = published_at + timedelta(hours=target_hour)
                deadline_at = _deadline(due_at, target_hour)
                missed = started_at > deadline_at or current > deadline_at
                values.append({
                    "id": str(uuid4()), "user_id": tracked.user_id,
                    "tracked_post_id": tracked.id, "media_id": tracked.media_id,
                    "target_hour": target_hour, "due_at": due_at,
                    "deadline_at": deadline_at,
                    "next_attempt_at": max(current, due_at), "attempt_count": 0,
                    "status": "missed" if missed else "pending", "snapshot_id": None,
                    "last_error_code": "tracking_started_after_milestone" if started_at > deadline_at else "collection_window_missed" if missed else None,
                    "locked_at": None, "locked_by": None,
                    "completed_at": current if missed else None,
                    "created_at": current, "updated_at": current,
                })
            table = InstagramInsightCollectionJobRecord.__table__
            dialect = session.bind.dialect.name
            if dialect == "postgresql":
                statement = postgres_insert(table).values(values).on_conflict_do_nothing(
                    constraint="uq_instagram_insight_job_milestone"
                )
            elif dialect == "sqlite":
                statement = sqlite_insert(table).values(values).on_conflict_do_nothing(
                    index_elements=["tracked_post_id", "target_hour"]
                )
            else:
                for value in values:
                    if session.scalar(select(InstagramInsightCollectionJobRecord.id).where(
                        InstagramInsightCollectionJobRecord.tracked_post_id == tracked.id,
                        InstagramInsightCollectionJobRecord.target_hour == value["target_hour"],
                    )) is None:
                        session.add(InstagramInsightCollectionJobRecord(**value))
                session.flush()
                return self._jobs_in_session(session, tracked_id)
            session.execute(statement)
            return self._jobs_in_session(session, tracked_id)

    def ensure_all_active_jobs(self, now: datetime | None = None) -> int:
        with self._factory() as session:
            tracked_ids = list(session.scalars(select(TrackedPostRecord.id).where(TrackedPostRecord.is_active.is_(True))))
        for tracked_id in tracked_ids:
            self.ensure_jobs_for_tracking(tracked_id, now)
        return len(tracked_ids)

    def jobs_for_tracking(self, tracked_id: str) -> list[InstagramInsightCollectionJob]:
        with self._factory() as session:
            return self._jobs_in_session(session, tracked_id)

    def cancel_tracking_jobs(self, tracked_id: str, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            result = session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id,
                    InstagramInsightCollectionJobRecord.status.not_in({"completed", "missed", "cancelled", "unavailable"}),
                )
                .values(
                    status="cancelled", last_error_code="tracking_cancelled",
                    locked_at=None, locked_by=None, completed_at=current, updated_at=current,
                )
            )
            return int(result.rowcount or 0)

    def cancel_user_jobs(self, user_id: str, code: str = "account_disconnected", now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            result = session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.user_id == user_id,
                    InstagramInsightCollectionJobRecord.status.not_in({"completed", "missed", "cancelled", "unavailable"}),
                )
                .values(
                    status="cancelled", last_error_code=code,
                    locked_at=None, locked_by=None, completed_at=current, updated_at=current,
                )
            )
            return int(result.rowcount or 0)

    def block_user_for_reauthorization(self, user_id: str, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            result = session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.user_id == user_id,
                    InstagramInsightCollectionJobRecord.status.not_in(FINAL_STATUSES),
                )
                .values(
                    status="blocked_reauthorization", last_error_code="reconnect_required",
                    locked_at=None, locked_by=None, updated_at=current,
                )
            )
            return int(result.rowcount or 0)

    def block_user_for_permission(self, user_id: str, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            result = session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.user_id == user_id,
                    InstagramInsightCollectionJobRecord.status.not_in({"completed", "missed", "cancelled", "unavailable"}),
                )
                .values(
                    status="permission_required", last_error_code="instagram_permission_required",
                    locked_at=None, locked_by=None, updated_at=current,
                )
            )
            return int(result.rowcount or 0)

    def resume_user_jobs(self, user_id: str, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            jobs = list(session.scalars(
                select(InstagramInsightCollectionJobRecord).where(
                    InstagramInsightCollectionJobRecord.user_id == user_id,
                    InstagramInsightCollectionJobRecord.status.in_({"blocked_reauthorization", "permission_required"}),
                ).with_for_update()
            ))
            for job in jobs:
                if _utc(job.deadline_at) < current:
                    job.status = "missed"
                    job.last_error_code = "collection_window_missed"
                    job.completed_at = current
                else:
                    job.status = "retry"
                    job.last_error_code = None
                    job.next_attempt_at = max(current, _utc(job.due_at))
                job.updated_at = current
            return len(jobs)

    def claim_due(self, worker_id: str, limit: int = 5, now: datetime | None = None) -> list[InstagramInsightCollectionJob]:
        current = now or datetime.now(timezone.utc)
        stale_before = current - timedelta(minutes=LEASE_MINUTES)
        with self._factory.begin() as session:
            session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.status == "running",
                    InstagramInsightCollectionJobRecord.locked_at < stale_before,
                )
                .values(
                    status="retry", next_attempt_at=current, last_error_code="worker_lease_expired",
                    locked_at=None, locked_by=None, updated_at=current,
                )
            )
            session.execute(
                update(InstagramInsightCollectionJobRecord)
                .where(
                    InstagramInsightCollectionJobRecord.status.in_(CLAIMABLE_STATUSES),
                    InstagramInsightCollectionJobRecord.deadline_at < current,
                )
                .values(
                    status="missed", last_error_code="collection_window_missed",
                    locked_at=None, locked_by=None, completed_at=current, updated_at=current,
                )
            )
            statement = (
                select(InstagramInsightCollectionJobRecord)
                .join(TrackedPostRecord, TrackedPostRecord.id == InstagramInsightCollectionJobRecord.tracked_post_id)
                .where(
                    InstagramInsightCollectionJobRecord.status.in_(CLAIMABLE_STATUSES),
                    InstagramInsightCollectionJobRecord.due_at <= current,
                    InstagramInsightCollectionJobRecord.next_attempt_at <= current,
                    InstagramInsightCollectionJobRecord.deadline_at >= current,
                    TrackedPostRecord.is_active.is_(True),
                )
                .order_by(InstagramInsightCollectionJobRecord.next_attempt_at, InstagramInsightCollectionJobRecord.due_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            records = list(session.scalars(statement))
            for record in records:
                record.status = "running"
                record.attempt_count += 1
                record.locked_at = current
                record.locked_by = worker_id
                record.updated_at = current
            session.flush()
            return [self._job(record) for record in records]

    def job_context(self, job_id: str, worker_id: str) -> dict[str, Any] | None:
        with self._factory() as session:
            row = session.execute(
                select(
                    InstagramInsightCollectionJobRecord,
                    TrackedPostRecord,
                    InstagramMediaRecord,
                    InstagramConnectionRecord,
                )
                .join(TrackedPostRecord, TrackedPostRecord.id == InstagramInsightCollectionJobRecord.tracked_post_id)
                .join(InstagramMediaRecord, InstagramMediaRecord.id == InstagramInsightCollectionJobRecord.media_id)
                .join(InstagramConnectionRecord, InstagramConnectionRecord.id == InstagramMediaRecord.account_id)
                .where(
                    InstagramInsightCollectionJobRecord.id == job_id,
                    InstagramInsightCollectionJobRecord.status == "running",
                    InstagramInsightCollectionJobRecord.locked_by == worker_id,
                )
            ).one_or_none()
            if row is None:
                return None
            job, tracked, media, account = row
            if not tracked.is_active:
                return None
            return {"job": self._job(job), "media": media, "account": account}

    def complete_job(self, job_id: str, worker_id: str, snapshot: InstagramInsightSnapshot, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            job = session.scalar(
                select(InstagramInsightCollectionJobRecord)
                .where(InstagramInsightCollectionJobRecord.id == job_id)
                .with_for_update()
            )
            if job is None or job.status != "running" or job.locked_by != worker_id:
                return False
            active = session.scalar(select(TrackedPostRecord.is_active).where(TrackedPostRecord.id == job.tracked_post_id))
            if not active:
                self._finish(job, "cancelled", "tracking_cancelled", current)
                return False
            existing = session.scalar(select(InstagramInsightSnapshotRecord).where(
                InstagramInsightSnapshotRecord.media_id == job.media_id,
                InstagramInsightSnapshotRecord.target_hour == job.target_hour,
            ))
            if existing is None:
                session.add(InstagramInsightSnapshotRecord(**snapshot.model_dump()))
                session.flush()
                snapshot_id = snapshot.id
            else:
                snapshot_id = existing.id
            job.snapshot_id = snapshot_id
            self._finish(job, "completed", None, current)
            return True

    def retry_job(self, job_id: str, worker_id: str, error_code: str, delay_seconds: int, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            job = self._locked_job(session, job_id, worker_id)
            if job is None:
                return False
            next_attempt = current + timedelta(seconds=max(1, delay_seconds))
            if next_attempt > _utc(job.deadline_at):
                self._finish(job, "missed", "collection_window_missed", current)
            else:
                job.status = "retry"
                job.next_attempt_at = next_attempt
                job.last_error_code = error_code
                job.locked_at = None
                job.locked_by = None
                job.updated_at = current
            return True

    def fail_job(self, job_id: str, worker_id: str, status: str, error_code: str, now: datetime | None = None) -> bool:
        if status not in {"permission_required", "unavailable", "missed", "cancelled"}:
            raise ValueError("Invalid terminal tracking status.")
        current = now or datetime.now(timezone.utc)
        with self._factory.begin() as session:
            job = self._locked_job(session, job_id, worker_id)
            if job is None:
                return False
            self._finish(job, status, error_code, current)
            return True

    def status_counts(self) -> dict[str, int]:
        with self._factory() as session:
            rows = session.execute(
                select(InstagramInsightCollectionJobRecord.status, func.count())
                .group_by(InstagramInsightCollectionJobRecord.status)
            ).all()
            return {status: int(count) for status, count in rows}

    @staticmethod
    def _locked_job(session: Session, job_id: str, worker_id: str) -> InstagramInsightCollectionJobRecord | None:
        return session.scalar(
            select(InstagramInsightCollectionJobRecord)
            .where(
                InstagramInsightCollectionJobRecord.id == job_id,
                InstagramInsightCollectionJobRecord.status == "running",
                InstagramInsightCollectionJobRecord.locked_by == worker_id,
            )
            .with_for_update()
        )

    @staticmethod
    def _finish(job: InstagramInsightCollectionJobRecord, status: str, error_code: str | None, current: datetime) -> None:
        job.status = status
        job.last_error_code = error_code
        job.locked_at = None
        job.locked_by = None
        job.completed_at = current
        job.updated_at = current

    def _jobs_in_session(self, session: Session, tracked_id: str) -> list[InstagramInsightCollectionJob]:
        records = session.scalars(
            select(InstagramInsightCollectionJobRecord)
            .where(InstagramInsightCollectionJobRecord.tracked_post_id == tracked_id)
            .order_by(InstagramInsightCollectionJobRecord.target_hour)
        ).all()
        return [self._job(record) for record in records]

    @staticmethod
    def _job(record: InstagramInsightCollectionJobRecord) -> InstagramInsightCollectionJob:
        return InstagramInsightCollectionJob(
            id=record.id, user_id=record.user_id, tracked_post_id=record.tracked_post_id,
            media_id=record.media_id, target_hour=record.target_hour,
            due_at=_utc(record.due_at), deadline_at=_utc(record.deadline_at),
            next_attempt_at=_utc(record.next_attempt_at), attempt_count=record.attempt_count,
            status=record.status, snapshot_id=record.snapshot_id,
            last_error_code=record.last_error_code, locked_at=_utc(record.locked_at),
            locked_by=record.locked_by, completed_at=_utc(record.completed_at),
            created_at=_utc(record.created_at), updated_at=_utc(record.updated_at),
        )


@lru_cache(maxsize=1)
def get_tracking_repository() -> TrackingRepository:
    return TrackingRepository(session_factory())
