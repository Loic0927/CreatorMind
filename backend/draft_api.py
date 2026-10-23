"""Authenticated media, draft, and durable publication endpoints."""

import base64
import binascii
import hashlib
import os
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from backend.auth import AuthenticatedUser, require_user
from backend.storage.draft_repository import (
    DraftConflictError,
    DraftNotFoundError,
    DraftRepositoryError,
    MediaAssetNotFoundError,
    get_draft_repository,
)
from backend.services.publishing import PublishInput
from backend.storage.models import MediaAsset, PostDraft, PostPublication
from backend.storage.oci_object_storage import OCIStorageConfigurationError, upload_private_bytes


router = APIRouter(prefix="/drafts", tags=["drafts"])
media_router = APIRouter(prefix="/media-assets", tags=["media-assets"])
Platform = Literal["Instagram", "Twitter", "Facebook", "Threads", "YouTube"]
CAPTION_LIMITS = {
    "Instagram": 2200,
    "Twitter": 280,
    "Facebook": 63_206,
    "Threads": 500,
    "YouTube": 5_000,
}
HASHTAG_PATTERN = re.compile(r"^#[^\s#]{1,99}$")
MEDIA_SIGNATURES = {
    "image/jpeg": lambda body: body.startswith(b"\xff\xd8\xff"),
    "image/png": lambda body: body.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda body: len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP",
}
MEDIA_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _unique_platforms(values: list[Platform]) -> list[Platform]:
    return list(dict.fromkeys(values))


def _normalize_hashtags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and not value.startswith("#"):
            value = f"#{value}"
        if not HASHTAG_PATTERN.fullmatch(value):
            raise ValueError("Each hashtag must be one word of at most 100 characters.")
        if value.lower() not in {item.lower() for item in normalized}:
            normalized.append(value)
    if len(normalized) > 30:
        raise ValueError("A draft can contain at most 30 hashtags.")
    return normalized


class DraftCreate(BaseModel):
    media_asset_id: str | None = None
    target_platforms: list[Platform] = Field(..., min_length=1, max_length=5)
    content_brief: str = Field(default="", max_length=5000)
    goal: str = Field(default="", max_length=255)
    caption: str = Field(default="", max_length=63_206)
    hashtags: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("target_platforms")
    @classmethod
    def validate_platforms(cls, value: list[Platform]) -> list[Platform]:
        return _unique_platforms(value)

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, value: list[str]) -> list[str]:
        return _normalize_hashtags(value)


class DraftUpdate(BaseModel):
    media_asset_id: str | None = None
    target_platforms: list[Platform] | None = Field(default=None, min_length=1, max_length=5)
    content_brief: str | None = Field(default=None, max_length=5000)
    goal: str | None = Field(default=None, max_length=255)
    caption: str | None = Field(default=None, max_length=63_206)
    hashtags: list[str] | None = Field(default=None, max_length=30)

    @field_validator("target_platforms")
    @classmethod
    def validate_platforms(cls, value: list[Platform] | None) -> list[Platform] | None:
        return _unique_platforms(value) if value is not None else None

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_hashtags(value) if value is not None else None


class MediaAssetUpload(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(..., min_length=4)


class DraftPublishRequest(BaseModel):
    platforms: list[Platform] = Field(..., min_length=1, max_length=5)
    idempotency_key: str = Field(..., min_length=8, max_length=128)

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value: list[Platform]) -> list[Platform]:
        return _unique_platforms(value)


def _validate_caption(platforms: list[str], caption: str) -> None:
    if not caption:
        return
    limit = min(CAPTION_LIMITS[item] for item in platforms)
    if len(caption) > limit:
        constrained = min(platforms, key=lambda item: CAPTION_LIMITS[item])
        raise HTTPException(
            status_code=422,
            detail={
                "code": "caption_too_long",
                "message": f"The caption exceeds the {limit}-character {constrained} limit.",
            },
        )


def _repository_error(exc: DraftRepositoryError) -> HTTPException:
    if isinstance(exc, (DraftNotFoundError, MediaAssetNotFoundError)):
        return HTTPException(status_code=404, detail={"code": "draft_resource_not_found", "message": str(exc)})
    if isinstance(exc, DraftConflictError):
        return HTTPException(status_code=409, detail={"code": "invalid_draft_state", "message": str(exc)})
    return HTTPException(status_code=503, detail={"code": "draft_storage_unavailable", "message": "Draft storage is unavailable."})


