"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Connection, Session, TrackedPost, connectInstagram, getConnection,
  getInstagramMedia, getTrackedPosts, refreshTrackedPost, requestCode,
  saveSession, storedSession, trackInstagramPost, verifyCode,
} from "@/lib/postbridge";
import { WireframeAnalyze } from "@/components/dashboard/WireframeAnalyze";
import { WireframeInsights } from "@/components/dashboard/WireframeInsights";
import { LegacyCreate } from "@/components/dashboard/LegacyCreate";
import { LegacySettings } from "@/components/dashboard/LegacySettings";

type Tab = "home" | "create" | "analyze" | "insights" | "settings";
const tabs: Array<{ key: Tab; label: string; icon: string }> = [
  { key: "home", label: "Home", icon: "⌂" },
  { key: "create", label: "Create", icon: "+" },
  { key: "analyze", label: "Analyze", icon: "◎" },
  { key: "insights", label: "Insights", icon: "↗" },
  { key: "settings", label: "Settings", icon: "⚙" },
];

export default function DashboardPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<Tab>("home");
  const [analyzeId, setAnalyzeId] = useState("");
  useEffect(() => { setSession(storedSession()); setReady(true); }, []);
  const finishLogout = () => { saveSession(null); setSession(null); };

  if (!ready) return <div className="grid min-h-screen place-items-center bg-[#f7f5ff] text-[#5b21b6]">Loading PostBridge…</div>;
  if (!session) return <Login onLogin={(value) => { saveSession(value); setSession(value); }} />;

  return <div className="min-h-screen bg-[#f7f5ff] text-[#201633]">
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-[#e7e0f0] bg-white p-5 lg:flex lg:flex-col">
      <Brand />
      <nav className="mt-10 space-y-2">{tabs.map((item) => <NavButton key={item.key} label={item.label} icon={item.icon} active={tab === item.key} onClick={() => setTab(item.key)} />)}</nav>
      <p className="mt-auto break-all rounded-2xl bg-[#f2edff] p-4 text-sm font-bold leading-5 text-[#5b516c]">{session.user.email}</p>
    </aside>
    <header className="sticky top-0 z-20 flex h-16 items-center border-b border-[#e7e0f0] bg-[#f7f5ff]/90 px-5 backdrop-blur lg:hidden"><Brand compact /></header>
    <main className="mx-auto max-w-6xl px-5 pb-28 pt-7 lg:ml-64 lg:px-9 lg:pb-12">
      {tab === "home" && <Home session={session} onConnect={async () => { const result = await connectInstagram(session); window.location.href = result.authorization_url; }} />}
      {tab === "create" && <LegacyCreate session={session} />}
      {tab === "analyze" && <WireframeAnalyze session={session} initialId={analyzeId} onClear={() => setAnalyzeId("")} />}
      {tab === "insights" && <WireframeInsights session={session} onOpen={(id) => { setAnalyzeId(id); setTab("analyze"); }} />}
      {tab === "settings" && <LegacySettings session={session} onLogout={finishLogout} />}
    </main>
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-[#e7e0f0] bg-white lg:hidden">{tabs.map((item) => <button key={item.key} onClick={() => setTab(item.key)} className={`flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-bold ${tab === item.key ? "text-[#7c3aed]" : "text-[#80778b]"}`}><span className="text-lg">{item.icon}</span>{item.label}</button>)}</nav>
  </div>;
}

function Brand({ compact = false }: { compact?: boolean }) { return <div className={`flex items-center gap-3 ${compact ? "lg:hidden" : ""}`}><div className="grid h-10 w-10 place-items-center rounded-xl bg-[#7c3aed] font-black text-white">PB</div><div><div className="font-black">PostBridge</div>{!compact && <div className="text-[10px] uppercase tracking-[.2em] text-[#80778b]">Creator intelligence</div>}</div></div>; }
function NavButton({ label, icon, active, onClick }: { label: string; icon: string; active: boolean; onClick: () => void }) { return <button onClick={onClick} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold ${active ? "bg-[#eee8fa] text-[#5b21b6]" : "text-[#746b82] hover:bg-[#f7f5ff]"}`}><span className="w-5 text-center text-lg">{icon}</span>{label}</button>; }
function Title({ children, className = "mb-7" }: { children: React.ReactNode; className?: string }) { return <h1 className={`text-2xl font-black tracking-tight md:text-3xl ${className}`}>{children}</h1>; }
function Card({ children }: { children: React.ReactNode }) { return <div className="rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6">{children}</div>; }
function ErrorText({ value }: { value: string }) { return value ? <div className="mb-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{value}</div> : null; }
function Metric({ label, value }: { label: string; value?: number | string | null }) { return <div><p className="text-[10px] font-black uppercase tracking-wider text-[#80778b]">{label}</p><p className="mt-1 font-black">{typeof value === "number" ? value.toLocaleString() : value ?? "–"}</p></div>; }

function Login({ onLogin }: { onLogin: (value: Session) => void }) {
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [sent, setSent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const submit = async () => { setBusy(true); setError(""); try { if (!sent) { const result = await requestCode(email); setSent(true); if (result.development_code) setCode(result.development_code); } else onLogin(await verifyCode(email, code)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign in failed."); } finally { setBusy(false); } };
  return <main className="grid min-h-screen bg-[#24163b] p-5 md:grid-cols-2"><section className="hidden flex-col justify-between rounded-[2rem] bg-gradient-to-br from-[#7c3aed] to-[#4c1d95] p-12 text-white md:flex"><Brand /><div><p className="text-sm font-bold uppercase tracking-[.25em] text-violet-200">One account. Every screen.</p><h1 className="mt-5 max-w-lg text-5xl font-black leading-tight">Bridge every post to better results.</h1><p className="mt-5 max-w-md text-violet-100">Your Instagram connections, AI analyses and tracking history stay in sync across web and mobile.</p></div><span className="text-sm text-violet-200">PostBridge</span></section><section className="grid place-items-center p-4"><div className="w-full max-w-md"><div className="mb-8 md:hidden"><Brand /></div><p className="text-sm font-bold uppercase tracking-[.2em] text-violet-300">Welcome</p><h2 className="mt-3 text-4xl font-black text-white">Sign in to PostBridge</h2><p className="mt-3 text-sm leading-6 text-violet-200">We’ll email you a secure six-digit code. No password required.</p><ErrorText value={error} /><div className="mt-8 space-y-4"><input className="w-full rounded-2xl bg-white px-4 py-4 text-[#201633]" type="email" value={email} disabled={sent} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />{sent && <input className="w-full rounded-2xl bg-white px-4 py-4 text-[#201633]" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} placeholder="6-digit code" />}<button disabled={busy || !email || (sent && code.length !== 6)} onClick={() => void submit()} className="w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Please wait…" : sent ? "Verify and sign in" : "Email me a code"}</button></div></div></section></main>;
}

function Home({ session, onConnect }: { session: Session; onConnect: () => Promise<void> }) {
  const [connection, setConnection] = useState<Connection | null>(null); const [posts, setPosts] = useState<TrackedPost[]>([]); const [media, setMedia] = useState<Array<{ id: string; caption: string; media_url?: string; thumbnail_url?: string }>>([]); const [choosing, setChoosing] = useState(false); const [loading, setLoading] = useState(true); const [addingId, setAddingId] = useState(""); const [refreshingId, setRefreshingId] = useState(""); const [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); try { const [nextConnection, tracked] = await Promise.all([getConnection(session), getTrackedPosts(session)]); setConnection(nextConnection); setPosts(tracked.items); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load posts."); } finally { setLoading(false); } }, [session]);
  useEffect(() => { void load(); }, [load]);
  const choosePost = async () => { try { const items = (await getInstagramMedia(session)).items; const trackedIds = new Set(posts.map((post) => post.media.id)); setMedia(items.filter((item) => !trackedIds.has(item.id))); setChoosing(true); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load Instagram posts."); } };
  const addPost = async (mediaId: string) => { setAddingId(mediaId); setError(""); try { const tracked = await trackInstagramPost(session, mediaId); setChoosing(false); await refreshTrackedPost(session, tracked.id); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not add this Instagram post."); } finally { setAddingId(""); } };
  const refreshPost = async (trackedId: string) => { setRefreshingId(trackedId); setError(""); try { const refreshed = await refreshTrackedPost(session, trackedId); setPosts((current) => current.map((post) => post.tracking.id === trackedId ? refreshed : post)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not refresh metrics."); } finally { setRefreshingId(""); } };
  return <><div className="mb-8 flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:justify-between"><Title className="mb-0">Tracked posts</Title>{connection?.connected && <div className="flex flex-wrap gap-2">{connection.comment_ingestion?.enabled && !connection.comment_ingestion.permission_granted && <button onClick={() => void onConnect()} className="rounded-xl bg-[#eee8fa] px-4 py-3 text-sm font-bold text-[#5b21b6]">Reauthorize Instagram</button>}<button onClick={() => void choosePost()} className="rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Add a post</button></div>}</div><ErrorText value={error} />
    {choosing && <div className="mb-5"><Card><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-black">Choose an Instagram post</h2><button onClick={() => setChoosing(false)} className="text-sm font-bold text-[#5b21b6]">Close</button></div>{media.length ? <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{media.map((item) => <button key={item.id} disabled={Boolean(addingId)} onClick={() => void addPost(item.id)} className="overflow-hidden rounded-2xl bg-[#eee8fa] text-left disabled:opacity-60">{item.thumbnail_url || item.media_url ? <img alt="" src={item.thumbnail_url || item.media_url} className="aspect-square w-full object-cover" /> : <div className="aspect-square" />}<p className="line-clamp-2 p-3 text-xs font-bold">{addingId === item.id ? "Adding…" : item.caption || "Instagram post"}</p></button>)}</div> : <p className="py-8 text-center text-sm font-bold text-[#746b82]">All Instagram posts are already tracked.</p>}</Card></div>}
    {loading ? <Card>Loading your account…</Card> : !connection?.connected ? <Card><h2 className="text-xl font-black">Connect Instagram</h2><button onClick={() => void onConnect()} className="mt-5 rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Connect Instagram</button></Card> : posts.length === 0 ? <Card><h2 className="text-xl font-black">No tracked posts yet</h2><button onClick={() => void choosePost()} className="mt-5 rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Add a post</button></Card> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{posts.map((post) => <Card key={post.tracking.id}>{post.media.thumbnail_url || post.media.media_url ? <img alt="" src={post.media.thumbnail_url || post.media.media_url} className="mb-4 aspect-video w-full rounded-2xl object-cover" /> : null}<p className="line-clamp-2 font-bold">{post.media.caption || "Instagram post"}</p><div className="mt-5 grid grid-cols-3 gap-2 text-sm"><Metric label="Likes" value={post.latest?.likes} /><Metric label="Reach" value={post.latest?.reach} /><Metric label="Engagement" value={post.latest?.engagement_rate == null ? undefined : `${Number(post.latest.engagement_rate).toFixed(1)}%`} /></div><div className="mt-5 flex items-center justify-between gap-3 border-t border-[#eee8fa] pt-4"><p className="text-[11px] text-[#80778b]">{post.latest?.captured_at ? `Updated ${new Date(post.latest.captured_at).toLocaleString()}` : "Metrics not loaded"}</p><button disabled={Boolean(refreshingId)} onClick={() => void refreshPost(post.tracking.id)} className="shrink-0 rounded-lg bg-[#eee8fa] px-3 py-2 text-xs font-bold text-[#5b21b6] disabled:opacity-60">{refreshingId === post.tracking.id ? "Refreshing…" : "Refresh metrics"}</button></div></Card>)}</div>}
  </>;
}
