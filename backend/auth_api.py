import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from backend.auth import AuthenticatedUser, create_login_code, get_account_context, normalize_email, require_user, revoke_session, update_account_context, verify_login_code
from backend.config import is_production
from backend.services.account_context import AccountContextFields, context_as_dict, serialize_account_context
from backend.services.email_login import EmailDeliveryError, send_login_code
from backend.storage.database import session_factory
from backend.storage.sql_models import (
    AuthSessionRecord, InstagramConnectionRecord, InstagramInsightSnapshotRecord,
    InstagramMediaRecord, LoginCodeRecord, OAuthStateRecord, PredictionHistoryRecord,
    TrackedPostRecord, UserRecord,
)


router = APIRouter(prefix="/auth", tags=["auth"])


class EmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str = Field(pattern=r"^\d{6}$")


class AccountContextRequest(BaseModel):
    account_theme: str = Field(default="", max_length=300)
    about_this_account: str = Field(default="", max_length=3000)
    target_audience: str = Field(default="", max_length=2000)


@router.post("/request-code")
def request_code(payload: EmailRequest) -> dict:
    email = normalize_email(payload.email)
    code = create_login_code(email)
    try:
        send_login_code(email, code)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail={"code": "email_unavailable", "message": str(exc)}) from None
    response = {"sent": True, "message": "Check your email for a six-digit sign-in code."}
    if not is_production() and not os.getenv("POSTBRIDGE_SMTP_HOST"):
        response["development_code"] = code
    return response


@router.post("/verify-code")
def verify_code(payload: VerifyCodeRequest) -> dict:
    email = normalize_email(payload.email)
    user, token, expires_at = verify_login_code(email, payload.code)
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at.isoformat(), "user": {"id": user.id, "email": user.email}}


@router.get("/session")
def session(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return {"user": {"id": user.id, "email": user.email}}


@router.get("/account-context")
def account_context(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return context_as_dict(get_account_context(user.id))


@router.patch("/account-context")
def save_account_context(payload: AccountContextRequest, user: AuthenticatedUser = Depends(require_user)) -> dict:
    try:
        encoded = serialize_account_context(AccountContextFields(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    update_account_context(user.id, encoded)
    return context_as_dict(encoded)


@router.post("/logout")
def logout(user: AuthenticatedUser = Depends(require_user)) -> dict:
    revoke_session(user.token_hash)
    return {"logged_out": True}


@router.delete("/account")
def delete_account(user: AuthenticatedUser = Depends(require_user)) -> dict:
    factory = session_factory()
    with factory.begin() as session:
        media_ids = list(session.scalars(select(InstagramMediaRecord.id).join(InstagramConnectionRecord, InstagramConnectionRecord.id == InstagramMediaRecord.account_id).where(InstagramConnectionRecord.user_id == user.id)))
        if media_ids:
            session.execute(delete(InstagramInsightSnapshotRecord).where(InstagramInsightSnapshotRecord.media_id.in_(media_ids)))
            session.execute(delete(TrackedPostRecord).where(TrackedPostRecord.media_id.in_(media_ids)))
            session.execute(delete(InstagramMediaRecord).where(InstagramMediaRecord.id.in_(media_ids)))
        session.execute(delete(PredictionHistoryRecord).where(PredictionHistoryRecord.user_id == user.id))
        session.execute(delete(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user.id))
        session.execute(delete(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id))
        session.execute(delete(OAuthStateRecord).where(OAuthStateRecord.user_id == user.id))
        session.execute(delete(LoginCodeRecord).where(LoginCodeRecord.email == user.email))
        session.execute(delete(UserRecord).where(UserRecord.id == user.id))
    return {"deleted": True}
