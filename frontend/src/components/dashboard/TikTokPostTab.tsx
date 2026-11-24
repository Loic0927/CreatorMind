"use client";

import { useEffect, useState } from "react";
import { Session, TikTokTrackedPost, getTikTokTrackedPost } from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { Card, PageTitle } from "@/components/dashboard/ui";

export function TikTokPostTab({
  session,
  trackedId,
  onBack,
}: {
  session: Session;
  trackedId: string;
  onBack: () => void;
}) {
  const [post, setPost] = useState<TikTokTrackedPost | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getTikTokTrackedPost(session, trackedId)
      .then(setPost)
      .catch((reason) => setError(errorMessage(reason, "Could not load TikTok post.")));
  }, [session, trackedId]);
  return (
    <section className="mx-auto w-full max-w-[720px]">
      <div className="mb-5 flex items-center justify-between gap-3 md:mb-7">
        <PageTitle>TikTok</PageTitle>
        <button
          onClick={onBack}
          className="min-h-10 rounded-xl bg-selected px-4 text-sm font-bold text-selected-ink hover:bg-line-strong"
        >
          Back
        </button>
      </div>
      {error ? (
        <Card>{error}</Card>
      ) : !post ? (
        <Card>Loading TikTok post…</Card>
      ) : (
        <Card>
          <div className="flex gap-4">
            {post.thumbnail_url ? (
              <img src={post.thumbnail_url} alt="" className="h-[104px] w-[104px] shrink-0 rounded-2xl object-cover" />
            ) : null}
            <div className="min-w-0">
              <p className="text-lg font-black">{post.caption || "TikTok post"}</p>
              <p className="mt-2 text-sm text-muted">
                {post.published_at ? new Date(post.published_at).toLocaleDateString() : "Date unavailable"}
              </p>
              {post.permalink ? (
                <a
                  href={post.permalink}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-sm font-bold text-primary"
                >
                  Open on TikTok
                </a>
              ) : null}
            </div>
          </div>
        </Card>
      )}
    </section>
  );
}
