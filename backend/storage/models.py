from datetime import datetime
from typing import Literal, Optional

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
    social_connections: list[SocialConnection] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    analytics_snapshots: list[AnalyticsSnapshot] = Field(default_factory=list)
    prediction_history: list[PredictionHistory] = Field(default_factory=list)
