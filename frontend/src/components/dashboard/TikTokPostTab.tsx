"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Session,
  TikTokAnalysisRow,
  TikTokMetricKey,
  TikTokTrackedPost,
  getTikTokTrackedPost,
  refreshTikTokTrackedPost,
} from "@/lib/postbridge";
import { errorMessage, formatNumber, formatRate } from "@/lib/format";
import { Card, PageTitle } from "@/components/dashboard/ui";

const metricLabels: Record<TikTokMetricKey, string> = {
  views: "Views",
  likes: "Likes",
  engagement_rate: "Engagement",
  shares: "Shares",
  comments: "Comments",
};
const markerColors: Record<TikTokAnalysisRow["status"], string> = {
  above: "#15803D",
  below: "#92400E",
  inside: "#076BD1",
};
const formatTikTokMetric = (metric: TikTokMetricKey, value: number) =>
  metric === "engagement_rate" ? formatRate(value) : formatNumber(value);

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
  const [refreshing, setRefreshing] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const load = useCallback(() => {
    setError("");
    getTikTokTrackedPost(session, trackedId)
      .then(setPost)
      .catch((reason) => setError(errorMessage(reason, "Could not load TikTok post.")));
  }, [session, trackedId]);
  useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    if (refreshing || cooldown) return;
    setRefreshing(true);
    setError("");
    try {
      setPost(await refreshTikTokTrackedPost(session, trackedId));
      setCooldown(true);
      window.setTimeout(() => setCooldown(false), 60_000);
    } catch (reason) {
      setError(errorMessage(reason, "Could not refresh TikTok metrics."));
    } finally {
      setRefreshing(false);
    }
  };

  const analysis = post?.analysis;
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
      {error && post ? <p className="mb-3 text-sm text-muted">{error}</p> : null}
      {error && !post ? (
        <Card>{error}</Card>
      ) : !post ? (
        <Card>Loading TikTok post…</Card>
      ) : (
        <div className="space-y-4">
          <Card>
            <div className="flex gap-4">
              {post.thumbnail_url ? (
                <img
                  src={post.thumbnail_url}
                  alt=""
                  className="h-[104px] w-[104px] shrink-0 rounded-2xl object-cover"
                />
              ) : (
                <div className="h-[104px] w-[104px] shrink-0 rounded-2xl bg-line-strong" />
              )}
              <div className="flex min-w-0 flex-1 flex-col">
                <p className="truncate text-[17px] font-black lg:text-lg">{post.caption || "TikTok post"}</p>
                <p className="mt-1 text-[13px] text-muted">
                  {post.published_at ? new Date(post.published_at).toLocaleDateString() : "Date unavailable"} · Video ·{" "}
                  {analysis?.age_days ?? 0} days
                </p>
                <button
                  type="button"
                  onClick={() => void refresh()}
                  disabled={refreshing || cooldown}
                  className="-ml-3 mt-auto flex min-h-11 w-fit items-end px-3 text-[13px] font-semibold text-primary disabled:opacity-50"
                >
                  {refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh metrics"}
                </button>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <Headline label="Views" value={formatNumber(post.views)} />
              <Headline label="Likes" value={formatNumber(post.likes)} />
              <Headline label="Engagement" value={formatRate(post.engagement_rate)} />
            </div>
          </Card>

          {analysis?.summary ? (
            <Card>
              <h2 className="text-xl font-black">Summary</h2>
              <p className="mt-3 text-[15px] leading-5">{analysis.summary}</p>
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
                <h2 className="mb-4 text-xl font-black">Usual range</h2>
                <div className="space-y-5">
                  {analysis.usual_ranges.map((row) => (
                    <TikTokRange key={row.metric} row={row} />
                  ))}
                </div>
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-sm text-muted">Track at least three TikTok posts to compare their usual ranges.</p>
            </Card>
          )}

          <Card>
            <h2 className="text-xl font-black">Audience comments</h2>
            <p className="mt-3 text-sm leading-5 text-muted">
              {analysis?.audience_comments.message ??
                "TikTok Display API provides the public comment count, but not comment text."}
            </p>
          </Card>

          {post.permalink ? (
            <a
              href={post.permalink}
              target="_blank"
              rel="noreferrer"
              className="inline-block min-h-10 px-1 py-2 text-sm font-bold text-primary"
            >
              Open on TikTok
            </a>
          ) : null}
        </div>
      )}
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
  rows: TikTokAnalysisRow[];
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
                {metricLabels[row.metric]}: {formatTikTokMetric(row.metric, row.value)}
              </b>
              <span className="shrink-0 text-muted">
                usual {formatTikTokMetric(row.metric, row.usual_min)}–{formatTikTokMetric(row.metric, row.usual_max)}
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

function TikTokRange({ row }: { row: TikTokAnalysisRow }) {
  const [showValue, setShowValue] = useState(false);
  const label = metricLabels[row.metric];
  const detail = `${formatTikTokMetric(row.metric, row.value)} · ${row.status === "inside" ? `#${row.rank}` : row.status}`;
  return (
    <div className="grid grid-cols-[72px_1fr] items-center gap-3 text-sm sm:grid-cols-[88px_1fr_108px]">
      <span className="font-semibold">{row.metric === "engagement_rate" ? "Engage." : label}</span>
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
