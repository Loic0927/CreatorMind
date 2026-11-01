from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.feedback as feedback
from backend.storage.sql_models import Base, InstagramConnectionRecord, InstagramMediaRecord, TrackedPostRecord, UserRecord
from backend.storage.tracking_repository import MILESTONES, TrackingRepository
from backend.storage.models import InstagramInsightSnapshot
from backend.storage.sql_models import InstagramInsightCollectionJobRecord, InstagramInsightSnapshotRecord
from backend import instagram_api
from backend.auth import AuthenticatedUser
import backend.storage.tracking_repository as tracking_repository_module

NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def _factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory, published_at, started_at=NOW):
    with factory.begin() as session:
        session.add(UserRecord(id="u", email="u@example.test", account_context="", created_at=NOW, updated_at=NOW))
        session.add(InstagramConnectionRecord(
            id="a", user_id="u", instagram_user_id="ig", username="creator", account_type="BUSINESS",
            media_count=1, encrypted_access_token="encrypted", token_expires_at=None, scopes=[],
            session_synced_at=None, session_sync_error=None, tracking_start_at=NOW,
            status="connected", created_at=NOW, updated_at=NOW,
        ))
        session.add(InstagramMediaRecord(
            id="m", account_id="a", instagram_media_id="provider", media_type="REELS",
            media_url=None, thumbnail_url=None, permalink=None, caption="", published_at=published_at, last_synced_at=NOW,
        ))
        session.add(TrackedPostRecord(
            id="t", user_id="u", media_id="m", is_active=True, started_at=started_at, stopped_at=None,
            first_24h_status="collecting", first_24h_reason=None,
        ))


def test_fresh_post_gets_all_five_idempotent_jobs():
    factory = _factory(); _seed(factory, NOW)
    repository = TrackingRepository(factory)
    first = repository.ensure_jobs_for_tracking("t", NOW)
    second = repository.ensure_jobs_for_tracking("t", NOW)
    assert [job.milestone_hours for job in first] == list(MILESTONES)
    assert len(second) == 5
    assert all(job.status == "pending" for job in second)


def test_late_detection_marks_expired_milestones_but_keeps_remaining():
    factory = _factory(); _seed(factory, NOW - timedelta(hours=8))
    jobs = TrackingRepository(factory).ensure_jobs_for_tracking("t", NOW)
    assert [job.status for job in jobs] == ["missed", "missed", "missed", "pending", "pending"]
    assert all(job.reason == "tracking_started_late" for job in jobs[:3])
    with factory() as session:
        tracked = session.get(TrackedPostRecord, "t")
        assert tracked.first_24h_status == "partial"


def test_post_added_after_first_day_has_no_jobs_and_is_unavailable():
    factory = _factory(); _seed(factory, NOW - timedelta(hours=25))
    assert TrackingRepository(factory).ensure_jobs_for_tracking("t", NOW) == []
    with factory() as session:
        tracked = session.get(TrackedPostRecord, "t")
        assert (tracked.first_24h_status, tracked.first_24h_reason) == ("unavailable", "added_after_24h")


def test_retry_becomes_missed_after_grace_and_restart_does_not_duplicate_snapshot():
    factory = _factory(); _seed(factory, NOW - timedelta(hours=1))
    repository = TrackingRepository(factory); repository.ensure_jobs_for_tracking("t", NOW)
    claimed = repository.claim_due("worker-a", now=NOW)
    assert [job.milestone_hours for job in claimed] == [1]
    assert repository.retry(claimed[0].id, "worker-a", "instagram_upstream_error", 10, NOW)
    repository.claim_due("worker-b", now=NOW + timedelta(minutes=31))
    with factory() as session:
        first = session.get(InstagramInsightCollectionJobRecord, claimed[0].id)
        assert first.status == "missed" and first.reason == "collection_window_missed"

    # A separate fresh queue completes exactly once even if another worker cycle runs.
    factory2 = _factory(); _seed(factory2, NOW - timedelta(hours=1))
    repository2 = TrackingRepository(factory2); repository2.ensure_jobs_for_tracking("t", NOW)
    job = repository2.claim_due("worker-a", now=NOW)[0]
    snapshot = InstagramInsightSnapshot(id="snapshot", media_id="m", captured_at=NOW,
        views=10, scheduled_for=job.due_at, milestone_hours=1, source="api", lateness_seconds=0)
    assert repository2.complete(job.id, "worker-a", snapshot, NOW)
    assert repository2.claim_due("worker-after-restart", now=NOW) == []
    repository2.ensure_jobs_for_tracking("t", NOW + timedelta(hours=25))
    with factory2() as session:
        assert session.query(InstagramInsightSnapshotRecord).count() == 1
        assert session.get(TrackedPostRecord, "t").first_24h_status != "unavailable"


