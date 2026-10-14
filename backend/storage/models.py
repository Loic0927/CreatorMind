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
    engagement_rate: float = 0.0
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
