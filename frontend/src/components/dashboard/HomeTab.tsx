"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Connection,
  Session,
  TrackedPost,
  deleteTrackedPost,
  getConnection,
  getInstagramMedia,
  getTikTokMedia,
  getTrackedPosts,
  trackInstagramPost,
} from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { ErrorBanner, PageTitle, Panel } from "@/components/dashboard/ui";

type InstagramMediaItem = {
  id: string;
  caption: string;
  media_url?: string;
  thumbnail_url?: string;
  published_at?: string;
};
type SelectionPlatform = "Instagram" | "TikTok";
type TikTokMediaItem = {
  id: string;
  caption: string;
  thumbnail_url?: string;
  permalink?: string;
  published_at?: number | string;
};

const primaryButton = "rounded-xl bg-primary px-5 py-3 font-bold text-white hover:bg-primary-hover";
const byOldestFirst = <T,>(items: T[]) =>
  [...items].sort(
    (left, right) =>
      new Date((left as { published_at?: string }).published_at ?? 0).getTime() -
      new Date((right as { published_at?: string }).published_at ?? 0).getTime(),
  );
const tikTokPublishedAt = (value: number | string | undefined) => {
  if (typeof value === "number") return value * 1000;
  return value ? new Date(value).getTime() : 0;
};

