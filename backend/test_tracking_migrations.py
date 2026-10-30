from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

def _config() -> Config:
    return Config("alembic.ini")

def _url(path):
    return f"sqlite:///{path.as_posix()}"

def test_retirement_migration_round_trips_empty_database(tmp_path, monkeypatch):
    url = _url(tmp_path / "empty.db")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", url)
    command.upgrade(_config(), "head")
    engine = create_engine(url)
    tables = inspect(engine).get_table_names()
    assert "insight_text_cache" in tables
    assert "tracked_post_analyses" not in tables
    command.downgrade(_config(), "20261029_0010")
    tables = inspect(engine).get_table_names()
    assert {"tracked_post_analyses", "external_insight_records", "instagram_insight_collection_jobs"} <= set(tables)
    command.upgrade(_config(), "head")
    assert "insight_text_cache" in inspect(engine).get_table_names()

def test_retirement_migration_preserves_populated_raw_snapshot(tmp_path, monkeypatch):
    url = _url(tmp_path / "populated.db")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", url)
    command.upgrade(_config(), "20261029_0010")
    engine = create_engine(url)
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, account_context, created_at, updated_at) VALUES ('u', 'creator@example.test', '', :now, :now)"), {"now": now})
        connection.execute(text("INSERT INTO instagram_connections (id, user_id, instagram_user_id, username, account_type, media_count, encrypted_access_token, token_expires_at, scopes, status, created_at, updated_at) VALUES ('a', 'u', 'ig', 'creator', 'BUSINESS', 1, 'encrypted', NULL, '[]', 'connected', :now, :now)"), {"now": now})
        connection.execute(text("INSERT INTO instagram_media (id, account_id, instagram_media_id, media_type, media_url, thumbnail_url, permalink, caption, published_at, last_synced_at) VALUES ('m', 'a', 'provider', 'IMAGE', NULL, NULL, NULL, 'Keep', :now, :now)"), {"now": now})
        connection.execute(text("INSERT INTO tracked_posts (id, user_id, media_id, is_active, started_at, stopped_at) VALUES ('t', 'u', 'm', 1, :now, NULL)"), {"now": now})
        connection.execute(text("INSERT INTO instagram_insight_snapshots (id, media_id, captured_at, likes, comments, saves, shares, reach, views, engagement_rate, raw_metrics) VALUES ('s', 'm', :now, 2, 1, 3, 4, 20, 25, 50.0, '{\"provider\": 1}')"), {"now": now})
    command.upgrade(_config(), "head")
    with engine.connect() as connection:
        snapshot = connection.execute(text("SELECT views, raw_metrics FROM instagram_insight_snapshots WHERE id='s'")).one()
    assert snapshot.views == 25
    assert "provider" in snapshot.raw_metrics
    columns = {column["name"] for column in inspect(engine).get_columns("instagram_insight_snapshots")}
    assert not {"target_hour", "scheduled_for", "collection_type"} & columns
    assert "instagram_insight_collection_jobs" not in inspect(engine).get_table_names()
    command.downgrade(_config(), "20261029_0010")
    assert "instagram_insight_collection_jobs" in inspect(engine).get_table_names()
