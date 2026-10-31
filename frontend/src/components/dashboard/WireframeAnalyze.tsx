"use client";

import { useCallback, useEffect, useState } from "react";
import { RangeRow, Session, TrackedPost, getTrackedPost, getTrackedPosts, refreshTrackedPost } from "@/lib/postbridge";
import { DashboardPageTitle } from "@/components/dashboard/DashboardPageTitle";

const label: Record<string, string> = { views: "Views", reach: "Reach", engagement_rate: "Engagement", shares: "Shares", saves: "Saves", comments: "Comments" };
const value = (metric: string, amount: number | null | undefined) => amount == null ? "–" : metric === "engagement_rate" ? `${Number(amount).toFixed(1)}%` : Number(amount).toLocaleString();
const shortDate = (date: string) => new Date(date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

export function WireframeAnalyze({ session, initialId, onClear }: { session: Session; initialId?: string; onClear: () => void }) {
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [selectedId, setSelectedId] = useState(initialId ?? "");
  const [post, setPost] = useState<TrackedPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (id: string) => {
    setLoading(true); setError("");
    try { setPost(await getTrackedPost(session, id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Couldn't load this post."); }
    finally { setLoading(false); }
  }, [session]);

  useEffect(() => {
    setSelectedId(initialId ?? "");
    if (initialId) void load(initialId);
    else getTrackedPosts(session).then(({ items }) => setPosts(items)).catch((reason) => setError(reason instanceof Error ? reason.message : "Couldn't load posts.")).finally(() => setLoading(false));
  }, [initialId, load, session]);

  const choose = (id: string) => { setSelectedId(id); void load(id); };
  const back = () => { setSelectedId(""); setPost(null); onClear(); setLoading(true); getTrackedPosts(session).then(({ items }) => setPosts(items)).finally(() => setLoading(false)); };
  const refresh = async () => {
    if (!selectedId || refreshing || cooldown) return;
    setRefreshing(true); setError("");
    try { setPost(await refreshTrackedPost(session, selectedId)); setCooldown(true); window.setTimeout(() => setCooldown(false), 60_000); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Couldn't update, showing earlier data"); }
    finally { setRefreshing(false); }
  };

  if (!selectedId) return <section className="mx-auto w-full lg:w-4/5"><div className="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 md:mb-7"><DashboardPageTitle>Post</DashboardPageTitle><span className="text-sm font-medium text-[#80778b] md:text-base">Choose one to analyze</span></div>{error ? <p className="mb-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}{loading ? <Card>Loading tracked posts…</Card> : posts.length ? <div className="grid gap-5 md:grid-cols-2">{posts.map((item) => <button key={item.tracking.id} onClick={() => choose(item.tracking.id)} className="text-left"><div className="h-full rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6">{item.media.thumbnail_url || item.media.media_url ? <img alt="Instagram post" src={item.media.thumbnail_url || item.media.media_url} className="mb-4 aspect-video w-full rounded-2xl object-cover" /> : <div className="mb-4 aspect-video w-full rounded-2xl bg-[#eee8fa]" />}<p className="line-clamp-2 font-bold">{item.media.caption || "Instagram post"}</p><div className="mt-5 grid grid-cols-3 gap-2 text-sm"><PickerMetric label="Likes" value={item.latest?.likes} /><PickerMetric label="Reach" value={item.latest?.reach} /><PickerMetric label="Engagement" value={item.latest?.engagement_rate == null ? undefined : `${Number(item.latest.engagement_rate).toFixed(1)}%`} /></div></div></button>)}</div> : <Card>Track an Instagram post first.</Card>}</section>;

  const analysis = post?.analysis;
  return <section className="mx-auto w-full max-w-[720px]">
    <div className="mb-5 flex items-center justify-between gap-3 md:mb-7">
      <DashboardPageTitle>Analyze</DashboardPageTitle>
      <button onClick={back} className="min-h-10 rounded-xl bg-[#EDE9FE] px-4 text-sm font-bold text-[#4C1D95]">Back</button>
    </div>
    {error ? <p className="mb-3 text-sm text-[#5F587A]">{error.includes("reconnect") ? "Reconnect Instagram to update." : "Couldn't update, showing earlier data"}</p> : null}
    {loading || !post ? <Card>Loading post…</Card> : <div className="space-y-4">
      <Card>
        <div className="flex gap-4">
          {post.media.thumbnail_url || post.media.media_url ? <img alt="Post cover" src={post.media.thumbnail_url || post.media.media_url} className="h-[104px] w-[104px] shrink-0 rounded-2xl object-cover" /> : <div className="h-[104px] w-[104px] shrink-0 rounded-2xl bg-[#D9D1F5]" />}
          <div className="flex min-w-0 flex-1 flex-col">
            <p className="truncate text-[17px] font-black lg:text-lg">{post.media.caption || "Instagram post"}</p>
            <p className="mt-1 text-[13px] text-[#5F587A]">{shortDate(post.media.published_at)} · {analysis?.media_format ?? "Post"} · {analysis?.age_days ?? 0} days</p>
            <button onClick={() => void refresh()} disabled={refreshing || cooldown} className="-ml-3 mt-auto flex min-h-11 w-fit items-end px-3 pb-0 text-[13px] font-semibold text-[#6D28D9] disabled:opacity-50">{refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh metrics"}</button>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-3">
          <Headline label="Reach" amount={post.latest?.reach} />
          <Headline label="Views" amount={post.latest?.views} />
          <Headline label="Engagement" amount={post.latest?.engagement_rate} rate />
        </div>
      </Card>

      {analysis?.summary ? <Card><h2 className="text-xl font-black">Post feedback</h2><p className="mt-3 text-[15px] leading-5 text-[#1E1633]">{analysis.summary}</p></Card> : null}

      {analysis?.comparable ? <>
        <div className="grid gap-4 lg:grid-cols-2">
          <FindingCard title="Stands out" tone="positive" rows={analysis.stands_out} empty="Nothing is above the usual range." />
          <FindingCard title="Weaker" tone="weaker" rows={analysis.weaker} empty="Nothing is weaker than usual." />
        </div>
        <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-black">Usual range</h2><span aria-hidden className="text-lg">⌃</span></div><div className="space-y-5">{analysis.usual_ranges.map((row) => <Range key={row.metric} row={row} />)}</div></Card>
      </> : <Card><p className="text-sm text-[#5F587A]">Not enough comparable posts yet</p></Card>}

      {analysis ? <Card><h2 className="text-xl font-black">Audience comments</h2><p className="mt-4 text-sm leading-5 text-[#5F587A]">{analysis.audience_comments.description ?? analysis.audience_comments.message}</p></Card> : null}
    </div>}
  </section>;
}

function Card({ children }: { children: React.ReactNode }) { return <div className="rounded-2xl border border-[#E8E2FA] bg-white p-5 shadow-[0_1px_2px_rgba(30,22,51,.03)]">{children}</div>; }
function PickerMetric({ label: metricLabel, value: metricValue }: { label: string; value?: number | string | null }) { return <div><p className="text-[10px] font-black uppercase tracking-wider text-[#80778b]">{metricLabel}</p><p className="mt-1 font-black">{typeof metricValue === "number" ? metricValue.toLocaleString() : metricValue ?? "–"}</p></div>; }
function Headline({ label, amount, rate = false }: { label: string; amount?: number | null; rate?: boolean }) { return <div><p className="text-[20px] font-black leading-none sm:text-[26px]">{amount == null ? "–" : rate ? `${Number(amount).toFixed(1)}%` : Number(amount).toLocaleString()}</p><p className="mt-2 text-[12px] text-[#5F587A] sm:text-[13px]">{label}</p></div>; }
function FindingCard({ title, tone, rows, empty }: { title: string; tone: "positive" | "weaker"; rows: RangeRow[]; empty: string }) { return <Card><p className={`text-[11px] font-black uppercase tracking-[.06em] ${tone === "positive" ? "text-[#166534]" : "text-[#92400E]"}`}>{title}</p>{rows.length ? <div className="mt-3 space-y-3">{rows.map((row) => <div key={row.metric} className="flex items-baseline justify-between gap-3 text-sm"><b>{label[row.metric]}: {value(row.metric, row.value)}</b><span className="shrink-0 text-[#5F587A]">usual {value(row.metric, row.usual_min)}–{value(row.metric, row.usual_max)}</span></div>)}</div> : <p className="mt-3 text-sm text-[#5F587A]">{empty}</p>}</Card>; }
function Range({ row }: { row: RangeRow }) {
  const [showValue, setShowValue] = useState(false);
  const markerColor = row.status === "above" ? "#15803D" : row.status === "below" ? "#92400E" : "#6D28D9";
  const detail = `${value(row.metric, row.value)} · ${row.status === "inside" ? `#${row.rank}` : row.status}`;
  return <div className="grid grid-cols-[72px_1fr] items-center gap-3 text-sm sm:grid-cols-[88px_1fr_108px]">
    <span className="font-semibold"><span className="sm:hidden">{row.metric === "engagement_rate" ? "Engage." : label[row.metric]}</span><span className="hidden sm:inline">{label[row.metric]}</span></span>
    <button type="button" aria-label={`${label[row.metric]}: ${detail}`} aria-expanded={showValue} onClick={() => setShowValue((current) => !current)} className="relative h-8 w-full rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
      <span className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-[#EEEAF9]" />
      <span className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-[#C4B5FD]" style={{ left: `${row.band_start}%`, width: `${Math.max(2, row.band_end - row.band_start)}%` }} />
      <span className="absolute top-1/2 h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white" style={{ left: `${row.marker}%`, background: markerColor }} />
      {showValue ? <span role="tooltip" className="absolute bottom-7 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-[#201633] px-2.5 py-1.5 text-xs font-bold text-white shadow-lg" style={{ left: `${Math.min(92, Math.max(8, row.marker))}%` }}>{detail}</span> : null}
    </button>
    <span className="hidden text-right text-[#5F587A] sm:block">{detail}</span>
  </div>;
}
