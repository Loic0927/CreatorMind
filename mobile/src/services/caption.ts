import { API_BASE_URL, CAPTION_MODE } from '../config/environment';
import { ImageMimeType, SocialPlatform } from '../types';

export type CaptionInput = {
  information: string;
  goal: string;
  platform: SocialPlatform;
  image: { mime_type: ImageMimeType; data: string };
};
export type CaptionResult = { caption: string; hashtags: string };

export function buildMockCaption(input: CaptionInput): CaptionResult {
  const information = input.information.trim();
  const goal = input.goal.trim();
  const caption = `${information}${goal ? `\n\nGoal: ${goal}.` : ''}\n\nWhat would you try first?`;
  const tags = information.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 3).slice(0, 3).map((word) => `#${word}`);
  return { caption, hashtags: [...new Set([...tags, '#contentcreator', '#postbridge'])].join(' ') };
}

export async function generateCaption(input: CaptionInput, accessToken?: string): Promise<CaptionResult> {
  if (CAPTION_MODE === 'mock') return Promise.resolve(buildMockCaption(input));
  if (!accessToken) throw new Error('Please sign in again.');
  const response = await fetch(`${API_BASE_URL}/mobile/caption`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(input) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload?.detail?.message ?? 'PostBridge caption generation is unavailable.');
  }
  return response.json() as Promise<CaptionResult>;
}
