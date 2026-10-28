"""Development-only JSON persistence.

This store is retained for local MVP development. It is not suitable for Cloud Run,
multi-instance deployments, or production credential storage.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from backend.storage.models import (
    AnalyticsSnapshot,
    ExternalInsightRecord,
    InstagramAccount,
    InstagramComment,
    InstagramInsightSnapshot,
    InstagramMedia,
    Post,
    PredictionHistory,
    SocialConnection,
    StoreData,
    TrackedPost,
    TrackedPostAnalysis,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_PATH = DATA_DIR / "store.json"
_LOCK = Lock()


def _ensure_store_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text(StoreData().model_dump_json(indent=2), encoding="utf-8")


def load_store() -> StoreData:
    _ensure_store_file()
    with _LOCK:
        raw = STORE_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return StoreData()
    return StoreData.model_validate(json.loads(raw))


def update_store(mutator):
    store = load_store()
    result = mutator(store)
    save_store(store)
    return result


def get_instagram_account(user_id: str) -> InstagramAccount | None:
    return next((item for item in load_store().instagram_accounts if item.user_id == user_id), None)


def upsert_instagram_account(account: InstagramAccount) -> InstagramAccount:
    def mutate(store: StoreData):
        for index, existing in enumerate(store.instagram_accounts):
            if existing.user_id == account.user_id or existing.instagram_user_id == account.instagram_user_id:
                store.instagram_accounts[index] = account
                return account
        store.instagram_accounts.append(account)
        return account
    return update_store(mutate)


def upsert_instagram_media(items: list[InstagramMedia]) -> list[InstagramMedia]:
    def mutate(store: StoreData):
        by_external_id = {item.instagram_media_id: index for index, item in enumerate(store.instagram_media)}
        for item in items:
            index = by_external_id.get(item.instagram_media_id)
            if index is None:
                by_external_id[item.instagram_media_id] = len(store.instagram_media)
                store.instagram_media.append(item)
            else:
                store.instagram_media[index] = item
        return items
    return update_store(mutate)


def get_instagram_media(account_id: str) -> list[InstagramMedia]:
    return [item for item in load_store().instagram_media if item.account_id == account_id]


def create_tracked_post(user_id: str, media_id: str) -> TrackedPost:
    def mutate(store: StoreData):
        existing = next((item for item in store.tracked_posts if item.user_id == user_id and item.media_id == media_id and item.is_active), None)
        if existing:
            return existing
        tracked = TrackedPost(id=str(uuid4()), user_id=user_id, media_id=media_id, started_at=datetime.now(timezone.utc))
        store.tracked_posts.append(tracked)
        return tracked
    return update_store(mutate)


def get_tracked_posts(user_id: str, active_only: bool = True) -> list[TrackedPost]:
    return [item for item in load_store().tracked_posts if item.user_id == user_id and (item.is_active or not active_only)]


def stop_tracked_post(user_id: str, tracked_id: str) -> bool:
    def mutate(store: StoreData):
        item = next((item for item in store.tracked_posts if item.id == tracked_id and item.user_id == user_id), None)
        if not item:
            return False
        item.is_active = False
        item.stopped_at = datetime.now(timezone.utc)
        return True
    return update_store(mutate)


def set_tracked_post_exclusion(user_id: str, tracked_id: str, excluded: bool) -> TrackedPost | None:
    def mutate(store: StoreData):
        item = next((item for item in store.tracked_posts if item.id == tracked_id and item.user_id == user_id), None)
        if item is not None:
            item.exclude_from_comparisons = excluded
        return item
    return update_store(mutate)


def append_instagram_snapshot(snapshot: InstagramInsightSnapshot) -> InstagramInsightSnapshot:
    return update_store(lambda store: (store.instagram_insight_snapshots.append(snapshot), snapshot)[1])


def append_tracked_post_analysis(analysis: TrackedPostAnalysis) -> TrackedPostAnalysis:
    return update_store(lambda store: (store.tracked_post_analyses.append(analysis), analysis)[1])


def get_tracked_post_analyses(user_id: str, tracked_post_id: str) -> list[TrackedPostAnalysis]:
    return [
        item
        for item in load_store().tracked_post_analyses
        if item.user_id == user_id and item.tracked_post_id == tracked_post_id
    ]


def upsert_instagram_comments(user_id: str, tracked_post_id: str, items: list[InstagramComment]) -> list[InstagramComment]:
    def mutate(store: StoreData):
        by_provider = {(item.user_id, item.provider_id): index for index, item in enumerate(store.instagram_comments)}
        for item in items:
            if item.user_id != user_id or item.tracked_post_id != tracked_post_id:
                continue
            index = by_provider.get((user_id, item.provider_id))
            if index is None:
                by_provider[(user_id, item.provider_id)] = len(store.instagram_comments)
                store.instagram_comments.append(item)
            else:
                store.instagram_comments[index] = item
        return items
    return update_store(mutate)


def get_instagram_comments(user_id: str, tracked_post_id: str | None = None) -> list[InstagramComment]:
    items = [item for item in load_store().instagram_comments if item.user_id == user_id and (tracked_post_id is None or item.tracked_post_id == tracked_post_id)]
    return sorted(items, key=lambda item: (item.like_count, item.timestamp), reverse=True)


def append_external_insight(item: ExternalInsightRecord) -> ExternalInsightRecord:
    return update_store(lambda store: (store.external_insight_records.append(item), item)[1])


def get_external_insights(user_id: str, tracked_post_id: str | None = None) -> list[ExternalInsightRecord]:
    items = [item for item in load_store().external_insight_records if item.user_id == user_id and (tracked_post_id is None or item.tracked_post_id == tracked_post_id)]
    return sorted(items, key=lambda item: item.created_at, reverse=True)


def save_store(store: StoreData) -> None:
    _ensure_store_file()
    with _LOCK:
        STORE_PATH.write_text(store.model_dump_json(indent=2), encoding="utf-8")


def append_prediction_history(input_payload: dict, output_payload: dict) -> PredictionHistory:
    store = load_store()
    entry = PredictionHistory(
        id=str(uuid4()),
        input_payload=input_payload,
        output_payload=output_payload,
        created_at=datetime.utcnow(),
    )
    store.prediction_history.append(entry)
    save_store(store)
    return entry


def get_prediction_history() -> list[PredictionHistory]:
    return load_store().prediction_history


def get_social_connections() -> list[SocialConnection]:
    return load_store().social_connections


def upsert_social_connection(connection: SocialConnection) -> SocialConnection:
    store = load_store()

    for index, existing in enumerate(store.social_connections):
        if existing.platform == connection.platform and existing.user_id == connection.user_id:
            store.social_connections[index] = connection
            save_store(store)
            return connection

    store.social_connections.append(connection)
    save_store(store)
    return connection


def get_social_connection(platform: str, user_id: str) -> SocialConnection | None:
    for connection in load_store().social_connections:
        if connection.platform == platform and connection.user_id == user_id:
            return connection
    return None


def delete_social_connection(platform: str, user_id: str) -> bool:
    store = load_store()
    remaining = [
        connection
        for connection in store.social_connections
        if not (connection.platform == platform and connection.user_id == user_id)
    ]
    if len(remaining) == len(store.social_connections):
        return False
    store.social_connections = remaining
    save_store(store)
    return True


def get_posts() -> list[Post]:
    return load_store().posts


def get_analytics_snapshots() -> list[AnalyticsSnapshot]:
    return load_store().analytics_snapshots
