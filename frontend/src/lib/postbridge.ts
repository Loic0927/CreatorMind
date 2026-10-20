const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "postbridge.web.session";

export type Session = { accessToken: string; expiresAt: string; user: { id: string; email: string } };
export type Prediction = { views: number; engagement: number; insights: { analysis: string; strengths: string[]; weaknesses: string[]; recommendations: string[] } };
export type Connection = { connected: boolean; configured: boolean; username?: string; status?: string };
export type TrackedPost = { tracking: { id: string }; media: { id: string; caption: string; media_url?: string; thumbnail_url?: string; published_at: string }; latest?: { likes?: number; comments?: number; saves?: number; shares?: number; reach?: number; views?: number; engagement_rate?: number; captured_at?: string } };
export type TrackingRecord = { id: string };

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
export const getInstagramMedia = (session: Session) => authRequest<{ items: Array<{ id: string; caption: string; media_url?: string; thumbnail_url?: string }> }>(session, "/api/instagram/media");
export const trackInstagramPost = (session: Session, mediaId: string) => authRequest<TrackingRecord>(session, "/tracked-posts", { method: "POST", body: JSON.stringify({ media_id: mediaId }) });
export const refreshTrackedPost = (session: Session, trackedId: string) => authRequest<TrackedPost>(session, `/tracked-posts/${encodeURIComponent(trackedId)}/refresh`, { method: "POST" });
export const getHistory = (session: Session) => authRequest<{ items: Array<{ id: string; created_at: string; platform: string; content_type: string; views: number; engagement: number }> }>(session, "/history");
export const predict = (session: Session, payload: { platform: string; contentType: string; captionLength: number; hashtagsCount: number; postingHour: number }) => authRequest<Prediction>(session, "/predict", { method: "POST", body: JSON.stringify(payload) });
export const caption = (session: Session, payload: { information: string; goal: string }) => authRequest<{ caption: string; hashtags: string }>(session, "/mobile/caption", { method: "POST", body: JSON.stringify(payload) });
export const connectInstagram = (session: Session) => authRequest<{ authorization_url: string }>(session, "/api/instagram/connect/start?client=web", { method: "POST" });
export const logout = (session: Session) => authRequest(session, "/auth/logout", { method: "POST" });
export const deleteAccount = (session: Session) => authRequest(session, "/auth/account", { method: "DELETE" });
