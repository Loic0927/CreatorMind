"""Development-only encrypted token sidecar.

The file is gitignored and intentionally separate from the tracked CreatorMind JSON
store. Replace this module with a production secrets/database implementation before
deploying PostBridge.
"""

import json
from pathlib import Path
from threading import Lock


TOKEN_STORE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "postbridge_tokens.local.json"
)
_LOCK = Lock()


def _load() -> dict[str, str]:
    if not TOKEN_STORE_PATH.exists():
        return {}
    raw = TOKEN_STORE_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _save(payload: dict[str, str]) -> None:
    TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_encrypted_token(account_id: str, encrypted_token: str) -> None:
    with _LOCK:
        payload = _load()
        payload[account_id] = encrypted_token
        _save(payload)


def get_encrypted_token(account_id: str) -> str | None:
    with _LOCK:
        return _load().get(account_id)


def delete_encrypted_token(account_id: str) -> bool:
    with _LOCK:
        payload = _load()
        removed = payload.pop(account_id, None) is not None
        if removed:
            _save(payload)
        return removed
