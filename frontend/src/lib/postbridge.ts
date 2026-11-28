const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "postbridge.web.session";
import type {
  AccountContext,
  AccountInsights,
  AIProcessingConsent,
  AudienceComment,
  AudienceComments,
  AuthIntent,
  CaptionInput,
  CaptionMedia,
  ComparisonBasis,
  Connection,
  Highlight,
  InsightSnapshot,
  MediaAsset,
  MetricKey,
  NotComparableReason,
  PostDraft,
  PostAnalysisView,
  PerformancePost,
  PerformanceMetrics,
  PublicationResult,
  PublishingCapability,
  RangeRow,
  Session,
  SocialPlatform,
  SummaryStatus,
  TikTokConnection,
  TikTokAnalysisRow,
  TikTokMetricKey,
  TikTokPostAnalysis,
  TikTokTrackedPost,
  TrackingRecord,
  TrackedPost,
} from "../../../shared/api";
export type {
  AccountContext,
  AccountInsights,
  AIProcessingConsent,
  AudienceComment,
  AudienceComments,
  AuthIntent,
  CaptionInput,
  CaptionMedia,
  ComparisonBasis,
  Connection,
  Highlight,
  InsightSnapshot,
  MediaAsset,
  MetricKey,
  NotComparableReason,
  PostDraft,
  PostAnalysisView,
  PerformancePost,
  PerformanceMetrics,
  PublicationResult,
  PublishingCapability,
  RangeRow,
  Session,
  SocialPlatform,
  SummaryStatus,
  TikTokConnection,
  TikTokAnalysisRow,
  TikTokMetricKey,
  TikTokPostAnalysis,
  TikTokTrackedPost,
  TrackingRecord,
  TrackedPost,
};

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function responseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? payload;
    throw new ApiError(
      typeof detail === "object" && detail?.code ? String(detail.code) : "request_failed",
      detail.message ?? (typeof detail === "string" ? detail : "PostBridge could not complete the request."),
      response.status,
    );
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
  if (typeof window !== "undefined")
    session
      ? window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
      : window.localStorage.removeItem(STORAGE_KEY);
}
export async function requestCode(email: string, intent: AuthIntent = "sign_in") {
  return responseJson<{ sent: boolean; development_code?: string }>(
    await fetch(`${API_BASE_URL}/auth/request-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, intent }),
    }),
  );
}
export type VerifyCodeOptions = {
  intent?: AuthIntent;
  privacyTermsAccepted?: boolean;
  aiProcessingConsent?: boolean;
};

export async function verifyCode(email: string, code: string, options: VerifyCodeOptions = {}): Promise<Session> {
  const result = await responseJson<{ access_token: string; expires_at: string; user: Session["user"] }>(
    await fetch(`${API_BASE_URL}/auth/verify-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        code,
        intent: options.intent ?? "sign_in",
        privacy_terms_accepted: options.privacyTermsAccepted ?? false,
        ai_processing_consent: options.aiProcessingConsent ?? false,
      }),
    }),
  );
  return { accessToken: result.access_token, expiresAt: result.expires_at, user: result.user };
}
export async function authRequest<T>(session: Session, path: string, init?: RequestInit): Promise<T> {
  return responseJson<T>(
    await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.accessToken}`, ...init?.headers },
    }),
  );
}

export const getConnection = (session: Session) => authRequest<Connection>(session, "/api/instagram/connection");
export const getTikTokConnection = (session: Session) =>
  authRequest<TikTokConnection>(session, "/api/tiktok/connection");
export const getTikTokMedia = (session: Session) =>
  authRequest<{
    items: Array<{
      id: string;
      caption: string;
      thumbnail_url?: string;
      permalink?: string;
      published_at?: number | string;
    }>;
  }>(session, "/api/tiktok/media");
export const getTikTokTrackedPosts = (session: Session) =>
  authRequest<{ items: TikTokTrackedPost[] }>(session, "/api/tiktok/tracked");
export const trackTikTokPost = (session: Session, videoId: string) =>
  authRequest<TikTokTrackedPost>(session, "/api/tiktok/tracked", {
    method: "POST",
    body: JSON.stringify({ video_id: videoId }),
  });
export const getTikTokTrackedPost = (session: Session, trackedId: string) =>
  authRequest<TikTokTrackedPost>(session, `/api/tiktok/tracked/${encodeURIComponent(trackedId)}`);
export const refreshTikTokTrackedPost = (session: Session, trackedId: string) =>
  authRequest<TikTokTrackedPost>(session, `/api/tiktok/tracked/${encodeURIComponent(trackedId)}/refresh`, {
    method: "POST",
  });
export const deleteTikTokTrackedPost = (session: Session, trackedId: string) =>
  authRequest<{ stopped: boolean }>(session, `/api/tiktok/tracked/${encodeURIComponent(trackedId)}`, {
    method: "DELETE",
  });
export const getTrackedPosts = (session: Session) => authRequest<{ items: TrackedPost[] }>(session, "/tracked-posts");
export const getTrackedPost = (session: Session, trackedId: string) =>
  authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}`);
