"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AccountInsights,
  ApiError,
  MetricKey,
  PerformancePost,
  Session,
  TikTokMetricKey,
  TikTokTrackedPost,
  getAccountInsights,
  getTikTokTrackedPosts,
  grantAIProcessingConsent,
  refreshTrackedPost,
  refreshTikTokTrackedPost,
} from "@/lib/postbridge";
import { AiConsentDialog } from "@/components/dashboard/AiConsentDialog";
import { errorMessage, formatMetric, formatNumber, formatRate, metricLabel } from "@/lib/format";
import { LoadingState } from "@/components/dashboard/LoadingState";
import { DashboardPlatform, PlatformNavigator } from "@/components/dashboard/PlatformNavigator";
import { Card } from "@/components/dashboard/ui";
import { UnifiedSelect } from "@/components/ui/UnifiedSelect";

type SortKey = MetricKey | "newest";
const sortKeys: SortKey[] = ["newest", "views", "reach", "engagement_rate", "shares", "saves", "comments"];
const sortLabel: Record<SortKey, string> = { ...metricLabel, newest: "Newest" } as Record<SortKey, string>;
const sortOptions = sortKeys.map((value) => ({ value, label: sortLabel[value] }));
const columns: Array<{ key: SortKey; label: string }> = [
  { key: "views", label: "Views" },
  { key: "reach", label: "Reach" },
  { key: "engagement_rate", label: "Eng." },
  { key: "shares", label: "Shares" },
  { key: "saves", label: "Saves" },
  { key: "comments", label: "Comments" },
  { key: "newest", label: "Date" },
];
const desktopGrid = "grid-cols-[44px_150px_repeat(6,minmax(52px,1fr))_72px]";
const collapsedCount = 5;
const staleMessage = "Couldn't update, showing earlier data";
const reconnectMessage = "Reconnect Instagram to update.";
const shortDate = (value: string) => new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const cellValue = (post: PerformancePost, key: SortKey) =>
  key === "newest" ? shortDate(post.published_at) : formatMetric(key, post.metrics[key]);

