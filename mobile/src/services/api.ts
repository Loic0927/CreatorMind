import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { API_BASE_URL } from '../config/environment';
import { AccountInsightsData, CommentInsights, First24Hours, First24Payload, ImageMimeType, InsightsData, InstagramConnection, InstagramMedia, PostAnalysis, SocialPlatform, TrackedPost } from '../types';

WebBrowser.maybeCompleteAuthSession();

export class ApiError extends Error { constructor(public code: string, message: string, public status: number) { super(message); } }

async function request<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}`, ...init?.headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) { const detail = payload.detail ?? payload; throw new ApiError(detail.code ?? 'request_failed', detail.message ?? 'PostBridge could not complete the request.', response.status); }
  return payload as T;
}

export const getConnection = (userId: string) => request<InstagramConnection>('/api/instagram/connection', userId);
export const getTrackedPosts = (userId: string) => request<{ items: TrackedPost[] }>('/tracked-posts', userId);
export const getTrackedPost = (userId: string, id: string) => request<TrackedPost>(`/tracked-posts/${id}`, userId);
export const getInstagramMedia = (userId: string) => request<{ status: string; items: InstagramMedia[] }>('/api/instagram/media', userId);
export const trackPost = (userId: string, mediaId: string) => request('/tracked-posts', userId, { method: 'POST', body: JSON.stringify({ media_id: mediaId }) });
export const stopTracking = (userId: string, id: string) => request(`/tracked-posts/${id}`, userId, { method: 'DELETE' });
export const refreshTrackedPost = (userId: string, id: string) => request(`/tracked-posts/${id}/refresh`, userId, { method: 'POST' });
export const refreshTrackedPostComments = (userId: string, id: string) => request<CommentInsights>(`/tracked-posts/${id}/comments/refresh`, userId, { method: 'POST' });
export const setComparisonExclusion = (userId: string, id: string, excluded: boolean) => request(`/tracked-posts/${id}`, userId, { method: 'PATCH', body: JSON.stringify({ exclude_from_comparisons: excluded }) });
export const extractFirst24Screenshots = (userId: string, id: string, screenshots: { filename: string; mime_type: ImageMimeType; data: string }[]) => request<{ candidate: First24Payload; validation: { mismatch_pct: number | null; possible_wrong_post: boolean; warning?: string | null }; upload_token: string }>(`/tracked-posts/${id}/first-24-hours/extract`, userId, { method: 'POST', body: JSON.stringify({ screenshots }) });
export const confirmFirst24Screenshots = (userId: string, id: string, payload: { upload_token: string; payload: First24Payload; keep_screenshots: boolean }) => request<{ first_24_hours: First24Hours }>(`/tracked-posts/${id}/first-24-hours/confirm`, userId, { method: 'POST', body: JSON.stringify(payload) });
export const analyzeTrackedPost = (userId: string, id: string) => request<PostAnalysis>(`/tracked-posts/${id}/analyses`, userId, { method: 'POST' });
export type PublicationResult = { platform: SocialPlatform; status: 'published' | 'failed' | 'unavailable'; message: string; code?: string; permalink?: string; tracked_post_id?: string };
export const publishPost = (userId: string, payload: { platforms: SocialPlatform[]; caption: string; hashtags: string; image: { mime_type: ImageMimeType; data: string } }) => request<{ results: PublicationResult[] }>('/publications', userId, { method: 'POST', body: JSON.stringify(payload) });
export const getInstagramInsights = (userId: string) => request<InsightsData>('/insights/instagram?period=7d', userId);
export const getAccountInsights = (userId: string) => request<AccountInsightsData>(`/insights/patterns?timezone_offset_minutes=${new Date().getTimezoneOffset()}`, userId);
export const queueMetricsBackfill = (userId: string) => request<{ eligible: number; queued: number; already_queued: number }>('/insights/metrics-backfill', userId, { method: 'POST' });
export const regenerateInsightThemes = (userId: string) => request<{ themes: string[] }>('/insights/themes/regenerate', userId, { method: 'POST' });
export const disconnectInstagram = (userId: string) => request('/api/instagram/connection', userId, { method: 'DELETE' });
export const deleteAccount = (accessToken: string) => request('/auth/account', accessToken, { method: 'DELETE' });

export async function connectInstagram(userId: string): Promise<void> {
  const result = await request<{ authorization_url: string }>('/api/instagram/connect/start', userId, { method: 'POST' });
  const returnUri = Linking.createURL('instagram-connected');
  const authResult = await WebBrowser.openAuthSessionAsync(result.authorization_url, returnUri);
  if (authResult.type !== 'success') throw new ApiError('oauth_cancelled', 'Instagram connection was cancelled.', 400);
  const parsed = Linking.parse(authResult.url);
  const status = typeof parsed.queryParams?.status === 'string' ? parsed.queryParams.status : '';
  const code = typeof parsed.queryParams?.code === 'string' ? parsed.queryParams.code : 'oauth_failed';
  if (status !== 'success') throw new ApiError(code, 'Instagram could not be connected. Please try again.', 400);
}