export const getInstagramMedia = (session: Session) =>
  authRequest<{
    items: Array<{
      id: string;
      instagram_media_id?: string;
      caption: string;
      media_url?: string;
      thumbnail_url?: string;
      permalink?: string | null;
      published_at?: string;
    }>;
  }>(session, "/api/instagram/media");
export const trackInstagramPost = (session: Session, mediaId: string) =>
  authRequest<TrackingRecord>(session, "/tracked-posts", {
    method: "POST",
    body: JSON.stringify({ media_id: mediaId }),
  });
export const deleteTrackedPost = (session: Session, trackedId: string) =>
  authRequest<{ stopped: boolean }>(session, `/tracked-posts/${encodeURIComponent(trackedId)}`, { method: "DELETE" });
export const refreshTrackedPost = (session: Session, trackedId: string) =>
  authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/refresh`, { method: "POST" });
export const getAccountInsights = (session: Session) => authRequest<AccountInsights>(session, "/insights/account");
export const getAIProcessingConsent = (session: Session) =>
  authRequest<AIProcessingConsent>(session, "/auth/ai-processing-consent");
export const grantAIProcessingConsent = (session: Session) =>
  authRequest<AIProcessingConsent>(session, "/auth/ai-processing-consent", { method: "POST" });
export const revokeAIProcessingConsent = (session: Session) =>
  authRequest<AIProcessingConsent>(session, "/auth/ai-processing-consent", { method: "DELETE" });
export const caption = (
  session: Session,
  payload: {
    information: string;
    goal: string;
    platform: SocialPlatform;
    platforms: SocialPlatform[];
    use_account_context: boolean;
    hashtag_count: number;
    image?: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string };
    media?: CaptionMedia;
  },
) =>
  authRequest<{ caption: string; hashtags: string }>(session, "/mobile/caption", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const getPublishingCapabilities = (session: Session) =>
  authRequest<{ items: PublishingCapability[] }>(session, "/publishing/capabilities");
export const publishPost = (
  session: Session,
  payload: {
    platforms: SocialPlatform[];
    caption: string;
    hashtags: string;
    image: { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string };
  },
) =>
  authRequest<{ results: PublicationResult[] }>(session, "/publications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const uploadMediaAsset = (
  session: Session,
  payload: { filename: string; mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string },
) => authRequest<MediaAsset>(session, "/media-assets", { method: "POST", body: JSON.stringify(payload) });
export const getDrafts = (session: Session) => authRequest<PostDraft[]>(session, "/drafts");
export const createDraft = (
  session: Session,
  payload: {
    media_asset_id?: string | null;
    target_platforms: SocialPlatform[];
    content_brief: string;
    goal: string;
    caption: string;
    hashtags: string[];
  },
) => authRequest<PostDraft>(session, "/drafts", { method: "POST", body: JSON.stringify(payload) });
export const updateDraft = (
  session: Session,
  draftId: string,
  payload: {
    media_asset_id?: string | null;
    target_platforms?: SocialPlatform[];
    content_brief?: string;
    goal?: string;
    caption?: string;
    hashtags?: string[];
  },
) =>
  authRequest<PostDraft>(session, `/drafts/${encodeURIComponent(draftId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
export const publishDraft = (
  session: Session,
  draftId: string,
  payload: { platforms: SocialPlatform[]; idempotency_key: string },
) =>
  authRequest<{ draft: PostDraft; results: PublicationResult[] }>(
    session,
    `/drafts/${encodeURIComponent(draftId)}/publish`,
    { method: "POST", body: JSON.stringify(payload) },
  );
export const connectInstagram = (session: Session) =>
  authRequest<{ authorization_url: string }>(session, "/api/instagram/connect/start?client=web", { method: "POST" });
export const disconnectInstagram = (session: Session) =>
  authRequest<{ disconnected: boolean }>(session, "/api/instagram/connection", { method: "DELETE" });
export const connectTikTok = (session: Session) =>
  authRequest<{ authorization_url: string }>(session, "/api/tiktok/connect/start?client=web", { method: "POST" });
export const disconnectTikTok = (session: Session) =>
  authRequest<{ disconnected: boolean }>(session, "/api/tiktok/connection", { method: "DELETE" });
export const getAccountContext = (session: Session) => authRequest<AccountContext>(session, "/auth/account-context");
export const updateAccountContext = (session: Session, accountContext: AccountContext) =>
  authRequest<AccountContext>(session, "/auth/account-context", {
    method: "PATCH",
    body: JSON.stringify(accountContext),
  });
export const suggestAccountContext = (session: Session) =>
  authRequest<{
    draft: AccountContext;
    source: { posts_considered: number; captions_considered: number; covers_available: number };
    not_inferred: string[];
  }>(session, "/auth/account-context/suggest");
export const logout = (session: Session) => authRequest(session, "/auth/logout", { method: "POST" });
export const deleteAccount = (session: Session) => authRequest(session, "/auth/account", { method: "DELETE" });
