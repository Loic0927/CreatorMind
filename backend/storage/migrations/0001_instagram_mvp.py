"""JSON-store schema migration for the Instagram MVP.

The Pydantic StoreData defaults make this migration safe for existing store.json
files. Loading and saving an old store adds the four Instagram collections and
schema_version without destroying existing CreatorMind data.
"""

from backend.storage.json_store import load_store, save_store


def migrate() -> None:
    store = load_store()
    store.schema_version = max(store.schema_version, 1)
    save_store(store)


if __name__ == "__main__":
    migrate()
