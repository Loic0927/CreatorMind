from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import tracking_worker
from backend.services.instagram import InstagramServiceError
from backend.storage.sql_models import (
    Base,
    InstagramConnectionRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    TrackedPostRecord,
    UserRecord,
)
from backend.storage.tracking_repository import TrackingRepository


NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


@pytest.fixture
def tracking_store():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield TrackingRepository(factory), factory
    finally:
        engine.dispose()


def _seed(
    factory,
    *,
    published_at: datetime,
    started_at: datetime,
    suffix: str = "1",
    media_type: str = "IMAGE",
) -> str:
    user_id = f"user-{suffix}"
    account_id = f"account-{suffix}"
    media_id = f"media-{suffix}"
    tracked_id = f"tracked-{suffix}"
    with factory.begin() as session:
        session.add(UserRecord(
            id=user_id, email=f"user-{suffix}@example.test", account_context="",
            created_at=NOW, updated_at=NOW,
        ))
        session.add(InstagramConnectionRecord(
            id=account_id, user_id=user_id, instagram_user_id=f"ig-{suffix}",
            username=f"creator-{suffix}", account_type="BUSINESS", media_count=1,
            encrypted_access_token="encrypted", token_expires_at=NOW + timedelta(days=30),
            scopes=["instagram_business_manage_insights"], status="connected",
            created_at=NOW, updated_at=NOW,
        ))
        session.add(InstagramMediaRecord(
            id=media_id, account_id=account_id, instagram_media_id=f"provider-{suffix}",
            media_type=media_type, media_url=None, thumbnail_url=None, permalink=None,
            caption=f"Original caption #{suffix}", published_at=published_at,
            last_synced_at=NOW,
        ))
        session.add(TrackedPostRecord(
            id=tracked_id, user_id=user_id, media_id=media_id, is_active=True,
            started_at=started_at, stopped_at=None,
        ))
    return tracked_id


def test_schedule_is_unique_and_has_one_24_hour_capture(tracking_store):
    repository, factory = tracking_store
    tracked_id = _seed(factory, published_at=NOW - timedelta(minutes=10), started_at=NOW)

    first = repository.ensure_jobs_for_tracking(tracked_id, NOW)
    second = repository.ensure_jobs_for_tracking(tracked_id, NOW)

    assert [job.target_hour for job in first] == [24]
    assert [job.id for job in second] == [job.id for job in first]


def test_two_workers_cannot_claim_the_same_job(tracking_store):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=NOW - timedelta(hours=24, minutes=5),
        started_at=NOW - timedelta(hours=24, minutes=5),
    )
    repository.ensure_jobs_for_tracking(tracked_id, NOW)

    first = repository.claim_due("worker-a", limit=5, now=NOW)
    second = repository.claim_due("worker-b", limit=5, now=NOW)

    assert len(first) == 1
    assert first[0].target_hour == 24
    assert second == []


def test_retry_uses_persisted_attempt_and_next_time(tracking_store):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=NOW - timedelta(hours=24, minutes=5),
        started_at=NOW - timedelta(hours=24, minutes=5),
    )
    repository.ensure_jobs_for_tracking(tracked_id, NOW)
    job = repository.claim_due("worker-a", now=NOW)[0]

    assert repository.retry_job(job.id, "worker-a", "instagram_rate_limited", 120, NOW)
    stored = repository.jobs_for_tracking(tracked_id)[0]
    assert stored.status == "retry"
    assert stored.attempt_count == 1
    assert stored.next_attempt_at == NOW + timedelta(seconds=120)


def test_cancelling_tracking_cancels_unfinished_jobs(tracking_store):
    repository, factory = tracking_store
    tracked_id = _seed(factory, published_at=NOW, started_at=NOW)
    repository.ensure_jobs_for_tracking(tracked_id, NOW)

    assert repository.cancel_tracking_jobs(tracked_id, NOW) == 1
    assert {job.status for job in repository.jobs_for_tracking(tracked_id)} == {"cancelled"}


def test_old_post_milestones_are_missed_without_snapshots(tracking_store):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=NOW - timedelta(days=10),
        started_at=NOW,
    )

    jobs = repository.ensure_jobs_for_tracking(tracked_id, NOW)

    assert {job.status for job in jobs} == {"missed"}
    assert jobs[0].last_error_code == "tracking_started_after_24h"
    with factory() as session:
        assert list(session.scalars(select(InstagramInsightSnapshotRecord))) == []


def test_new_post_discovery_is_idempotent(monkeypatch):
    account = type("Account", (), {"id": "account-1", "user_id": "user-1", "status": "connected", "auto_track_new_posts": True})()
    class Accounts:
        def list_connections(self): return [account]
    class Content:
        def __init__(self): self.media = []; self.tracks = []
        def upsert_media(self, items): self.media = items; return items
        def tracked(self, user_id, active_only=False): return self.tracks
        def create_tracked(self, user_id, media_id):
            item = type("Tracked", (), {"id": f"tracked-{len(self.tracks)}", "media_id": media_id})()
            self.tracks.append(item); return item
    class Tracking:
        def __init__(self): self.calls = []
        def ensure_jobs_for_tracking(self, tracked_id, now): self.calls.append(tracked_id)
    content, tracking = Content(), Tracking()
    monkeypatch.setattr(tracking_worker, "_usable_token", lambda value: "token")
    monkeypatch.setattr(tracking_worker, "fetch_instagram_media", lambda token: [{"id": "media-1", "media_type": "IMAGE", "timestamp": NOW.isoformat()}])
    assert tracking_worker.discover_new_posts(now=NOW, instagram_repository=Accounts(), content_repository=content, tracking_repository=tracking) == 1
    assert tracking_worker.discover_new_posts(now=NOW, instagram_repository=Accounts(), content_repository=content, tracking_repository=tracking) == 0
    assert tracking.calls == ["tracked-0"]


