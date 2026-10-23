from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config() -> Config:
    return Config("alembic.ini")


def test_draft_migration_upgrades_empty_database(tmp_path, monkeypatch):
    database = tmp_path / "empty.db"
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", f"sqlite:///{database.as_posix()}")
    command.upgrade(_config(), "head")

    tables = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert {"media_assets", "post_drafts", "post_publications"} <= tables


def test_draft_migration_preserves_populated_database(tmp_path, monkeypatch):
    database = tmp_path / "populated.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", url)
    command.upgrade(_config(), "20261022_0003")
    engine = create_engine(url)
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, email, created_at, updated_at) "
            "VALUES ('existing-user', 'existing@example.test', :now, :now)"
        ), {"now": now})

    command.upgrade(_config(), "head")
    with engine.connect() as connection:
        email = connection.execute(text(
            "SELECT email FROM users WHERE id = 'existing-user'"
        )).scalar_one()
    assert email == "existing@example.test"
    assert "post_drafts" in inspect(engine).get_table_names()
