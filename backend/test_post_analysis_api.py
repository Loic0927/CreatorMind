from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend import instagram_api
from backend.auth import AuthenticatedUser
from backend.services.post_analysis import PostAnalysisComputation
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


class FakeContentRepository:
    def __init__(self):
        self.saved = []
        self.snapshot = InstagramInsightSnapshot(
            id="snapshot-1",
            media_id="instagram:media-1",
            captured_at=NOW,
            reach=100,
            views=120,
            likes=10,
            engagement_rate=10,
        )

    def snapshots(self, media_ids):
        return [self.snapshot]

    def append_analysis(self, analysis):
        self.saved.append(analysis)
        return analysis

    def analyses(self, user_id, tracked_post_id):
        return [
            item
            for item in self.saved
            if item.user_id == user_id and item.tracked_post_id == tracked_post_id
        ]


def _user(identifier: str) -> AuthenticatedUser:
    return AuthenticatedUser(id=identifier, email=f"{identifier}@example.test", token_hash="hash")


def _tracked_item():
    return {
        "tracking": SimpleNamespace(id="tracked-1", media_id="instagram:media-1"),
        "media": InstagramMedia(
            id="instagram:media-1",
            account_id="account-1",
            instagram_media_id="media-1",
            media_type="IMAGE",
            caption="Test caption",
            published_at=NOW,
            last_synced_at=NOW,
        ),
        "latest": None,
    }


def test_analyze_tracking_persists_source_snapshot_and_owner(monkeypatch):
    repository = FakeContentRepository()
    peer_snapshot = repository.snapshot.model_copy(update={"id": "snapshot-2", "media_id": "instagram:media-2"})
    peer_item = {
        "tracking": SimpleNamespace(id="tracked-2", media_id="instagram:media-2"),
        "media": InstagramMedia(
            id="instagram:media-2", account_id="account-1", instagram_media_id="media-2",
            media_type="VIDEO", caption="Peer caption", published_at=NOW, last_synced_at=NOW,
        ),
        "latest": peer_snapshot,
    }
    captured = {}

    def fake_analyze(media, snapshots, **kwargs):
        captured.update(kwargs)
        return PostAnalysisComputation(
            source_snapshot_ids=["snapshot-1"], model_name="test-model",
            observed_metrics={"reach": 100}, metric_deltas={"reach": None},
            content_payload={"caption": media.caption},
            output_payload={"score": {"overall": 75, "grade": "B", "categories": {}}, "recommendations": []},
        )

    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: repository)
    monkeypatch.setattr(
        instagram_api,
        "tracked_payload",
        lambda user_id: [_tracked_item(), peer_item] if user_id == "owner" else [],
    )
    monkeypatch.setattr(instagram_api, "analyze_post", fake_analyze)
    monkeypatch.setattr(instagram_api, "get_account_context", lambda user_id: "Magic education account")

    result = instagram_api.analyze_tracking("tracked-1", _user("owner"))

    assert result.user_id == "owner"
    assert result.tracked_post_id == "tracked-1"
    assert result.source_snapshot_id == "snapshot-1"
    assert repository.saved == [result]
    assert captured["peer_metrics"] == [{
        "media_type": "VIDEO",
        "published_at": NOW.isoformat(),
        "captured_at": NOW.isoformat(),
        "metrics": {"likes": 10, "comments": None, "saves": None, "shares": None,
                    "reach": 100, "views": 120, "engagement_rate": 10.0},
    }]
    assert captured["account_context"] == "Magic education account"


def test_analyze_tracking_can_ignore_account_context(monkeypatch):
    repository = FakeContentRepository()
    captured = {}
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "tracked_payload", lambda user_id: [_tracked_item()])
    monkeypatch.setattr(instagram_api, "get_account_context", lambda user_id: "Must not be used")
    monkeypatch.setattr(instagram_api, "analyze_post", lambda media, snapshots, **kwargs: captured.update(kwargs) or PostAnalysisComputation(
        source_snapshot_ids=["snapshot-1"], model_name="test", observed_metrics={}, metric_deltas={},
        content_payload={}, output_payload={"recommendations": []},
    ))

    instagram_api.analyze_tracking("tracked-1", _user("owner"), use_account_context=False)

    assert captured["account_context"] == ""


def test_analysis_history_rejects_another_users_tracked_post(monkeypatch):
    monkeypatch.setattr(
        instagram_api,
        "tracked_payload",
        lambda user_id: [_tracked_item()] if user_id == "owner" else [],
    )
    with pytest.raises(HTTPException) as failure:
        instagram_api.tracked_analyses("tracked-1", _user("other"))
    assert failure.value.status_code == 404
