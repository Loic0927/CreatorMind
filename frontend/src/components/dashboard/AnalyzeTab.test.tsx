import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalyzeTab } from "./AnalyzeTab";
import { getTikTokTrackedPosts, getTrackedPost, getTrackedPosts, type TrackedPost } from "@/lib/postbridge";

vi.mock("@/lib/postbridge", () => ({
  ApiError: class ApiError extends Error {},
  getTikTokTrackedPosts: vi.fn(),
  getTrackedPost: vi.fn(),
  getTrackedPosts: vi.fn(),
  refreshTrackedPost: vi.fn(),
}));

const session = { accessToken: "token", expiresAt: "2099-01-01", user: { id: "user", email: "creator@example.com" } };

function postWithUnavailableComparison(
  reason: "too_early" | "too_few_posts",
  comparisonBasis: "same_age" | "lifetime",
): TrackedPost {
  return {
    tracking: { id: "tracked-post" },
    media: {
      id: "media",
      caption: "A tracked post",
      published_at: "2026-11-01T00:00:00Z",
    },
    analysis: {
      comparable: false,
      comparable_count: 2,
      comparison_basis: comparisonBasis,
      not_comparable_reason: reason,
      summary: null,
      stands_out: [],
      weaker: [],
      usual_ranges: [],
      audience_comments: { state: "feature_off" },
      age_days: 1,
      media_format: "Image",
    },
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AnalyzeTab", () => {
  it("shows tracked TikTok posts in the TikTok navigator", async () => {
    vi.mocked(getTrackedPosts).mockResolvedValueOnce({ items: [] });
    vi.mocked(getTikTokTrackedPosts).mockResolvedValueOnce({
      items: [
        {
          id: "tracked-tiktok",
          video_id: "video",
          caption: "Newest TikTok post",
          published_at: "2026-11-24T00:00:00Z",
          created_at: "2026-11-24T00:00:00Z",
        },
      ],
    });

    render(<AnalyzeTab session={session} onClear={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "TikTok" }));

    expect(await screen.findByText("Newest TikTok post")).toBeInTheDocument();
  });

  it.each([
    ["too_early", "same_age", "Too early to compare — check back later."],
    ["too_few_posts", "lifetime", "Track more posts in this format to compare."],
  ] as const)("shows the neutral %s comparison message", async (reason, comparisonBasis, message) => {
    vi.mocked(getTrackedPost).mockResolvedValueOnce(postWithUnavailableComparison(reason, comparisonBasis));

    render(<AnalyzeTab session={session} initialId="tracked-post" onClear={() => {}} />);

    expect(await screen.findByText(message)).toBeInTheDocument();
  });
});
