import logging
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from backend.auth import (
    AuthenticatedUser,
    ai_processing_consent_at,
    create_login_code,
    get_account_context,
    normalize_email,
    require_user,
    revoke_session,
    set_ai_processing_consent,
    update_account_context,
    verify_login_code,
)
from backend.config import is_production
from backend.services.account_context import (
    AccountContextFields,
    context_as_dict,
    preview_context,
    serialize_account_context,
    suggest_context_from_posts,
)
from backend.services.email_login import (
    EmailDeliveryError,
    reviewer_login_code_matches,
    reviewer_login_enabled_for,
    send_login_code,
)
from backend.services.instagram_sync import request_account_sync
from backend.storage.content_repository import get_content_repository
from backend.storage.database import session_factory
from backend.storage.instagram_repository import delete_local_user_data
from backend.storage.oci_object_storage import delete_private_prefix, oci_storage_enabled
from backend.storage.sql_models import (
    AIGenerationLogRecord,
    AuthSessionRecord,
    InsightTextCacheRecord,
    InstagramCommentRecord,
    InstagramConnectionRecord,
    InstagramInsightCollectionJobRecord,
    InstagramInsightSnapshotRecord,
    InstagramMediaRecord,
    LoginCodeRecord,
    MediaAssetRecord,
    OAuthStateRecord,
    PostDraftRecord,
    PostPublicationRecord,
    PredictionHistoryRecord,
    TrackedPostRecord,
    UserRecord,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class EmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str = Field(pattern=r"^\d{6}$")
    intent: Literal["sign_in", "sign_up"] = "sign_in"
    privacy_terms_accepted: bool = False
    ai_processing_consent: bool = False


class AccountContextRequest(BaseModel):
    account_theme: str = Field(default="", max_length=300)
    about_this_account: str = Field(default="", max_length=3000)
    target_audience: str = Field(default="", max_length=2000)
    tone_keys: list[str] = Field(default_factory=list, max_length=3)
    tone_other: str = Field(default="", max_length=120)
    content_formats: list[str] = Field(default_factory=list, max_length=5)
    caption_language: str = Field(default="auto", max_length=40)
    primary_category: str = Field(default="", max_length=40)
    primary_category_other: str = Field(default="", max_length=120)
    audience_age_ranges: list[str] = Field(default_factory=list, max_length=7)
    preferred_hashtags: list[str] = Field(default_factory=list, max_length=10)


def _consent_payload(user_id: str) -> dict:
    consented_at = ai_processing_consent_at(user_id)
    return {
        "ai_processing_consented": consented_at is not None,
        "ai_processing_consented_at": consented_at.isoformat() if consented_at else None,
    }


@router.post("/request-code")
def request_code(payload: EmailRequest) -> dict:
    email = normalize_email(payload.email)
    code = create_login_code(email)
    reviewer_login = reviewer_login_enabled_for(email)
    if reviewer_login:
        logger.info("review_login_code_requested email=%s", email)
    else:
        try:
            send_login_code(email, code)
        except EmailDeliveryError as exc:
            raise HTTPException(status_code=503, detail={"code": "email_unavailable", "message": str(exc)}) from None
    response = {"sent": True, "message": "Check your email for a six-digit sign-in code."}
    if not reviewer_login and not is_production() and not os.getenv("POSTBRIDGE_SMTP_HOST"):
        response["development_code"] = code
    return response


@router.post("/verify-code")
def verify_code(payload: VerifyCodeRequest, background_tasks: BackgroundTasks = None) -> dict:
    email = normalize_email(payload.email)
    if payload.intent == "sign_up" and not (payload.privacy_terms_accepted and payload.ai_processing_consent):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "registration_consent_required",
                "message": "Accept the Privacy Policy, Terms, and AI processing notice to create an account.",
            },
        )
    reviewer_login = reviewer_login_enabled_for(email)
    if reviewer_login:
        logger.info("review_login_verification_attempted email=%s", email)
    user, token, expires_at = verify_login_code(
        email,
        payload.code,
        intent=payload.intent,
        ai_processing_consent=payload.ai_processing_consent,
        reviewer_code_match=reviewer_login_code_matches(payload.code) if reviewer_login else None,
    )
    if reviewer_login:
        logger.info("review_login_verified email=%s", email)
    if background_tasks is not None:
        background_tasks.add_task(request_account_sync, user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "user": {"id": user.id, "email": user.email, **_consent_payload(user.id)},
    }


