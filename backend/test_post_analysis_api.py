from types import SimpleNamespace

from backend import instagram_api
from backend.main import app

REMOVED = {
    "/tracked-posts/{tracked_id}/analyses",
    "/tracked-posts/{tracked_id}/comments/refresh",
    "/insights/metrics-backfill",
    "/insights/themes/regenerate",
    "/api/instagram/preferences",
    "/extract-screenshot-metrics",
}

def test_removed_endpoints_are_not_registered_and_return_404_by_routing():
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert not (REMOVED & paths)


def test_feedback_media_rejects_non_meta_hosts_without_fetching(monkeypatch):
    monkeypatch.setattr(instagram_api, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not fetch")))
    media = SimpleNamespace(media_type="REELS", media_url="https://example.test/video.mp4", thumbnail_url=None)

    assert instagram_api._feedback_media(media) is None