def _snapshot(identifier, captured, views, reach=None, engagement=5, watch=1000, interactions=10):
    return SimpleNamespace(
        id=identifier, captured_at=captured, views=views, reach=reach if reach is not None else views,
        engagement_rate=engagement, average_watch_time_ms=watch,
        saves=interactions, shares=interactions, comments=interactions, likes=interactions,
    )


def _item(identifier, media_type, published_at, snapshots):
    return {"tracking": SimpleNamespace(id=identifier),
            "media": SimpleNamespace(media_type=media_type, published_at=published_at),
            "snapshots": snapshots, "latest": snapshots[-1] if snapshots else None}


def test_each_fact_type_qualifies_from_real_snapshot_evidence():
    published = NOW - timedelta(days=20)
    selected = _item("selected", "REELS", published, [
        _snapshot("s1", published + timedelta(hours=1), 100, 100, watch=500, interactions=2),
        _snapshot("s2", published + timedelta(hours=8), 200, 200, watch=1000, interactions=5),
        _snapshot("s3", published + timedelta(hours=30), 400, 3000, watch=5000, interactions=100),
    ])
    peers = [_item(f"p{i}", "REELS", NOW - timedelta(days=30),
                   [_snapshot(f"ps{i}", NOW, 1000, 1000, watch=1000, interactions=10)]) for i in range(6)]
    facts = feedback.build_feedback_facts(selected, [selected, *peers], {"usual_ranges": []}, now=NOW)
    assert {fact["type"] for fact in facts if fact["qualifies"]} == {
        "growth_stage", "accumulation_pace", "interaction_mix", "reach_interaction_relation", "watch_time"
    }


def test_fact_boundaries_and_novelty_rule_do_not_invent_evidence():
    selected = _item("selected", "IMAGE", NOW - timedelta(days=2), [_snapshot("only", NOW, 10)])
    facts = feedback.build_feedback_facts(selected, [selected], {"usual_ranges": []}, now=NOW)
    assert not any(fact["qualifies"] for fact in facts)

    rich = _item("rich", "REELS", NOW - timedelta(days=20), [
        _snapshot("a", NOW - timedelta(hours=12), 100, 100, interactions=2),
        _snapshot("b", NOW - timedelta(hours=6), 200, 200, interactions=5),
        _snapshot("c", NOW, 400, 3000, interactions=100),
    ])
    peers = [_item(f"q{i}", "REELS", NOW - timedelta(days=30), [_snapshot(f"q{i}s", NOW, 1000, 1000, interactions=10)]) for i in range(6)]
    visible = {"usual_ranges": [{"metric": key} for key in ("saves", "shares", "comments")]}
    mix = next(fact for fact in feedback.build_feedback_facts(rich, [rich, *peers], visible, NOW) if fact["type"] == "interaction_mix")
    assert mix["qualifies"] is False and mix["evidence"]["novelty_dropped"] is True


def _payload(text="Attention was still accumulating across the observed checkpoints.", kind="observation", ids=None):
    return {"sentences": [{"text": text, "kind": kind, "fact_ids": ids or ["growth_stage"]}]}


def test_validator_rejects_digits_causation_prediction_unknown_fact_advice_and_second_suggestion():
    facts = [{"id": "growth_stage", "type": "growth_stage", "value": "still_growing", "evidence": {}, "qualifies": True}]
    assert feedback.validate_output(_payload(), facts)
    assert not feedback.validate_output(_payload("It grew across 2 checkpoints."), facts)
    assert not feedback.validate_output(_payload("It grew because viewers stayed."), facts)
    assert not feedback.validate_output(_payload("It will keep growing."), facts)
    assert not feedback.validate_output(_payload(ids=["unknown"]), facts)
    assert not feedback.validate_output(_payload("Try another version."), facts)
    two = {"sentences": [
        {"text": "Consider another version.", "kind": "suggestion", "fact_ids": ["growth_stage"]},
        {"text": "Try a shorter version.", "kind": "suggestion", "fact_ids": ["growth_stage"]},
    ]}
    assert not feedback.validate_output(two, facts)


