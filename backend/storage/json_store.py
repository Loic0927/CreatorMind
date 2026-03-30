from datetime import datetime
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from backend.storage.models import (
    AnalyticsSnapshot,
    Post,
    PredictionHistory,
    SocialConnection,
    StoreData,
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
