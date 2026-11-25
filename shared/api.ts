/**
 * Generated API contract shared by the web and mobile clients.
 *
 * Refresh with `python scripts/generate_api_types.py`. Do not add client-only
 * view state here; keep that in the client that owns it.
 */

import type { components } from "./openapi";

type Schemas = components["schemas"];
export type SocialPlatform = NonNullable<Schemas["CaptionRequest"]["platform"]>;
export type AuthIntent = Schemas["EmailRequest"]["intent"];
export type ImageMimeType = Schemas["CaptionImage"]["mime_type"];
export type MediaMimeType = Schemas["CaptionMedia"]["mime_type"];

export type Session = {
  accessToken: string;
  expiresAt: string;
  user: {
    id: string;
    email: string;
    ai_processing_consented?: boolean;
    ai_processing_consented_at?: string | null;
  };
};

export type ConnectionStatus =
  "not_connected" | "connected" | "expired" | "reconnect_required" | "disconnected" | "error";
export type Connection = {
  connected: boolean;
  configured: boolean;
  status?: ConnectionStatus | string;
  username?: string;
  profile_picture_url?: string;
  account_type?: string;
  last_synced_at?: string;
  session_synced_at?: string | null;
  sync_error?: string | null;
  comment_ingestion?: { enabled: boolean; permission_granted: boolean };
};
export type InstagramConnection = Connection;

export type TikTokConnection = {
  connected: boolean;
  configured: boolean;
  status?: string;
  display_name?: string;
  avatar_url?: string | null;
  scopes?: string[];
  updated_at?: string | null;
};
export type TikTokMetricKey = "views" | "likes" | "engagement_rate" | "shares" | "comments";
export type TikTokAnalysisRow = {
  metric: TikTokMetricKey;
  value: number;
  usual_min: number;
  usual_max: number;
  status: "above" | "below" | "inside";
  rank: number;
  group_size: number;
  band_start: number;
  band_end: number;
  marker: number;
};
export type TikTokPostAnalysis = {
  comparable: boolean;
  comparable_count: number;
  summary: string;
  stands_out: TikTokAnalysisRow[];
  weaker: TikTokAnalysisRow[];
  usual_ranges: TikTokAnalysisRow[];
  age_days: number;
  media_format: "Video";
  audience_comments: { state: "unavailable"; message: string };
};
export type TikTokTrackedPost = {
  id: string;
  video_id: string;
  caption: string;
  thumbnail_url?: string;
  permalink?: string;
  published_at?: string;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
  views?: number | null;
  engagement_rate?: number | null;
  metrics_updated_at?: string | null;
  created_at: string;
  analysis?: TikTokPostAnalysis;
};

export type MetricKey = "views" | "reach" | "engagement_rate" | "shares" | "saves" | "comments";
export type MetricValue = number | null;
export type InsightSnapshot = {
  id: string;
  likes?: MetricValue;
  comments?: MetricValue;
  saves?: MetricValue;
  shares?: MetricValue;
  reach?: MetricValue;
  views?: MetricValue;
  engagement_rate?: MetricValue;
  average_watch_time_ms?: MetricValue;
  total_watch_time_ms?: MetricValue;
  captured_at: string;
  metric_status?: Record<string, "available" | "unavailable" | "permission_required">;
};
export type Snapshot = InsightSnapshot;
export type RangeRow = {
  metric: MetricKey;
  value: number;
  usual_min: number;
  usual_max: number;
  status: "above" | "below" | "inside";
  rank: number;
  group_size: number;
  band_start: number;
  band_end: number;
  marker: number;
};
export type AudienceComment = { text: string; like_count: number; timestamp: string };
export type AudienceComments = {
  state: "feature_off" | "reconnect_needed" | "access_denied" | "too_few" | "error" | "ready" | "consent_required";
  message?: string;
  description?: string;
  items?: AudienceComment[];
};
export type ComparisonBasis = "lifetime" | "same_age";
export type NotComparableReason = "too_early" | "too_few_posts";
export type SummaryStatus = "ready" | "pending" | "none";
export type PostAnalysisView = {
  comparable: boolean;
  comparable_count: number;
  comparison_basis: ComparisonBasis;
  not_comparable_reason: NotComparableReason | null;
  summary?: string | null;
  summary_status?: SummaryStatus;
  stands_out: RangeRow[];
  weaker: RangeRow[];
  usual_ranges: RangeRow[];
  audience_comments: AudienceComments;
  age_days: number;
  media_format: string;
};
export type InstagramMedia = {
  id: string;
  instagram_media_id?: string;
  account_id?: string;
  media_type?: string;
  media_url?: string;
  thumbnail_url?: string;
  caption: string;
  published_at: string;
  last_synced_at?: string;
  permalink?: string | null;
};
export type TrackedPost = {
  tracking: { id: string; media_id?: string; is_active?: boolean };
  media: InstagramMedia;
  latest?: InsightSnapshot;
  snapshots?: InsightSnapshot[];
  analysis?: PostAnalysisView;
};
export type TrackedPostListResponse = { items: TrackedPost[] };
export type TrackingRecord = { id: string };

