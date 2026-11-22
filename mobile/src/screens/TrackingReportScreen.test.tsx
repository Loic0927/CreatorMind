import { render, waitFor } from "@testing-library/react-native";
import { getTrackedPost } from "../services/api";
import { TrackedPost } from "../types";
import { TrackingReportScreen } from "./TrackingReportScreen";

jest.mock("../services/api", () => ({
  getTrackedPost: jest.fn(),
  getTrackedPosts: jest.fn(),
  refreshTrackedPost: jest.fn(),
}));

function postWithUnavailableComparison(
  reason: "too_early" | "too_few_posts",
  comparisonBasis: "same_age" | "lifetime",
): TrackedPost {
  return {
    tracking: { id: "tracked-post" },
    media: {
      id: "media",
      instagram_media_id: "instagram-media",
      media_type: "IMAGE",
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

describe("TrackingReportScreen", () => {
  it.each([
    ["too_early", "same_age", "Too early to compare — check back later."],
    ["too_few_posts", "lifetime", "Track more posts in this format to compare."],
  ] as const)("shows the neutral %s comparison message", async (reason, comparisonBasis, message) => {
    const post = postWithUnavailableComparison(reason, comparisonBasis);
    jest.mocked(getTrackedPost).mockResolvedValueOnce(post);

    const view = await render(<TrackingReportScreen accessToken="token" initial={post} />);

    await waitFor(() => expect(view.getByText(message)).toBeTruthy());
  });
});