def test_provider_fallback_and_cache_signature_invalidation(monkeypatch):
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    facts = [{"id": "growth_stage", "type": "growth_stage", "value": "still_growing", "evidence": {}, "qualifies": True}]
    calls = []
    class Invalid:
        name = "trained"; model = "bad"
        def generate(self, facts): calls.append("trained"); return _payload("It will grow.")
    class Good:
        name = "gemini"; model = "one"
        def generate(self, facts): calls.append("gemini-one"); return _payload()
    monkeypatch.setattr(feedback, "_selection", lambda: ([Invalid(), Good()], "auto:one"))
    first = feedback.generate_summary("fallback-user", "fallback-post", facts)
    second = feedback.generate_summary("fallback-user", "fallback-post", facts)
    assert first == second and calls == ["trained", "gemini-one"]

    class Changed(Good):
        model = "two"
        def generate(self, facts): calls.append("gemini-two"); return _payload("Attention continued accumulating across the observed checkpoints.")
    monkeypatch.setattr(feedback, "_selection", lambda: ([Changed()], "gemini:two"))
    assert "continued" in feedback.generate_summary("fallback-user", "fallback-post", facts)
    assert calls[-1] == "gemini-two"


def test_trained_numeric_predictor_is_always_disabled_and_notes_are_deterministic(monkeypatch):
    assert feedback.TrainedFeedbackProvider().healthy is False
    monkeypatch.setenv("FEEDBACK_PROVIDER", "trained"); monkeypatch.setenv("FEEDBACK_TRAINED_ENABLED", "true")
    providers, _ = feedback._selection()
    assert [provider.name for provider in providers] == ["gemini"]
    assert feedback.summary_note("unavailable").startswith("Early-growth data isn't available")
    assert feedback.summary_note("partial").startswith("Some early-growth checkpoints")
    assert feedback.summary_note("complete") is None
    assert feedback.summary_note("collecting") is None


def test_no_qualifying_fact_hides_summary_and_cache_read_never_selects_provider(monkeypatch):
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    empty = [{"id": "growth_stage", "type": "growth_stage", "value": "", "evidence": {}, "qualifies": False}]
    assert feedback.generate_summary("empty-user", "empty-post", empty) is None
    monkeypatch.setattr(feedback, "_selection", lambda: (_ for _ in ()).throw(AssertionError("page read must not select a provider")))
    assert feedback.cached_summary("empty-user", "empty-post") is None


def test_home_picker_adds_old_post_fetches_lifetime_metrics_and_schedules_only_valid_windows(monkeypatch):
    media = SimpleNamespace(id="m", instagram_media_id="provider", media_type="IMAGE", published_at=NOW - timedelta(hours=10))
    tracked = SimpleNamespace(id="t", media_id="m", is_active=True, started_at=NOW, stopped_at=None)
    class Content:
        def media_for_account(self, account_id): return [media]
        def create_tracked(self, user_id, media_id): return tracked
    class Queue:
        def __init__(self): self.ids = []
        def ensure_jobs_for_tracking(self, tracked_id): self.ids.append(tracked_id)
    queue = Queue(); refreshed = []
    account = SimpleNamespace(id="a", status="connected")
    monkeypatch.setattr(instagram_api, "stored_connection", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: Content())
    monkeypatch.setattr(instagram_api, "usable_token", lambda value: "token")
    monkeypatch.setattr(instagram_api, "refresh_one_post", lambda *args, **kwargs: refreshed.append(args))
    monkeypatch.setattr(tracking_repository_module, "get_tracking_repository", lambda: queue)
    result = instagram_api.track(instagram_api.TrackRequest(media_id="m"), AuthenticatedUser(id="u", email="u@example.test", token_hash="h"))
    assert result["id"] == "t"
    assert len(refreshed) == 1 and queue.ids == ["t"]


def test_internal_first_day_fields_are_not_exposed_by_tracked_post_api():
    tracked = SimpleNamespace(id="t", media_id="m", is_active=True, started_at=NOW, stopped_at=None,
                              first_24h_status="partial", first_24h_reason="tracking_started_late")
    snapshot = InstagramInsightSnapshot(id="s", media_id="m", captured_at=NOW, views=10,
        scheduled_for=NOW, milestone_hours=1, source="api", lateness_seconds=12)
    public = instagram_api._public_tracked_item({"tracking": tracked, "media": {}, "latest": snapshot, "snapshots": [snapshot]})
    assert "first_24h_status" not in public["tracking"] and "first_24h_reason" not in public["tracking"]
    for value in [public["latest"], *public["snapshots"]]:
        assert not {"scheduled_for", "milestone_hours", "source", "lateness_seconds"} & value.keys()
