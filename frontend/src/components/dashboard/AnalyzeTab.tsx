"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  NotComparableReason,
  RangeRow,
  Session,
  TrackedPost,
  getTrackedPost,
  getTrackedPosts,
  grantAIProcessingConsent,
  refreshTrackedPost,
} from "@/lib/postbridge";
import { AiConsentDialog } from "@/components/dashboard/AiConsentDialog";
import { errorMessage, formatMetric, formatNumber, formatRate, metricLabel } from "@/lib/format";
import { LoadingState } from "@/components/dashboard/LoadingState";
import { Card, ErrorBanner, Metric, PageTitle } from "@/components/dashboard/ui";

const deletedMediaCodes = ["media_not_found", "instagram_media_unavailable"];
const staleMessage = "Couldn't update, showing earlier data";
const markerColors: Record<RangeRow["status"], string> = { above: "#15803D", below: "#92400E", inside: "#076BD1" };
const backButton = "min-h-10 rounded-xl bg-selected px-4 text-sm font-bold text-selected-ink hover:bg-line-strong";
const shortDate = (date: string) =>
  new Date(date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const cover = (post: TrackedPost) => post.media.thumbnail_url || post.media.media_url;
const comparisonUnavailableMessage = (reason?: NotComparableReason | null) => {
  if (reason === "too_early") return "Too early to compare — check back later.";
  if (reason === "too_few_posts") return "Track more posts in this format to compare.";
  return "Not enough comparable posts yet.";
};

export function AnalyzeTab({
  session,
  initialId,
  onOpen,
  onClear,
}: {
  session: Session;
  initialId?: string;
  onOpen?: (id: string) => void;
  onClear: () => void;
}) {
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [selectedId, setSelectedId] = useState(initialId ?? "");
  const [post, setPost] = useState<TrackedPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [consentDialogOpen, setConsentDialogOpen] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    async (id: string) => {
      setLoading(true);
      setError("");
      try {
        setPost(await getTrackedPost(session, id));
      } catch (reason) {
        setError(errorMessage(reason, "Couldn't load this post."));
      } finally {
        setLoading(false);
      }
    },
    [session],
  );

  const loadPosts = useCallback(
    () =>
      getTrackedPosts(session)
        .then(({ items }) => setPosts(items))
        .catch((reason) => setError(errorMessage(reason, "Couldn't load posts.")))
        .finally(() => setLoading(false)),
    [session],
  );

  useEffect(() => {
    setSelectedId(initialId ?? "");
    if (initialId) void load(initialId);
    else void loadPosts();
  }, [initialId, load, loadPosts]);

  const choose = (id: string) => {
    setDeleted(false);
    setShowComments(false);
    setSelectedId(id);
    onOpen?.(id);
    void load(id);
  };

  const back = () => {
    setSelectedId("");
    setPost(null);
    onClear();
    setLoading(true);
    void loadPosts();
  };

  const refreshMetrics = async () => {
    if (!selectedId || refreshing || cooldown) return;
    setRefreshing(true);
    setError("");
    try {
      setPost(await refreshTrackedPost(session, selectedId));
      setCooldown(true);
      window.setTimeout(() => setCooldown(false), 60_000);
    } catch (reason) {
      if (reason instanceof ApiError && deletedMediaCodes.includes(reason.code)) setDeleted(true);
      else if (reason instanceof ApiError && reason.code === "consent_required") setConsentDialogOpen(true);
      else setError(errorMessage(reason, staleMessage));
    } finally {
      setRefreshing(false);
    }
  };

  const acceptConsent = async () => {
    setSavingConsent(true);
    setError("");
    try {
      await grantAIProcessingConsent(session);
      setConsentDialogOpen(false);
      await refreshMetrics();
    } catch (reason) {
      setError(errorMessage(reason, "Could not save AI processing consent."));
    } finally {
      setSavingConsent(false);
    }
  };

  if (!selectedId) {
    return (
      <section className="mx-auto w-full lg:w-4/5">
        <div className="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 md:mb-7">
          <PageTitle>Post</PageTitle>
          <span className="text-sm font-medium text-muted md:text-base">Choose one to analyze</span>
        </div>
        <ErrorBanner message={error} />
        {loading ? (
          <Card>Loading tracked posts…</Card>
        ) : posts.length ? (
          <div className="grid gap-5 md:grid-cols-2">
            {posts.map((item) => (
              <button key={item.tracking.id} onClick={() => choose(item.tracking.id)} className="text-left">
                <div className="h-full rounded-3xl border border-line bg-surface p-5 shadow-soft md:p-6">
                  {cover(item) ? (
                    <img
                      alt="Instagram post"
                      src={cover(item)}
                      className="mb-4 aspect-video w-full rounded-2xl object-cover"
                    />
                  ) : (
                    <div className="mb-4 aspect-video w-full rounded-2xl bg-selected" />
                  )}
                  <p className="line-clamp-2 font-bold">{item.media.caption || "Instagram post"}</p>
                  <div className="mt-5 grid grid-cols-3 gap-2 text-sm">
                    <Metric label="Likes" value={item.latest?.likes} />
                    <Metric label="Reach" value={item.latest?.reach} />
                    <Metric
                      label="Engagement"
                      value={item.latest?.engagement_rate == null ? undefined : formatRate(item.latest.engagement_rate)}
                    />
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <Card>Track an Instagram post first.</Card>
        )}
      </section>
    );
  }

  const analysis = post?.analysis;
  return (
    <section className="mx-auto w-full max-w-[720px]">
      <div className="mb-5 flex items-center justify-between gap-3 md:mb-7">
        <PageTitle>Analyze</PageTitle>
        <button onClick={back} className={backButton}>
          Back
        </button>
      </div>
      {error ? (
        <p className="mb-3 text-sm text-muted">
          {error.includes("reconnect") ? "Reconnect Instagram to update." : staleMessage}
        </p>
      ) : null}
      {deleted ? (
        <Card>
          <p className="text-lg font-black">This post is deleted</p>
          <p className="mt-2 text-sm text-muted">This post is no longer available on Instagram.</p>
          <button onClick={back} className={`mt-5 ${backButton}`}>
            Back
          </button>
        </Card>
      ) : loading || !post ? (
        <LoadingState label="Analyzing your post" />
      ) : (
        <div className="space-y-4">
          <Card>
            <div className="flex gap-4">
              {cover(post) ? (
                <img
                  alt="Post cover"
                  src={cover(post)}
                  className="h-[104px] w-[104px] shrink-0 rounded-2xl object-cover"
                />
              ) : (
                <div className="h-[104px] w-[104px] shrink-0 rounded-2xl bg-line-strong" />
              )}
              <div className="flex min-w-0 flex-1 flex-col">
                <p className="truncate text-[17px] font-black lg:text-lg">{post.media.caption || "Instagram post"}</p>
                <p className="mt-1 text-[13px] text-muted">
                  {shortDate(post.media.published_at)} · {analysis?.media_format ?? "Post"} · {analysis?.age_days ?? 0}{" "}
                  days
                </p>
                <button
                  onClick={() => void refreshMetrics()}
                  disabled={refreshing || cooldown}
                  className="-ml-3 mt-auto flex min-h-11 w-fit items-end px-3 pb-0 text-[13px] font-semibold text-primary disabled:opacity-50"
                >
                  {refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh metrics"}
                </button>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <Headline label="Reach" value={formatNumber(post.latest?.reach)} />
              <Headline label="Views" value={formatNumber(post.latest?.views)} />
              <Headline label="Engagement" value={formatRate(post.latest?.engagement_rate)} />
            </div>
          </Card>

          {analysis?.summary ? (
            <Card>
              <h2 className="text-xl font-black">Summary</h2>
              <p className="mt-3 text-[15px] leading-5 text-ink">{analysis.summary}</p>
            </Card>
          ) : analysis?.summary_status === "pending" ? (
            <Card>
              <h2 className="text-xl font-black">Summary</h2>
              <p className="mt-3 text-[15px] leading-5 text-muted">Your summary is being prepared.</p>
            </Card>
          ) : null}

          {analysis?.comparable ? (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                <FindingCard
                  title="Stands out"
                  positive
                  rows={analysis.stands_out}
                  empty="Nothing is above the usual range."
                />
                <FindingCard title="Weaker" rows={analysis.weaker} empty="Nothing is weaker than usual." />
              </div>
              <Card>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-black">Usual range</h2>
                  <span aria-hidden className="text-lg">
                    ⌃
                  </span>
                </div>
                <div className="space-y-5">
                  {analysis.usual_ranges.map((row) => (
                    <Range key={row.metric} row={row} />
                  ))}
                </div>
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-sm text-muted">{comparisonUnavailableMessage(analysis?.not_comparable_reason)}</p>
            </Card>
          )}

          {analysis ? (
            <Card>
              <h2 className="text-xl font-black">Audience comments</h2>
              <p className="mt-4 text-sm leading-5 text-muted">
                {analysis.audience_comments.description ??
                  analysis.audience_comments.message ??
                  "Audience comments are not available yet."}
              </p>
              {analysis.audience_comments.state === "consent_required" ? (
                <button
                  type="button"
                  onClick={() => setConsentDialogOpen(true)}
                  className="mt-4 min-h-10 rounded-xl bg-primary px-4 text-sm font-black text-white hover:bg-primary-hover"
                >
                  Review AI data use
                </button>
              ) : null}
              {analysis.audience_comments.items?.length ? (
                <>
                  <button
                    type="button"
                    aria-expanded={showComments}
                    onClick={() => setShowComments((current) => !current)}
                    className="mt-4 min-h-10 text-sm font-black text-primary-hover"
                  >
                    {showComments ? "Hide comments" : `Show comments (${analysis.audience_comments.items.length})`}
                  </button>
                  {showComments ? (
                    <ul className="mt-2 divide-y divide-line border-t border-line">
                      {analysis.audience_comments.items.map((comment) => (
                        <li key={`${comment.timestamp}-${comment.text}`} className="py-3">
                          <p className="whitespace-pre-wrap text-sm leading-5 text-ink">{comment.text}</p>
                          <p className="mt-1 text-xs text-muted">
                            {shortDate(comment.timestamp)} · {comment.like_count}{" "}
                            {comment.like_count === 1 ? "like" : "likes"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              ) : null}
            </Card>
          ) : null}
        </div>
      )}
      <AiConsentDialog
        open={consentDialogOpen}
        busy={savingConsent}
        onAccept={acceptConsent}
        onNotNow={() => setConsentDialogOpen(false)}
      />
    </section>
  );
}

function Headline({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[20px] font-black leading-none sm:text-[26px]">{value}</p>
      <p className="mt-2 text-[12px] text-muted sm:text-[13px]">{label}</p>
    </div>
  );
}

function FindingCard({
  title,
  positive = false,
  rows,
  empty,
}: {
  title: string;
  positive?: boolean;
  rows: RangeRow[];
  empty: string;
}) {
  return (
    <Card>
      <p
        className={`text-[11px] font-black uppercase tracking-[.06em] ${positive ? "text-green-800" : "text-amber-800"}`}
      >
        {title}
      </p>
      {rows.length ? (
        <div className="mt-3 space-y-3">
          {rows.map((row) => (
            <div key={row.metric} className="flex items-baseline justify-between gap-3 text-sm">
              <b>
                {metricLabel[row.metric]}: {formatMetric(row.metric, row.value)}
              </b>
              <span className="shrink-0 text-muted">
                usual {formatMetric(row.metric, row.usual_min)}–{formatMetric(row.metric, row.usual_max)}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted">{empty}</p>
      )}
    </Card>
  );
}

function Range({ row }: { row: RangeRow }) {
  const [showValue, setShowValue] = useState(false);
  const label = metricLabel[row.metric];
  const detail = `${formatMetric(row.metric, row.value)} · ${row.status === "inside" ? `#${row.rank}` : row.status}`;
  return (
    <div className="grid grid-cols-[72px_1fr] items-center gap-3 text-sm sm:grid-cols-[88px_1fr_108px]">
      <span className="font-semibold">
        <span className="sm:hidden">{row.metric === "engagement_rate" ? "Engage." : label}</span>
        <span className="hidden sm:inline">{label}</span>
      </span>
      <button
        type="button"
        aria-label={`${label}: ${detail}`}
        aria-expanded={showValue}
        onClick={() => setShowValue((current) => !current)}
        className="relative h-8 w-full rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
      >
        <span className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-subtle" />
        <span
          className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-line-strong"
          style={{ left: `${row.band_start}%`, width: `${Math.max(2, row.band_end - row.band_start)}%` }}
        />
        <span
          className="absolute top-1/2 h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface"
          style={{ left: `${row.marker}%`, background: markerColors[row.status] }}
        />
        {showValue ? (
          <span
            role="tooltip"
            className="absolute bottom-7 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1.5 text-xs font-bold text-white shadow-float"
            style={{ left: `${Math.min(92, Math.max(8, row.marker))}%` }}
          >
            {detail}
          </span>
        ) : null}
      </button>
      <span className="hidden text-right text-muted sm:block">{detail}</span>
    </div>
  );
}
