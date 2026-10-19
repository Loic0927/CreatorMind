import os
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import select

from backend.storage import json_store
from backend.storage.database import session_factory
from backend.storage.models import InstagramInsightSnapshot, InstagramMedia, PredictionHistory, TrackedPost
from backend.storage.sql_models import InstagramInsightSnapshotRecord, InstagramMediaRecord, PredictionHistoryRecord, TrackedPostRecord


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class ContentRepository:
    @property
    def persistent(self) -> bool:
        return bool(os.getenv("POSTBRIDGE_DATABASE_URL"))

    def append_prediction(self, user_id: str, input_payload: dict, output_payload: dict) -> PredictionHistory:
        if not self.persistent:
            return json_store.append_prediction_history(input_payload, output_payload)
        item = PredictionHistory(id=str(uuid4()), created_at=datetime.now(timezone.utc), input_payload=input_payload, output_payload=output_payload)
        factory = session_factory()
        with factory.begin() as session:
            session.add(PredictionHistoryRecord(id=item.id, user_id=user_id, input_payload=input_payload, output_payload=output_payload, created_at=item.created_at))
        return item

    def predictions(self, user_id: str) -> list[PredictionHistory]:
        if not self.persistent:
            return json_store.get_prediction_history()
        factory = session_factory()
        with factory() as session:
            records = session.scalars(select(PredictionHistoryRecord).where(PredictionHistoryRecord.user_id == user_id).order_by(PredictionHistoryRecord.created_at.desc())).all()
        return [PredictionHistory(id=item.id, created_at=_utc(item.created_at), input_payload=item.input_payload, output_payload=item.output_payload) for item in records]

    def upsert_media(self, items: list[InstagramMedia]) -> list[InstagramMedia]:
        if not self.persistent:
            return json_store.upsert_instagram_media(items)
        factory = session_factory()
        with factory.begin() as session:
            for item in items:
                record = session.get(InstagramMediaRecord, item.id)
                values = item.model_dump()
                if record is None:
                    session.add(InstagramMediaRecord(**values))
                else:
                    for key, value in values.items():
                        setattr(record, key, value)
        return items

    def media_for_account(self, account_id: str) -> list[InstagramMedia]:
        if not self.persistent:
            return json_store.get_instagram_media(account_id)
        factory = session_factory()
        with factory() as session:
            records = session.scalars(select(InstagramMediaRecord).where(InstagramMediaRecord.account_id == account_id)).all()
        return [self._media(item) for item in records]

    def create_tracked(self, user_id: str, media_id: str) -> TrackedPost:
        if not self.persistent:
            return json_store.create_tracked_post(user_id, media_id)
        factory = session_factory()
        with factory.begin() as session:
            record = session.scalar(select(TrackedPostRecord).where(TrackedPostRecord.user_id == user_id, TrackedPostRecord.media_id == media_id, TrackedPostRecord.is_active.is_(True)))
            if record is None:
                record = TrackedPostRecord(id=str(uuid4()), user_id=user_id, media_id=media_id, is_active=True, started_at=datetime.now(timezone.utc), stopped_at=None)
                session.add(record)
                session.flush()
            return self._tracked(record)

    def tracked(self, user_id: str, active_only: bool = True) -> list[TrackedPost]:
        if not self.persistent:
            return json_store.get_tracked_posts(user_id, active_only)
        statement = select(TrackedPostRecord).where(TrackedPostRecord.user_id == user_id)
        if active_only:
            statement = statement.where(TrackedPostRecord.is_active.is_(True))
        factory = session_factory()
        with factory() as session:
            return [self._tracked(item) for item in session.scalars(statement).all()]

    def stop_tracked(self, user_id: str, tracked_id: str) -> bool:
        if not self.persistent:
            return json_store.stop_tracked_post(user_id, tracked_id)
        factory = session_factory()
        with factory.begin() as session:
            record = session.scalar(select(TrackedPostRecord).where(TrackedPostRecord.id == tracked_id, TrackedPostRecord.user_id == user_id))
            if record is None:
                return False
            record.is_active = False
            record.stopped_at = datetime.now(timezone.utc)
            return True

    def stop_all_tracked(self, user_id: str) -> None:
        for item in self.tracked(user_id):
            self.stop_tracked(user_id, item.id)

    def snapshots(self, media_ids: list[str] | None = None) -> list[InstagramInsightSnapshot]:
        if not self.persistent:
            items = json_store.load_store().instagram_insight_snapshots
            return [item for item in items if media_ids is None or item.media_id in media_ids]
        statement = select(InstagramInsightSnapshotRecord)
        if media_ids is not None:
            if not media_ids:
                return []
            statement = statement.where(InstagramInsightSnapshotRecord.media_id.in_(media_ids))
        factory = session_factory()
        with factory() as session:
            records = session.scalars(statement).all()
        return [self._snapshot(item) for item in records]

    def append_snapshot(self, item: InstagramInsightSnapshot) -> InstagramInsightSnapshot:
        if not self.persistent:
            return json_store.append_instagram_snapshot(item)
        factory = session_factory()
        with factory.begin() as session:
            session.add(InstagramInsightSnapshotRecord(**item.model_dump()))
        return item

    @staticmethod
    def _media(item: InstagramMediaRecord) -> InstagramMedia:
        return InstagramMedia(id=item.id, account_id=item.account_id, instagram_media_id=item.instagram_media_id, media_type=item.media_type, media_url=item.media_url, thumbnail_url=item.thumbnail_url, permalink=item.permalink, caption=item.caption, published_at=_utc(item.published_at), last_synced_at=_utc(item.last_synced_at))

    @staticmethod
    def _tracked(item: TrackedPostRecord) -> TrackedPost:
        return TrackedPost(id=item.id, user_id=item.user_id, media_id=item.media_id, is_active=item.is_active, started_at=_utc(item.started_at), stopped_at=_utc(item.stopped_at) if item.stopped_at else None)

    @staticmethod
    def _snapshot(item: InstagramInsightSnapshotRecord) -> InstagramInsightSnapshot:
        return InstagramInsightSnapshot(id=item.id, media_id=item.media_id, captured_at=_utc(item.captured_at), likes=item.likes, comments=item.comments, saves=item.saves, shares=item.shares, reach=item.reach, views=item.views, engagement_rate=item.engagement_rate, raw_metrics=item.raw_metrics or {})


@lru_cache(maxsize=1)
def get_content_repository() -> ContentRepository:
    return ContentRepository()
