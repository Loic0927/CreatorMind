"""Durable TikTok OAuth and connection persistence."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.storage.database import session_factory
from backend.storage.models import TikTokConnection
from backend.storage.sql_models import TikTokConnectionRecord, TikTokOAuthStateRecord, TikTokTrackedPostRecord


class TikTokRepositoryError(RuntimeError):
    """Safe persistence error that never contains credentials."""


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class TikTokRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def create_oauth_state(
        self,
        nonce: str,
        user_id: str,
        client: str,
        expires_at: datetime,
    ) -> None:
        try:
            with self._factory.begin() as session:
                session.add(
                    TikTokOAuthStateRecord(
                        nonce=nonce,
                        user_id=user_id,
                        client=client,
                        expires_at=expires_at,
                        consumed_at=None,
                        created_at=datetime.now(UTC),
                    )
                )
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def consume_oauth_state(self, nonce: str, now: datetime) -> tuple[str, str] | None:
        try:
            with self._factory.begin() as session:
                row = session.execute(
                    update(TikTokOAuthStateRecord)
                    .where(
                        TikTokOAuthStateRecord.nonce == nonce,
                        TikTokOAuthStateRecord.consumed_at.is_(None),
                        TikTokOAuthStateRecord.expires_at >= now,
                    )
                    .values(consumed_at=now)
                    .returning(TikTokOAuthStateRecord.user_id, TikTokOAuthStateRecord.client)
                ).one_or_none()
                return (str(row.user_id), str(row.client)) if row else None
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def get_connection(self, user_id: str) -> TikTokConnection | None:
        try:
            with self._factory() as session:
                record = session.scalar(select(TikTokConnectionRecord).where(TikTokConnectionRecord.user_id == user_id))
                return self._connection(record) if record else None
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def get_encrypted_tokens(self, connection_id: str) -> tuple[str, str] | None:
        try:
            with self._factory() as session:
                row = session.execute(
                    select(
                        TikTokConnectionRecord.encrypted_access_token,
                        TikTokConnectionRecord.encrypted_refresh_token,
                    ).where(TikTokConnectionRecord.id == connection_id)
                ).one_or_none()
                return (str(row[0]), str(row[1])) if row else None
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def upsert_connection(
        self,
        connection: TikTokConnection,
        *,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
    ) -> TikTokConnection:
        try:
            with self._factory.begin() as session:
                record = session.scalar(
                    select(TikTokConnectionRecord)
                    .where(TikTokConnectionRecord.user_id == connection.user_id)
                    .with_for_update()
                )
                now = datetime.now(UTC)
                if record is None:
                    record = TikTokConnectionRecord(
                        id=connection.id,
                        user_id=connection.user_id,
                        open_id=connection.open_id,
                        union_id=connection.union_id,
                        display_name=connection.display_name,
                        avatar_url=connection.avatar_url,
                        encrypted_access_token=encrypted_access_token,
                        encrypted_refresh_token=encrypted_refresh_token,
                        access_token_expires_at=connection.access_token_expires_at,
                        refresh_token_expires_at=connection.refresh_token_expires_at,
                        scopes=list(connection.scopes),
                        status=connection.status,
                        created_at=connection.connected_at,
                        updated_at=now,
                    )
                    session.add(record)
                else:
                    record.open_id = connection.open_id
                    record.union_id = connection.union_id
                    record.display_name = connection.display_name
                    record.avatar_url = connection.avatar_url
                    record.encrypted_access_token = encrypted_access_token
                    record.encrypted_refresh_token = encrypted_refresh_token
                    record.access_token_expires_at = connection.access_token_expires_at
                    record.refresh_token_expires_at = connection.refresh_token_expires_at
                    record.scopes = list(connection.scopes)
                    record.status = connection.status
                    record.updated_at = now
                session.flush()
                return self._connection(record)
        except TikTokRepositoryError:
            raise
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def update_tokens(
        self,
        user_id: str,
        *,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        access_token_expires_at: datetime | None,
        refresh_token_expires_at: datetime | None,
        scopes: list[str],
    ) -> TikTokConnection | None:
        try:
            with self._factory.begin() as session:
                record = session.scalar(
                    select(TikTokConnectionRecord).where(TikTokConnectionRecord.user_id == user_id).with_for_update()
                )
                if record is None:
                    return None
                record.encrypted_access_token = encrypted_access_token
                record.encrypted_refresh_token = encrypted_refresh_token
                record.access_token_expires_at = access_token_expires_at
                record.refresh_token_expires_at = refresh_token_expires_at
                record.scopes = list(scopes)
                record.status = "connected"
                record.updated_at = datetime.now(UTC)
                session.flush()
                return self._connection(record)
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def mark_reconnect_required(self, user_id: str) -> None:
        try:
            with self._factory.begin() as session:
                session.execute(
                    update(TikTokConnectionRecord)
                    .where(TikTokConnectionRecord.user_id == user_id)
                    .values(status="reconnect_required", updated_at=datetime.now(UTC))
                )
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def disconnect(self, user_id: str) -> bool:
        try:
            with self._factory.begin() as session:
                result = session.execute(
                    update(TikTokConnectionRecord)
                    .where(TikTokConnectionRecord.user_id == user_id)
                    .values(
                        encrypted_access_token="",
                        encrypted_refresh_token="",
                        access_token_expires_at=None,
                        refresh_token_expires_at=None,
                        status="disconnected",
                        updated_at=datetime.now(UTC),
                    )
                )
                return bool(result.rowcount)
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    def tracked_posts(self, user_id: str) -> list[dict]:
        try:
            with self._factory() as session:
                rows = session.scalars(
                    select(TikTokTrackedPostRecord)
                    .where(TikTokTrackedPostRecord.user_id == user_id)
                    .order_by(TikTokTrackedPostRecord.published_at.desc(), TikTokTrackedPostRecord.created_at.desc())
                ).all()
                return [self._tracked(row) for row in rows]
        except Exception:
            raise TikTokRepositoryError("TikTok post storage is unavailable.") from None

    def track_post(self, user_id: str, item: dict) -> dict:
        try:
            with self._factory.begin() as session:
                row = session.scalar(
                    select(TikTokTrackedPostRecord).where(
                        TikTokTrackedPostRecord.user_id == user_id,
                        TikTokTrackedPostRecord.video_id == str(item["id"]),
                    )
                )
                if row is None:
                    row = TikTokTrackedPostRecord(
                        id=str(uuid4()), user_id=user_id, video_id=str(item["id"]),
                        caption=str(item.get("video_description") or item.get("title") or "TikTok post"),
                        thumbnail_url=item.get("cover_image_url"), permalink=item.get("share_url"),
                        published_at=datetime.fromtimestamp(int(item["create_time"]), UTC) if item.get("create_time") else None,
                        created_at=datetime.now(UTC),
                    )
                    session.add(row)
                    session.flush()
                return self._tracked(row)
        except Exception:
            raise TikTokRepositoryError("TikTok post storage is unavailable.") from None

    def get_tracked_post(self, user_id: str, tracked_id: str) -> dict | None:
        try:
            with self._factory() as session:
                row = session.scalar(select(TikTokTrackedPostRecord).where(TikTokTrackedPostRecord.user_id == user_id, TikTokTrackedPostRecord.id == tracked_id))
                return self._tracked(row) if row else None
        except Exception:
            raise TikTokRepositoryError("TikTok post storage is unavailable.") from None

    @staticmethod
    def _tracked(row: TikTokTrackedPostRecord) -> dict:
        return {"id": row.id, "video_id": row.video_id, "caption": row.caption, "thumbnail_url": row.thumbnail_url, "permalink": row.permalink, "published_at": _utc(row.published_at), "created_at": _utc(row.created_at)}

    def delete_user_data(self, user_id: str) -> None:
        try:
            with self._factory.begin() as session:
                session.execute(delete(TikTokOAuthStateRecord).where(TikTokOAuthStateRecord.user_id == user_id))
                session.execute(delete(TikTokConnectionRecord).where(TikTokConnectionRecord.user_id == user_id))
        except Exception:
            raise TikTokRepositoryError("TikTok connection storage is unavailable.") from None

    @staticmethod
    def _connection(record: TikTokConnectionRecord) -> TikTokConnection:
        return TikTokConnection(
            id=record.id,
            user_id=record.user_id,
            open_id=record.open_id,
            union_id=record.union_id,
            display_name=record.display_name,
            avatar_url=record.avatar_url,
            encrypted_access_token="",
            encrypted_refresh_token="",
            access_token_expires_at=_utc(record.access_token_expires_at),
            refresh_token_expires_at=_utc(record.refresh_token_expires_at),
            scopes=list(record.scopes or []),
            status=record.status,
            connected_at=_utc(record.created_at),
            updated_at=_utc(record.updated_at),
        )


def get_tiktok_repository() -> TikTokRepository:
    return TikTokRepository(session_factory())
