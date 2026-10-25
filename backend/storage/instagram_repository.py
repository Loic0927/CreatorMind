"""Instagram persistence selection and implementations.

PostgreSQL is mandatory whenever POSTBRIDGE_DATABASE_URL is configured. The local
implementation is an explicit development-only fallback and is never selected after
a configured database error.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache
from threading import Lock
from typing import Protocol

from sqlalchemy import Engine, create_engine, delete, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.storage import json_store, token_store
from backend.storage.models import InstagramAccount
from backend.storage.sql_models import InstagramConnectionRecord, OAuthStateRecord
from backend.config import is_production


class InstagramRepositoryError(RuntimeError):
    """Safe persistence error that never includes a database URL or credentials."""


class InstagramRepository(Protocol):
    def create_oauth_state(
        self, nonce: str, user_id: str, expires_at: datetime
    ) -> None: ...

    def consume_oauth_state(self, nonce: str, now: datetime) -> str | None: ...

    def get_connection(self, user_id: str) -> InstagramAccount | None: ...

    def upsert_connection(
        self,
        account: InstagramAccount,
        encrypted_token: str | None = None,
        scopes: list[str] | None = None,
    ) -> InstagramAccount: ...

    def get_encrypted_token(self, connection_id: str) -> str | None: ...

    def delete_connection(self, user_id: str) -> bool: ...

    def set_insight_themes(self, user_id: str, themes: list[str]) -> InstagramAccount | None: ...


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class SQLAlchemyInstagramRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> "SQLAlchemyInstagramRepository":
        return cls(sessionmaker(bind=engine, expire_on_commit=False))

    @classmethod
    def from_database_url(cls, database_url: str) -> "SQLAlchemyInstagramRepository":
        try:
            parsed = make_url(database_url)
            if parsed.get_backend_name() != "postgresql":
                raise ValueError
            engine = create_engine(database_url, pool_pre_ping=True)
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database configuration is invalid."
            ) from None
        return cls.from_engine(engine)

    def create_oauth_state(
        self, nonce: str, user_id: str, expires_at: datetime
    ) -> None:
        try:
            with self._session_factory.begin() as session:
                session.add(
                    OAuthStateRecord(
                        nonce=nonce,
                        user_id=user_id,
                        expires_at=expires_at,
                        consumed_at=None,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    def consume_oauth_state(self, nonce: str, now: datetime) -> str | None:
        try:
            with self._session_factory.begin() as session:
                statement = (
                    update(OAuthStateRecord)
                    .where(
                        OAuthStateRecord.nonce == nonce,
                        OAuthStateRecord.consumed_at.is_(None),
                        OAuthStateRecord.expires_at >= now,
                    )
                    .values(consumed_at=now)
                    .returning(OAuthStateRecord.user_id)
                )
                return session.execute(statement).scalar_one_or_none()
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    def get_connection(self, user_id: str) -> InstagramAccount | None:
        try:
            with self._session_factory() as session:
                record = session.scalar(
                    select(InstagramConnectionRecord).where(
                        InstagramConnectionRecord.user_id == user_id
                    )
                )
                return self._to_account(record) if record else None
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    def upsert_connection(
        self,
        account: InstagramAccount,
        encrypted_token: str | None = None,
        scopes: list[str] | None = None,
    ) -> InstagramAccount:
        try:
            with self._session_factory.begin() as session:
                record = session.scalar(
                    select(InstagramConnectionRecord).where(
                        InstagramConnectionRecord.user_id == account.user_id
                    )
                )
                now = datetime.now(timezone.utc)
                if record is None:
                    if not encrypted_token:
                        raise InstagramRepositoryError(
                            "An encrypted Instagram token is required."
                        )
                    record = InstagramConnectionRecord(
                        id=account.id,
                        user_id=account.user_id,
                        instagram_user_id=account.instagram_user_id,
                        username=account.username,
                        account_type=account.account_type,
                        media_count=account.media_count,
                        encrypted_access_token=encrypted_token,
                        token_expires_at=account.token_expires_at,
                        scopes=list(scopes or account.scopes),
                        insight_themes=list(account.insight_themes),
                        insight_themes_updated_at=account.insight_themes_updated_at,
                        status=account.status,
                        created_at=account.connected_at,
                        updated_at=now,
                    )
                    session.add(record)
                else:
                    record.instagram_user_id = account.instagram_user_id
                    record.username = account.username
                    record.account_type = account.account_type
                    record.media_count = account.media_count
                    if encrypted_token:
                        record.encrypted_access_token = encrypted_token
                    record.token_expires_at = account.token_expires_at
                    if scopes is not None:
                        record.scopes = list(scopes)
                    record.status = account.status
                    record.updated_at = now
                session.flush()
                return self._to_account(record)
        except InstagramRepositoryError:
            raise
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    def set_insight_themes(self, user_id: str, themes: list[str]) -> InstagramAccount | None:
        try:
            with self._session_factory.begin() as session:
                record = session.scalar(select(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user_id))
                if record is None:
                    return None
                record.insight_themes = list(themes)
                record.insight_themes_updated_at = datetime.now(timezone.utc)
                record.updated_at = datetime.now(timezone.utc)
                session.flush()
                return self._to_account(record)
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def get_encrypted_token(self, connection_id: str) -> str | None:
        try:
            with self._session_factory() as session:
                return session.scalar(
                    select(InstagramConnectionRecord.encrypted_access_token).where(
                        InstagramConnectionRecord.id == connection_id
                    )
                )
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    def delete_connection(self, user_id: str) -> bool:
        try:
            with self._session_factory.begin() as session:
                result = session.execute(
                    delete(InstagramConnectionRecord).where(
                        InstagramConnectionRecord.user_id == user_id
                    )
                )
                return bool(result.rowcount)
        except Exception:
            raise InstagramRepositoryError(
                "PostBridge database operation failed."
            ) from None

    @staticmethod
    def _to_account(record: InstagramConnectionRecord) -> InstagramAccount:
        return InstagramAccount(
            id=record.id,
            user_id=record.user_id,
            instagram_user_id=record.instagram_user_id,
            username=record.username,
            profile_picture_url=None,
            account_type=record.account_type,
            media_count=record.media_count,
            encrypted_access_token="",
            token_expires_at=_as_utc(record.token_expires_at),
            scopes=list(record.scopes or []),
            insight_themes=list(record.insight_themes or []),
            insight_themes_updated_at=_as_utc(record.insight_themes_updated_at),
            status=record.status,
            connected_at=_as_utc(record.created_at),
            last_synced_at=_as_utc(record.updated_at),
            last_error=None,
        )


class LocalDevelopmentInstagramRepository:
    """Development-only JSON/sidecar fallback used when no DB URL is configured."""

    def __init__(self):
        self._states: dict[str, tuple[str, datetime, datetime | None]] = {}
        self._state_lock = Lock()

    def create_oauth_state(
        self, nonce: str, user_id: str, expires_at: datetime
    ) -> None:
        with self._state_lock:
            self._states[nonce] = (user_id, expires_at, None)

    def consume_oauth_state(self, nonce: str, now: datetime) -> str | None:
        with self._state_lock:
            state = self._states.get(nonce)
            if not state:
                return None
            user_id, expires_at, consumed_at = state
            if consumed_at is not None or expires_at < now:
                return None
            self._states[nonce] = (user_id, expires_at, now)
            return user_id

    def get_connection(self, user_id: str) -> InstagramAccount | None:
        return json_store.get_instagram_account(user_id)

    def upsert_connection(
        self,
        account: InstagramAccount,
        encrypted_token: str | None = None,
        scopes: list[str] | None = None,
    ) -> InstagramAccount:
        stored = account.model_copy(
            update={
                "encrypted_access_token": "",
                "scopes": list(scopes if scopes is not None else account.scopes),
            }
        )
        if encrypted_token:
            token_store.save_encrypted_token(account.id, encrypted_token)
        try:
            return json_store.upsert_instagram_account(stored)
        except Exception:
            if encrypted_token:
                token_store.delete_encrypted_token(account.id)
            raise

    def get_encrypted_token(self, connection_id: str) -> str | None:
        return token_store.get_encrypted_token(connection_id)

    def delete_connection(self, user_id: str) -> bool:
        existing = json_store.get_instagram_account(user_id)
        if not existing:
            return False

        def mutate(store):
            store.instagram_accounts = [
                item for item in store.instagram_accounts if item.user_id != user_id
            ]

        json_store.update_store(mutate)
        token_store.delete_encrypted_token(existing.id)
        return True

    def set_insight_themes(self, user_id: str, themes: list[str]) -> InstagramAccount | None:
        existing = self.get_connection(user_id)
        if existing is None:
            return None
        updated = existing.model_copy(update={
            "insight_themes": list(themes),
            "insight_themes_updated_at": datetime.now(timezone.utc),
        })
        return json_store.upsert_instagram_account(updated)


_local_repository = LocalDevelopmentInstagramRepository()


@lru_cache(maxsize=4)
def _postgres_repository(database_url: str) -> SQLAlchemyInstagramRepository:
    return SQLAlchemyInstagramRepository.from_database_url(database_url)


def get_instagram_repository() -> InstagramRepository:
    database_url = os.getenv("POSTBRIDGE_DATABASE_URL")
    if database_url:
        return _postgres_repository(database_url)
    if is_production():
        raise InstagramRepositoryError(
            "PostBridge database configuration is required in production."
        )
    return _local_repository
