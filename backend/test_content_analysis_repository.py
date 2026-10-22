from datetime import datetime, timezone

from backend.storage import json_store
from backend.storage.content_repository import ContentRepository
from backend.storage.models import TrackedPostAnalysis


def _analysis(user_id: str = "user-1", tracked_post_id: str = "tracked-1") -> TrackedPostAnalysis:
    return TrackedPostAnalysis(
        id="analysis-1",
        user_id=user_id,
        tracked_post_id=tracked_post_id,
        source_snapshot_id="snapshot-1",
        source_snapshot_ids=["snapshot-1"],
        model_name="test-model",
        observed_metrics={"reach": 100},
        metric_deltas={"reach": None},
        content_payload={"caption": "Test"},
        output_payload={"summary": "Test summary"},
        created_at=datetime.now(timezone.utc),
    )


def test_local_analysis_history_is_scoped_to_user_and_tracked_post(monkeypatch, tmp_path):
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)
    monkeypatch.setattr(json_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(json_store, "STORE_PATH", tmp_path / "store.json")
    repository = ContentRepository()
    repository.append_analysis(_analysis())

    assert [item.id for item in repository.analyses("user-1", "tracked-1")] == [
        "analysis-1"
    ]
    assert repository.analyses("user-2", "tracked-1") == []
    assert repository.analyses("user-1", "tracked-2") == []
