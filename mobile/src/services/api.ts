import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { API_BASE_URL } from '../config/environment';
import { AccountInsightsData, ImageMimeType, InstagramConnection, InstagramMedia, SocialPlatform, TrackedPost } from '../types';

WebBrowser.maybeCompleteAuthSession();
export class ApiError extends Error { constructor(public code: string, message: string, public status: number) { super(message); } }
async function request<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}`, ...init?.headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) { const detail = payload.detail ?? payload; throw new ApiError(detail.code ?? 'request_failed', detail.message ?? 'PostBridge could not complete the request.', response.status); }
  return payload as T;
}
export const getConnection = (token: string) => request<InstagramConnection>('/api/instagram/connection', token);
export const getTrackedPosts = (token: string) => request<{ items: TrackedPost[] }>('/tracked-posts', token);
export const getTrackedPost = (token: string, id: string) => request<TrackedPost>(`/tracked-posts/${encodeURIComponent(id)}`, token);
export const getInstagramMedia = (token: string) => request<{ status: string; items: InstagramMedia[] }>('/api/instagram/media', token);
export const trackPost = (token: string, mediaId: string) => request<{ id: string }>('/tracked-posts', token, { method: 'POST', body: JSON.stringify({ media_id: mediaId }) });
export const refreshTrackedPost = (token: string, id: string) => request<TrackedPost>(`/tracked-posts/${encodeURIComponent(id)}/refresh`, token, { method: 'POST' });
export const getAccountInsights = (token: string) => request<AccountInsightsData>('/insights/account', token);
export type PublicationResult = { platform: SocialPlatform; status: 'published' | 'failed' | 'unavailable'; message: string; code?: string; permalink?: string; tracked_post_id?: string };
export const publishPost = (token: string, payload: { platforms: SocialPlatform[]; caption: string; hashtags: string; image: { mime_type: ImageMimeType; data: string } }) => request<{ results: PublicationResult[] }>('/publications', token, { method: 'POST', body: JSON.stringify(payload) });
export const disconnectInstagram = (token: string) => request('/api/instagram/connection', token, { method: 'DELETE' });
export const deleteAccount = (token: string) => request('/auth/account', token, { method: 'DELETE' });
export async function connectInstagram(token: string): Promise<void> {
  const result = await request<{ authorization_url: string }>('/api/instagram/connect/start', token, { method: 'POST' });
  const authResult = await WebBrowser.openAuthSessionAsync(result.authorization_url, Linking.createURL('instagram-connected'));
  if (authResult.type !== 'success') throw new ApiError('oauth_cancelled', 'Instagram connection was cancelled.', 400);
  const parsed = Linking.parse(authResult.url);
  if (parsed.queryParams?.status !== 'success') throw new ApiError(String(parsed.queryParams?.code ?? 'oauth_failed'), 'Instagram could not be connected. Please try again.', 400);
}