@router.get("/session")
def session(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return {"user": {"id": user.id, "email": user.email, **_consent_payload(user.id)}}


@router.get("/ai-processing-consent")
def ai_processing_consent(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return _consent_payload(user.id)


@router.post("/ai-processing-consent")
def grant_ai_processing_consent(
    user: AuthenticatedUser = Depends(require_user),
    background_tasks: BackgroundTasks = None,
) -> dict:
    set_ai_processing_consent(user.id, True)
    # A consent grant is a write-side event. Queue generated text rather than
    # making the consent request itself wait for Gemini or media downloads.
    if background_tasks is not None:
        from backend.services.insight_refresh import refresh_cached_insights

        background_tasks.add_task(refresh_cached_insights, user.id)
    return _consent_payload(user.id)


@router.delete("/ai-processing-consent")
def revoke_ai_processing_consent(
    user: AuthenticatedUser = Depends(require_user),
    background_tasks: BackgroundTasks = None,
) -> dict:
    set_ai_processing_consent(user.id, False)
    get_content_repository().clear_text_cache_for_user(user.id)
    # Rebuild only deterministic Summary text on the write side. Audience and
    # suggestion generators themselves remain consent-gated.
    if background_tasks is not None:
        from backend.services.insight_refresh import refresh_cached_insights

        background_tasks.add_task(refresh_cached_insights, user.id)
    return _consent_payload(user.id)


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


@router.get("/account-context/suggest")
def suggest_account_context(user: AuthenticatedUser = Depends(require_user)) -> dict:
    factory = session_factory()
    with factory() as session:
        records = session.execute(
            select(InstagramMediaRecord.caption, InstagramMediaRecord.media_type, InstagramMediaRecord.thumbnail_url)
            .join(InstagramConnectionRecord, InstagramConnectionRecord.id == InstagramMediaRecord.account_id)
            .join(TrackedPostRecord, TrackedPostRecord.media_id == InstagramMediaRecord.id)
            .where(InstagramConnectionRecord.user_id == user.id)
            .order_by(InstagramMediaRecord.published_at.desc())
            .limit(10)
        ).all()
    return suggest_context_from_posts(
        [{"caption": row.caption, "media_type": row.media_type, "thumbnail_url": row.thumbnail_url} for row in records]
    )


@router.post("/account-context/preview")
def preview_account_context(payload: AccountContextRequest, user: AuthenticatedUser = Depends(require_user)) -> dict:
    del user
    return preview_context(AccountContextFields(**payload.model_dump()))


@router.post("/logout")
def logout(user: AuthenticatedUser = Depends(require_user)) -> dict:
    revoke_session(user.token_hash)
    return {"logged_out": True}


@router.delete("/account")
def delete_account(user: AuthenticatedUser = Depends(require_user)) -> dict:
    delete_local_user_data(user.id)

    factory = session_factory()
    with factory.begin() as session:
        tracked_ids = list(session.scalars(select(TrackedPostRecord.id).where(TrackedPostRecord.user_id == user.id)))
        media_ids = set(session.scalars(select(TrackedPostRecord.media_id).where(TrackedPostRecord.user_id == user.id)))
        connection_ids = list(
            session.scalars(select(InstagramConnectionRecord.id).where(InstagramConnectionRecord.user_id == user.id))
        )
        if connection_ids:
            media_ids.update(
                session.scalars(
                    select(InstagramMediaRecord.id).where(InstagramMediaRecord.account_id.in_(connection_ids))
                )
            )

        # RESTRICT relationships require this order regardless of database
        # cascade timing: publications -> drafts -> media assets.
        session.execute(delete(PostPublicationRecord).where(PostPublicationRecord.user_id == user.id))
        session.execute(delete(PostDraftRecord).where(PostDraftRecord.user_id == user.id))
        session.execute(delete(MediaAssetRecord).where(MediaAssetRecord.user_id == user.id))

        # Delete every record that references tracked posts before deleting the
        # tracked posts themselves. AI logs do not carry a user_id, so they are
        # selected through the owned tracked-post IDs.
        session.execute(
            delete(InstagramInsightCollectionJobRecord).where(InstagramInsightCollectionJobRecord.user_id == user.id)
        )
        if tracked_ids:
            session.execute(delete(AIGenerationLogRecord).where(AIGenerationLogRecord.tracked_post_id.in_(tracked_ids)))
        session.execute(delete(InstagramCommentRecord).where(InstagramCommentRecord.user_id == user.id))
        session.execute(delete(InsightTextCacheRecord).where(InsightTextCacheRecord.user_id == user.id))

        if media_ids:
            session.execute(
                delete(InstagramInsightSnapshotRecord).where(InstagramInsightSnapshotRecord.media_id.in_(media_ids))
            )
        session.execute(delete(TrackedPostRecord).where(TrackedPostRecord.user_id == user.id))
        if media_ids:
            session.execute(delete(InstagramMediaRecord).where(InstagramMediaRecord.id.in_(media_ids)))

        session.execute(delete(PredictionHistoryRecord).where(PredictionHistoryRecord.user_id == user.id))
        session.execute(delete(InstagramConnectionRecord).where(InstagramConnectionRecord.user_id == user.id))
        session.execute(delete(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id))
        session.execute(delete(OAuthStateRecord).where(OAuthStateRecord.user_id == user.id))
        session.execute(delete(LoginCodeRecord).where(LoginCodeRecord.email == user.email))
        session.execute(delete(UserRecord).where(UserRecord.id == user.id))
    if oci_storage_enabled():
        for prefix in (f"draft-assets/{user.id}/", f"publication-assets/{user.id}/"):
            try:
                delete_private_prefix(prefix)
            except Exception:
                logger.exception("account_media_cleanup_failed prefix=%s", prefix)
    return {"deleted": True}
