const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "postbridge.web.session";

export type Session = { accessToken: string; expiresAt: string; user: { id: string; email: string } };
export type SocialPlatform = "Instagram" | "Twitter" | "Facebook" | "Threads" | "YouTube";
export type Connection = { connected: boolean; configured: boolean; username?: string; status?: string };
export type InsightSnapshot = { id: string; likes?: number | null; comments?: number | null; saves?: number | null; shares?: number | null; reach?: number | null; views?: number | null; engagement_rate?: number | null; captured_at: string };
export type PostAnalysis = {
  id: string;
  tracked_post_id: string;
  source_snapshot_id: string;
  source_snapshot_ids: string[];
  model_name: string;
  schema_version: string;
  observed_metrics: Record<string, number | null>;
  metric_deltas: Record<string, number | null>;
  content_payload: { platform?: string; media_type?: string; caption?: string; published_at?: string; visual_context_used?: boolean; visual_context_kind?: string };
  output_payload: {
    score?: { overall: number; grade: string; categories: Record<string, number> };
    score_context?: { account_average: number | null; points_difference: number | null; rank: number; total: number; percentile_label: string };
    executive_summary?: string[];
    top_insights?: Array<{ status: "strong" | "attention" | "neutral"; text: string }>;
    why_it_worked?: Array<{ title?: string; evidence?: string; interpretation?: string; why_it_matters?: string; factor?: string; estimated_impact?: string; explanation?: string }>;
    benchmarks?: Array<{ metric: string; current: number | null; average: number | null; percent_change: number | null; direction: string }>;
    risks?: string[];
    recommendations: Array<string | { action: string; reason: string; expected_outcome?: string; expected_impact?: string }>;
    confidence?: { score: number; level?: "High" | "Medium" | "Low"; inputs: Array<{ name: string; available: boolean; weight?: number; earned?: number; detail?: string | null }> };
    content_patterns?: Array<{ pattern: string; sample_size: number; average_score: number; difference_from_baseline: number }>;
    content_attributes?: { topic: string; thumbnail_style: string; caption_style: string; cta_usage: string };
    summary?: string; strengths?: string[]; concerns?: string[]; missing_inputs?: string[];
  };
  created_at: string;
};
export type TrackedPost = {
  tracking: { id: string };
  media: { id: string; media_type?: string; caption: string; media_url?: string; thumbnail_url?: string; published_at: string };
  latest?: InsightSnapshot;
  snapshots?: InsightSnapshot[];
  analyses?: PostAnalysis[];
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
export type PatternInsight = { label: string; average_score: number; posts: number; difference_from_baseline: number; category?: string };
export type AccountInsights = {
  sample_size: number;
  required_sample_size: number;
  progress: { topics: number; hashtags: number; thumbnails: number; posting_times: number };
  top_patterns: PatternInsight[];
  top_hashtags: PatternInsight[];
  thumbnail_insights: PatternInsight[];
  best_posting_times: PatternInsight[];
  winning_formula?: { topic?: string | null; thumbnail?: string | null; caption?: string | null; cta?: string | null; posting_time?: string | null; confidence: number } | null;
};

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
export const analyzeTrackedPost = (session: Session, trackedId: string) => authRequest<PostAnalysis>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/analyses`, { method: "POST" });
export const getAccountInsights = (session: Session) => authRequest<AccountInsights>(session, `/insights/patterns?timezone_offset_minutes=${new Date().getTimezoneOffset()}`);
export const caption = (session: Session, payload: { information: string; goal: string; platform: SocialPlatform; platforms: SocialPlatform[]; image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string } }) => authRequest<{ caption: string; hashtags: string }>(session, "/mobile/caption", { method: "POST", body: JSON.stringify(payload) });
export const getPublishingCapabilities = (session: Session) => authRequest<{ items: PublishingCapability[] }>(session, "/publishing/capabilities");
export const publishPost = (session: Session, payload: { platforms: SocialPlatform[]; caption: string; hashtags: string; image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string } }) => authRequest<{ results: PublicationResult[] }>(session, "/publications", { method: "POST", body: JSON.stringify(payload) });
export const uploadMediaAsset = (session: Session, payload: { filename: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string }) => authRequest<MediaAsset>(session, "/media-assets", { method: "POST", body: JSON.stringify(payload) });
export const getDrafts = (session: Session) => authRequest<PostDraft[]>(session, "/drafts");
export const createDraft = (session: Session, payload: { media_asset_id?: string | null; target_platforms: SocialPlatform[]; content_brief: string; goal: string; caption: string; hashtags: string[] }) => authRequest<PostDraft>(session, "/drafts", { method: "POST", body: JSON.stringify(payload) });
export const updateDraft = (session: Session, draftId: string, payload: { media_asset_id?: string | null; target_platforms?: SocialPlatform[]; content_brief?: string; goal?: string; caption?: string; hashtags?: string[] }) => authRequest<PostDraft>(session, `/drafts/${encodeURIComponent(draftId)}`, { method: "PATCH", body: JSON.stringify(payload) });
export const publishDraft = (session: Session, draftId: string, payload: { platforms: SocialPlatform[]; idempotency_key: string }) => authRequest<{ draft: PostDraft; results: PublicationResult[] }>(session, `/drafts/${encodeURIComponent(draftId)}/publish`, { method: "POST", body: JSON.stringify(payload) });
export const connectInstagram = (session: Session) => authRequest<{ authorization_url: string }>(session, "/api/instagram/connect/start?client=web", { method: "POST" });
export const logout = (session: Session) => authRequest(session, "/auth/logout", { method: "POST" });
export const deleteAccount = (session: Session) => authRequest(session, "/auth/account", { method: "DELETE" });