export function InsightsTab({ session, onOpen }: { session: Session; onOpen: (trackedId: string) => void }) {
  const [data, setData] = useState<AccountInsights | null>(null);
  const [platform, setPlatform] = useState<DashboardPlatform>("Instagram");
  const [sort, setSort] = useState<SortKey>("newest");
  const [showAll, setShowAll] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [cooldowns, setCooldowns] = useState<Set<string>>(new Set());
  const [consentDialogOpen, setConsentDialogOpen] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await getAccountInsights(session));
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "consent_required") {
        setConsentDialogOpen(true);
        setError("");
        return;
      }
      setError(errorMessage(reason, "Couldn't load insights."));
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  const posts = useMemo(() => {
    const sorted = [...(data?.performance_posts ?? [])].sort((a, b) =>
      sort === "newest"
        ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
        : (b.metrics[sort] ?? -1) - (a.metrics[sort] ?? -1),
    );
    return showAll ? sorted : sorted.slice(0, collapsedCount);
  }, [data, showAll, sort]);

  const refresh = async (post: PerformancePost) => {
    const id = post.tracked_post_id;
    if (!post.needs_refresh || refreshing || cooldowns.has(id)) return;
    setRefreshing(id);
    setError("");
    try {
      await refreshTrackedPost(session, id);
      setCooldowns((current) => new Set(current).add(id));
      window.setTimeout(
        () =>
          setCooldowns((current) => {
            const next = new Set(current);
            next.delete(id);
            return next;
          }),
        60_000,
      );
      await load();
    } catch (reason) {
      setError(errorMessage(reason, "").toLowerCase().includes("reconnect") ? reconnectMessage : staleMessage);
    } finally {
      setRefreshing(null);
    }
  };

  const acceptConsent = async () => {
    setSavingConsent(true);
    setError("");
    try {
      await grantAIProcessingConsent(session);
      setConsentDialogOpen(false);
      await load();
    } catch (reason) {
      setError(errorMessage(reason, "Could not save AI processing consent."));
    } finally {
      setSavingConsent(false);
    }
  };

  const notice =
    error ||
    (data?.sync_status === "failed"
      ? staleMessage
      : data?.sync_status === "reconnect_required"
        ? reconnectMessage
        : "");

  if (platform === "TikTok") {
    return <TikTokInsights session={session} onOpen={onOpen} onPlatformChange={setPlatform} />;
  }

  return (
    <section className="mx-auto w-full max-w-[880px]">
      <PlatformNavigator value={platform} onChange={setPlatform} className="mb-5 md:mb-7" />
      {notice ? <p className="mb-3 text-sm text-muted">{notice}</p> : null}
      {!data ? (
        <LoadingState label="Preparing your insights" />
      ) : (
        <div className="space-y-4">
          {data.highlights.length === 4 ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {data.highlights.map((item) => (
                <button key={item.label} onClick={() => onOpen(item.tracked_post_id)} className="h-full text-left">
                  <Card compact className="h-full">
                    <p className="min-h-8 text-[11px] font-black uppercase tracking-[.06em] text-muted lg:min-h-0">
                      {item.label}
                    </p>
                    <div className="mt-3 grid grid-cols-[40px_minmax(0,1fr)] items-center gap-2.5 sm:grid-cols-[56px_minmax(0,1fr)]">
                      {item.thumbnail_url ? (
                        <img
                          src={item.thumbnail_url}
                          alt=""
                          className="h-14 w-10 shrink-0 rounded-lg object-cover object-center sm:w-14 sm:rounded-xl"
                        />
                      ) : (
                        <div className="h-14 w-10 shrink-0 rounded-lg bg-line-strong sm:w-14 sm:rounded-xl" />
                      )}
                      <div className="min-w-0">
                        <p className="text-[20px] font-black leading-none sm:text-[22px]">
                          {item.metric === "engagement_rate" ? formatRate(item.value) : formatNumber(item.value)}
                        </p>
                        <p className="mt-2 whitespace-nowrap text-[12px] text-muted sm:text-[13px]">
                          {shortDate(item.published_at)}
                        </p>
                      </div>
                    </div>
                  </Card>
                </button>
              ))}
            </div>
          ) : null}

          {data.next_post_suggestion ? (
            <Card>
              <h2 className="text-xl font-black">Next post suggestion</h2>
              <p className="mt-3 text-[15px] leading-5">{data.next_post_suggestion}</p>
            </Card>
          ) : data.next_post_suggestion_status === "pending" ? (
            <Card>
              <h2 className="text-xl font-black">Next post suggestion</h2>
              <p className="mt-3 text-[15px] leading-5 text-muted">Your suggestion is being prepared.</p>
            </Card>
          ) : data.next_post_suggestion_status === "consent_required" ? (
            <Card>
              <h2 className="text-xl font-black">Next post suggestion</h2>
              <p className="mt-3 text-[15px] leading-5 text-muted">
                Enable optional AI processing to receive a next-post suggestion.
              </p>
              <button
                type="button"
                onClick={() => setConsentDialogOpen(true)}
                className="mt-4 min-h-10 rounded-xl bg-primary px-4 text-sm font-black text-white hover:bg-primary-hover"
              >
                Review AI data use
              </button>
            </Card>
          ) : null}

          <Card>
            <div className="mb-3 flex items-center gap-3">
              <h2 className="text-xl font-black">Posts</h2>
              <div className="ml-auto w-[150px]">
                <UnifiedSelect
                  label="Sort"
                  title="Sort posts"
                  options={sortOptions}
                  value={sort}
                  onChange={(next) => setSort(next as SortKey)}
                  compact
                />
              </div>
            </div>
            <div
              className={`hidden ${desktopGrid} items-center gap-3 border-b border-line pb-3 text-[11px] uppercase tracking-[.06em] text-muted lg:grid`}
            >
              <span className="font-normal">Rank</span>
              <span className="font-normal">Post</span>
              {columns.map((column) => (
                <span key={column.key} className={sort === column.key ? "font-black" : "font-normal"}>
                  {column.label}
                </span>
              ))}
            </div>
            {posts.map((post) => (
              <PostRow
                key={post.tracked_post_id}
                post={post}
                sort={sort}
                refreshing={refreshing === post.tracked_post_id}
                cooldown={cooldowns.has(post.tracked_post_id)}
                onOpen={() => onOpen(post.tracked_post_id)}
                onRefresh={() => void refresh(post)}
              />
            ))}
            {data.performance_posts.length > collapsedCount && !showAll ? (
              <button
                onClick={() => setShowAll(true)}
                className="min-h-11 pt-4 text-left text-[15px] font-black text-primary"
              >
                Show all {data.performance_posts.length}
              </button>
            ) : null}
          </Card>
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

type TikTokSortKey = TikTokMetricKey | "newest";
const tikTokSortKeys: TikTokSortKey[] = ["newest", "views", "likes", "engagement_rate", "shares", "comments"];
const tikTokSortLabels: Record<TikTokSortKey, string> = {
  newest: "Newest",
  views: "Views",
  likes: "Likes",
  engagement_rate: "Engagement",
  shares: "Shares",
  comments: "Comments",
};
const tikTokSortOptions = tikTokSortKeys.map((value) => ({ value, label: tikTokSortLabels[value] }));
const tikTokColumns: Array<{ key: TikTokSortKey; label: string }> = [
  { key: "views", label: "Views" },
  { key: "likes", label: "Likes" },
  { key: "engagement_rate", label: "Eng." },
  { key: "shares", label: "Shares" },
  { key: "comments", label: "Comments" },
  { key: "newest", label: "Date" },
];
const tikTokDesktopGrid = "grid-cols-[44px_150px_repeat(5,minmax(52px,1fr))_72px]";
const tikTokMetricValue = (post: TikTokTrackedPost, key: TikTokSortKey) => {
  if (key === "newest") return shortDate(post.published_at ?? post.created_at);
  if (key === "engagement_rate") return formatRate(post.engagement_rate);
  return formatNumber(post[key]);
};

function TikTokInsights({
  session,
  onOpen,
  onPlatformChange,
}: {
  session: Session;
  onOpen: (trackedId: string) => void;
  onPlatformChange: (platform: DashboardPlatform) => void;
}) {
  const [items, setItems] = useState<TikTokTrackedPost[]>([]);
  const [sort, setSort] = useState<TikTokSortKey>("newest");
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { items: nextItems } = await getTikTokTrackedPosts(session);
      setItems(nextItems);
      setError("");
    } catch (reason) {
      setError(errorMessage(reason, "Couldn't load TikTok insights."));
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(() => {
    const next = [...items].sort((left, right) => {
      if (sort === "newest") {
        return (
          new Date(right.published_at ?? right.created_at).getTime() -
          new Date(left.published_at ?? left.created_at).getTime()
        );
      }
      return (right[sort] ?? -1) - (left[sort] ?? -1);
    });
    return showAll ? next : next.slice(0, collapsedCount);
  }, [items, showAll, sort]);

  const highlights = useMemo(() => {
    const views = items.filter((item) => item.views != null);
    const engagement = items.filter((item) => item.engagement_rate != null);
    if (!views.length || !engagement.length) return [];
    return [
      {
        label: "Highest views",
        post: views.reduce((a, b) => ((a.views ?? 0) >= (b.views ?? 0) ? a : b)),
        metric: "views" as const,
      },
      {
        label: "Lowest views",
        post: views.reduce((a, b) => ((a.views ?? 0) <= (b.views ?? 0) ? a : b)),
        metric: "views" as const,
      },
      {
        label: "Highest engagement",
        post: engagement.reduce((a, b) => ((a.engagement_rate ?? 0) >= (b.engagement_rate ?? 0) ? a : b)),
        metric: "engagement_rate" as const,
      },
      {
        label: "Lowest engagement",
        post: engagement.reduce((a, b) => ((a.engagement_rate ?? 0) <= (b.engagement_rate ?? 0) ? a : b)),
        metric: "engagement_rate" as const,
      },
    ];
  }, [items]);

  const refresh = async (post: TikTokTrackedPost) => {
    if (refreshing) return;
    setRefreshing(post.id);
    try {
      const updated = await refreshTikTokTrackedPost(session, post.id);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setError("");
    } catch (reason) {
      setError(errorMessage(reason, "Couldn't refresh TikTok metrics."));
    } finally {
      setRefreshing(null);
    }
  };

  const strongest = highlights.find((item) => item.label === "Highest engagement")?.post;

  return (
    <section className="mx-auto w-full max-w-[880px]">
      <PlatformNavigator value="TikTok" onChange={onPlatformChange} className="mb-5 md:mb-7" />
      {error ? <p className="mb-3 text-sm text-muted">{error}</p> : null}
      {loading ? (
        <LoadingState label="Preparing your TikTok insights" />
      ) : !items.length ? (
        <Card>Track a TikTok post first.</Card>
      ) : (
        <div className="space-y-4">
          {highlights.length === 4 ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {highlights.map(({ label, post, metric }) => (
                <button key={label} onClick={() => onOpen(`tiktok:${post.id}`)} className="h-full text-left">
                  <Card compact className="h-full">
                    <p className="min-h-8 text-[11px] font-black uppercase tracking-[.06em] text-muted lg:min-h-0">
                      {label}
                    </p>
                    <div className="mt-3 grid grid-cols-[40px_minmax(0,1fr)] items-center gap-2.5 sm:grid-cols-[56px_minmax(0,1fr)]">
                      {post.thumbnail_url ? (
                        <img src={post.thumbnail_url} alt="" className="h-14 w-10 rounded-lg object-cover sm:w-14" />
                      ) : (
                        <div className="h-14 w-10 rounded-lg bg-line-strong sm:w-14" />
                      )}
                      <div className="min-w-0">
                        <p className="text-[20px] font-black leading-none sm:text-[22px]">
                          {metric === "engagement_rate" ? formatRate(post.engagement_rate) : formatNumber(post.views)}
                        </p>
                        <p className="mt-2 whitespace-nowrap text-[12px] text-muted">
                          {shortDate(post.published_at ?? post.created_at)}
                        </p>
                      </div>
                    </div>
                  </Card>
                </button>
              ))}
            </div>
          ) : null}

          {strongest && items.length >= 3 ? (
            <Card>
              <h2 className="text-xl font-black">Next post suggestion</h2>
              <p className="mt-3 text-[15px] leading-5">
                Your strongest tracked TikTok by engagement is “{strongest.caption || "TikTok post"}”. Test one similar
                opening or format in your next post while changing only one creative element.
              </p>
            </Card>
          ) : null}

          <Card>
            <div className="mb-3 flex items-center gap-3">
              <h2 className="text-xl font-black">Posts</h2>
              <div className="ml-auto w-[150px]">
                <UnifiedSelect
                  label="Sort"
                  title="Sort TikTok posts"
                  options={tikTokSortOptions}
                  value={sort}
                  onChange={(next) => setSort(next as TikTokSortKey)}
                  compact
                />
              </div>
            </div>
            <div
              className={`hidden ${tikTokDesktopGrid} items-center gap-3 border-b border-line pb-3 text-[11px] uppercase tracking-[.06em] text-muted lg:grid`}
            >
              <span>Rank</span>
              <span>Post</span>
              {tikTokColumns.map((column) => (
                <span key={column.key} className={sort === column.key ? "font-black" : "font-normal"}>
                  {column.label}
                </span>
              ))}
            </div>
            {sorted.map((post, index) => (
              <TikTokPostRow
                key={post.id}
                post={post}
                rank={index + 1}
                sort={sort}
                refreshing={refreshing === post.id}
                onOpen={() => onOpen(`tiktok:${post.id}`)}
                onRefresh={() => void refresh(post)}
              />
            ))}
            {items.length > collapsedCount && !showAll ? (
              <button onClick={() => setShowAll(true)} className="min-h-11 pt-4 text-[15px] font-black text-primary">
                Show all {items.length}
              </button>
            ) : null}
          </Card>
        </div>
      )}
    </section>
  );
}

function TikTokPostRow({
  post,
  rank,
  sort,
  refreshing,
  onOpen,
  onRefresh,
}: {
  post: TikTokTrackedPost;
  rank: number;
  sort: TikTokSortKey;
  refreshing: boolean;
  onOpen: () => void;
  onRefresh: () => void;
}) {
  const cover = post.thumbnail_url ? (
    <img src={post.thumbnail_url} alt="" className="h-14 w-14 shrink-0 rounded-xl object-cover" />
  ) : (
    <span className="h-14 w-14 shrink-0 rounded-xl bg-line-strong" />
  );
  const rowProps = {
    role: "button",
    tabIndex: 0,
    onClick: onOpen,
    onKeyDown: (event: React.KeyboardEvent) => {
      if (event.key === "Enter") onOpen();
    },
  };
  const refreshButton = (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onRefresh();
      }}
      className="min-h-8 text-[12px] font-semibold text-primary disabled:opacity-50"
      disabled={refreshing}
    >
      {refreshing ? "Refreshing…" : "Refresh"}
    </button>
  );
  return (
    <div className="border-b border-line last:border-0">
      <div
        {...rowProps}
        className="grid min-h-[72px] cursor-pointer grid-cols-[32px_minmax(108px,1fr)_72px] items-center gap-3 py-2 lg:hidden"
      >
        <span className="font-semibold">#{rank}</span>
        <span className="flex items-center gap-2">
          {cover}
          {refreshButton}
        </span>
        <span className="text-right font-black">{tikTokMetricValue(post, sort)}</span>
      </div>
      <div
        {...rowProps}
        className={`hidden min-h-[72px] cursor-pointer ${tikTokDesktopGrid} items-center gap-3 py-2 lg:grid`}
      >
        <span className="font-semibold">#{rank}</span>
        <span className="flex items-center gap-3">
          {cover}
          {refreshButton}
        </span>
        {tikTokColumns.map((column) => (
          <span key={column.key} className={sort === column.key ? "font-black" : "font-normal"}>
            {tikTokMetricValue(post, column.key)}
          </span>
        ))}
      </div>
    </div>
  );
}

