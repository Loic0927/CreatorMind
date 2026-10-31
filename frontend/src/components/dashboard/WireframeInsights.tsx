"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AccountInsights, MetricKey, PerformancePost, Session, getAccountInsights, refreshTrackedPost } from "@/lib/postbridge";

type SortKey = MetricKey | "newest";
const sortLabel: Record<SortKey, string> = { views: "Views", reach: "Reach", engagement_rate: "Engagement", shares: "Shares", saves: "Saves", comments: "Comments", newest: "Newest" };
const number = (value: number | null | undefined) => value == null ? "–" : Number(value).toLocaleString();
const rate = (value: number | null | undefined) => value == null ? "–" : `${Number(value).toFixed(1)}%`;
const date = (value: string) => new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function WireframeInsights({ session, onOpen }: { session: Session; onOpen: (trackedId: string) => void }) {
  const [data, setData] = useState<AccountInsights | null>(null);
  const [sort, setSort] = useState<SortKey>("newest");
  const [showAll, setShowAll] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [cooldowns, setCooldowns] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  const load = useCallback(async () => { try { setData(await getAccountInsights(session)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Couldn't load insights."); } }, [session]);
  useEffect(() => { void load(); }, [load]);

  const posts = useMemo(() => {
    const sorted = [...(data?.performance_posts ?? [])];
    sorted.sort((a, b) => sort === "newest" ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime() : (b.metrics[sort] ?? -1) - (a.metrics[sort] ?? -1));
    return showAll ? sorted : sorted.slice(0, 5);
  }, [data, showAll, sort]);

  const refresh = async (post: PerformancePost) => {
    if (!post.needs_refresh || refreshing || cooldowns.has(post.tracked_post_id)) return;
    setRefreshing(post.tracked_post_id); setError("");
    try {
      await refreshTrackedPost(session, post.tracked_post_id);
      setCooldowns((current) => new Set(current).add(post.tracked_post_id));
      window.setTimeout(() => setCooldowns((current) => { const next = new Set(current); next.delete(post.tracked_post_id); return next; }), 60_000);
      await load();
    } catch (reason) { setError(reason instanceof Error && reason.message.toLowerCase().includes("reconnect") ? "Reconnect Instagram to update." : "Couldn't update, showing earlier data"); }
    finally { setRefreshing(null); }
  };

  return <section className="mx-auto w-full max-w-[880px]">
    <h1 className="mb-5 text-[34px] font-black tracking-tight">Insights</h1>
    {error ? <p className="mb-3 text-sm text-[#5F587A]">{error}</p> : data?.sync_status === "failed" ? <p className="mb-3 text-sm text-[#5F587A]">Couldn't update, showing earlier data</p> : data?.sync_status === "reconnect_required" ? <p className="mb-3 text-sm text-[#5F587A]">Reconnect Instagram to update.</p> : null}
    {!data ? <Card>Loading insights…</Card> : <div className="space-y-4">
      {data.highlights.length === 4 ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{data.highlights.map((item) => <button key={item.label} onClick={() => onOpen(item.tracked_post_id)} className="text-left"><Card compact><p className="text-[11px] font-black uppercase tracking-[.06em] text-[#5F587A]">{item.label}</p><div className="mt-3 flex items-center gap-3">{item.thumbnail_url ? <img src={item.thumbnail_url} alt="" className="h-14 w-14 rounded-xl object-cover" /> : <div className="h-14 w-14 rounded-xl bg-[#D9D1F5]" />}<div><p className="text-[22px] font-black leading-none">{item.metric === "engagement_rate" ? rate(item.value) : number(item.value)}</p><p className="mt-2 text-[13px] text-[#5F587A]">{date(item.published_at)}</p></div></div></Card></button>)}</div> : null}

      {data.next_post_suggestion ? <Card><h2 className="text-xl font-black">Next post suggestion</h2><p className="mt-3 text-[15px] leading-5">{data.next_post_suggestion}</p></Card> : null}

      <Card>
        <div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-xl font-black">Posts</h2><label className="relative"><span className="sr-only">Sort posts</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)} className="min-h-11 appearance-none rounded-full border-0 bg-[#EDE9FE] py-2 pl-4 pr-8 text-sm font-bold text-[#4C1D95] outline-none"><option value="newest">Sort: Newest</option><option value="views">Sort: Views</option><option value="reach">Sort: Reach</option><option value="engagement_rate">Sort: Engagement</option><option value="shares">Sort: Shares</option><option value="saves">Sort: Saves</option><option value="comments">Sort: Comments</option></select><span className="pointer-events-none absolute right-3 top-3 text-[#4C1D95]">⌄</span></label></div>
        <div className="hidden grid-cols-[44px_64px_repeat(6,minmax(60px,.75fr))_minmax(88px,1fr)] items-center gap-3 border-b border-[#EEEAF9] pb-3 text-[11px] uppercase tracking-[.06em] text-[#5F587A] lg:grid"><span className="font-normal">Rank</span><span className="font-normal">Post</span><span className={sort === "views" ? "font-black" : "font-normal"}>Views</span><span className={sort === "reach" ? "font-black" : "font-normal"}>Reach</span><span className={sort === "engagement_rate" ? "font-black" : "font-normal"}>Eng.</span><span className={sort === "shares" ? "font-black" : "font-normal"}>Shares</span><span className={sort === "saves" ? "font-black" : "font-normal"}>Saves</span><span className={sort === "comments" ? "font-black" : "font-normal"}>Comments</span><span className={sort === "newest" ? "font-black" : "font-normal"}>Date</span></div>
        {posts.map((post) => <PostRow key={post.tracked_post_id} post={post} sort={sort} refreshing={refreshing === post.tracked_post_id} cooldown={cooldowns.has(post.tracked_post_id)} onOpen={() => onOpen(post.tracked_post_id)} onRefresh={() => void refresh(post)} />)}
        {(data.performance_posts.length > 5 && !showAll) ? <button onClick={() => setShowAll(true)} className="min-h-11 pt-4 text-left text-[15px] font-black text-[#6D28D9]">Show all {data.performance_posts.length}</button> : null}
      </Card>
    </div>}
  </section>;
}

function Card({ children, compact = false }: { children: React.ReactNode; compact?: boolean }) { return <div className={`rounded-2xl border border-[#E8E2FA] bg-white shadow-[0_1px_2px_rgba(30,22,51,.03)] ${compact ? "p-4" : "p-5"}`}>{children}</div>; }
function PostRow({ post, sort, refreshing, cooldown, onOpen, onRefresh }: { post: PerformancePost; sort: SortKey; refreshing: boolean; cooldown: boolean; onOpen: () => void; onRefresh: () => void }) { const rank = post.rank ? `#${post.rank}` : "–"; const weight = (key: SortKey) => sort === key ? "font-black" : "font-normal"; const refreshControl = post.needs_refresh ? <span role="button" tabIndex={0} onClick={(event) => { event.stopPropagation(); onRefresh(); }} onKeyDown={(event) => { if (event.key === "Enter") { event.stopPropagation(); onRefresh(); } }} className={`flex min-h-8 items-center text-[12px] font-semibold text-[#6D28D9] ${refreshing || cooldown ? "opacity-50" : ""}`}>{refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh"}</span> : null; return <div className="border-b border-[#EEEAF9] last:border-0"><button onClick={onOpen} className="grid min-h-[70px] w-full grid-cols-[32px_56px_1fr_70px] items-center gap-3 py-2 text-left lg:grid-cols-[44px_64px_repeat(6,minmax(60px,.75fr))_minmax(88px,1fr)]"><span className="font-semibold">{rank}</span>{post.thumbnail_url ? <img src={post.thumbnail_url} alt="" className="h-14 w-14 rounded-xl object-cover" /> : <span className="h-14 w-14 rounded-xl bg-[#D9D1F5]" />}<span className="lg:hidden"><span className={`block ${weight("newest")}`}>{date(post.published_at)}</span>{refreshControl}</span><span className="text-right lg:text-left"><span className={`block ${weight("views")}`}>{number(post.metrics.views)}</span><span className={`text-[13px] text-[#5F587A] lg:hidden ${weight("engagement_rate")}`}>{rate(post.metrics.engagement_rate)}</span></span><span className={`hidden lg:block ${weight("reach")}`}>{number(post.metrics.reach)}</span><span className={`hidden lg:block ${weight("engagement_rate")}`}>{rate(post.metrics.engagement_rate)}</span><span className={`hidden lg:block ${weight("shares")}`}>{number(post.metrics.shares)}</span><span className={`hidden lg:block ${weight("saves")}`}>{number(post.metrics.saves)}</span><span className={`hidden lg:block ${weight("comments")}`}>{number(post.metrics.comments)}</span><span className="hidden lg:block"><span className={weight("newest")}>{date(post.published_at)}</span>{refreshControl}</span></button></div>; }
