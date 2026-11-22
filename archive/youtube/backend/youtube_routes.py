"""Archived YouTube routes, moved verbatim out of backend/main.py on 2026-11-22.

Not imported by the running app. See archive/youtube/README.md before restoring:
these routes trust a client-supplied ``user_id`` and must be rewritten to use
``Depends(require_user)`` first.
"""

import logging
import os
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.services.youtube import (  # archive/youtube/backend/youtube_service.py
    build_youtube_oauth_url,
    consume_youtube_oauth_state,
    create_youtube_oauth_state,
    disconnect_youtube_connection,
    exchange_youtube_oauth_code,
    extract_youtube_video_id,
    fetch_youtube_advanced_analytics,
    fetch_youtube_analytics,
    fetch_youtube_public_video_data,
    get_frontend_base_url,
    get_google_client_id,
    get_google_client_secret,
    get_youtube_api_key,
    get_youtube_connection,
    store_youtube_connection,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class YouTubeAuditRequest(BaseModel):
    url: str = Field(..., min_length=8)
    user_id: str = Field(..., min_length=6)
    caption: Optional[str] = None
    hashtags: list[str] = Field(default_factory=list)


class YouTubeAuditResponse(BaseModel):
    connection_required: bool
    platform: str
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    published_at: Optional[str] = None
    thumbnail_url: Optional[str] = None
    channel_title: Optional[str] = None
    real_metrics_summary: dict[str, Optional[float]]
    missing_inputs: list[str]
    confidence_level: str
    diagnosis: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    connection_message: str
    advanced_analytics_message: str
    connected_account_name: Optional[str] = None


class YouTubeConnectionStatusResponse(BaseModel):
    connected: bool
    account_name: Optional[str] = None
    channel_id: Optional[str] = None
    token_scope: Optional[str] = None
    public_data_enabled: bool
    oauth_configured: bool
    advanced_analytics_ready: bool
    message: str


@router.get("/auth/youtube/start")
def youtube_auth_start(user_id: str) -> RedirectResponse:
    if not get_google_client_id() or not get_google_client_secret():
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first.",
        )
    state = create_youtube_oauth_state(user_id)
    return RedirectResponse(build_youtube_oauth_url(state))


@router.get("/auth/youtube/callback")
def youtube_auth_callback(
    code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None
) -> RedirectResponse:
    frontend_url = f"{get_frontend_base_url().rstrip('/')}/analysis/youtube"
    if error:
        return RedirectResponse(f"{frontend_url}?{urlencode({'youtube': 'error', 'message': error})}")
    user_id = consume_youtube_oauth_state(state) if code and state else None
    if not user_id:
        return RedirectResponse(
            f"{frontend_url}?{urlencode({'youtube': 'error', 'message': 'invalid_oauth_state'})}"
        )
    try:
        connection = store_youtube_connection(user_id, exchange_youtube_oauth_code(code))
    except Exception as exc:
        logger.exception("YOUTUBE_OAUTH callback failed: %s", exc)
        return RedirectResponse(
            f"{frontend_url}?{urlencode({'youtube': 'error', 'message': 'oauth_exchange_failed'})}"
        )
    return RedirectResponse(
        f"{frontend_url}?{urlencode({'youtube': 'connected', 'account_name': connection.account_name})}"
    )


@router.get("/auth/youtube/status", response_model=YouTubeConnectionStatusResponse)
def youtube_auth_status(user_id: str) -> YouTubeConnectionStatusResponse:
    connection = get_youtube_connection(user_id)
    connected = connection is not None and connection.status == "connected"
    return YouTubeConnectionStatusResponse(
        connected=connected,
        account_name=connection.account_name if connection else None,
        channel_id=connection.external_account_id if connection else None,
        token_scope=connection.token_scope if connection else None,
        public_data_enabled=bool(get_youtube_api_key()),
        oauth_configured=bool(get_google_client_id() and get_google_client_secret()),
        advanced_analytics_ready=False,
        message=f"Connected as {connection.account_name}." if connected else "YouTube is not connected yet.",
    )


@router.delete("/auth/youtube/disconnect")
def youtube_auth_disconnect(user_id: str) -> dict:
    disconnected = disconnect_youtube_connection(user_id)
    return {
        "disconnected": disconnected,
        "message": "YouTube disconnected." if disconnected else "No YouTube connection was found for this user.",
    }


