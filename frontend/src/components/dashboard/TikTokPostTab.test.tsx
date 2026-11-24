import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TikTokPostTab } from "./TikTokPostTab";
import { getTikTokTrackedPost } from "@/lib/postbridge";

vi.mock("@/lib/postbridge", () => ({
  getTikTokTrackedPost: vi.fn(),
  refreshTikTokTrackedPost: vi.fn(),
}));

const session = { accessToken: "token", expiresAt: "2099-01-01", user: { id: "user", email: "creator@example.com" } };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TikTokPostTab", () => {
  it("shows official metrics and the TikTok analysis report", async () => {
    vi.mocked(getTikTokTrackedPost).mockResolvedValueOnce({
      id: "tracked",
      video_id: "video",
      caption: "A TikTok post",
      published_at: "2026-11-20T00:00:00Z",
      created_at: "2026-11-20T00:00:00Z",
      views: 1234,
      likes: 120,
      comments: 4,
      shares: 3,
      engagement_rate: 10.3,
      analysis: {
        comparable: false,
        comparable_count: 0,
        summary: "This TikTok is ready for review.",
        stands_out: [],
        weaker: [],
        usual_ranges: [],
        age_days: 4,
        media_format: "Video",
        audience_comments: {
          state: "unavailable",
          message: "TikTok provides the public comment count, but not comment text.",
        },
      },
    });

    render(<TikTokPostTab session={session} trackedId="tracked" onBack={() => {}} />);

    expect(await screen.findByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("10.3%")).toBeInTheDocument();
    expect(screen.getByText("This TikTok is ready for review.")).toBeInTheDocument();
    expect(screen.getByText(/not comment text/i)).toBeInTheDocument();
  });
});
