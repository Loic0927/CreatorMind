"""Account-scoped persistence for reusable media, drafts, and publications."""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.storage.database import session_factory
from backend.storage.models import MediaAsset, PostDraft, PostPublication
from backend.storage.sql_models import MediaAssetRecord, PostDraftRecord, PostPublicationRecord


class DraftRepositoryError(RuntimeError):
    """Base error whose message is safe to return without database details."""


class DraftNotFoundError(DraftRepositoryError):
    pass


class MediaAssetNotFoundError(DraftRepositoryError):
    pass


class DraftConflictError(DraftRepositoryError):
    pass


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class DraftRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    @classmethod
    def from_engine(cls, engine: Engine) -> "DraftRepository":
        return cls(sessionmaker(bind=engine, expire_on_commit=False))

    def create_media_asset(
        self,
        user_id: str,
        *,
        storage_provider: str,
        object_name: str,
        original_filename: str,
        mime_type: str,
        byte_size: int,
        checksum_sha256: str,
        status: str = "uploaded",
    ) -> MediaAsset:
        now = datetime.now(timezone.utc)
        record = MediaAssetRecord(
            id=str(uuid4()), user_id=user_id, storage_provider=storage_provider,
            object_name=object_name, original_filename=original_filename,
            mime_type=mime_type, byte_size=byte_size, checksum_sha256=checksum_sha256,
            status=status, created_at=now, updated_at=now,
        )
        try:
            with self._factory.begin() as session:
                session.add(record)
                session.flush()
            return self._media(record)
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def get_media_asset(self, user_id: str, asset_id: str) -> MediaAsset | None:
        try:
            with self._factory() as session:
                record = session.scalar(select(MediaAssetRecord).where(
                    MediaAssetRecord.id == asset_id, MediaAssetRecord.user_id == user_id,
                ))
            return self._media(record) if record else None
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def create_draft(
        self,
        user_id: str,
        *,
        media_asset_id: str | None,
        target_platforms: list[str],
        content_brief: str,
        goal: str,
        caption: str,
        hashtags: list[str],
    ) -> PostDraft:
        now = datetime.now(timezone.utc)
        try:
            with self._factory.begin() as session:
                self._require_owned_media(session, user_id, media_asset_id)
                record = PostDraftRecord(
                    id=str(uuid4()), user_id=user_id, media_asset_id=media_asset_id,
                    target_platforms=target_platforms, content_brief=content_brief,
                    goal=goal, caption=caption, hashtags=hashtags, status="draft",
                    created_at=now, updated_at=now,
                )
                session.add(record)
                session.flush()
                return self._draft(record)
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def list_drafts(self, user_id: str) -> list[PostDraft]:
        try:
            with self._factory() as session:
                records = session.scalars(
                    select(PostDraftRecord)
                    .where(PostDraftRecord.user_id == user_id)
                    .order_by(PostDraftRecord.updated_at.desc())
                ).all()
            return [self._draft(item) for item in records]
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def get_draft(self, user_id: str, draft_id: str) -> PostDraft | None:
        try:
            with self._factory() as session:
                record = self._owned_draft(session, user_id, draft_id)
            return self._draft(record) if record else None
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def update_draft(self, user_id: str, draft_id: str, changes: dict[str, Any]) -> PostDraft:
        allowed = {"media_asset_id", "target_platforms", "content_brief", "goal", "caption", "hashtags"}
        if not changes or set(changes) - allowed:
            raise DraftConflictError("The draft update is invalid.")
        try:
            with self._factory.begin() as session:
                record = self._owned_draft(session, user_id, draft_id)
                if record is None:
                    raise DraftNotFoundError("Draft not found.")
                if record.status not in {"draft", "failed"}:
                    raise DraftConflictError("Only an unpublished draft can be edited.")
                if "media_asset_id" in changes:
                    self._require_owned_media(session, user_id, changes["media_asset_id"])
                for key, value in changes.items():
                    setattr(record, key, value)
                record.updated_at = datetime.now(timezone.utc)
                session.flush()
                return self._draft(record)
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def delete_draft(self, user_id: str, draft_id: str) -> bool:
        try:
            with self._factory.begin() as session:
                record = self._owned_draft(session, user_id, draft_id)
                if record is None:
                    return False
                if record.status not in {"draft", "failed"}:
                    raise DraftConflictError("A publishing or published draft cannot be deleted.")
                publication = session.scalar(select(PostPublicationRecord.id).where(
                    PostPublicationRecord.user_id == user_id,
                    PostPublicationRecord.draft_id == draft_id,
                ).limit(1))
                if publication is not None:
                    raise DraftConflictError("A draft with publication history cannot be deleted.")
                session.execute(delete(PostDraftRecord).where(PostDraftRecord.id == draft_id))
                return True
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def transition_draft_status(self, user_id: str, draft_id: str, status: str) -> PostDraft:
        transitions = {
            "draft": {"publishing"},
            "publishing": {"published", "failed"},
            "failed": {"publishing"},
            "published": set(),
        }
        try:
            with self._factory.begin() as session:
                record = session.scalar(select(PostDraftRecord).where(
                    PostDraftRecord.id == draft_id, PostDraftRecord.user_id == user_id,
                ).with_for_update())
                if record is None:
                    raise DraftNotFoundError("Draft not found.")
                if status not in transitions.get(record.status, set()):
                    raise DraftConflictError(f"A {record.status} draft cannot transition to {status}.")
                record.status = status
                record.updated_at = datetime.now(timezone.utc)
                session.flush()
                return self._draft(record)
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def create_publication(
        self, user_id: str, draft_id: str, platform: str, idempotency_key: str
    ) -> tuple[PostPublication, bool]:
        """Return the existing attempt for a repeated key, otherwise create one."""
        now = datetime.now(timezone.utc)
        try:
            with self._factory.begin() as session:
                draft = self._owned_draft(session, user_id, draft_id)
                if draft is None:
                    raise DraftNotFoundError("Draft not found.")
                if platform not in (draft.target_platforms or []):
                    raise DraftConflictError("The platform is not selected on this draft.")
                existing = session.scalar(select(PostPublicationRecord).where(
                    PostPublicationRecord.user_id == user_id,
                    PostPublicationRecord.platform == platform,
                    PostPublicationRecord.idempotency_key == idempotency_key,
                ))
                if existing:
                    if existing.draft_id != draft_id:
                        raise DraftConflictError("The idempotency key belongs to another draft.")
                    return self._publication(existing), False
                record = PostPublicationRecord(
                    id=str(uuid4()), user_id=user_id, draft_id=draft_id, platform=platform,
                    provider_media_id=None, provider_post_id=None,
                    idempotency_key=idempotency_key, status="pending", error_code=None,
                    error_message=None, created_at=now, updated_at=now, published_at=None,
                )
                session.add(record)
                session.flush()
                return self._publication(record), True
        except IntegrityError:
            try:
                with self._factory() as session:
                    existing = session.scalar(select(PostPublicationRecord).where(
                        PostPublicationRecord.user_id == user_id,
                        PostPublicationRecord.platform == platform,
                        PostPublicationRecord.idempotency_key == idempotency_key,
                    ))
                if existing and existing.draft_id == draft_id:
                    return self._publication(existing), False
                raise DraftConflictError("The idempotency key belongs to another draft.")
            except DraftRepositoryError:
                raise
            except Exception as exc:
                raise DraftRepositoryError("Draft storage is unavailable.") from exc
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def list_publications(self, user_id: str, draft_id: str) -> list[PostPublication]:
        try:
            with self._factory() as session:
                if self._owned_draft(session, user_id, draft_id) is None:
                    raise DraftNotFoundError("Draft not found.")
                records = session.scalars(select(PostPublicationRecord).where(
                    PostPublicationRecord.user_id == user_id,
                    PostPublicationRecord.draft_id == draft_id,
                ).order_by(PostPublicationRecord.created_at.desc())).all()
            return [self._publication(item) for item in records]
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    def transition_publication(
        self,
        user_id: str,
        publication_id: str,
        status: str,
        *,
        provider_media_id: str | None = None,
        provider_post_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PostPublication:
        transitions = {
            "pending": {"validating", "failed"},
            "validating": {"publishing", "failed"},
            "publishing": {"published", "failed"},
            "failed": {"pending"},
            "published": set(),
        }
        try:
            with self._factory.begin() as session:
                record = session.scalar(select(PostPublicationRecord).where(
                    PostPublicationRecord.id == publication_id,
                    PostPublicationRecord.user_id == user_id,
                ).with_for_update())
                if record is None:
                    raise DraftNotFoundError("Publication not found.")
                if status not in transitions.get(record.status, set()):
                    raise DraftConflictError(
                        f"A {record.status} publication cannot transition to {status}."
                    )
                if status == "published" and not provider_post_id:
                    raise DraftConflictError("A published attempt requires a provider post ID.")
                record.status = status
                record.provider_media_id = provider_media_id or record.provider_media_id
                record.provider_post_id = provider_post_id or record.provider_post_id
                record.error_code = error_code if status == "failed" else None
                record.error_message = error_message if status == "failed" else None
                record.updated_at = datetime.now(timezone.utc)
                record.published_at = record.updated_at if status == "published" else None
                session.flush()
                return self._publication(record)
        except DraftRepositoryError:
            raise
        except Exception as exc:
            raise DraftRepositoryError("Draft storage is unavailable.") from exc

    @staticmethod
    def _owned_draft(session: Session, user_id: str, draft_id: str) -> PostDraftRecord | None:
        return session.scalar(select(PostDraftRecord).where(
            PostDraftRecord.id == draft_id, PostDraftRecord.user_id == user_id,
        ))

    @staticmethod
    def _require_owned_media(session: Session, user_id: str, asset_id: str | None) -> None:
        if asset_id is None:
            return
        owned = session.scalar(select(MediaAssetRecord.id).where(
            MediaAssetRecord.id == asset_id, MediaAssetRecord.user_id == user_id,
            MediaAssetRecord.status.in_(("uploaded", "ready")),
        ))
        if owned is None:
            raise MediaAssetNotFoundError("Media asset not found.")

    @staticmethod
    def _media(item: MediaAssetRecord) -> MediaAsset:
        return MediaAsset(
            id=item.id, user_id=item.user_id, storage_provider=item.storage_provider,
            object_name=item.object_name, original_filename=item.original_filename,
            mime_type=item.mime_type, byte_size=item.byte_size,
            checksum_sha256=item.checksum_sha256, status=item.status,
            created_at=_utc(item.created_at), updated_at=_utc(item.updated_at),
        )

    @staticmethod
    def _draft(item: PostDraftRecord) -> PostDraft:
        return PostDraft(
            id=item.id, user_id=item.user_id, media_asset_id=item.media_asset_id,
            target_platforms=item.target_platforms or [], content_brief=item.content_brief,
            goal=item.goal, caption=item.caption, hashtags=item.hashtags or [], status=item.status,
            created_at=_utc(item.created_at), updated_at=_utc(item.updated_at),
        )

    @staticmethod
    def _publication(item: PostPublicationRecord) -> PostPublication:
        return PostPublication(
            id=item.id, user_id=item.user_id, draft_id=item.draft_id, platform=item.platform,
            provider_media_id=item.provider_media_id, provider_post_id=item.provider_post_id,
            idempotency_key=item.idempotency_key, status=item.status,
            error_code=item.error_code, error_message=item.error_message,
            created_at=_utc(item.created_at), updated_at=_utc(item.updated_at),
            published_at=_utc(item.published_at),
        )


@lru_cache(maxsize=1)
def get_draft_repository() -> DraftRepository:
    return DraftRepository(session_factory())
