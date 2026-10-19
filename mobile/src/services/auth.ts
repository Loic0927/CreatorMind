import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL } from '../config/environment';

const SESSION_KEY = 'postbridge.mobile.session';

export type Session = {
  accessToken: string;
  expiresAt: string;
  user: { id: string; email: string };
};

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? payload;
    throw new Error(detail.message ?? 'PostBridge could not complete the request.');
  }
  return payload as T;
}

export async function getSession(): Promise<Session | null> {
  const value = await SecureStore.getItemAsync(SESSION_KEY);
  if (!value) return null;
  try {
    const session = JSON.parse(value) as Session;
    if (!session.accessToken || !session.user?.id || new Date(session.expiresAt) <= new Date()) {
      await clearSession();
      return null;
    }
    return session;
  } catch {
    await clearSession();
    return null;
  }
}

export async function requestLoginCode(email: string): Promise<{ developmentCode?: string }> {
  const result = await json<{ development_code?: string }>('/auth/request-code', {
    method: 'POST', body: JSON.stringify({ email }),
  });
  return { developmentCode: result.development_code };
}

export async function verifyLoginCode(email: string, code: string): Promise<Session> {
  const result = await json<{ access_token: string; expires_at: string; user: Session['user'] }>('/auth/verify-code', {
    method: 'POST', body: JSON.stringify({ email, code }),
  });
  const session: Session = { accessToken: result.access_token, expiresAt: result.expires_at, user: result.user };
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED,
  });
  return session;
}

export async function logout(session: Session): Promise<void> {
  try {
    await json('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${session.accessToken}` } });
  } finally {
    await clearSession();
  }
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}
