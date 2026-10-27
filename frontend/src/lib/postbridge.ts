const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "postbridge.web.session";

export type Session = { accessToken: string; expiresAt: string; user: { id: string; email: string } };
export type SocialPlatform = "Instagram" | "Twitter" | "Facebook" | "Threads" | "YouTube";
export type Connection = { connected: boolean; configured: boolean; username?: string; status?: string };
export type InsightSnapshot = {
  id: string;
  likes?: number | null;
  comments?: number | null;
  saves?: number | null;
  shares?: number | null;
  reach?: number | null;
  views?: number | null;
  engagement_rate?: number | null;
  average_watch_time_ms?: number | null;
  total_watch_time_ms?: number | null;
  captured_at: string;
  metric_status?: Record<string, "available" | "unavailable" | "permission_required">;
  collection_type?: "manual_current" | "milestone";
  target_hour?: number | null;
  scheduled_for?: string | null;
};
export type TrackingMilestone = {
  target_hour: 1 | 3 | 6 | 12 | 24;
  scheduled_for: string;
  deadline_at: string;
  status: "pending" | "running" | "retry" | "completed" | "missed" | "cancelled" | "blocked_reauthorization" | "permission_required" | "unavailable";
  attempt_count: number;
  actual_captured_at?: string | null;
  snapshot?: InsightSnapshot | null;
  views_since_previous_snapshot?: number | null;
  error_code?: string | null;
};
export type PostPublishTracking = {
  automatic_collection: boolean;
  status: "scheduler_unavailable" | "tracking" | "complete" | "blocked_reauthorization" | "permission_required";
  next_capture_at?: string | null;
  milestones: TrackingMilestone[];
};
export type PostAnalysis = {
  id: string;
  tracked_post_id: string;
  source_snapshot_id: string;
  source_snapshot_ids: string[];
  model_name: string;
  schema_version: string;
  observed_metrics: Record<string, number | null>;
  metric_deltas: Record<string, number | null>;
  content_payload: { platform?: string; media_type?: string; caption?: string; published_at?: string; visual_context_used?: boolean; visual_context_kind?: string; account_context_used?: boolean; account_context_relevance?: "none" | "low" | "related" };
  output_payload: {
    score?: { overall: number; grade: string; categories: Record<string, number>; weights?: Record<string, number>; comparable?: boolean; method?: string; category_meanings?: Record<string, string> };
    score_context?: { account_average: number | null; points_difference: number | null; rank: number; total: number; percentile_label: string };
    conclusion?: string;
    verdict?: string;
    comparison_notice?: string | null;
    mature_reference?: { metric: string; current: number; median: number; sample_size: number; percent_of_median: number; text: string } | null;
    diluted_by_wider_reach?: boolean;
    strongest_metric?: MetricComparison | null;
    what_worked?: AnalysisFinding[];
    what_to_improve?: AnalysisFinding[];
    metric_comparisons?: MetricComparison[];
    experiment?: Array<{ test_variable: string; metric_to_watch: string; action: string; reason: string; comparison: string; decision_rule: string }>;
    methodology?: { noise_rule: string; significant_rule: string; ranking_basis: string };
    baseline?: { sample_size: number; available_account_posts: number; same_format_posts?: number; mature_sample_size?: number; maturity_threshold_hours?: number; comparison_ready?: boolean; is_mature_basis?: boolean; metric_coverage: number; group: string; label: string; age_basis?: string; current_post_age_hours?: number | null; statistic: string; secondary_statistic?: string; published_range: { start: string | null; end: string | null }; snapshot_range: { start: string | null; end: string | null }; limited_sample: boolean; sample_notice: string; limitations: string[] };
    executive_summary?: string[];
    top_insights?: Array<{ status: "strong" | "attention" | "neutral"; text: string }>;
    why_it_worked?: Array<{ title?: string; evidence?: string; interpretation?: string; why_it_matters?: string; classification?: string; factor?: string; estimated_impact?: string; explanation?: string }>;
    benchmarks?: MetricComparison[];
    trend?: { scope: string; status: string; growth_status?: string; observation_count: number; metric: string | null; start: string; end: string; span_hours: number; summary: string; metric_changes?: Record<string, number | null>; minimum_requirements: { observations: number; span_hours: number; interval_minutes: number } };
    risks?: string[];
    recommendations: Array<string | { action: string; reason: string; expected_outcome?: string; expected_impact?: string; test_variable?: string; metric_to_watch?: string; comparison?: string }>;
    evidence_quality?: { score?: number; level: "Strong" | "Moderate" | "Limited"; label?: string; meaning?: string; plain_language?: string; sample_size?: number; metric_fields?: number; snapshot_count?: number; visual_available?: boolean; inputs: Array<{ name: string; available: boolean; weight: number; earned: number; detail?: string | null }>; missing_evidence?: string[] };
    confidence?: { score: number; level?: "High" | "Medium" | "Low"; inputs: Array<{ name: string; available: boolean; weight?: number; earned?: number; detail?: string | null }> };
    data_gaps?: string[];
    content_patterns?: Array<{ pattern: string; sample_size: number; average_score: number; difference_from_baseline: number }>;
    content_attributes?: { thumbnail_style: string; caption_style: string; cta_usage: string; on_screen_text_hook?: string };
    content_snapshot?: { on_screen_text_hook: string; caption_length: string; cta: string; format: string; theme: string };
    similar_posts?: Array<{ tracked_post_id?: string | null; thumbnail_url?: string | null; title: string; theme: string; views: number | null; engagement_rate: number | null }>;
    summary?: string; strengths?: string[]; concerns?: string[]; missing_inputs?: string[];
  };
  created_at: string;
};
export type MetricComparison = { metric: string; current: number | null; average: number | null; median: number | null; sample_size: number; percent_change: number | null; percent_of_median?: number | null; absolute_difference?: number | null; direction: string; is_noise?: boolean; real_gap?: boolean; significant?: boolean; comparison_text?: string; rank?: number | null; group_size?: number; percentile?: number | null; percentile_label?: string; basis?: string };
export type AnalysisFinding = { metric: string; title: string; evidence: string; interpretation?: string | null; sample_size: number; basis: string; tone: "positive" | "neutral" | "improve" };
export type TrackedPost = {
  tracking: { id: string };
  media: { id: string; media_type?: string; caption: string; media_url?: string; thumbnail_url?: string; permalink?: string | null; published_at: string };
  latest?: InsightSnapshot;
  snapshots?: InsightSnapshot[];
  analyses?: PostAnalysis[];
  post_publish_tracking?: PostPublishTracking;
};
export type TrackingRecord = { id: string };
export type PublishingCapability = { platform: SocialPlatform; available: boolean; reason?: string | null };
export type PublicationResult = { platform: SocialPlatform; status: "publishing" | "published" | "failed" | "unavailable"; message: string; code?: string | null; permalink?: string; tracked_post_id?: string; provider_post_id?: string | null; publication_id?: string };
export type MediaAsset = { id: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; original_filename: string; byte_size: number; status: "uploaded" | "ready" | "failed" | "deleted" };
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
export type PatternInsight = {
  label: string;
  value: number;
  posts: number;
  comparison_posts?: number;
  baseline: number;
  difference: number;
  basis: string;
  sample_note: string;
  metric_label: string;
  distribution: { minimum: number; median: number; maximum: number };
  category?: string | null;
  average_score: number;
  baseline_score: number;
  difference_from_baseline: number;
  benchmark: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  confidence_label: string;
  confidence_meaning: string;
  evidence: string;
  difference_interpretation: string;
};
export type AccountContext = {
  account_theme: string;
  about_this_account: string;
  target_audience: string;
};
export type ContentOpportunity = {
  title: string;
  priority: number;
  status: "DATA_GAP" | "HYPOTHESIS";
  current_observation: string;
  sample_size: number;
  observation_period: { start?: string | null; end?: string | null };
  data_gap: string;
  suggested_test: string;
  primary_variable: string;
  tracking_metric: string;
  capture_timing: string;
  decision_method: string;
  repetitions_required: number;
  effect_estimate?: number | null;
  effect_estimate_label?: string;
};
export type PerformanceMetrics = { views: number | null; reach: number | null; likes: number | null; comments: number | null; saves: number | null; shares: number | null; engagement_rate: number | null; average_watch_time_ms?: number | null; total_watch_time_ms?: number | null };
export type PerformanceMilestone = {
  target_hour: 1 | 3 | 6 | 12 | 24;
  status: string;
  scheduled_for?: string | null;
  captured_at?: string | null;
  tracking_period_hours?: number | null;
  metrics?: PerformanceMetrics | null;
  metric_status: Record<string, "available" | "unavailable" | "permission_required">;
  views_since_previous_snapshot?: number | null;
};
export type PerformancePost = {
  tracked_post_id?: string | null;
  instagram_media_id: string;
  permalink?: string | null;
  media_type: string;
  media_type_label: string;
  thumbnail_url?: string | null;
  theme: string;
  topic?: string;
  published_at: string;
  posting_window: string;
  caption_excerpt: string;
  display_title?: string;
  observation_kind: "Mature lifetime snapshot" | "Latest cumulative snapshot" | "No snapshot";
  comparison_basis: string;
  mature: boolean;
  age_days?: number | null;
  snapshot_captured_at?: string | null;
  tracking_period_hours?: number | null;
  metrics?: PerformanceMetrics | null;
  metric_status: Record<string, "available" | "unavailable" | "permission_required">;
  milestones: PerformanceMilestone[];
  historical_backfill_unavailable: boolean;
  comparison?: { rank: number; group_size: number; metric: "views" | "reach"; group: string } | null;
};
export type AccountInsights = {
  sample_size: number;
  required_sample_size: number;
  enough_data: boolean;
  heading: string;
  sample_notice: string;
  confidence_explanation?: string;
  observation_period: { start?: string | null; end?: string | null; timezone: string };
  progress: { patterns: number; posting_times: number; mature_posts: number };
  themes: string[];
  theme_stats: Array<{ name: string; post_count: number; median_views: number | null }>;
  theme_method: string;
  patterns: PatternInsight[];
  posting_time_insights: PatternInsight[];
  untested_posting_windows: string[];
  posting_time_metadata: { timezone: string; period_start?: string | null; period_end?: string | null; metric: string; complete_posts: number; incomplete_posts: number };
  tracking_24h: { available: boolean; complete_posts: number; total_posts: number; target_hours: number[]; automatic_collection: boolean; pending_posts: number; blocked_posts: number; unavailable_posts: number; status: "LIMITED" | "AVAILABLE"; message: string; reason: string };
  metric_capabilities: {
    account_requirement: string;
    required_scope: string;
    definitions: { views: string; reach: string };
    currently_collected: string[];
    advanced_metrics: Array<{ key: string; status: "collected_when_available" | "unavailable"; reason: string }>;
  };
  performance_posts: PerformancePost[];
  performance_summary?: { media_type: string; media_type_label: string; sample_size: number; reach_sample_size: number; engagement_rate_sample_size: number; reach_median: number; engagement_rate_median: number; highest_reach: PerformanceSummaryItem; lowest_reach: PerformanceSummaryItem; highest_engagement_rate: PerformanceSummaryItem; lowest_engagement_rate: PerformanceSummaryItem } | null;
  show_average_watch_time: boolean;
  historical_backfill_note: boolean;
  content_opportunities: ContentOpportunity[];
  tested_combination?: (PatternInsight & { label_type: string; caution: string }) | null;
  methodology: { default_basis: string; pattern_rule: string; advanced_basis: string };
};
export type PerformanceSummaryItem = { kind: "highest_reach" | "lowest_reach" | "highest_engagement_rate" | "lowest_engagement_rate"; title: string; value: number; difference: number; metric: "reach" | "engagement_rate"; note?: string | null };

