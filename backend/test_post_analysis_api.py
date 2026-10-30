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
