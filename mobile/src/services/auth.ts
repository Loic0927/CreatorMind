import * as SecureStore from 'expo-secure-store';

const SESSION_KEY = 'creatormind.mobile.session';
export type Session = { email: string; mode: 'demo' };

export async function getSession(): Promise<Session | null> {
  const value = await SecureStore.getItemAsync(SESSION_KEY);
  if (!value) return null;
  try { return JSON.parse(value) as Session; } catch { await SecureStore.deleteItemAsync(SESSION_KEY); return null; }
}

export async function saveDemoSession(email: string): Promise<Session> {
  const session: Session = { email, mode: 'demo' };
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
  return session;
}

export async function clearSession(): Promise<void> { await SecureStore.deleteItemAsync(SESSION_KEY); }
