from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.services.instagram import decrypt_access_token, encrypt_access_token
from backend.storage.instagram_repository import (
    InstagramRepositoryError,
    SQLAlchemyInstagramRepository,
    get_instagram_repository,
)
from backend.storage.models import InstagramAccount
from backend.storage.sql_models import Base


@pytest.fixture
def repository():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield SQLAlchemyInstagramRepository.from_engine(engine)
    finally:
        engine.dispose()


def test_state_create_consume_and_replay(repository):
    now = datetime.now(timezone.utc)
    repository.create_oauth_state("nonce-1", "user-1", now + timedelta(minutes=5))

    assert repository.consume_oauth_state("nonce-1", now) == "user-1"
    assert repository.consume_oauth_state("nonce-1", now) is None


def test_expired_state_cannot_be_consumed(repository):
    now = datetime.now(timezone.utc)
    repository.create_oauth_state("nonce-expired", "user-1", now - timedelta(seconds=1))

    assert repository.consume_oauth_state("nonce-expired", now) is None


def _account(username: str = "creator") -> InstagramAccount:
    return InstagramAccount(
        id="connection-1",
        user_id="user-1",
        instagram_user_id="instagram-1",
        username=username,
        account_type="BUSINESS",
        media_count=3,
        encrypted_access_token="",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        scopes=["instagram_business_basic"],
        status="connected",
        connected_at=datetime.now(timezone.utc),
    )


def test_connection_create_update_read_delete(repository, monkeypatch):
    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setenv("POSTBRIDGE_TOKEN_ENCRYPTION_KEY", encryption_key)
    encrypted = encrypt_access_token("round-trip-token")

    created = repository.upsert_connection(
        _account(),
        encrypted_token=encrypted,
        scopes=["instagram_business_basic"],
    )
    assert created.username == "creator"
    assert created.encrypted_access_token == ""

    read = repository.get_connection("user-1")
    assert read is not None
    assert read.scopes == ["instagram_business_basic"]
    stored_encrypted = repository.get_encrypted_token(read.id)
    assert stored_encrypted != "round-trip-token"
    assert decrypt_access_token(stored_encrypted) == "round-trip-token"

    updated = read.model_copy(update={"username": "updated", "media_count": 9})
    repository.upsert_connection(updated)
    assert repository.get_connection("user-1").username == "updated"
    assert repository.get_encrypted_token(read.id) == stored_encrypted

    assert repository.delete_connection("user-1") is True
    assert repository.get_connection("user-1") is None
    assert repository.delete_connection("user-1") is False


def test_configured_non_postgres_database_fails_closed(monkeypatch):
    monkeypatch.setenv(
        "POSTBRIDGE_DATABASE_URL",
        "sqlite:///must-not-fall-back-to-json.db",
    )

    with pytest.raises(InstagramRepositoryError) as failure:
        get_instagram_repository()

    assert str(failure.value) == "PostBridge database configuration is invalid."


def test_database_failure_does_not_expose_credentials():
    class FailingSessionFactory:
        def begin(self):
            raise RuntimeError("database-password-should-not-escape")

    repository = SQLAlchemyInstagramRepository(FailingSessionFactory())
    with pytest.raises(InstagramRepositoryError) as failure:
        repository.create_oauth_state(
            "nonce",
            "user",
            datetime.now(timezone.utc) + timedelta(minutes=5),
        )

    assert "database-password-should-not-escape" not in str(failure.value)
