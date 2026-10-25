from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config() -> Config:
    return Config("alembic.ini")


def test_tracking_migration_preserves_snapshots_and_round_trips(tmp_path, monkeypatch):
    database = tmp_path / "tracking.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", url)
    command.upgrade(_config(), "20261024_0005")
    engine = create_engine(url)
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, email, account_context, created_at, updated_at) "
            "VALUES ('user-1', 'creator@example.test', '', :now, :now)"
        ), {"now": now})
        connection.execute(text(
            "INSERT INTO instagram_connections "
            "(id, user_id, instagram_user_id, username, account_type, media_count, encrypted_access_token, token_expires_at, scopes, status, created_at, updated_at) "
            "VALUES ('account-1', 'user-1', 'ig-1', 'creator', 'BUSINESS', 1, 'encrypted', NULL, '[]', 'connected', :now, :now)"
        ), {"now": now})
        connection.execute(text(
            "INSERT INTO instagram_media "
            "(id, account_id, instagram_media_id, media_type, media_url, thumbnail_url, permalink, caption, published_at, last_synced_at) "
            "VALUES ('media-1', 'account-1', 'provider-1', 'IMAGE', NULL, NULL, NULL, 'Keep #original', :now, :now)"
        ), {"now": now})
        connection.execute(text(
            "INSERT INTO tracked_posts (id, user_id, media_id, is_active, started_at, stopped_at) "
            "VALUES ('tracked-1', 'user-1', 'media-1', 1, :now, NULL)"
        ), {"now": now})
        connection.execute(text(
            "INSERT INTO instagram_insight_snapshots "
            "(id, media_id, captured_at, likes, comments, saves, shares, reach, views, engagement_rate, raw_metrics) "
            "VALUES ('snapshot-1', 'media-1', :now, 2, 1, NULL, NULL, 20, 25, 15.0, '{}')"
        ), {"now": now})

    command.upgrade(_config(), "head")
    with engine.connect() as connection:
        snapshot = connection.execute(text(
            "SELECT engagement_rate, collection_type, target_hour, metric_status "
            "FROM instagram_insight_snapshots WHERE id = 'snapshot-1'"
        )).one()
    assert snapshot.engagement_rate == 15.0
    assert snapshot.collection_type == "manual_current"
    assert snapshot.target_hour is None
    assert snapshot.metric_status == "{}"
    assert "instagram_insight_collection_jobs" in inspect(engine).get_table_names()

    command.downgrade(_config(), "20261024_0005")
    assert "instagram_insight_collection_jobs" not in inspect(engine).get_table_names()
    command.upgrade(_config(), "head")
    assert "instagram_insight_collection_jobs" in inspect(engine).get_table_names()
