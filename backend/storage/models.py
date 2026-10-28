from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


PlatformName = Literal["Instagram", "YouTube", "TikTok"]


class SocialConnection(BaseModel):
    id: str
    user_id: str
    platform: PlatformName
    account_name: str
    status: Literal["connected", "not_connected", "sync_pending"] = "not_connected"
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    external_account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_scope: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class Post(BaseModel):
    id: str
    platform: PlatformName
    external_id: str
    title: str
    created_at: datetime


class AnalyticsSnapshot(BaseModel):
    id: str
    post_id: str
    captured_at: datetime
    views: Optional[int] = None
    engagement_rate: Optional[float] = None


class PredictionHistory(BaseModel):
    id: str
    created_at: datetime
    input_payload: dict
    output_payload: dict


class TrackedPostAnalysis(BaseModel):
    id: str
    user_id: str
    tracked_post_id: str
    source_snapshot_id: str
    source_snapshot_ids: list[str] = Field(default_factory=list)
    model_name: str
    schema_version: str = "post-analysis-v1"
    observed_metrics: dict[str, Any] = Field(default_factory=dict)
    metric_deltas: dict[str, Any] = Field(default_factory=dict)
    content_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


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
    media_asset_id: Optional[str] = None
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
    provider_media_id: Optional[str] = None
    provider_post_id: Optional[str] = None
    idempotency_key: str
    status: Literal["pending", "validating", "publishing", "published", "failed"] = "pending"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class StoreData(BaseModel):
    schema_version: int = 1
    social_connections: list[SocialConnection] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    analytics_snapshots: list[AnalyticsSnapshot] = Field(default_factory=list)
    prediction_history: list[PredictionHistory] = Field(default_factory=list)
    instagram_accounts: list["InstagramAccount"] = Field(default_factory=list)
    instagram_media: list["InstagramMedia"] = Field(default_factory=list)
    tracked_posts: list["TrackedPost"] = Field(default_factory=list)
    instagram_insight_snapshots: list["InstagramInsightSnapshot"] = Field(default_factory=list)
    tracked_post_analyses: list[TrackedPostAnalysis] = Field(default_factory=list)
    instagram_comments: list["InstagramComment"] = Field(default_factory=list)
    external_insight_records: list["ExternalInsightRecord"] = Field(default_factory=list)


class InstagramAccount(BaseModel):
    id: str
    user_id: str
    instagram_user_id: str
    username: str
    profile_picture_url: Optional[str] = None
    account_type: Optional[str] = None
    media_count: Optional[int] = None
    encrypted_access_token: str
    token_expires_at: Optional[datetime] = None
    scopes: list[str] = Field(default_factory=list)
    insight_themes: list[str] = Field(default_factory=list)
    insight_themes_updated_at: Optional[datetime] = None
    status: Literal[
        "connected", "expired", "reconnect_required", "disconnected", "error"
    ] = "connected"
    connected_at: datetime
    last_synced_at: Optional[datetime] = None
    last_error: Optional[str] = None


class InstagramMedia(BaseModel):
    id: str
    account_id: str
    instagram_media_id: str
    media_type: str
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    permalink: Optional[str] = None
    caption: str = ""
    published_at: datetime
    last_synced_at: datetime


class TrackedPost(BaseModel):
    id: str
    user_id: str
    media_id: str
    is_active: bool = True
    exclude_from_comparisons: bool = False
    started_at: datetime
    stopped_at: Optional[datetime] = None


class InstagramInsightSnapshot(BaseModel):
    id: str
    media_id: str
    captured_at: datetime
    likes: Optional[int] = None
    comments: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    reach: Optional[int] = None
    views: Optional[int] = None
    engagement_rate: Optional[float] = None
    average_watch_time_ms: Optional[int] = None
    total_watch_time_ms: Optional[int] = None
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    metric_status: dict[str, str] = Field(default_factory=dict)
    collection_type: Literal["manual_current", "milestone"] = "manual_current"
    target_hour: Optional[int] = None
    scheduled_for: Optional[datetime] = None


class InstagramInsightCollectionJob(BaseModel):
    id: str
    user_id: str
    tracked_post_id: str
    media_id: str
    target_hour: int
    due_at: datetime
    deadline_at: datetime
    next_attempt_at: datetime
    attempt_count: int = 0
    status: Literal[
        "pending", "running", "retry", "completed", "missed", "cancelled",
        "blocked_reauthorization", "permission_required", "unavailable",
    ]
    snapshot_id: Optional[str] = None
    last_error_code: Optional[str] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class InstagramComment(BaseModel):
    id: str
    provider_id: str
    user_id: str
    tracked_post_id: str
    text: str
    like_count: int = 0
    timestamp: datetime
    is_owner_reply: bool = False
    category: Literal["question", "request", "praise", "joke_or_emoji_only", "criticism"] | None = None
    classification_model: str | None = None
    fetched_at: datetime


class ExternalInsightRecord(BaseModel):
    id: str
    user_id: str
    tracked_post_id: str
    source: Literal["user_screenshot"] = "user_screenshot"
    payload: dict[str, Any] = Field(default_factory=dict)
    extraction_model: str
    extraction_version: str
    screenshot_objects: list[str] = Field(default_factory=list)
    confirmed_at: datetime
    created_at: datetime
