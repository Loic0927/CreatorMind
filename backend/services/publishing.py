"""Provider-neutral publication contract and the first Instagram adapter."""

import base64
import binascii
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.services.instagram import InstagramServiceError, publish_instagram_image, publish_instagram_reel
from backend.storage.content_repository import ContentRepository, get_content_repository
from backend.storage.models import InstagramMedia
from backend.storage.oci_object_storage import (
    OCIStorageConfigurationError,
    create_temporary_read_url,
    download_private_bytes,
    upload_bytes_with_temporary_read_url,
)


SUPPORTED_INSTAGRAM_SOURCE_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_INSTAGRAM_VIDEO_TYPES = {"video/mp4", "video/quicktime"}


def convert_to_instagram_jpeg(body: bytes, mime_type: str) -> bytes:
    """Normalize a supported source image to a standard RGB JPEG for Meta."""
    if mime_type not in SUPPORTED_INSTAGRAM_SOURCE_TYPES:
        raise ValueError("Unsupported source image format.")
    try:
        with Image.open(BytesIO(body)) as source:
            source = ImageOps.exif_transpose(source)
            source.load()
            if source.width * source.height > 40_000_000:
                raise ValueError("Image dimensions exceed the processing limit.")
            if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
                rgba = source.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, "white")
                flattened.paste(rgba, mask=rgba.getchannel("A"))
                image = flattened
            else:
                image = source.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded image could not be converted to JPEG.") from exc


@dataclass(frozen=True)
class PublishingCapability:
    platform: str
    available: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"platform": self.platform, "available": self.available, "reason": self.reason}


@dataclass(frozen=True)
class PublishInput:
    caption: str
    hashtags: str
    mime_type: str
    encoded_media: str | None = None
    object_name: str | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True)
class PublicationResult:
    platform: str
    status: str
    message: str
    provider_post_id: str | None = None
    permalink: str | None = None
    tracked_post_id: str | None = None
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "platform": self.platform, "status": self.status, "message": self.message,
            "provider_post_id": self.provider_post_id, "permalink": self.permalink,
            "tracked_post_id": self.tracked_post_id, "code": self.code,
        }.items() if value is not None}


class PublishingAdapter(ABC):
    platform: str

    @abstractmethod
    def capability(self, user_id: str) -> PublishingCapability: ...

    @abstractmethod
    def validate(self, request: PublishInput) -> PublicationResult | None: ...

    @abstractmethod
    def publish(self, user_id: str, request: PublishInput) -> PublicationResult: ...

    @abstractmethod
    def status(self, user_id: str, provider_post_id: str) -> str: ...

    def normalize_error(self, exc: Exception) -> PublicationResult:
        return PublicationResult(
            platform=self.platform, status="failed", code="publish_failed",
            message="Publishing failed.",
        )


class UnavailablePublishingAdapter(PublishingAdapter):
    def __init__(self, platform: str, reason: str = "Publishing integration is not available yet."):
        self.platform = platform
        self.reason = reason

    def capability(self, user_id: str) -> PublishingCapability:
        return PublishingCapability(self.platform, False, self.reason)

    def validate(self, request: PublishInput) -> PublicationResult | None:
        return PublicationResult(self.platform, "unavailable", self.reason)

    def publish(self, user_id: str, request: PublishInput) -> PublicationResult:
        return PublicationResult(self.platform, "unavailable", self.reason)

    def status(self, user_id: str, provider_post_id: str) -> str:
        return "unavailable"


