import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Header, HTTPException
from sqlalchemy import delete, select

from backend.config import is_production
from backend.storage.database import session_factory
from backend.storage.sql_models import AuthSessionRecord, LoginCodeRecord, UserRecord


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    token_hash: str


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=422, detail={"code": "invalid_email", "message": "Enter a valid email address."})
    return email


def auth_secret() -> str:
    value = os.getenv("POSTBRIDGE_AUTH_SECRET", "").strip()
    if value:
        return value
    if is_production():
        raise RuntimeError("POSTBRIDGE_AUTH_SECRET is required in production.")
    return "postbridge-development-only-auth-secret"


def _code_hash(email: str, code: str) -> str:
    return hmac.new(auth_secret().encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_login_code(email: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)
    factory = session_factory()
    with factory.begin() as session:
        latest = session.scalar(
            select(LoginCodeRecord)
            .where(LoginCodeRecord.email == email)
            .order_by(LoginCodeRecord.created_at.desc())
        )
        if latest is not None:
            created_at = latest.created_at.replace(
                tzinfo=latest.created_at.tzinfo or timezone.utc
            )
            cooldown = max(
                0, int(os.getenv("POSTBRIDGE_LOGIN_CODE_COOLDOWN_SECONDS", "60"))
            )
            if created_at + timedelta(seconds=cooldown) > now:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "code_requested_too_soon",
                        "message": "Wait a moment before requesting another sign-in code.",
                    },
                )
        session.execute(delete(LoginCodeRecord).where(LoginCodeRecord.email == email))
        session.add(LoginCodeRecord(
            id=str(uuid4()), email=email, code_hash=_code_hash(email, code),
            expires_at=now + timedelta(minutes=10), consumed_at=None, attempts=0, created_at=now,
        ))
    return code


def verify_login_code(email: str, code: str) -> tuple[UserRecord, str, datetime]:
    now = datetime.now(timezone.utc)
    factory = session_factory()
    with factory() as session:
        record = session.scalar(
            select(LoginCodeRecord)
            .where(LoginCodeRecord.email == email)
            .order_by(LoginCodeRecord.created_at.desc())
            .with_for_update()
        )
        if record is None or record.consumed_at is not None or record.expires_at.replace(tzinfo=record.expires_at.tzinfo or timezone.utc) < now or record.attempts >= 5:
            raise HTTPException(status_code=401, detail={"code": "invalid_code", "message": "The sign-in code is invalid or expired."})
        record.attempts += 1
        if not hmac.compare_digest(record.code_hash, _code_hash(email, code.strip())):
            # Persist failed attempts before returning the error; otherwise a
            # transaction rollback would let an attacker retry indefinitely.
            session.commit()
            raise HTTPException(status_code=401, detail={"code": "invalid_code", "message": "The sign-in code is invalid or expired."})
        record.consumed_at = now
        user = session.scalar(select(UserRecord).where(UserRecord.email == email))
        if user is None:
            user = UserRecord(id=str(uuid4()), email=email, created_at=now, updated_at=now)
            session.add(user)
            session.flush()
        token = secrets.token_urlsafe(48)
        expires_at = now + timedelta(days=30)
        session.add(AuthSessionRecord(token_hash=_token_hash(token), user_id=user.id, expires_at=expires_at, created_at=now, revoked_at=None))
        session.commit()
        return user, token, expires_at


def authenticate_token(token: str) -> AuthenticatedUser:
    now = datetime.now(timezone.utc)
    token_hash = _token_hash(token)
    factory = session_factory()
    with factory() as session:
        row = session.execute(
            select(AuthSessionRecord, UserRecord)
            .join(UserRecord, UserRecord.id == AuthSessionRecord.user_id)
            .where(AuthSessionRecord.token_hash == token_hash, AuthSessionRecord.revoked_at.is_(None), AuthSessionRecord.expires_at >= now)
        ).one_or_none()
        if row is None:
            raise HTTPException(status_code=401, detail={"code": "invalid_session", "message": "Please sign in again."})
        auth_session, user = row
        return AuthenticatedUser(id=user.id, email=user.email, token_hash=auth_session.token_hash)


def require_user(authorization: str | None = Header(default=None, alias="Authorization")) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Authentication is required."})
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Authentication is required."})
    return authenticate_token(token)


def revoke_session(token_hash: str) -> None:
    factory = session_factory()
    with factory.begin() as session:
        record = session.get(AuthSessionRecord, token_hash)
        if record:
            record.revoked_at = datetime.now(timezone.utc)
