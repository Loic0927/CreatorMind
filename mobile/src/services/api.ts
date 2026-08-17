import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { API_BASE_URL } from '../config/environment';
import { InsightsData, InstagramConnection, InstagramMedia, TrackedPost } from '../types';

WebBrowser.maybeCompleteAuthSession();

export class ApiError extends Error { constructor(public code: string, message: string, public status: number) { super(message); } }

async function request<T>(path: string, userId: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', 'X-User-Id': userId, ...init?.headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) { const detail = payload.detail ?? payload; throw new ApiError(detail.code ?? 'request_failed', detail.message ?? 'CreatorMind could not complete the request.', response.status); }
  return payload as T;
}

export const getConnection = (userId: string) => request<InstagramConnection>('/api/instagram/connection', userId);
export const getTrackedPosts = (userId: string) => request<{ items: TrackedPost[] }>('/tracked-posts', userId);
export const getTrackedPost = (userId: string, id: string) => request<TrackedPost>(`/tracked-posts/${id}`, userId);
export const getInstagramMedia = (userId: string) => request<{ status: string; items: InstagramMedia[] }>('/api/instagram/media', userId);
export const trackPost = (userId: string, mediaId: string) => request('/tracked-posts', userId, { method: 'POST', body: JSON.stringify({ media_id: mediaId }) });
export const stopTracking = (userId: string, id: string) => request(`/tracked-posts/${id}`, userId, { method: 'DELETE' });
export const refreshTrackedPost = (userId: string, id: string) => request(`/tracked-posts/${id}/refresh`, userId, { method: 'POST' });
export const getInstagramInsights = (userId: string) => request<InsightsData>('/insights/instagram?period=7d', userId);
export const disconnectInstagram = (userId: string) => request('/api/instagram/connection', userId, { method: 'DELETE' });
export async function connectInstagram(userId: string): Promise<void> {
  const result = await request<{ authorization_url: string }>('/api/instagram/connect/start', userId, { method: 'POST' });
  const authResult = await WebBrowser.openAuthSessionAsync(result.authorization_url, Linking.createURL('instagram-connected'));
  if (authResult.type !== 'success') throw new ApiError('oauth_cancelled', 'Instagram connection was cancelled.', 400);
}