function PostRow({
  post,
  sort,
  refreshing,
  cooldown,
  onOpen,
  onRefresh,
}: {
  post: PerformancePost;
  sort: SortKey;
  refreshing: boolean;
  cooldown: boolean;
  onOpen: () => void;
  onRefresh: () => void;
}) {
  const rank = post.rank ? `#${post.rank}` : "–";
  const selectedValue = cellValue(post, sort);
  const rowProps = {
    role: "button",
    tabIndex: 0,
    onClick: onOpen,
    onKeyDown: (event: React.KeyboardEvent) => {
      if (event.key === "Enter") onOpen();
    },
  };
  const refreshControl = post.needs_refresh ? (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onRefresh();
      }}
      className={`min-h-8 shrink-0 text-[12px] font-semibold text-primary ${refreshing || cooldown ? "opacity-50" : ""}`}
    >
      {refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh"}
    </button>
  ) : null;
  const cover = post.thumbnail_url ? (
    <img src={post.thumbnail_url} alt="" className="h-14 w-14 shrink-0 rounded-xl object-cover object-center" />
  ) : (
    <span className="h-14 w-14 shrink-0 rounded-xl bg-line-strong" />
  );

  return (
    <div className="border-b border-line last:border-0">
      <div
        {...rowProps}
        className="grid min-h-[72px] cursor-pointer grid-cols-[32px_minmax(108px,1fr)_72px] items-center gap-3 py-2 text-left lg:hidden"
      >
        <span className="font-semibold">{rank}</span>
        <span className="flex min-w-0 items-center gap-2">
          {cover}
          {refreshControl}
        </span>
        <span className="text-right font-black" aria-label={`${sortLabel[sort]}: ${selectedValue}`}>
          {selectedValue}
        </span>
      </div>
      <div
        {...rowProps}
        className={`hidden min-h-[72px] cursor-pointer ${desktopGrid} items-center gap-3 py-2 text-left lg:grid`}
      >
        <span className="font-semibold">{rank}</span>
        <span className="flex min-w-0 items-center gap-3">
          {cover}
          {refreshControl}
        </span>
        {columns.map((column) => (
          <span key={column.key} className={sort === column.key ? "font-black" : "font-normal"}>
            {cellValue(post, column.key)}
          </span>
        ))}
      </div>
    </div>
  );
}
