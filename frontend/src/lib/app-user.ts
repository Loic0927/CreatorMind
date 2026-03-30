"use client";

const STORAGE_KEY = "creatormind_user_id";

export function getOrCreateAppUserId(): string {
  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const nextId =
    typeof window.crypto !== "undefined" && "randomUUID" in window.crypto
      ? window.crypto.randomUUID()
      : `user-${Date.now()}`;

  window.localStorage.setItem(STORAGE_KEY, nextId);
  return nextId;
}
