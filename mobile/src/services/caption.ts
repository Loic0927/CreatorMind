import { API_BASE_URL, CAPTION_MODE } from "../config/environment";
import type { CaptionInput, CaptionResult } from "../types";

export type { CaptionInput, CaptionResult } from "../types";

export class CaptionGenerationError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "CaptionGenerationError";
  }
}

export function buildMockCaption(input: CaptionInput): CaptionResult {
  const information = input.information.trim();
  const goal = input.goal.trim();
  const caption = `${information}${goal ? `\n\nGoal: ${goal}.` : ""}\n\nWhat would you try first?`;
  const tags = information
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 3)
    .slice(0, 3)
    .map((word) => `#${word}`);
  const count = input.hashtag_count ?? 5;
  return { caption, hashtags: [...new Set([...tags, "#contentcreator", "#postbridge"])].slice(0, count).join(" ") };
}

export async function generateCaption(input: CaptionInput, accessToken?: string): Promise<CaptionResult> {
  if (CAPTION_MODE === "mock") return Promise.resolve(buildMockCaption(input));
  if (!accessToken) throw new Error("Please sign in again.");
  const response = await fetch(`${API_BASE_URL}/mobile/caption`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload?.detail ?? payload;
    throw new CaptionGenerationError(
      String(detail?.code ?? "caption_generation_unavailable"),
      detail?.message ?? "PostBridge caption generation is unavailable.",
    );
  }
  return response.json() as Promise<CaptionResult>;
}