export function HomeTab({ session, onConnect }: { session: Session; onConnect: () => Promise<void> }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [media, setMedia] = useState<InstagramMediaItem[]>([]);
  const [tikTokMedia, setTikTokMedia] = useState<TikTokMediaItem[]>([]);
  const [choosing, setChoosing] = useState(false);
  const [selectionPlatform, setSelectionPlatform] = useState<SelectionPlatform>("Instagram");
  const [loading, setLoading] = useState(true);
  const [addingId, setAddingId] = useState("");
  const [loadingTikTokMedia, setLoadingTikTokMedia] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const carousel = useRef<HTMLDivElement>(null);

  const orderedPosts = useMemo(
    () =>
      [...posts].sort(
        (left, right) => new Date(right.media.published_at).getTime() - new Date(left.media.published_at).getTime(),
      ),
    [posts],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextConnection, tracked] = await Promise.all([getConnection(session), getTrackedPosts(session)]);
      setConnection(nextConnection);
      setPosts(tracked.items);
    } catch (reason) {
      setError(errorMessage(reason, "Could not load posts."));
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  const attempt = async (fallback: string, action: () => Promise<void>) => {
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason, fallback));
    }
  };

  const openPostPicker = () => {
    setSelectionPlatform("Instagram");
    void attempt("Could not load Instagram posts.", async () => {
      const trackedIds = new Set(posts.map((post) => post.media.id));
      const { items } = await getInstagramMedia(session);
      setMedia(byOldestFirst(items.filter((item) => !trackedIds.has(item.id))));
      setChoosing(true);
    });
  };

  const addPost = async (mediaId: string) => {
    setAddingId(mediaId);
    await attempt("Could not add this Instagram post.", async () => {
      await trackInstagramPost(session, mediaId);
      setChoosing(false);
      await load();
    });
    setAddingId("");
  };

  const loadTikTokMedia = () =>
    attempt("Could not load TikTok posts. Reconnect TikTok with the video.list permission and try again.", async () => {
      setLoadingTikTokMedia(true);
      try {
        const { items } = await getTikTokMedia(session);
        setTikTokMedia(
          [...items].sort(
            (left, right) => tikTokPublishedAt(left.published_at) - tikTokPublishedAt(right.published_at),
          ),
        );
      } finally {
        setLoadingTikTokMedia(false);
      }
    });

  const selectPlatform = (platform: SelectionPlatform) => {
    setSelectionPlatform(platform);
    if (platform === "TikTok" && !tikTokMedia.length && !loadingTikTokMedia) void loadTikTokMedia();
  };

  const removePost = async (post: TrackedPost) => {
    if (!window.confirm("Remove this post from your tracked posts?")) return;
    setDeletingId(post.tracking.id);
    await attempt("Could not remove this post.", async () => {
      await deleteTrackedPost(session, post.tracking.id);
      setPosts((current) => current.filter((item) => item.tracking.id !== post.tracking.id));
    });
    setDeletingId("");
  };

  const scrollCarousel = (direction: number) =>
    carousel.current?.scrollBy({ left: direction * 320, behavior: "smooth" });

  return (
    <section className="mx-auto w-full lg:w-4/5">
      <div className="mb-5 flex items-center justify-between gap-3 md:mb-7">
        <PageTitle>Tracked posts</PageTitle>
        {connection?.connected ? (
          <div className="ml-auto flex flex-wrap justify-end gap-2">
            {connection.comment_ingestion?.enabled && !connection.comment_ingestion.permission_granted ? (
              <button
                onClick={() => void onConnect()}
                className="rounded-xl bg-selected px-3 py-2 text-xs font-bold text-selected-ink hover:bg-line-strong sm:px-4 sm:py-3 sm:text-sm"
              >
                Reauthorize Instagram
              </button>
            ) : null}
            <button
              onClick={openPostPicker}
              className="shrink-0 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-white hover:bg-primary-hover sm:px-5 sm:py-3 sm:text-base"
            >
              Add a post
            </button>
          </div>
        ) : null}
      </div>
      <ErrorBanner message={error} />

      {choosing ? (
        <Panel>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-xl font-black">Add a post</h2>
            <button onClick={() => setChoosing(false)} className="text-sm font-bold text-primary-hover">
              Close
            </button>
          </div>
          <div className="mb-4 flex border-b border-line" role="tablist" aria-label="Post platform">
            {(["Instagram", "TikTok"] as const).map((platform) => (
              <button
                key={platform}
                type="button"
                role="tab"
                aria-selected={selectionPlatform === platform}
                onClick={() => selectPlatform(platform)}
                className={`relative min-h-11 px-4 text-sm font-black ${selectionPlatform === platform ? "text-primary" : "text-muted hover:text-ink"}`}
              >
                {platform} Post
                {selectionPlatform === platform ? (
                  <span aria-hidden className="absolute inset-x-4 bottom-0 h-0.5 bg-primary" />
                ) : null}
              </button>
            ))}
          </div>
          {selectionPlatform === "Instagram" ? (
            media.length ? (
              <div className="relative">
                <div
                  ref={carousel}
                  className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3 pr-2 [scrollbar-width:thin]"
                >
                  {media.map((item) => (
                    <button
                      key={item.id}
                      disabled={Boolean(addingId)}
                      onClick={() => void addPost(item.id)}
                      className="w-32 shrink-0 snap-start overflow-hidden rounded-2xl bg-selected text-left disabled:opacity-60 sm:w-40"
                    >
                      {item.thumbnail_url || item.media_url ? (
                        <img
                          alt=""
                          src={item.thumbnail_url || item.media_url}
                          className="aspect-square w-full object-cover"
                        />
                      ) : (
                        <div className="aspect-square" />
                      )}
                      <p className="line-clamp-2 min-h-12 p-2 text-xs font-bold">
                        {addingId === item.id ? "Adding…" : item.caption || "Instagram post"}
                      </p>
                    </button>
                  ))}
                </div>
                {media.length > 2 ? (
                  <div className="mt-1 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => scrollCarousel(-1)}
                      aria-label="Previous Instagram posts"
                      className="rounded-lg bg-selected px-3 py-1 font-black text-selected-ink"
                    >
                      ‹
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollCarousel(1)}
                      aria-label="Next Instagram posts"
                      className="rounded-lg bg-selected px-3 py-1 font-black text-selected-ink"
                    >
                      ›
                    </button>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="py-8 text-center text-sm font-bold text-muted">All Instagram posts are already tracked.</p>
            )
          ) : loadingTikTokMedia ? (
            <p className="py-8 text-center text-sm font-bold text-muted">Loading TikTok posts…</p>
          ) : tikTokMedia.length ? (
            <div className="relative">
              <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3 pr-2 [scrollbar-width:thin]">
                {tikTokMedia.map((item) => (
                  <a
                    key={item.id}
                    href={item.permalink}
                    target="_blank"
                    rel="noreferrer"
                    className="w-32 shrink-0 snap-start overflow-hidden rounded-2xl bg-selected text-left sm:w-40"
                  >
                    {item.thumbnail_url ? (
                      <img alt="" src={item.thumbnail_url} className="aspect-square w-full object-cover" />
                    ) : (
                      <div className="aspect-square bg-line-strong" />
                    )}
                    <p className="line-clamp-2 min-h-12 p-2 text-xs font-bold">{item.caption || "TikTok post"}</p>
                  </a>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">TikTok videos are read directly from your connected account.</p>
            </div>
          ) : (
            <p className="py-8 text-center text-sm font-bold text-muted">No public TikTok posts were found.</p>
          )}
        </Panel>
      ) : null}

      {loading ? (
        <Panel>Loading your account…</Panel>
      ) : !connection?.connected ? (
        <Panel>
          <h2 className="text-xl font-black">Connect Instagram</h2>
          <button onClick={() => void onConnect()} className={`mt-5 ${primaryButton}`}>
            Connect Instagram
          </button>
        </Panel>
      ) : (
        <div className="space-y-8">
          <PlatformPostSection
            platform="Instagram"
            posts={orderedPosts}
            deletingId={deletingId}
            onRemove={removePost}
          />
          <PlatformPostSection platform="TikTok" posts={[]} deletingId={deletingId} onRemove={removePost} />
        </div>
      )}
    </section>
  );
}

function PlatformPostSection({
  platform,
  posts,
  deletingId,
  onRemove,
}: {
  platform: SelectionPlatform;
  posts: TrackedPost[];
  deletingId: string;
  onRemove: (post: TrackedPost) => Promise<void>;
}) {
  return (
    <section aria-labelledby={`${platform.toLowerCase()}-posts`}>
      <h2 id={`${platform.toLowerCase()}-posts`} className="mb-3 text-lg font-black">
        {platform}
      </h2>
      {posts.length ? (
        <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
          {posts.map((post) => {
            const image = post.media.thumbnail_url || post.media.media_url;
            return (
              <div key={post.tracking.id} className="group relative aspect-square overflow-hidden bg-selected">
                {image ? (
                  <img
                    alt={post.media.caption || `${platform} post`}
                    src={image}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="h-full w-full bg-line-strong" />
                )}
                <button
                  type="button"
                  aria-label="Remove tracked post"
                  disabled={Boolean(deletingId)}
                  onClick={() => void onRemove(post)}
                  className="absolute right-1.5 top-1.5 grid h-7 w-7 place-items-center rounded-full bg-surface/95 text-lg font-bold leading-none text-primary-hover opacity-0 shadow-float transition-opacity focus:opacity-100 group-hover:opacity-100 disabled:opacity-50"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <Panel>
          <p className="text-sm font-bold text-muted">
            {platform === "TikTok" ? "No tracked TikTok posts yet." : "No tracked Instagram posts yet."}
          </p>
        </Panel>
      )}
    </section>
  );
}
