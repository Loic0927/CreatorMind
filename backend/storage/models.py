from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DraftPlatform = Literal["Instagram", "Twitter", "Facebook", "Threads", "YouTube"]


class MediaAsset(BaseModel):
    id: str
    user_id: str
    storage_provider: str
    object_name: str
    original_filename: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    status: Literal["uploaded", "ready", "failed", "deleted"] = "uploaded"
    created_at: datetime
    updated_at: datetime


class PostDraft(BaseModel):
    id: str
    user_id: str
    media_asset_id: str | None = None
    target_platforms: list[DraftPlatform] = Field(default_factory=list)
    content_brief: str = ""
    goal: str = ""
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    status: Literal["draft", "publishing", "published", "failed"] = "draft"
    created_at: datetime
    updated_at: datetime


class PostPublication(BaseModel):
    id: str
    user_id: str
    draft_id: str
    platform: DraftPlatform
    provider_media_id: str | None = None
    provider_post_id: str | None = None
    idempotency_key: str
    status: Literal["pending", "validating", "publishing", "published", "failed"] = "pending"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class StoreData(BaseModel):
    schema_version: int = 1
    instagram_accounts: list["InstagramAccount"] = Field(default_factory=list)
    instagram_media: list["InstagramMedia"] = Field(default_factory=list)
    tracked_posts: list["TrackedPost"] = Field(default_factory=list)
    instagram_insight_snapshots: list["InstagramInsightSnapshot"] = Field(default_factory=list)
    instagram_comments: list["InstagramComment"] = Field(default_factory=list)


class InstagramAccount(BaseModel):
    id: str
    user_id: str
    instagram_user_id: str
    username: str
    profile_picture_url: str | None = None
    account_type: str | None = None
    media_count: int | None = None
    encrypted_access_token: str
    token_expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    session_synced_at: datetime | None = None
    session_sync_error: str | None = None
    tracking_start_at: datetime | None = None
    status: Literal["connected", "expired", "reconnect_required", "disconnected", "error"] = "connected"
    connected_at: datetime
    last_synced_at: datetime | None = None
    last_error: str | None = None


class InstagramMedia(BaseModel):
    id: str
    account_id: str
    instagram_media_id: str
    media_type: str
    media_url: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    caption: str = ""
    published_at: datetime
    last_synced_at: datetime


class TrackedPost(BaseModel):
    id: str
    user_id: str
    media_id: str
    is_active: bool = True
    started_at: datetime
    stopped_at: datetime | None = None
    first_24h_status: Literal["collecting", "complete", "partial", "unavailable"] = "collecting"
    first_24h_reason: str | None = None


class InstagramInsightSnapshot(BaseModel):
    id: str
    media_id: str
    captured_at: datetime
    likes: int | None = None
    comments: int | None = None
    saves: int | None = None
    shares: int | None = None
    reach: int | None = None
    views: int | None = None
    engagement_rate: float | None = None
    average_watch_time_ms: int | None = None
    total_watch_time_ms: int | None = None
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    metric_status: dict[str, str] = Field(default_factory=dict)
    scheduled_for: datetime | None = None
    milestone_hours: int | None = None
    source: str = "api"
    lateness_seconds: int | None = None


class InstagramComment(BaseModel):
    id: str
    provider_id: str
    user_id: str
    tracked_post_id: str
    text: str
    like_count: int = 0
    timestamp: datetime
    is_owner_reply: bool = False
    fetched_at: datetime


class InsightTextCache(BaseModel):
    id: str
    user_id: str
    tracked_post_id: str | None = None
    cache_key: str
    input_hash: str
    text: str
    model_name: str
    provider: str = "template"
    prompt_version: str = "unknown"
    facts_json: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
