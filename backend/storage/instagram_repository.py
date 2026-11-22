"""Instagram persistence selection and implementations.

PostgreSQL is mandatory whenever POSTBRIDGE_DATABASE_URL is configured. The local
implementation is an explicit development-only fallback and is never selected after
a configured database error.
"""

import os
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Protocol

from sqlalchemy import Engine, create_engine, delete, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.config import is_production
from backend.storage import json_store, token_store
from backend.storage.models import InstagramAccount, InstagramDataDeletionRequest
from backend.storage.sql_models import (
    AIGenerationLogRecord,
    InsightTextCacheRecord,
    InstagramCommentRecord,
    InstagramConnectionRecord,
    InstagramDataDeletionRequestRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    OAuthStateRecord,
    TrackedPostRecord,
)


class InstagramRepositoryError(RuntimeError):
    """Safe persistence error that never includes a database URL or credentials."""


class InstagramRepository(Protocol):
    def create_oauth_state(self, nonce: str, user_id: str, expires_at: datetime) -> None: ...

    def consume_oauth_state(self, nonce: str, now: datetime) -> str | None: ...

    def get_connection(self, user_id: str) -> InstagramAccount | None: ...

    def list_connections(self) -> list[InstagramAccount]: ...

    def upsert_connection(
        self,
        account: InstagramAccount,
        encrypted_token: str | None = None,
        scopes: list[str] | None = None,
    ) -> InstagramAccount: ...

    def get_encrypted_token(self, connection_id: str) -> str | None: ...

    def delete_connection(self, user_id: str) -> bool: ...

    def deauthorize_instagram_user(self, instagram_user_id: str) -> int: ...

    def delete_instagram_data(
        self,
        instagram_user_id: str,
        confirmation_code: str,
        now: datetime,
    ) -> None: ...

    def get_data_deletion_request(self, code: str) -> InstagramDataDeletionRequest | None: ...

    def mark_session_sync(
        self, user_id: str, synced_at: datetime | None, error: str | None
    ) -> InstagramAccount | None: ...


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


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
            raise InstagramRepositoryError("PostBridge database configuration is invalid.") from None
        return cls.from_engine(engine)

    def create_oauth_state(self, nonce: str, user_id: str, expires_at: datetime) -> None:
        try:
            with self._session_factory.begin() as session:
                session.add(
                    OAuthStateRecord(
                        nonce=nonce,
                        user_id=user_id,
                        expires_at=expires_at,
                        consumed_at=None,
                        created_at=datetime.now(UTC),
                    )
                )
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

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
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def get_connection(self, user_id: str) -> InstagramAccount | None:
        try:
            with self._session_factory() as session:
                record = session.scalar(
                    select(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user_id)
                )
                return self._to_account(record) if record else None
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def upsert_connection(
        self,
        account: InstagramAccount,
        encrypted_token: str | None = None,
        scopes: list[str] | None = None,
    ) -> InstagramAccount:
        try:
            with self._session_factory.begin() as session:
                record = session.scalar(
                    select(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == account.user_id)
                )
                now = datetime.now(UTC)
                if record is None:
                    if not encrypted_token:
                        raise InstagramRepositoryError("An encrypted Instagram token is required.")
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
                        session_synced_at=account.session_synced_at,
                        session_sync_error=account.session_sync_error,
                        tracking_start_at=account.tracking_start_at or account.connected_at,
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
                    record.session_synced_at = account.session_synced_at
                    record.session_sync_error = account.session_sync_error
                    # tracking_start_at is deliberately immutable across re-authorization.
                    record.updated_at = now
                session.flush()
                return self._to_account(record)
        except InstagramRepositoryError:
            raise
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def mark_session_sync(self, user_id: str, synced_at: datetime | None, error: str | None) -> InstagramAccount | None:
        try:
            with self._session_factory.begin() as session:
                record = session.scalar(
                    select(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user_id)
                )
                if record is None:
                    return None
                record.session_synced_at = synced_at
                record.session_sync_error = error
                record.updated_at = datetime.now(UTC)
                session.flush()
                return self._to_account(record)
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def list_connections(self) -> list[InstagramAccount]:
        try:
            with self._session_factory() as session:
                return [self._to_account(item) for item in session.scalars(select(InstagramConnectionRecord)).all()]
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
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def delete_connection(self, user_id: str) -> bool:
        try:
            with self._session_factory.begin() as session:
                result = session.execute(
                    delete(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user_id)
                )
                return bool(result.rowcount)
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def deauthorize_instagram_user(self, instagram_user_id: str) -> int:
        """Invalidate Meta-authorized connections without deleting user history."""
        try:
            with self._session_factory.begin() as session:
                result = session.execute(
                    update(InstagramConnectionRecord)
                    .where(InstagramConnectionRecord.instagram_user_id == instagram_user_id)
                    .values(
                        status="disconnected",
                        # This column is NOT NULL, so an empty value is the
                        # safe erased-token representation.
                        encrypted_access_token="",
                        token_expires_at=None,
                        session_sync_error=None,
                        updated_at=datetime.now(UTC),
                    )
                )
                return int(result.rowcount or 0)
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def delete_instagram_data(
        self,
        instagram_user_id: str,
        confirmation_code: str,
        now: datetime,
    ) -> None:
        """Delete Instagram-derived records while preserving the PostBridge user.

        The deletion confirmation is stored in the same transaction so an
        acknowledged request always has a public status record, including when
        Meta sends an app-scoped user id that is no longer known locally.
        """
        try:
            with self._session_factory.begin() as session:
                connections = list(
                    session.scalars(
                        select(InstagramConnectionRecord).where(
                            InstagramConnectionRecord.instagram_user_id == instagram_user_id
                        )
                    )
                )
                connection_ids = [item.id for item in connections]
                user_ids = list({item.user_id for item in connections})
                media_ids: list[str] = []
                tracked_ids: list[str] = []
                if connection_ids:
                    media_ids = list(
                        session.scalars(
                            select(InstagramMediaRecord.id).where(InstagramMediaRecord.account_id.in_(connection_ids))
                        )
                    )
                if media_ids:
                    tracked_ids = list(
                        session.scalars(select(TrackedPostRecord.id).where(TrackedPostRecord.media_id.in_(media_ids)))
                    )

                # These references are explicit to support every configured
                # database and to remove account-level caches that do not have
                # a tracked-post foreign key.
                if tracked_ids:
                    session.execute(
                        delete(InstagramInsightCollectionJobRecord).where(
                            InstagramInsightCollectionJobRecord.tracked_post_id.in_(tracked_ids)
                        )
                    )
                    session.execute(
                        delete(AIGenerationLogRecord).where(AIGenerationLogRecord.tracked_post_id.in_(tracked_ids))
                    )
                    session.execute(
                        delete(InstagramCommentRecord).where(InstagramCommentRecord.tracked_post_id.in_(tracked_ids))
                    )
                if user_ids:
                    session.execute(delete(InsightTextCacheRecord).where(InsightTextCacheRecord.user_id.in_(user_ids)))
                    # OAuth states are Instagram authorization artifacts, not
                    # PostBridge account data, so remove them too.
                    session.execute(delete(OAuthStateRecord).where(OAuthStateRecord.user_id.in_(user_ids)))
                if media_ids:
                    session.execute(
                        delete(InstagramInsightSnapshotRecord).where(
                            InstagramInsightSnapshotRecord.media_id.in_(media_ids)
                        )
                    )
                    session.execute(delete(TrackedPostRecord).where(TrackedPostRecord.media_id.in_(media_ids)))
                    session.execute(delete(InstagramMediaRecord).where(InstagramMediaRecord.id.in_(media_ids)))
                if connection_ids:
                    session.execute(
                        delete(InstagramConnectionRecord).where(InstagramConnectionRecord.id.in_(connection_ids))
                    )

                session.add(
                    InstagramDataDeletionRequestRecord(
                        code=confirmation_code,
                        status="completed",
                        created_at=now,
                        completed_at=now,
                    )
                )

        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

    def get_data_deletion_request(self, code: str) -> InstagramDataDeletionRequest | None:
        try:
            with self._session_factory() as session:
                record = session.get(InstagramDataDeletionRequestRecord, code)
                return self._to_data_deletion_request(record) if record else None
        except Exception:
            raise InstagramRepositoryError("PostBridge database operation failed.") from None

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
            session_synced_at=_as_utc(record.session_synced_at),
            session_sync_error=record.session_sync_error,
            tracking_start_at=_as_utc(record.tracking_start_at),
            status=record.status,
            connected_at=_as_utc(record.created_at),
            last_synced_at=_as_utc(record.updated_at),
            last_error=None,
        )

    @staticmethod
    def _to_data_deletion_request(
        record: InstagramDataDeletionRequestRecord,
    ) -> InstagramDataDeletionRequest:
        return InstagramDataDeletionRequest(
            code=record.code,
            status=record.status,
            created_at=_as_utc(record.created_at),
            completed_at=_as_utc(record.completed_at),
        )


