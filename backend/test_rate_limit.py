from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.rate_limit import enforce_rate_limit_in_session
from backend.storage.database import engine_for_url, session_factory_for_url


@pytest.fixture
def rate_limit_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{(tmp_path / 'rate-limit.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    engine_for_url(database_url)
    factory = session_factory_for_url(database_url)
    yield factory
    engine_for_url(database_url).dispose()
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()


def test_rate_limit_state_is_shared_between_database_sessions(rate_limit_database):
    with rate_limit_database.begin() as first_session:
        enforce_rate_limit_in_session(first_session, "caption:user-1", 1)

    with rate_limit_database.begin() as second_session:
        with pytest.raises(HTTPException) as rejected:
            enforce_rate_limit_in_session(second_session, "caption:user-1", 1)

    assert rejected.value.status_code == 429
    assert rejected.value.detail == {
        "code": "rate_limited",
        "message": "Too many requests. Please try again later.",
    }
