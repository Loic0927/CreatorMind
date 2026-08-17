export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
export const API_ENVIRONMENT = process.env.EXPO_PUBLIC_API_ENV ?? 'local';
export const CAPTION_MODE = process.env.EXPO_PUBLIC_CAPTION_MODE === 'api' ? 'api' : 'mock';