class LocalDevelopmentInstagramRepository:
    """Development-only JSON/sidecar fallback used when no DB URL is configured."""

    def __init__(self):
        self._states: dict[str, tuple[str, datetime, datetime | None]] = {}
        self._state_lock = Lock()

    def create_oauth_state(self, nonce: str, user_id: str, expires_at: datetime) -> None:
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

    def list_connections(self) -> list[InstagramAccount]:
        return list(json_store.load_store().instagram_accounts)

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
            store.instagram_accounts = [item for item in store.instagram_accounts if item.user_id != user_id]

        json_store.update_store(mutate)
        token_store.delete_encrypted_token(existing.id)
        return True

    def deauthorize_instagram_user(self, instagram_user_id: str) -> int:
        accounts = json_store.mark_instagram_connections_disconnected(instagram_user_id)
        for account in accounts:
            token_store.delete_encrypted_token(account.id)
        return len(accounts)

    def delete_instagram_data(
        self,
        instagram_user_id: str,
        confirmation_code: str,
        now: datetime,
    ) -> None:
        accounts = [
            item for item in json_store.load_store().instagram_accounts if item.instagram_user_id == instagram_user_id
        ]
        for account in accounts:
            token_store.delete_encrypted_token(account.id)
        user_ids = json_store.delete_instagram_data_for_instagram_user(instagram_user_id)
        json_store.upsert_instagram_data_deletion_request(
            InstagramDataDeletionRequest(
                code=confirmation_code,
                status="completed",
                created_at=now,
                completed_at=now,
            )
        )

        # Text caches are process-local in the development store. They can
        # contain summaries derived from the deleted media/comments.
        if user_ids:
            from backend.storage.content_repository import get_content_repository

            content_repository = get_content_repository()
            for user_id in user_ids:
                content_repository.clear_local_user_cache(user_id)

    def get_data_deletion_request(self, code: str) -> InstagramDataDeletionRequest | None:
        return json_store.get_instagram_data_deletion_request(code)

    def mark_session_sync(self, user_id: str, synced_at: datetime | None, error: str | None) -> InstagramAccount | None:
        existing = self.get_connection(user_id)
        if existing is None:
            return None
        updated = existing.model_copy(
            update={
                "session_synced_at": synced_at,
                "session_sync_error": error,
            }
        )
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
        raise InstagramRepositoryError("PostBridge database configuration is required in production.")
    return _local_repository


def delete_local_user_data(user_id: str) -> None:
    """Clear the JSON store, token sidecar, and process cache used by local development."""
    if os.getenv("POSTBRIDGE_DATABASE_URL") or is_production():
        return

    account = json_store.get_instagram_account(user_id)
    if account is not None:
        # Delete the token first so a failed JSON write can be retried while the
        # account-to-token identifier is still present in the local store.
        token_store.delete_encrypted_token(account.id)
    json_store.delete_user_data(user_id)

    # Imported lazily to avoid coupling the repository modules at import time.
    from backend.storage.content_repository import get_content_repository

    get_content_repository().clear_local_user_cache(user_id)
