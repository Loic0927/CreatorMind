import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Header, HTTPException
from sqlalchemy import delete, select, update

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
        raise HTTPException(
            status_code=422, detail={"code": "invalid_email", "message": "Enter a valid email address."}
        )
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


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=value.tzinfo or UTC)


def _too_many(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=429, detail={"code": code, "message": message})


def create_login_code(email: str) -> str:
    """Issue a new code. Older codes are invalidated but kept for 24h to enforce the daily cap,
    which bounds guesses to (daily cap x 5 attempts) per email per day."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=24)
    cooldown = max(0, int(os.getenv("POSTBRIDGE_LOGIN_CODE_COOLDOWN_SECONDS", "60")))
    daily_cap = max(1, int(os.getenv("POSTBRIDGE_LOGIN_CODES_PER_DAY", "10")))
    factory = session_factory()
    with factory.begin() as session:
        session.execute(
            delete(LoginCodeRecord).where(LoginCodeRecord.email == email, LoginCodeRecord.created_at < window_start)
        )
        recent = session.scalars(select(LoginCodeRecord.created_at).where(LoginCodeRecord.email == email)).all()
        if recent and _utc(max(recent)) + timedelta(seconds=cooldown) > now:
            raise _too_many("code_requested_too_soon", "Wait a moment before requesting another sign-in code.")
        if len(recent) >= daily_cap:
            raise _too_many("too_many_codes", "Too many sign-in codes were requested. Try again tomorrow.")
        session.execute(
            update(LoginCodeRecord)
            .where(LoginCodeRecord.email == email, LoginCodeRecord.consumed_at.is_(None))
            .values(consumed_at=now)
        )
        session.add(
            LoginCodeRecord(
                id=str(uuid4()),
                email=email,
                code_hash=_code_hash(email, code),
                expires_at=now + timedelta(minutes=10),
                consumed_at=None,
                attempts=0,
                created_at=now,
            )
        )
    return code


def verify_login_code(
    email: str,
    code: str,
    *,
    intent: str = "sign_in",
    ai_processing_consent: bool = False,
    reviewer_code_match: bool | None = None,
) -> tuple[UserRecord, str, datetime]:
    if intent not in {"sign_in", "sign_up"}:
        raise ValueError("intent must be sign_in or sign_up")
    now = datetime.now(UTC)
    factory = session_factory()
    with factory() as session:
        record = session.scalar(
            select(LoginCodeRecord)
            .where(LoginCodeRecord.email == email)
            .order_by(LoginCodeRecord.created_at.desc())
            .with_for_update()
        )
        if record is None or record.consumed_at is not None or _utc(record.expires_at) < now or record.attempts >= 5:
            raise HTTPException(
                status_code=401, detail={"code": "invalid_code", "message": "The sign-in code is invalid or expired."}
            )
        record.attempts += 1
        code_matches = (
            reviewer_code_match
            if reviewer_code_match is not None
            else hmac.compare_digest(record.code_hash, _code_hash(email, code.strip()))
        )
        if not code_matches:
            # Persist failed attempts before returning the error; otherwise a
            # transaction rollback would let an attacker retry indefinitely.
            session.commit()
            raise HTTPException(
                status_code=401, detail={"code": "invalid_code", "message": "The sign-in code is invalid or expired."}
            )
        record.consumed_at = now
        user = session.scalar(select(UserRecord).where(UserRecord.email == email))
        if intent == "sign_in" and user is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "account_not_found", "message": "No account exists for this email. Create one first."},
            )
        if intent == "sign_up" and user is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "account_exists",
                    "message": "An account already exists for this email. Sign in instead.",
                },
            )
        if intent == "sign_up":
            user = UserRecord(
                id=str(uuid4()),
                email=email,
                ai_processing_consented_at=now if ai_processing_consent else None,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.flush()
        token = secrets.token_urlsafe(48)
        expires_at = now + timedelta(days=30)
        session.add(
            AuthSessionRecord(
                token_hash=_token_hash(token), user_id=user.id, expires_at=expires_at, created_at=now, revoked_at=None
            )
        )
        session.commit()
        return user, token, expires_at


def authenticate_token(token: str) -> AuthenticatedUser:
    now = datetime.now(UTC)
    token_hash = _token_hash(token)
    factory = session_factory()
    with factory() as session:
        row = session.execute(
            select(AuthSessionRecord, UserRecord)
            .join(UserRecord, UserRecord.id == AuthSessionRecord.user_id)
            .where(
                AuthSessionRecord.token_hash == token_hash,
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at >= now,
            )
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
            record.revoked_at = datetime.now(UTC)


def get_account_context(user_id: str) -> str:
    factory = session_factory()
    with factory() as session:
        user = session.get(UserRecord, user_id)
        return (user.account_context or "").strip() if user else ""


def update_account_context(user_id: str, value: str) -> str:
    normalized = value.strip()
    factory = session_factory()
    with factory.begin() as session:
        user = session.get(UserRecord, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "Account was not found."})
        user.account_context = normalized
        user.updated_at = datetime.now(UTC)
    return normalized


def ai_processing_consent_at(user_id: str) -> datetime | None:
    """Return the opt-in timestamp without treating an absent account as consent."""
    factory = session_factory()
    with factory() as session:
        user = session.get(UserRecord, user_id)
        return _utc(user.ai_processing_consented_at) if user and user.ai_processing_consented_at else None


def has_ai_processing_consent(user_id: str) -> bool:
    return ai_processing_consent_at(user_id) is not None


def set_ai_processing_consent(user_id: str, granted: bool) -> datetime | None:
    now = datetime.now(UTC)
    factory = session_factory()
    with factory.begin() as session:
        user = session.get(UserRecord, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "Account was not found."})
        user.ai_processing_consented_at = now if granted else None
        user.updated_at = now
        return user.ai_processing_consented_at
