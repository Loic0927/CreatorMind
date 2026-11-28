import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeTab } from "./HomeTab";
import {
  deleteTikTokTrackedPost,
  deleteTrackedPost,
  getConnection,
  getInstagramMedia,
  getTikTokMedia,
  getTikTokTrackedPosts,
  getTrackedPosts,
} from "@/lib/postbridge";

vi.mock("@/lib/postbridge", () => ({
  deleteTikTokTrackedPost: vi.fn(),
  deleteTrackedPost: vi.fn(),
  getConnection: vi.fn(),
  getInstagramMedia: vi.fn(),
  getTikTokMedia: vi.fn(),
  getTikTokTrackedPosts: vi.fn(),
  getTrackedPosts: vi.fn(),
  trackInstagramPost: vi.fn(),
  trackTikTokPost: vi.fn(),
}));

const session = { accessToken: "token", expiresAt: "2099-01-01", user: { id: "user", email: "creator@example.com" } };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("HomeTab", () => {
  it("keeps tracked posts out of the picker, restores deleted posts, and links tiles to their social posts", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    vi.mocked(getConnection).mockResolvedValue({ connected: true, configured: true });
    vi.mocked(getTrackedPosts).mockResolvedValue({
      items: [
        {
          tracking: { id: "tracked-instagram" },
          media: {
            id: "instagram:instagram-1",
            instagram_media_id: "instagram-1",
            caption: "Tracked Instagram caption",
            permalink: "https://www.instagram.com/p/instagram-1/",
            published_at: "2026-11-24T00:00:00Z",
          },
        },
      ],
    });
    vi.mocked(getTikTokTrackedPosts).mockResolvedValue({
      items: [
        {
          id: "tracked-tiktok",
          video_id: "tiktok-1",
          caption: "Tracked TikTok caption",
          permalink: "https://www.tiktok.com/@creator/video/tiktok-1",
          published_at: "2026-11-24T00:00:00Z",
          created_at: "2026-11-24T00:00:00Z",
        },
      ],
    });
    vi.mocked(getInstagramMedia).mockResolvedValue({
      items: [
        {
          id: "instagram:instagram-1",
          instagram_media_id: "instagram-1",
          caption: "Tracked Instagram caption",
          permalink: "https://www.instagram.com/p/instagram-1/",
          published_at: "2026-11-24T00:00:00Z",
        },
        {
          id: "instagram:instagram-2",
          instagram_media_id: "instagram-2",
          caption: "Available Instagram caption",
          permalink: "https://www.instagram.com/p/instagram-2/",
          published_at: "2026-11-23T00:00:00Z",
        },
      ],
    });
    vi.mocked(getTikTokMedia).mockResolvedValue({
      items: [
        { id: "tiktok-1", caption: "Tracked TikTok caption", published_at: 1795478400 },
        { id: "tiktok-2", caption: "Available TikTok caption", published_at: 1795392000 },
      ],
    });
    vi.mocked(deleteTrackedPost).mockResolvedValue({ stopped: true });
    vi.mocked(deleteTikTokTrackedPost).mockResolvedValue({ stopped: true });

    render(<HomeTab session={session} onConnect={vi.fn()} />);

    expect(await screen.findByRole("link", { name: "Open Instagram post" })).toHaveAttribute(
      "href",
      "https://www.instagram.com/p/instagram-1/",
    );
    expect(screen.getByRole("link", { name: "Open TikTok post" })).toHaveAttribute(
      "href",
      "https://www.tiktok.com/@creator/video/tiktok-1",
    );

    fireEvent.click(screen.getByRole("button", { name: "Add a post" }));
    expect(await screen.findByText("Available Instagram caption")).toBeInTheDocument();
    expect(screen.queryByText("Tracked Instagram caption")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "TikTok" }));
    expect(await screen.findByText("Available TikTok caption")).toBeInTheDocument();
    expect(screen.queryByText("Tracked TikTok caption")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remove tracked TikTok post" }));
    expect(await screen.findByText("Tracked TikTok caption")).toBeInTheDocument();
    expect(deleteTikTokTrackedPost).toHaveBeenCalledWith(session, "tracked-tiktok");

    fireEvent.click(screen.getByRole("tab", { name: "Instagram" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove tracked post" }));
    await waitFor(() => expect(screen.getByText("Tracked Instagram caption")).toBeInTheDocument());
    expect(deleteTrackedPost).toHaveBeenCalledWith(session, "tracked-instagram");
  });
});