@media_router.post("", response_model=MediaAsset, status_code=201)
def upload_media_asset(payload: MediaAssetUpload, user: AuthenticatedUser = Depends(require_user)) -> MediaAsset:
    try:
        body = base64.b64decode(payload.data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail={"code": "invalid_media", "message": "Uploaded media is not valid base64 data."}) from None
    max_bytes = min(int(os.getenv("POSTBRIDGE_MAX_IMAGE_BYTES", str(5 * 1024 * 1024))), 5 * 1024 * 1024)
    if not body or len(body) > max_bytes:
        raise HTTPException(status_code=413, detail={"code": "media_too_large", "message": "The image is empty or exceeds 5 MB."})
    if not MEDIA_SIGNATURES[payload.mime_type](body):
        raise HTTPException(status_code=422, detail={"code": "invalid_media_signature", "message": "The image contents do not match its MIME type."})
    safe_name = Path(payload.filename.replace("\\", "/")).name[:180] or f"image{MEDIA_EXTENSIONS[payload.mime_type]}"
    object_name = f"draft-assets/{user.id}/{uuid4()}{MEDIA_EXTENSIONS[payload.mime_type]}"
    try:
        upload_private_bytes(body, object_name, payload.mime_type)
        return get_draft_repository().create_media_asset(
            user.id,
            storage_provider="oci",
            object_name=object_name,
            original_filename=safe_name,
            mime_type=payload.mime_type,
            byte_size=len(body),
            checksum_sha256=hashlib.sha256(body).hexdigest(),
            status="ready",
        )
    except OCIStorageConfigurationError:
        raise HTTPException(status_code=503, detail={"code": "media_storage_unavailable", "message": "Private media storage is not configured."}) from None
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None


@router.post("", response_model=PostDraft, status_code=201)
def create_draft(payload: DraftCreate, user: AuthenticatedUser = Depends(require_user)) -> PostDraft:
    _validate_caption(payload.target_platforms, payload.caption)
    try:
        return get_draft_repository().create_draft(user.id, **payload.model_dump())
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None


@router.get("", response_model=list[PostDraft])
def list_drafts(user: AuthenticatedUser = Depends(require_user)) -> list[PostDraft]:
    try:
        return get_draft_repository().list_drafts(user.id)
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None


@router.get("/{draft_id}", response_model=PostDraft)
def get_draft(draft_id: str, user: AuthenticatedUser = Depends(require_user)) -> PostDraft:
    try:
        draft = get_draft_repository().get_draft(user.id, draft_id)
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None
    if draft is None:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "message": "Draft not found."})
    return draft


@router.patch("/{draft_id}", response_model=PostDraft)
def update_draft(payload: DraftUpdate, draft_id: str, user: AuthenticatedUser = Depends(require_user)) -> PostDraft:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "empty_draft_update", "message": "Provide at least one field to update."})
    try:
        existing = get_draft_repository().get_draft(user.id, draft_id)
        if existing is None:
            raise DraftNotFoundError("Draft not found.")
        platforms = changes.get("target_platforms", existing.target_platforms)
        caption = changes.get("caption", existing.caption)
        _validate_caption(platforms, caption)
        return get_draft_repository().update_draft(user.id, draft_id, changes)
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None


@router.delete("/{draft_id}", status_code=204)
def delete_draft(draft_id: str, user: AuthenticatedUser = Depends(require_user)) -> Response:
    try:
        deleted = get_draft_repository().delete_draft(user.id, draft_id)
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "message": "Draft not found."})
    return Response(status_code=204)


@router.get("/{draft_id}/publications", response_model=list[PostPublication])
def list_publications(draft_id: str, user: AuthenticatedUser = Depends(require_user)) -> list[PostPublication]:
    try:
        return get_draft_repository().list_publications(user.id, draft_id)
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None


