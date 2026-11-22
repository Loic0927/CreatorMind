"""Archived YouTube connection storage, removed from backend/storage on 2026-11-22.

Kept verbatim for reference. It relied on a ``social_connections: list[SocialConnection]``
field on ``StoreData`` (backend/storage/models.py) and stored OAuth tokens unencrypted in
backend/data/store.json. Replace it with an encrypted PostgreSQL table before restoring
(see archive/youtube/README.md).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from backend.storage.json_store import load_store, save_store


class SocialConnection(BaseModel):
    id: str
    user_id: str
    platform: Literal["Instagram", "YouTube", "TikTok"]
    account_name: str
    status: Literal["connected", "not_connected", "sync_pending"] = "not_connected"
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    external_account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_scope: Optional[str] = None
    token_expires_at: Optional[datetime] = None


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