@router.post("/audit-youtube", response_model=YouTubeAuditResponse)
def audit_youtube(payload: YouTubeAuditRequest) -> YouTubeAuditResponse:
    try:
        video_id = extract_youtube_video_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    connection = get_youtube_connection(payload.user_id)
    connected_name = connection.account_name if connection else None
    public_data = fetch_youtube_public_video_data(video_id)
    advanced_message = (
        "Private YouTube Analytics fields such as average view duration and deeper retention "
        "metrics still require OAuth-backed YouTube Analytics API access."
    )

    if public_data is None:
        return YouTubeAuditResponse(
            connection_required=connection is None,
            platform="YouTube",
            video_id=video_id,
            real_metrics_summary={},
            missing_inputs=["title", "description", "published_at", "views", "likes", "comments", "averageViewDuration"],
            confidence_level="low",
            diagnosis=["Public YouTube video data could not be retrieved from the official API in this environment."],
            strengths=[],
            weaknesses=[
                "Official public YouTube metadata is not available yet for this request.",
                "Advanced YouTube Analytics metrics still require OAuth and are not available from public API access alone.",
            ],
            recommendations=[
                "Set YOUTUBE_API_KEY so PostBridge can fetch public YouTube video metadata and public statistics.",
                "Connect YouTube with OAuth later if you want private metrics such as average view duration.",
            ],
            connection_message=(
                "Public YouTube data is unavailable right now."
                if os.getenv("YOUTUBE_API_KEY")
                else "Add a YouTube Data API key to enable public YouTube video data."
            ),
            advanced_analytics_message=advanced_message,
            connected_account_name=connected_name,
        )

    analytics = fetch_youtube_advanced_analytics(payload.user_id, video_id) or fetch_youtube_analytics(video_id)
    metrics = {
        "views": public_data.get("views"),
        "likes": public_data.get("likes"),
        "comments": public_data.get("comments"),
        "averageViewDuration": analytics.get("averageViewDuration") if analytics else None,
    }
    diagnosis = [
        "This audit is based on public YouTube video metadata and public engagement counts returned by the official YouTube Data API."
    ]
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []

    if public_data.get("title"):
        strengths.append("A public video title was retrieved, so the audit can evaluate the visible promise of the video.")
    if len(str(public_data.get("description") or "").strip()) < 80:
        weaknesses.append("The public description is short, which limits how much context or search relevance the video communicates.")
        recommendations.append("Expand the description with a clearer summary, keywords, or next action for viewers.")
    else:
        strengths.append("The public description provides enough text for a basic content-positioning audit.")

    views, likes, comments = metrics["views"], metrics["likes"], metrics["comments"]
    if views and comments is not None and comments / views < 0.002:
        weaknesses.append("Comments are low relative to public views, suggesting the video is not triggering much discussion.")
        recommendations.append("Add a stronger opinion prompt or specific question to increase discussion in future uploads.")
    if views and likes is not None and likes / views >= 0.03:
        strengths.append("Likes are reasonably healthy relative to public views, which suggests the topic or framing resonates.")
    elif views and likes is not None and likes / views < 0.015:
        weaknesses.append("Likes are light relative to public views, which may indicate the title-package promise is not converting into strong approval.")
        recommendations.append("Test a sharper title or thumbnail pairing that makes the viewer payoff more explicit.")
    if metrics["averageViewDuration"] is None:
        diagnosis.append("Hook and retention diagnosis is limited because average view duration is not available from the public API.")
        recommendations.append("Connect YouTube with OAuth to unlock deeper retention-based diagnosis.")

    fetched = "Public YouTube metadata and public statistics were fetched successfully."
    return YouTubeAuditResponse(
        connection_required=connection is None,
        platform="YouTube",
        video_id=video_id,
        title=public_data.get("title"),
        description=public_data.get("description"),
        published_at=public_data.get("published_at"),
        thumbnail_url=public_data.get("thumbnail_url"),
        channel_title=public_data.get("channel_title"),
        real_metrics_summary=metrics,
        missing_inputs=[key for key, value in metrics.items() if value is None],
        confidence_level="medium" if views is not None else "low",
        diagnosis=diagnosis,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations
        or ["Use the public YouTube metrics as a starting point, then connect OAuth for deeper analytics later."],
        connection_message=fetched
        if connection is None
        else f"{fetched} Advanced analytics can use your connected YouTube account once configured.",
        advanced_analytics_message=advanced_message,
        connected_account_name=connected_name,
    )