@router.post("/{draft_id}/publish")
def publish_draft(payload: DraftPublishRequest, draft_id: str, user: AuthenticatedUser = Depends(require_user)) -> dict:
    # Imported lazily to keep the shared adapter contract independent from API wiring.
    from backend.instagram_api import publishing_registry

    repository = get_draft_repository()
    try:
        draft = repository.get_draft(user.id, draft_id)
        if draft is None:
            raise DraftNotFoundError("Draft not found.")
        if any(platform not in draft.target_platforms for platform in payload.platforms):
            raise DraftConflictError("Every publication platform must be selected on the draft.")
        if draft.status in {"published", "publishing"}:
            existing = {
                (item.platform, item.idempotency_key): item
                for item in repository.list_publications(user.id, draft.id)
            }
            repeated = [existing.get((platform, payload.idempotency_key)) for platform in payload.platforms]
            if all(item is not None for item in repeated):
                return {
                    "draft": draft,
                    "results": [
                        {
                            "platform": item.platform,
                            "status": item.status,
                            "provider_post_id": item.provider_post_id,
                            "publication_id": item.id,
                            "code": item.error_code,
                            "message": "This publication request was already received.",
                        }
                        for item in repeated
                    ],
                }
            raise DraftConflictError(f"A {draft.status} draft cannot accept a new publication request.")
        if draft.status not in {"draft", "failed"}:
            raise DraftConflictError(f"A {draft.status} draft cannot be published.")
        if not draft.media_asset_id:
            raise DraftConflictError("Add an image before publishing this draft.")
        asset = repository.get_media_asset(user.id, draft.media_asset_id)
        if asset is None or asset.status != "ready":
            raise MediaAssetNotFoundError("Publishable media asset not found.")

        registry = publishing_registry()
        request = PublishInput(
            caption=draft.caption,
            hashtags=" ".join(draft.hashtags),
            mime_type=asset.mime_type,
            object_name=asset.object_name,
        )
        preflight: dict[str, object] = {}
        results: list[dict] = []
        for platform in payload.platforms:
            adapter = registry.get(platform)
            if adapter is None:
                raise DraftConflictError(f"Unsupported platform: {platform}.")
            capability = adapter.capability(user.id)
            if not capability.available:
                results.append({
                    "platform": platform, "status": "unavailable",
                    "code": "platform_unavailable", "message": capability.reason or "Publishing is unavailable.",
                })
                continue
            invalid = adapter.validate(request)
            if invalid:
                results.append(invalid.as_dict())
                continue
            preflight[platform] = adapter

        if not preflight:
            return {"draft": draft, "results": results}

        repository.transition_draft_status(user.id, draft.id, "publishing")
        all_published = True
        for platform, adapter in preflight.items():
            publication, created = repository.create_publication(
                user.id, draft.id, platform, payload.idempotency_key
            )
            if not created and publication.status == "published":
                results.append({
                    "platform": platform, "status": "published",
                    "provider_post_id": publication.provider_post_id,
                    "publication_id": publication.id,
                    "message": "This request was already published.",
                })
                continue
            if not created and publication.status in {"validating", "publishing"}:
                results.append({
                    "platform": platform, "status": "publishing",
                    "publication_id": publication.id,
                    "message": "This publication request is already in progress.",
                })
                all_published = False
                continue
            if not created and publication.status == "failed":
                publication = repository.transition_publication(user.id, publication.id, "pending")
            publication = repository.transition_publication(user.id, publication.id, "validating")
            publication = repository.transition_publication(user.id, publication.id, "publishing")
            result = adapter.publish(user.id, request)
            if result.status == "published" and result.provider_post_id:
                repository.transition_publication(
                    user.id, publication.id, "published",
                    provider_media_id=result.provider_post_id,
                    provider_post_id=result.provider_post_id,
                )
            else:
                all_published = False
                repository.transition_publication(
                    user.id, publication.id, "failed",
                    error_code=result.code or "publish_failed", error_message=result.message,
                )
            item = result.as_dict()
            item["publication_id"] = publication.id
            results.append(item)

        final_status = "published" if all_published and len(preflight) == len(payload.platforms) else "failed"
        final_draft = repository.transition_draft_status(user.id, draft.id, final_status)
        return {"draft": final_draft, "results": results}
    except DraftRepositoryError as exc:
        raise _repository_error(exc) from None
