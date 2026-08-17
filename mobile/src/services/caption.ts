import { API_BASE_URL, CAPTION_MODE } from '../config/environment';

export type CaptionInput = { information: string; goal: string };
export type CaptionResult = { caption: string; hashtags: string };

export function buildMockCaption(input: CaptionInput): CaptionResult {
  const information = input.information.trim();
  const goal = input.goal.trim();
  const caption = `${information}${goal ? `\n\nGoal: ${goal}.` : ''}\n\nWhat would you try first?`;
  const tags = information.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 3).slice(0, 3).map((word) => `#${word}`);
  return { caption, hashtags: [...new Set([...tags, '#contentcreator', '#creatormind'])].join(' ') };
}

export async function generateCaption(input: CaptionInput): Promise<CaptionResult> {
  if (CAPTION_MODE === 'mock') return Promise.resolve(buildMockCaption(input));
  // TODO(api-integration): Enable only after CreatorMind provides an authenticated
  // backend endpoint that calls the AI provider server-side.
  const response = await fetch(`${API_BASE_URL}/mobile/caption`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) });
  if (!response.ok) throw new Error('CreatorMind caption API is unavailable. Set EXPO_PUBLIC_CAPTION_MODE=mock for phase-one testing.');
  return response.json() as Promise<CaptionResult>;
}
