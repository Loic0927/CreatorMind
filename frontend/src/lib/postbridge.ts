const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "postbridge.web.session";

export type Session = { accessToken: string; expiresAt: string; user: { id: string; email: string } };
export type SocialPlatform = "Instagram" | "Twitter" | "Facebook" | "Threads" | "YouTube";
export type Connection = { connected: boolean; configured: boolean; username?: string; status?: string; session_synced_at?: string | null; sync_error?: string | null; comment_ingestion?: { enabled: boolean; permission_granted: boolean } };
export type InsightSnapshot = { id: string; likes?: number | null; comments?: number | null; saves?: number | null; shares?: number | null; reach?: number | null; views?: number | null; engagement_rate?: number | null; average_watch_time_ms?: number | null; total_watch_time_ms?: number | null; captured_at: string; metric_status?: Record<string, "available" | "unavailable" | "permission_required"> };
export type MetricKey = "views" | "reach" | "engagement_rate" | "shares" | "saves" | "comments";
export type RangeRow = { metric: MetricKey; value: number; usual_min: number; usual_max: number; status: "above" | "below" | "inside"; rank: number; group_size: number; band_start: number; band_end: number; marker: number };
export type AudienceComments = { state: "feature_off" | "reconnect_needed" | "access_denied" | "too_few" | "error" | "ready"; message?: string; description?: string };
export type PostAnalysisView = { comparable: boolean; comparable_count: number; summary?: string | null; stands_out: RangeRow[]; weaker: RangeRow[]; usual_ranges: RangeRow[]; audience_comments: AudienceComments; age_days: number; media_format: string };
export type TrackedPost = { tracking: { id: string; media_id?: string; is_active?: boolean }; media: { id: string; instagram_media_id?: string; media_type?: string; caption: string; media_url?: string; thumbnail_url?: string; permalink?: string | null; published_at: string }; latest?: InsightSnapshot; snapshots?: InsightSnapshot[]; analysis?: PostAnalysisView };
export type TrackingRecord = { id: string };
export type PublishingCapability = { platform: SocialPlatform; available: boolean; reason?: string | null };
export type PublicationResult = { platform: SocialPlatform; status: "publishing" | "published" | "failed" | "unavailable"; message: string; code?: string | null; permalink?: string; tracked_post_id?: string; provider_post_id?: string | null; publication_id?: string };
export type MediaAsset = { id: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; original_filename: string; byte_size: number; status: "uploaded" | "ready" | "failed" | "deleted" };
export type PostDraft = { id: string; media_asset_id?: string | null; target_platforms: SocialPlatform[]; content_brief: string; goal: string; caption: string; hashtags: string[]; status: "draft" | "publishing" | "published" | "failed"; created_at: string; updated_at: string };
export type AccountContext = { account_theme: string; about_this_account: string; target_audience: string; tone_keys: string[]; tone_other: string; content_formats: string[]; caption_language: string; primary_category: string; primary_category_other: string; audience_age_ranges: string[] };
export type PerformanceMetrics = { views: number | null; reach: number | null; likes: number | null; comments: number | null; saves: number | null; shares: number | null; engagement_rate: number | null };
export type PerformancePost = { tracked_post_id: string; instagram_media_id: string; thumbnail_url?: string | null; published_at: string; media_type: string; media_type_label: string; mature: boolean; has_metrics: boolean; needs_refresh: boolean; metrics: PerformanceMetrics; rank: number | null; comparison_size: number };
export type Highlight = { label: "Highest reach" | "Lowest reach" | "Highest engagement" | "Lowest engagement"; tracked_post_id: string; thumbnail_url?: string | null; published_at: string; metric: "reach" | "engagement_rate"; value: number };
export type AccountInsights = { highlights: Highlight[]; next_post_suggestion?: string | null; performance_posts: PerformancePost[]; needs_refresh_after_hours: number; sync_status: "ok" | "failed" | "reconnect_required" };

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
    if (!session.accessToken || new Date(session.expiresAt) <= new Date()) { window.localStorage.removeItem(STORAGE_KEY); return null; }
    return session;
  } catch { window.localStorage.removeItem(STORAGE_KEY); return null; }
}