async function responseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? payload;
    throw new Error(detail.message ?? (typeof detail === "string" ? detail : "PostBridge could not complete the request."));
  }
  return payload as T;
}

export function storedSession(): Session | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(STORAGE_KEY);
  if (!value) return null;
  try {
    const session = JSON.parse(value) as Session;
    if (!session.accessToken || new Date(session.expiresAt) <= new Date()) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveSession(session: Session | null) {
  if (typeof window === "undefined") return;
  if (session) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else window.localStorage.removeItem(STORAGE_KEY);
}

export async function requestCode(email: string) {
  return responseJson<{ sent: boolean; development_code?: string }>(await fetch(`${API_BASE_URL}/auth/request-code`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) }));
}

export async function verifyCode(email: string, code: string): Promise<Session> {
  const result = await responseJson<{ access_token: string; expires_at: string; user: Session["user"] }>(await fetch(`${API_BASE_URL}/auth/verify-code`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, code }) }));
  return { accessToken: result.access_token, expiresAt: result.expires_at, user: result.user };
}

export async function authRequest<T>(session: Session, path: string, init?: RequestInit): Promise<T> {
  return responseJson<T>(await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.accessToken}`, ...init?.headers } }));
}

export const getConnection = (session: Session) => authRequest<Connection>(session, "/api/instagram/connection");
export const getTrackedPosts = (session: Session) => authRequest<{ items: TrackedPost[] }>(session, "/tracked-posts");
export const getTrackedPost = (session: Session, trackedId: string) => authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}`);
export const getInstagramMedia = (session: Session) => authRequest<{ items: Array<{ id: string; caption: string; media_url?: string; thumbnail_url?: string }> }>(session, "/api/instagram/media");
export const trackInstagramPost = (session: Session, mediaId: string) => authRequest<TrackingRecord>(session, "/tracked-posts", { method: "POST", body: JSON.stringify({ media_id: mediaId }) });
export const refreshTrackedPost = (session: Session, trackedId: string) => authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/refresh`, { method: "POST" });
export const analyzeTrackedPost = (session: Session, trackedId: string, useAccountContext = true) => authRequest<PostAnalysis>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/analyses?use_account_context=${useAccountContext}`, { method: "POST" });
export const getAccountInsights = (session: Session) => authRequest<AccountInsights>(session, `/insights/patterns?timezone_offset_minutes=${new Date().getTimezoneOffset()}`);
export const regenerateInsightThemes = (session: Session) => authRequest<{ themes: string[] }>(session, "/insights/themes/regenerate", { method: "POST" });
export const caption = (session: Session, payload: { information: string; goal: string; platform: SocialPlatform; platforms: SocialPlatform[]; use_account_context: boolean; image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string } }) => authRequest<{ caption: string; hashtags: string }>(session, "/mobile/caption", { method: "POST", body: JSON.stringify(payload) });
export const getPublishingCapabilities = (session: Session) => authRequest<{ items: PublishingCapability[] }>(session, "/publishing/capabilities");
export const publishPost = (session: Session, payload: { platforms: SocialPlatform[]; caption: string; hashtags: string; image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string } }) => authRequest<{ results: PublicationResult[] }>(session, "/publications", { method: "POST", body: JSON.stringify(payload) });
export const uploadMediaAsset = (session: Session, payload: { filename: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string }) => authRequest<MediaAsset>(session, "/media-assets", { method: "POST", body: JSON.stringify(payload) });
export const getDrafts = (session: Session) => authRequest<PostDraft[]>(session, "/drafts");
export const createDraft = (session: Session, payload: { media_asset_id?: string | null; target_platforms: SocialPlatform[]; content_brief: string; goal: string; caption: string; hashtags: string[] }) => authRequest<PostDraft>(session, "/drafts", { method: "POST", body: JSON.stringify(payload) });
export const updateDraft = (session: Session, draftId: string, payload: { media_asset_id?: string | null; target_platforms?: SocialPlatform[]; content_brief?: string; goal?: string; caption?: string; hashtags?: string[] }) => authRequest<PostDraft>(session, `/drafts/${encodeURIComponent(draftId)}`, { method: "PATCH", body: JSON.stringify(payload) });
export const publishDraft = (session: Session, draftId: string, payload: { platforms: SocialPlatform[]; idempotency_key: string }) => authRequest<{ draft: PostDraft; results: PublicationResult[] }>(session, `/drafts/${encodeURIComponent(draftId)}/publish`, { method: "POST", body: JSON.stringify(payload) });
export const connectInstagram = (session: Session) => authRequest<{ authorization_url: string }>(session, "/api/instagram/connect/start?client=web", { method: "POST" });
export const getAccountContext = (session: Session) => authRequest<AccountContext>(session, "/auth/account-context");
export const updateAccountContext = (session: Session, accountContext: AccountContext) => authRequest<AccountContext>(session, "/auth/account-context", { method: "PATCH", body: JSON.stringify(accountContext) });
export const logout = (session: Session) => authRequest(session, "/auth/logout", { method: "POST" });
export const deleteAccount = (session: Session) => authRequest(session, "/auth/account", { method: "DELETE" });
