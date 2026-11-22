"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Connection,
  Session,
  TrackedPost,
  deleteTrackedPost,
  getConnection,
  getInstagramMedia,
  getTrackedPosts,
  refreshTrackedPost,
  trackInstagramPost,
} from "@/lib/postbridge";
import { errorMessage, formatRate } from "@/lib/format";
import { ErrorBanner, Metric, PageTitle, Panel } from "@/components/dashboard/ui";

type InstagramMediaItem = { id: string; caption: string; media_url?: string; thumbnail_url?: string };
const primaryButton = "mt-5 rounded-xl bg-sky-600 px-5 py-3 font-bold text-white";

export function HomeTab({ session, onConnect }: { session: Session; onConnect: () => Promise<void> }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [media, setMedia] = useState<InstagramMediaItem[]>([]);
  const [choosing, setChoosing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [addingId, setAddingId] = useState("");
  const [refreshingId, setRefreshingId] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");

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

  /** Runs an action with error reporting; `fallback` is shown when the error has no message. */
  const attempt = async (fallback: string, action: () => Promise<void>) => {
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason, fallback));
    }
  };

  const choosePost = () =>
    attempt("Could not load Instagram posts.", async () => {
      const trackedIds = new Set(posts.map((post) => post.media.id));
      const { items } = await getInstagramMedia(session);
      setMedia(items.filter((item) => !trackedIds.has(item.id)));
      setChoosing(true);
    });

  const addPost = async (mediaId: string) => {
    setAddingId(mediaId);
    await attempt("Could not add this Instagram post.", async () => {
      const tracked = await trackInstagramPost(session, mediaId);
      setChoosing(false);
      await refreshTrackedPost(session, tracked.id);
      await load();
    });
    setAddingId("");
  };

  const refreshPost = async (trackedId: string) => {
    setRefreshingId(trackedId);
    await attempt("Could not refresh metrics.", async () => {
      const refreshed = await refreshTrackedPost(session, trackedId);
      setPosts((current) => current.map((post) => (post.tracking.id === trackedId ? refreshed : post)));
    });
    setRefreshingId("");
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

  return (
    <section className="mx-auto w-full lg:w-4/5">
      <div className="mb-5 flex items-center justify-between gap-3 md:mb-7">
        <PageTitle>Tracked posts</PageTitle>
        {connection?.connected && (
          <div className="ml-auto flex flex-wrap justify-end gap-2">
            {connection.comment_ingestion?.enabled && !connection.comment_ingestion.permission_granted && (
              <button
                onClick={() => void onConnect()}
                className="rounded-xl bg-sky-100 px-3 py-2 text-xs font-bold text-sky-700 sm:px-4 sm:py-3 sm:text-sm"
              >
                Reauthorize Instagram
              </button>
            )}
            <button
              onClick={() => void choosePost()}
              className="shrink-0 rounded-xl bg-sky-600 px-3 py-2 text-xs font-bold text-white sm:px-5 sm:py-3 sm:text-base"
            >
              Add a post
            </button>
          </div>
        )}
      </div>
      <ErrorBanner message={error} />

      {choosing && (
        <div className="mb-5">
          <Panel>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-black">Choose an Instagram post</h2>
              <button onClick={() => setChoosing(false)} className="text-sm font-bold text-sky-700">
                Close
              </button>
            </div>
            {media.length ? (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {media.map((item) => (
                  <button
                    key={item.id}
                    disabled={Boolean(addingId)}
                    onClick={() => void addPost(item.id)}
                    className="overflow-hidden rounded-2xl bg-sky-100 text-left disabled:opacity-60"
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
                    <p className="line-clamp-2 p-3 text-xs font-bold">
                      {addingId === item.id ? "Adding…" : item.caption || "Instagram post"}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm font-bold text-slate-500">
                All Instagram posts are already tracked.
              </p>
            )}
          </Panel>
        </div>
      )}

      {loading ? (
        <Panel>Loading your account…</Panel>
      ) : !connection?.connected ? (
        <Panel>
          <h2 className="text-xl font-black">Connect Instagram</h2>
          <button onClick={() => void onConnect()} className={primaryButton}>
            Connect Instagram
          </button>
        </Panel>
      ) : posts.length === 0 ? (
        <Panel>
          <h2 className="text-xl font-black">No tracked posts yet</h2>
          <button onClick={() => void choosePost()} className={primaryButton}>
            Add a post
          </button>
        </Panel>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {posts.map((post) => (
            <Panel key={post.tracking.id}>
              <div className="relative">
                {post.media.thumbnail_url || post.media.media_url ? (
                  <img
                    alt=""
                    src={post.media.thumbnail_url || post.media.media_url}
                    className="mb-4 aspect-video w-full rounded-2xl object-cover"
                  />
                ) : null}
                <button
                  type="button"
                  aria-label="Remove tracked post"
                  disabled={Boolean(deletingId)}
                  onClick={() => void removePost(post)}
                  className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-white/95 text-xl font-bold leading-none text-sky-700 shadow-sm disabled:opacity-50"
                >
                  ×
                </button>
              </div>
              <p className="line-clamp-2 font-bold">{post.media.caption || "Instagram post"}</p>
              <div className="mt-5 grid grid-cols-3 gap-2 text-sm">
                <Metric label="Likes" value={post.latest?.likes} />
                <Metric label="Reach" value={post.latest?.reach} />
                <Metric
                  label="Engagement"
                  value={post.latest?.engagement_rate == null ? undefined : formatRate(post.latest.engagement_rate)}
                />
              </div>
              <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-200 pt-4">
                <p className="text-[11px] text-slate-500">
                  {post.latest?.captured_at
                    ? `Updated ${new Date(post.latest.captured_at).toLocaleString()}`
                    : "Metrics not loaded"}
                </p>
                <button
                  disabled={Boolean(refreshingId) || Boolean(deletingId)}
                  onClick={() => void refreshPost(post.tracking.id)}
                  className="shrink-0 rounded-lg bg-sky-100 px-3 py-2 text-xs font-bold text-sky-700 disabled:opacity-60"
                >
                  {refreshingId === post.tracking.id ? "Refreshing…" : "Refresh metrics"}
                </button>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </section>
  );
}