def test_worker_completes_partial_snapshot_and_keeps_scheduled_and_actual_times(tracking_store, monkeypatch):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
        started_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
    )
    repository.ensure_jobs_for_tracking(tracked_id)
    job = repository.claim_due("worker-a")[0]
    monkeypatch.setattr(tracking_worker, "_usable_token", lambda account: "safe-token")
    monkeypatch.setattr(tracking_worker, "fetch_instagram_media_insights", lambda *args: {
        "reach": 100, "likes": 4, "comments": 1,
        "_metric_status": {
            "reach": "available", "likes": "available", "comments": "available",
            "saves": "unavailable", "shares": "unavailable", "views": "unavailable",
        },
    })

    assert tracking_worker.process_job(repository, job, "worker-a") == "completed"
    stored = repository.jobs_for_tracking(tracked_id)[0]
    with factory() as session:
        snapshot = session.get(InstagramInsightSnapshotRecord, stored.snapshot_id)
        assert snapshot.engagement_rate == 5.0
        assert snapshot.views is None
        assert snapshot.metric_status["views"] == "unavailable"
        assert "views" not in snapshot.raw_metrics
        assert snapshot.saves is None and snapshot.shares is None
        assert snapshot.collection_type == "milestone"
        assert snapshot.target_hour == 24
        assert snapshot.scheduled_for == job.due_at.replace(tzinfo=None)
        assert snapshot.captured_at >= snapshot.scheduled_for


@pytest.mark.parametrize(
    ("target_hour", "media_type"),
    [(24, "IMAGE"), (24, "VIDEO"), (24, "CAROUSEL_ALBUM")],
)
def test_worker_fetches_and_persists_views_for_every_milestone(
    tracking_store, monkeypatch, target_hour, media_type
):
    repository, factory = tracking_store
    current = datetime.now(timezone.utc)
    tracked_id = _seed(
        factory,
        published_at=current - timedelta(hours=target_hour, minutes=5),
        started_at=current - timedelta(hours=target_hour, minutes=5),
        suffix=f"{target_hour}-{media_type.lower()}",
        media_type=media_type,
    )
    repository.ensure_jobs_for_tracking(tracked_id, current)
    jobs = repository.claim_due("worker-a", now=current)
    job = next(item for item in jobs if item.target_hour == target_hour)
    calls = []

    monkeypatch.setattr(tracking_worker, "_usable_token", lambda account: "safe-token")

    def fetch(token, provider_media_id, fetched_media_type):
        calls.append((token, provider_media_id, fetched_media_type))
        return {
            "views": 1000 + target_hour,
            "reach": 800 + target_hour,
            "likes": 20,
            "comments": 3,
            "_metric_status": {
                "views": "available",
                "reach": "available",
                "likes": "available",
                "comments": "available",
                "saves": "unavailable",
                "shares": "unavailable",
            },
        }

    monkeypatch.setattr(tracking_worker, "fetch_instagram_media_insights", fetch)

    assert tracking_worker.process_job(repository, job, "worker-a") == "completed"
    assert calls == [("safe-token", f"provider-{target_hour}-{media_type.lower()}", media_type)]

    stored = next(
        item for item in repository.jobs_for_tracking(tracked_id)
        if item.target_hour == target_hour
    )
    with factory() as session:
        snapshot = session.get(InstagramInsightSnapshotRecord, stored.snapshot_id)
        assert snapshot.collection_type == "milestone"
        assert snapshot.target_hour == target_hour
        assert snapshot.views == 1000 + target_hour
        assert snapshot.raw_metrics["views"] == 1000 + target_hour
        assert snapshot.metric_status["views"] == "available"
        assert snapshot.captured_at >= snapshot.scheduled_for


def test_invalid_token_blocks_all_user_jobs(tracking_store, monkeypatch):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
        started_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
    )
    repository.ensure_jobs_for_tracking(tracked_id)
    job = repository.claim_due("worker-a")[0]
    monkeypatch.setattr(tracking_worker, "_usable_token", lambda account: (_ for _ in ()).throw(
        InstagramServiceError("instagram_token_invalid", "safe", 401)
    ))
    monkeypatch.setattr(tracking_worker, "_mark_reconnect_required", lambda user_id: None)

    assert tracking_worker.process_job(repository, job, "worker-a") == "blocked_reauthorization"
    assert {item.status for item in repository.jobs_for_tracking(tracked_id)} == {"blocked_reauthorization"}


def test_rate_limit_is_retried_without_storing_provider_error(tracking_store, monkeypatch):
    repository, factory = tracking_store
    tracked_id = _seed(
        factory,
        published_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
        started_at=datetime.now(timezone.utc) - timedelta(hours=24, minutes=5),
    )
    repository.ensure_jobs_for_tracking(tracked_id)
    job = repository.claim_due("worker-a")[0]
    monkeypatch.setattr(tracking_worker, "_usable_token", lambda account: "safe-token")
    monkeypatch.setattr(tracking_worker, "fetch_instagram_media_insights", lambda *args: (_ for _ in ()).throw(
        InstagramServiceError("instagram_rate_limited", "provider body must not persist", 429, retry_after_seconds=90)
    ))

    assert tracking_worker.process_job(repository, job, "worker-a") == "retry"
    stored = repository.jobs_for_tracking(tracked_id)[0]
    assert stored.status == "retry"
    assert stored.last_error_code == "instagram_rate_limited"
    assert "provider" not in (stored.last_error_code or "")
