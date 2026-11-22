export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const API_ENVIRONMENT = process.env.EXPO_PUBLIC_API_ENV ?? "local";
export const CAPTION_MODE = process.env.EXPO_PUBLIC_CAPTION_MODE === "mock" ? "mock" : "api";
export const WEB_BASE_URL = (process.env.EXPO_PUBLIC_WEB_URL ?? "https://postbridge.dev").replace(/\/$/, "");
export const legalUrl = (path: "/privacy" | "/terms") => `${WEB_BASE_URL}${path}`;
