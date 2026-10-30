from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import backend.services.instagram_sync as sync

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)

class InstagramRepo:
    def __init__(self, account):
        self.account = account
        self.marks = []
    def get_connection(self, user_id): return self.account
    def mark_session_sync(self, user_id, when, error):
        self.marks.append((when, error))
        if when: self.account.session_synced_at = when
    def upsert_connection(self, account, **kwargs): self.account = account
    def get_encrypted_token(self, account_id): return "token"

class ContentRepo:
    def __init__(self, media=None, tracked=None):
        self._media = list(media or [])
        self._tracked = list(tracked or [])
    def upsert_media(self, media):
        by_id = {item.id: item for item in self._media}
        by_id.update({item.id: item for item in media})
        self._media = list(by_id.values())
    def create_tracked(self, user_id, media_id): return None
    def tracked(self, user_id, active_only=True): return list(self._tracked)
    def media_for_account(self, account_id): return list(self._media)
    def snapshots(self, media_ids): return []
    def comments(self, user_id, tracked_id): return []

def account(last=None):
    return SimpleNamespace(id="a", status="connected", session_synced_at=last, instagram_user_id="ig", scopes=[])

def test_session_sync_runs_once_then_skips_second_login_within_30_minutes(monkeypatch):
    instagram = InstagramRepo(account())
    content = ContentRepo()
    monkeypatch.setattr(sync, "get_instagram_repository", lambda: instagram)
    monkeypatch.setattr(sync, "get_content_repository", lambda: content)
    monkeypatch.setattr(sync, "usable_token", lambda account: "token")
    monkeypatch.setattr(sync, "fetch_instagram_media", lambda token: [])
    monkeypatch.setattr(sync, "next_post_suggestion", lambda *args, **kwargs: None)
    first = sync.run_account_sync("u", now=NOW)
    second = sync.run_account_sync("u", now=NOW + timedelta(minutes=29))
    assert first["status"] == "complete"
    assert second["status"] == "skipped"
    assert len(instagram.marks) == 1

def test_one_failed_post_does_not_abort_remaining_posts(monkeypatch):
    media = [
        SimpleNamespace(id=f"m{index}", instagram_media_id=f"ig{index}", thumbnail_url=None, media_url=None, published_at=NOW - timedelta(days=20), media_type="IMAGE")
        for index in (1, 2)
    ]
    tracked = [SimpleNamespace(id="t1", media_id="m1"), SimpleNamespace(id="t2", media_id="m2")]
    instagram = InstagramRepo(account())
    content = ContentRepo(media, tracked)
    calls = []
    monkeypatch.setattr(sync, "get_instagram_repository", lambda: instagram)
    monkeypatch.setattr(sync, "get_content_repository", lambda: content)
    monkeypatch.setattr(sync, "usable_token", lambda account: "token")
    monkeypatch.setattr(sync, "fetch_instagram_media", lambda token: [])
    monkeypatch.setattr(sync, "next_post_suggestion", lambda *args, **kwargs: None)
    def refresh(user_id, tracked_post, media_item, token):
        calls.append(tracked_post.id)
        if tracked_post.id == "t1":
            raise sync.InstagramServiceError("instagram_upstream_error", "failed", 502)
    monkeypatch.setattr(sync, "refresh_one_post", refresh)
    result = sync.run_account_sync("u", now=NOW)
    assert calls == ["t1", "t2"]
    assert result == {"status": "partial_failure", "refreshed": 1, "failed": 1}

def test_refresh_is_idempotent_when_provider_metrics_are_unchanged(monkeypatch):
    metrics = {"likes": 5, "comments": 2, "saves": 1, "shares": 1, "reach": 100, "views": 120, "average_watch_time_ms": None, "total_watch_time_ms": None, "_metric_status": {}}
    previous = SimpleNamespace(captured_at=NOW, raw_metrics={}, engagement_rate=9.0, **{key: metrics[key] for key in ("likes", "comments", "saves", "shares", "reach", "views", "average_watch_time_ms", "total_watch_time_ms")})
    class Repo:
        def snapshots(self, media_ids): return [previous]
        def append_snapshot(self, value): raise AssertionError("duplicate snapshot")
        def comments(self, user_id, tracked_id): return []
    monkeypatch.setattr(sync, "get_content_repository", lambda: Repo())
    monkeypatch.setattr(sync, "fetch_instagram_media_insights", lambda *args: metrics)
    monkeypatch.setattr(sync, "get_instagram_repository", lambda: SimpleNamespace(get_connection=lambda user_id: None))
    changed = sync.refresh_one_post("u", SimpleNamespace(id="t"), SimpleNamespace(id="m", instagram_media_id="ig", media_type="IMAGE"), "token")
    assert changed is False