export function saveSession(session: Session | null) { if (typeof window !== "undefined") session ? window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session)) : window.localStorage.removeItem(STORAGE_KEY); }
export async function requestCode(email: string) { return responseJson<{ sent: boolean; development_code?: string }>(await fetch(`${API_BASE_URL}/auth/request-code`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) })); }
export async function verifyCode(email: string, code: string): Promise<Session> { const result = await responseJson<{ access_token: string; expires_at: string; user: Session["user"] }>(await fetch(`${API_BASE_URL}/auth/verify-code`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, code }) })); return { accessToken: result.access_token, expiresAt: result.expires_at, user: result.user }; }
export async function authRequest<T>(session: Session, path: string, init?: RequestInit): Promise<T> { return responseJson<T>(await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.accessToken}`, ...init?.headers } })); }

export const getConnection = (session: Session) => authRequest<Connection>(session, "/api/instagram/connection");
export const getTrackedPosts = (session: Session) => authRequest<{ items: TrackedPost[] }>(session, "/tracked-posts");
export const getTrackedPost = (session: Session, trackedId: string) => authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}`);
export const getInstagramMedia = (session: Session) => authRequest<{ items: Array<{ id: string; caption: string; media_url?: string; thumbnail_url?: string }> }>(session, "/api/instagram/media");
export const trackInstagramPost = (session: Session, mediaId: string) => authRequest<TrackingRecord>(session, "/tracked-posts", { method: "POST", body: JSON.stringify({ media_id: mediaId }) });
export const refreshTrackedPost = (session: Session, trackedId: string) => authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/refresh`, { method: "POST" });
export const getAccountInsights = (session: Session) => authRequest<AccountInsights>(session, "/insights/account");
export type CaptionMedia = { mime_type: "image/jpeg" | "image/png" | "image/webp" | "video/mp4" | "video/webm" | "video/quicktime"; data: string; duration_seconds?: number };
export const caption = (session: Session, payload: { information: string; goal: string; platform: SocialPlatform; platforms: SocialPlatform[]; use_account_context: boolean; image?: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string }; media?: CaptionMedia }) => authRequest<{ caption: string; hashtags: string }>(session, "/mobile/caption", { method: "POST", body: JSON.stringify(payload) });
export const getPublishingCapabilities = (session: Session) => authRequest<{ items: PublishingCapability[] }>(session, "/publishing/capabilities");
export const publishPost = (session: Session, payload: { platforms: SocialPlatform[]; caption: string; hashtags: string; image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string } }) => authRequest<{ results: PublicationResult[] }>(session, "/publications", { method: "POST", body: JSON.stringify(payload) });
export const uploadMediaAsset = (session: Session, payload: { filename: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string }) => authRequest<MediaAsset>(session, "/media-assets", { method: "POST", body: JSON.stringify(payload) });
export const getDrafts = (session: Session) => authRequest<PostDraft[]>(session, "/drafts");
export const createDraft = (session: Session, payload: { media_asset_id?: string | null; target_platforms: SocialPlatform[]; content_brief: string; goal: string; caption: string; hashtags: string[] }) => authRequest<PostDraft>(session, "/drafts", { method: "POST", body: JSON.stringify(payload) });
export const updateDraft = (session: Session, draftId: string, payload: { media_asset_id?: string | null; target_platforms?: SocialPlatform[]; content_brief?: string; goal?: string; caption?: string; hashtags?: string[] }) => authRequest<PostDraft>(session, `/drafts/${encodeURIComponent(draftId)}`, { method: "PATCH", body: JSON.stringify(payload) });
export const publishDraft = (session: Session, draftId: string, payload: { platforms: SocialPlatform[]; idempotency_key: string }) => authRequest<{ draft: PostDraft; results: PublicationResult[] }>(session, `/drafts/${encodeURIComponent(draftId)}/publish`, { method: "POST", body: JSON.stringify(payload) });
export const connectInstagram = (session: Session) => authRequest<{ authorization_url: string }>(session, "/api/instagram/connect/start?client=web", { method: "POST" });
export const disconnectInstagram = (session: Session) => authRequest<{ disconnected: boolean }>(session, "/api/instagram/connection", { method: "DELETE" });
export const getAccountContext = (session: Session) => authRequest<AccountContext>(session, "/auth/account-context");
export const updateAccountContext = (session: Session, accountContext: AccountContext) => authRequest<AccountContext>(session, "/auth/account-context", { method: "PATCH", body: JSON.stringify(accountContext) });
export const suggestAccountContext = (session: Session) => authRequest<{ draft: AccountContext; source: { posts_considered: number; captions_considered: number; covers_available: number }; not_inferred: string[] }>(session, "/auth/account-context/suggest");
export const previewAccountContext = (session: Session, accountContext: AccountContext) => authRequest<{ label: string; caption: string; stored: boolean; used_for: string[]; not_used_for: string[] }>(session, "/auth/account-context/preview", { method: "POST", body: JSON.stringify(accountContext) });
export const logout = (session: Session) => authRequest(session, "/auth/logout", { method: "POST" });
export const deleteAccount = (session: Session) => authRequest(session, "/auth/account", { method: "DELETE" });