export type PerformanceMetrics = {
  views: MetricValue;
  reach: MetricValue;
  likes: MetricValue;
  comments: MetricValue;
  saves: MetricValue;
  shares: MetricValue;
  engagement_rate: MetricValue;
};
export type PerformancePost = {
  tracked_post_id: string;
  instagram_media_id: string;
  thumbnail_url?: string | null;
  published_at: string;
  media_type: string;
  media_type_label: string;
  mature: boolean;
  has_metrics: boolean;
  needs_refresh: boolean;
  metrics: PerformanceMetrics;
  rank: number | null;
  comparison_size: number;
};
export type Highlight = {
  label: "Highest reach" | "Lowest reach" | "Highest engagement" | "Lowest engagement";
  tracked_post_id: string;
  thumbnail_url?: string | null;
  published_at: string;
  metric: "reach" | "engagement_rate";
  value: number;
};
export type AccountInsights = {
  highlights: Highlight[];
  next_post_suggestion?: string | null;
  next_post_suggestion_status?: "ready" | "pending" | "none" | "consent_required";
  performance_posts: PerformancePost[];
  needs_refresh_after_hours: number;
  sync_status: "ok" | "failed" | "reconnect_required";
};
export type AccountInsightsData = AccountInsights;
export type AIProcessingConsent = {
  ai_processing_consented: boolean;
  ai_processing_consented_at: string | null;
};

export type PublishingCapability = { platform: SocialPlatform; available: boolean; reason?: string | null };
export type PublicationResult = {
  platform: SocialPlatform;
  status: "publishing" | "published" | "failed" | "unavailable";
  message: string;
  code?: string | null;
  permalink?: string;
  tracked_post_id?: string;
  provider_post_id?: string | null;
  publication_id?: string;
};
export type MediaAsset = {
  id: string;
  mime_type: ImageMimeType;
  original_filename: string;
  byte_size: number;
  status: "uploaded" | "ready" | "failed" | "deleted";
};
export type PostDraft = {
  id: string;
  media_asset_id?: string | null;
  target_platforms: SocialPlatform[];
  content_brief: string;
  goal: string;
  caption: string;
  hashtags: string[];
  status: "draft" | "publishing" | "published" | "failed";
  created_at: string;
  updated_at: string;
};
export type AccountContext = {
  account_theme: string;
  about_this_account: string;
  target_audience: string;
  tone_keys: string[];
  tone_other: string;
  content_formats: string[];
  caption_language: string;
  primary_category: string;
  primary_category_other: string;
  audience_age_ranges: string[];
  preferred_hashtags: string[];
};

export type CaptionMedia = Schemas["CaptionMedia"];
type CaptionRequest = Schemas["CaptionRequest"];
export type CaptionInput = Omit<
  CaptionRequest,
  "platforms" | "hashtag_count" | "use_account_context" | "image" | "media"
> &
  Partial<Pick<CaptionRequest, "platforms" | "hashtag_count" | "use_account_context" | "image" | "media">>;
export type CaptionResult = Schemas["CaptionResponse"];
