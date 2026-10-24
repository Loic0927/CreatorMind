from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import auth
from backend.auth_api import AccountContextRequest, EmailRequest, VerifyCodeRequest, account_context, request_code, save_account_context, verify_code
from backend.storage.database import engine_for_url, session_factory_for_url


@pytest.fixture
def auth_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{(tmp_path / 'auth.db').as_posix()}"
    monkeypatch.setenv("POSTBRIDGE_ENV", "development")
    monkeypatch.setenv("POSTBRIDGE_DATABASE_URL", database_url)
    monkeypatch.setenv("POSTBRIDGE_AUTH_SECRET", "unit-test-auth-secret")
    monkeypatch.delenv("POSTBRIDGE_SMTP_HOST", raising=False)
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()
    yield
    engine_for_url.cache_clear()
    session_factory_for_url.cache_clear()


def test_email_code_creates_a_reusable_cross_client_session(auth_database):
    requested = request_code(EmailRequest(email="Owner@Example.Test"))
    assert requested["sent"] is True
    assert len(requested["development_code"]) == 6

    verified = verify_code(
        VerifyCodeRequest(email="owner@example.test", code=requested["development_code"])
    )
    identity = auth.authenticate_token(verified["access_token"])
    assert identity.email == "owner@example.test"
    assert identity.id == verified["user"]["id"]


def test_login_code_cannot_be_replayed(auth_database):
    requested = request_code(EmailRequest(email="owner@example.test"))
    payload = VerifyCodeRequest(
        email="owner@example.test", code=requested["development_code"]
    )
    verify_code(payload)
    with pytest.raises(Exception):
        verify_code(payload)


def test_failed_login_attempts_are_persisted(auth_database):
    requested = request_code(EmailRequest(email="owner@example.test"))
    incorrect_code = (
        "000000" if requested["development_code"] != "000000" else "999999"
    )
    for _ in range(5):
        with pytest.raises(HTTPException):
            verify_code(
                VerifyCodeRequest(email="owner@example.test", code=incorrect_code)
            )

    with pytest.raises(HTTPException) as locked:
        verify_code(
            VerifyCodeRequest(
                email="owner@example.test", code=requested["development_code"]
            )
        )
    assert locked.value.status_code == 401


def test_account_context_is_persisted_and_scoped_to_the_user(auth_database):
    first_code = request_code(EmailRequest(email="first@example.test"))["development_code"]
    first_session = verify_code(VerifyCodeRequest(email="first@example.test", code=first_code))
    first = auth.authenticate_token(first_session["access_token"])
    second_code = request_code(EmailRequest(email="second@example.test"))["development_code"]
    second_session = verify_code(VerifyCodeRequest(email="second@example.test", code=second_code))
    second = auth.authenticate_token(second_session["access_token"])

    saved = save_account_context(AccountContextRequest(
        account_context="  Practical magic tutorials for beginner creators.  "
    ), first)

    assert saved["account_context"] == "Practical magic tutorials for beginner creators."
    assert account_context(first)["account_context"] == saved["account_context"]
    assert account_context(second)["account_context"] == ""
