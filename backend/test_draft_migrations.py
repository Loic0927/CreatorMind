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

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert {"media_assets", "post_drafts", "post_publications"} <= tables
    assert "account_context" in {column["name"] for column in inspect(engine).get_columns("users")}


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
        row = connection.execute(text(
            "SELECT email, account_context FROM users WHERE id = 'existing-user'"
        )).one()
    assert row.email == "existing@example.test"
    assert row.account_context == ""
    assert "post_drafts" in inspect(engine).get_table_names()