class InstagramPublishingAdapter(PublishingAdapter):
    platform = "Instagram"

    def __init__(
        self,
        *,
        account_loader: Callable[[str], Any],
        token_loader: Callable[[Any], str],
        repository_loader: Callable[[], ContentRepository] = get_content_repository,
        uploader: Callable[[bytes, str, str], str] = upload_bytes_with_temporary_read_url,
        object_loader: Callable[[str], bytes] = download_private_bytes,
        temporary_url_factory: Callable[..., str] = create_temporary_read_url,
        provider_publisher: Callable[[str, str, str, str], dict[str, Any]] = publish_instagram_image,
        video_publisher: Callable[[str, str, str, str], dict[str, Any]] = publish_instagram_reel,
    ):
        self._account_loader = account_loader
        self._token_loader = token_loader
        self._repository_loader = repository_loader
        self._uploader = uploader
        self._object_loader = object_loader
        self._temporary_url_factory = temporary_url_factory
        self._provider_publisher = provider_publisher
        self._video_publisher = video_publisher

    def capability(self, user_id: str) -> PublishingCapability:
        try:
            account = self._account_loader(user_id)
        except Exception:
            account = None
        available = bool(account and getattr(account, "status", None) == "connected")
        return PublishingCapability(
            self.platform, available,
            None if available else "Connect Instagram before publishing.",
        )

    def validate(self, request: PublishInput) -> PublicationResult | None:
        supported_types = SUPPORTED_INSTAGRAM_SOURCE_TYPES | SUPPORTED_INSTAGRAM_VIDEO_TYPES
        if request.mime_type not in supported_types:
            return PublicationResult(
                self.platform, "failed", "Choose a JPG, PNG, WebP, MP4 or MOV file.",
                code="unsupported_media_format",
            )
        is_video = request.mime_type in SUPPORTED_INSTAGRAM_VIDEO_TYPES
        if is_video and (request.duration_seconds is None or not 0 < request.duration_seconds <= 60.05):
            return PublicationResult(
                self.platform, "failed", "Choose a video that is one minute or shorter.",
                code="invalid_video_duration",
            )
        if request.object_name:
            return None
        if not request.encoded_media:
            return PublicationResult(self.platform, "failed", "Publishable media is required.", code="media_required")
        try:
            media = base64.b64decode(request.encoded_media, validate=True)
        except (binascii.Error, ValueError):
            return PublicationResult(self.platform, "failed", "Uploaded media is not valid base64 data.", code="invalid_media")
        max_bytes = min(int(os.getenv("POSTBRIDGE_MAX_UPLOAD_BYTES", "10485760")), 10 * 1024 * 1024)
        if not media or len(media) > max_bytes:
            return PublicationResult(self.platform, "failed", "The publish media is empty or exceeds the configured limit.", code="media_too_large")
        return None

    def publish(self, user_id: str, request: PublishInput) -> PublicationResult:
        invalid = self.validate(request)
        if invalid:
            return invalid
        try:
            account = self._account_loader(user_id)
            is_video = request.mime_type in SUPPORTED_INSTAGRAM_VIDEO_TYPES
            if is_video:
                if request.object_name:
                    media_url = self._temporary_url_factory(request.object_name, lifetime_minutes=60)
                else:
                    media_bytes = base64.b64decode(request.encoded_media or "", validate=True)
                    extension = ".mov" if request.mime_type == "video/quicktime" else ".mp4"
                    object_name = f"publication-assets/{user_id}/{uuid4()}{extension}"
                    media_url = self._uploader(media_bytes, object_name, request.mime_type)
            elif request.object_name and request.mime_type == "image/jpeg":
                media_url = self._temporary_url_factory(request.object_name, lifetime_minutes=60)
            else:
                source_bytes = self._object_loader(request.object_name) if request.object_name else base64.b64decode(request.encoded_media or "", validate=True)
                image_bytes = convert_to_instagram_jpeg(source_bytes, request.mime_type)
                object_name = f"publication-assets/{user_id}/{uuid4()}.jpg"
                media_url = self._uploader(image_bytes, object_name, "image/jpeg")
            full_caption = "\n\n".join(
                value.strip() for value in (request.caption, request.hashtags) if value.strip()
            )
            publisher = self._video_publisher if is_video else self._provider_publisher
            item = publisher(self._token_loader(account), account.instagram_user_id, media_url, full_caption)
            now = datetime.now(timezone.utc)
            media_item = InstagramMedia(
                id=f"instagram:{item['id']}", account_id=account.id,
                instagram_media_id=str(item["id"]), media_type=str(item.get("media_type", "IMAGE")),
                media_url=item.get("media_url"), thumbnail_url=item.get("thumbnail_url"),
                permalink=item.get("permalink"), caption=str(item.get("caption", full_caption)),
                published_at=_parse_timestamp(item.get("timestamp")), last_synced_at=now,
            )
            repository = self._repository_loader()
            repository.upsert_media([media_item])
            return PublicationResult(
                self.platform, "published", "Published successfully.",
                provider_post_id=media_item.instagram_media_id, permalink=media_item.permalink,
            )
        except Exception as exc:
            return self.normalize_error(exc)

    def status(self, user_id: str, provider_post_id: str) -> str:
        # The initial image adapter is synchronous: a provider ID is returned only
        # after media_publish succeeds. Video/container polling can extend this.
        return "published" if provider_post_id else "unknown"

    def normalize_error(self, exc: Exception) -> PublicationResult:
        if isinstance(exc, OCIStorageConfigurationError):
            return PublicationResult(self.platform, "failed", "Private media storage is not configured for publishing.", code="media_storage_unavailable")
        if isinstance(exc, InstagramServiceError):
            return PublicationResult(self.platform, "failed", exc.message, code=exc.code)
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return PublicationResult(
                self.platform, "failed", str(detail.get("message", "Instagram publishing failed.")),
                code=str(detail.get("code", "publish_failed")),
            )
        return super().normalize_error(exc)


class PublishingAdapterRegistry:
    def __init__(self, adapters: list[PublishingAdapter]):
        self._adapters = {adapter.platform: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("Publishing platforms must be registered once.")

    def get(self, platform: str) -> PublishingAdapter | None:
        return self._adapters.get(platform)

    def capabilities(self, user_id: str) -> list[PublishingCapability]:
        return [adapter.capability(user_id) for adapter in self._adapters.values()]


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
