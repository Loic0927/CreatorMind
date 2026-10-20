"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Connection, Prediction, Session, TrackedPost, caption, connectInstagram,
  deleteAccount, getConnection, getHistory, getInstagramMedia, getTrackedPosts, logout,
  predict, refreshTrackedPost, requestCode, saveSession, storedSession, trackInstagramPost, verifyCode,
} from "@/lib/postbridge";

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
  useEffect(() => { setSession(storedSession()); setReady(true); }, []);
  const finishLogin = (value: Session) => { saveSession(value); setSession(value); };
  const finishLogout = () => { saveSession(null); setSession(null); };
  if (!ready) return <div className="grid min-h-screen place-items-center bg-[#f7f5ff] text-[#5b21b6]">Loading PostBridge…</div>;
  if (!session) return <Login onLogin={finishLogin} />;
  return <div className="min-h-screen bg-[#f7f5ff] text-[#201633]">
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-[#e7e0f0] bg-white p-5 lg:flex lg:flex-col">
      <Brand />
      <nav className="mt-10 space-y-2">{tabs.map((item) => <NavButton key={item.key} active={tab === item.key} label={item.label} icon={item.icon} onClick={() => setTab(item.key)} />)}</nav>
      <p className="mt-auto rounded-2xl bg-[#f2edff] p-4 text-xs leading-5 text-[#6b5c7c]">Create, analyze and track every post from the same account you use in the PostBridge app.</p>
    </aside>
    <header className="sticky top-0 z-20 flex h-16 items-center border-b border-[#e7e0f0] bg-[#f7f5ff]/90 px-5 backdrop-blur lg:ml-64 lg:px-9"><Brand compact /><div className="ml-auto text-sm font-semibold text-[#746b82]">{session.user.email}</div></header>
    <main className="mx-auto max-w-6xl px-5 pb-28 pt-7 lg:ml-64 lg:px-9 lg:pb-12">
      {tab === "home" && <Home session={session} onConnect={async () => { const result = await connectInstagram(session); window.location.href = result.authorization_url; }} />}
      {tab === "create" && <Create session={session} />}
      {tab === "analyze" && <Analyze session={session} />}
      {tab === "insights" && <Insights session={session} />}
      {tab === "settings" && <Settings session={session} onLogout={finishLogout} />}
    </main>
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-[#e7e0f0] bg-white lg:hidden">{tabs.map((item) => <button key={item.key} onClick={() => setTab(item.key)} className={`flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-bold ${tab === item.key ? "text-[#7c3aed]" : "text-[#80778b]"}`}><span className="text-lg">{item.icon}</span>{item.label}</button>)}</nav>
  </div>;
}

function Brand({ compact = false }: { compact?: boolean }) { return <div className={`flex items-center gap-3 ${compact ? "lg:hidden" : ""}`}><div className="grid h-10 w-10 place-items-center rounded-xl bg-[#7c3aed] font-black text-white">PB</div><div><div className="font-black">PostBridge</div>{!compact && <div className="text-[10px] uppercase tracking-[.2em] text-[#80778b]">Creator intelligence</div>}</div></div>; }
function NavButton({ label, icon, active, onClick }: { label: string; icon: string; active: boolean; onClick: () => void }) { return <button onClick={onClick} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold ${active ? "bg-[#eee8fa] text-[#5b21b6]" : "text-[#746b82] hover:bg-[#f7f5ff]"}`}><span className="w-5 text-center text-lg">{icon}</span>{label}</button>; }
function Title({ children, className = "mb-7" }: { children: React.ReactNode; text?: string; className?: string }) { return <h1 className={`text-2xl font-black tracking-tight md:text-3xl ${className}`}>{children}</h1>; }
function Card({ children, dark = false }: { children: React.ReactNode; dark?: boolean }) { return <div className={`rounded-3xl border p-5 shadow-sm md:p-6 ${dark ? "border-[#392651] bg-[#24163b] text-white" : "border-[#e7e0f0] bg-white"}`}>{children}</div>; }
function ErrorText({ value }: { value: string }) { return value ? <div className="mb-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{value}</div> : null; }

function Login({ onLogin }: { onLogin: (value: Session) => void }) {
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [sent, setSent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const submit = async () => { setBusy(true); setError(""); try { if (!sent) { const result = await requestCode(email); setSent(true); if (result.development_code) setCode(result.development_code); } else { onLogin(await verifyCode(email, code)); } } catch (e) { setError(e instanceof Error ? e.message : "Sign in failed."); } finally { setBusy(false); } };
  return <main className="grid min-h-screen bg-[#24163b] p-5 md:grid-cols-2"><section className="hidden flex-col justify-between rounded-[2rem] bg-gradient-to-br from-[#7c3aed] to-[#4c1d95] p-12 text-white md:flex"><Brand /><div><p className="text-sm font-bold uppercase tracking-[.25em] text-violet-200">One account. Every screen.</p><h1 className="mt-5 max-w-lg text-5xl font-black leading-tight">Bridge every post to better results.</h1><p className="mt-5 max-w-md text-violet-100">Your Instagram connections, AI analyses and tracking history stay in sync across web and mobile.</p></div><span className="text-sm text-violet-200">PostBridge</span></section><section className="grid place-items-center p-4"><div className="w-full max-w-md"><div className="mb-8 md:hidden"><Brand /></div><p className="text-sm font-bold uppercase tracking-[.2em] text-violet-300">Welcome</p><h2 className="mt-3 text-4xl font-black text-white">Sign in to PostBridge</h2><p className="mt-3 text-sm leading-6 text-violet-200">We’ll email you a secure six-digit code. No password required.</p><ErrorText value={error} /><div className="mt-8 space-y-4"><input className="w-full rounded-2xl border border-white/20 bg-white px-4 py-4 text-[#201633] outline-none ring-violet-400 focus:ring-2" type="email" value={email} disabled={sent} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />{sent && <input className="w-full rounded-2xl border border-white/20 bg-white px-4 py-4 text-[#201633] outline-none ring-violet-400 focus:ring-2" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} placeholder="6-digit code" />}<button disabled={busy || !email || (sent && code.length !== 6)} onClick={submit} className="w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Please wait…" : sent ? "Verify and sign in" : "Email me a code"}</button>{sent && <button onClick={() => { setSent(false); setCode(""); }} className="w-full py-2 text-sm font-bold text-violet-200">Use a different email</button>}</div></div></section></main>;
}

function Home({ session, onConnect }: { session: Session; onConnect: () => Promise<void> }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [media, setMedia] = useState<Array<{ id: string; caption: string; media_url?: string; thumbnail_url?: string }>>([]);
  const [choosing, setChoosing] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [addingMediaId, setAddingMediaId] = useState<string | null>(null);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const load = useCallback(async (clearError = true) => {
    setLoading(true);
    if (clearError) setError("");
    try {
      const [nextConnection, tracked] = await Promise.all([getConnection(session), getTrackedPosts(session)]);
      setConnection(nextConnection);
      setPosts(tracked.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load posts.");
    } finally {
      setLoading(false);
    }
  }, [session]);
  useEffect(() => { void load(); }, [load]);
  const choosePost = async () => {
    try {
      setError("");
      setMedia((await getInstagramMedia(session)).items);
      setChoosing(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Instagram posts.");
    }
  };
  const addPost = async (mediaId: string) => {
    setAddingMediaId(mediaId);
    setError("");
    try {
      const tracked = await trackInstagramPost(session, mediaId);
      setChoosing(false);
      try {
        await refreshTrackedPost(session, tracked.id);
      } catch (e) {
        setError(`Post added, but metrics could not be refreshed: ${e instanceof Error ? e.message : "Instagram insights are unavailable."}`);
      }
      await load(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add this Instagram post.");
    } finally {
      setAddingMediaId(null);
    }
  };
  const refreshPost = async (trackedId: string) => {
    setRefreshingId(trackedId);
    setError("");
    try {
      const refreshed = await refreshTrackedPost(session, trackedId);
      setPosts((current) => current.map((post) => post.tracking.id === trackedId ? refreshed : post));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not refresh Instagram metrics.");
    } finally {
      setRefreshingId(null);
    }
  };
  return <>
    <div className="mb-8 flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:justify-between">
      <Title className="mb-0">Tracked posts</Title>
      {connection?.connected && <button onClick={() => void choosePost()} className="rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Add a post</button>}
    </div>
    <ErrorText value={error} />
    {choosing && <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-black">Choose an Instagram post</h2><button disabled={addingMediaId !== null} onClick={() => setChoosing(false)} className="text-sm font-bold text-[#5b21b6] disabled:opacity-50">Close</button></div><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{media.map((item) => <button key={item.id} disabled={addingMediaId !== null} onClick={() => void addPost(item.id)} className="overflow-hidden rounded-2xl bg-[#eee8fa] text-left disabled:cursor-wait disabled:opacity-60">{(item.thumbnail_url || item.media_url) ? <img alt="Instagram post" src={item.thumbnail_url || item.media_url} className="aspect-square w-full object-cover" /> : <div className="aspect-square" />}<p className="line-clamp-2 p-3 text-xs font-bold">{addingMediaId === item.id ? "Adding and loading metrics…" : item.caption || "Instagram post"}</p></button>)}</div></Card>}
    {loading ? <Card>Loading your account…</Card> : !connection?.connected ? <Card><h2 className="text-xl font-black">Connect Instagram</h2><button onClick={() => void onConnect()} className="mt-5 rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Connect Instagram</button></Card> : posts.length === 0 ? <Card><h2 className="text-xl font-black">No tracked posts yet</h2><button onClick={() => void choosePost()} className="mt-5 rounded-xl bg-[#7c3aed] px-5 py-3 font-bold text-white">Add a post</button></Card> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{posts.map((post) => <Card key={post.tracking.id}>{(post.media.thumbnail_url || post.media.media_url) && <img alt="Instagram post" src={post.media.thumbnail_url || post.media.media_url} className="mb-4 aspect-video w-full rounded-2xl object-cover" />}<p className="line-clamp-2 font-bold">{post.media.caption || "Instagram post"}</p><div className="mt-5 grid grid-cols-3 gap-2 text-sm"><Metric label="Likes" value={post.latest?.likes} /><Metric label="Reach" value={post.latest?.reach} /><Metric label="Engagement" value={post.latest?.engagement_rate == null ? undefined : `${post.latest.engagement_rate}%`} /></div><div className="mt-5 flex items-center justify-between gap-3 border-t border-[#eee8fa] pt-4"><p className="text-[11px] text-[#80778b]">{post.latest?.captured_at ? `Updated ${new Date(post.latest.captured_at).toLocaleString()}` : "Metrics have not been loaded yet."}</p><button disabled={refreshingId !== null} onClick={() => void refreshPost(post.tracking.id)} className="shrink-0 rounded-lg bg-[#eee8fa] px-3 py-2 text-xs font-bold text-[#5b21b6] disabled:cursor-wait disabled:opacity-60">{refreshingId === post.tracking.id ? "Refreshing…" : "Refresh metrics"}</button></div></Card>)}</div>}
  </>;
}

function Create({ session }: { session: Session }) {
  const [information, setInformation] = useState(""); const [goal, setGoal] = useState("Grow engagement"); const [image, setImage] = useState(""); const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null); const [analysis, setAnalysis] = useState<Prediction | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const run = async () => { setBusy(true); setError(""); try { const generated = await caption(session, { information, goal }); setResult(generated); setAnalysis(await predict(session, { platform: "Instagram", contentType: "Post", captionLength: generated.caption.length, hashtagsCount: generated.hashtags.split(/\s+/).filter((item) => item.startsWith("#")).length, postingHour: new Date().getHours() })); } catch (e) { setError(e instanceof Error ? e.message : "Generation failed."); } finally { setBusy(false); } };
  return <><Title text="Create the same AI-assisted caption and prediction available in the mobile app.">Create post</Title><ErrorText value={error} /><div className="grid gap-6 xl:grid-cols-[1fr_.9fr]"><Card><label className="text-sm font-bold">Image</label><label className="mt-2 grid min-h-44 cursor-pointer place-items-center overflow-hidden rounded-2xl border border-dashed border-[#b9aec8] bg-[#f7f5ff] text-sm font-bold text-[#5b21b6]">{image ? <img src={image} alt="Selected post" className="h-full max-h-80 w-full object-cover" /> : "Choose an image"}<input type="file" accept="image/*" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) setImage(URL.createObjectURL(file)); }} /></label><label className="mt-5 block text-sm font-bold">Information</label><textarea value={information} onChange={(e) => setInformation(e.target.value)} className="mt-2 min-h-32 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Describe your content, audience and key message" /><label className="mt-5 block text-sm font-bold">Goal</label><select value={goal} onChange={(e) => setGoal(e.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4"><option>Grow engagement</option><option>Educate</option><option>Build trust</option><option>Drive conversions</option></select><button disabled={busy || !information || !image} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating…" : "Create caption + analysis"}</button></Card><div className="space-y-6">{result ? <><Card><h2 className="text-xl font-black">Caption</h2><textarea className="mt-4 min-h-40 w-full rounded-xl bg-[#f7f5ff] p-4" value={result.caption} onChange={(e) => setResult({ ...result, caption: e.target.value })} /><textarea className="mt-3 min-h-20 w-full rounded-xl bg-[#f7f5ff] p-4 text-[#5b21b6]" value={result.hashtags} onChange={(e) => setResult({ ...result, hashtags: e.target.value })} /></Card>{analysis && <AnalysisCard value={analysis} />}</> : <Card><p className="text-sm text-[#746b82]">Your editable caption, hashtags and model analysis will appear here.</p></Card>}</div></div></>;
}

function Analyze({ session }: { session: Session }) {
  const [captionLength, setCaptionLength] = useState(120); const [hashtags, setHashtags] = useState(5); const [hour, setHour] = useState(18); const [result, setResult] = useState<Prediction | null>(null); const [error, setError] = useState("");
  return <><Title>Analyze performance</Title><ErrorText value={error} /><div className="grid gap-6 xl:grid-cols-[.8fr_1.2fr]"><Card><NumberInput label="Caption length" value={captionLength} onChange={setCaptionLength} /><NumberInput label="Hashtag count" value={hashtags} onChange={setHashtags} /><NumberInput label="Posting hour (0–23)" value={hour} onChange={setHour} /><button onClick={async () => { try { setError(""); setResult(await predict(session, { platform: "Instagram", contentType: "Post", captionLength, hashtagsCount: hashtags, postingHour: hour })); } catch (e) { setError(e instanceof Error ? e.message : "Analysis failed."); } }} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white">Run analysis</button></Card>{result ? <AnalysisCard value={result} /> : <Card><p className="text-sm text-[#746b82]">Run the model to see predicted views, engagement and recommendations.</p></Card>}</div></>;
}

function Insights({ session }: { session: Session }) {
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [history, setHistory] = useState<Array<{ id: string; created_at: string; platform: string; content_type: string; views: number; engagement: number }>>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([getTrackedPosts(session), getHistory(session)])
      .then(([tracked, analyses]) => { setPosts(tracked.items); setHistory(analyses.items); })
      .catch((e) => setError(e instanceof Error ? e.message : "Insights failed."));
  }, [session]);
  return <>
    <Title>Insights</Title>
    <ErrorText value={error} />
    <h2 className="mb-4 text-lg font-black">Post performance</h2>
    {posts.length === 0 ? <Card><p className="text-sm text-[#746b82]">Track an Instagram post to see its individual metrics here.</p></Card> : <div className="grid gap-5 md:grid-cols-2">{posts.map((post) => <Card key={post.tracking.id}><div className="flex gap-4">{(post.media.thumbnail_url || post.media.media_url) && <img alt="Instagram post" src={post.media.thumbnail_url || post.media.media_url} className="h-20 w-20 shrink-0 rounded-xl object-cover" />}<div className="min-w-0"><p className="line-clamp-2 text-sm font-black">{post.media.caption || "Instagram post"}</p><p className="mt-1 text-[11px] text-[#80778b]">{post.latest?.captured_at ? `Updated ${new Date(post.latest.captured_at).toLocaleString()}` : "Metrics have not been loaded yet."}</p></div></div><div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3"><Metric label="Reach" value={post.latest?.reach} /><Metric label="Views" value={post.latest?.views} /><Metric label="Likes" value={post.latest?.likes} /><Metric label="Comments" value={post.latest?.comments} /><Metric label="Saves" value={post.latest?.saves} /><Metric label="Shares" value={post.latest?.shares} /><Metric label="Engagement" value={post.latest?.engagement_rate == null ? undefined : `${post.latest.engagement_rate}%`} /></div></Card>)}</div>}
    <h2 className="mb-4 mt-8 text-lg font-black">Analysis history</h2>
    <div className="space-y-3">{history.length ? history.map((item) => <Card key={item.id}><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-black">{item.platform} · {item.content_type}</p><p className="text-xs text-[#80778b]">{new Date(item.created_at).toLocaleString()}</p></div><div className="grid grid-cols-2 gap-5 text-sm"><Metric label="Views" value={item.views} /><Metric label="Engagement" value={`${item.engagement}%`} /></div></div></Card>) : <Card><p className="text-sm text-[#746b82]">No saved analyses yet.</p></Card>}</div>
  </>;
}

function Settings({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [error, setError] = useState("");
  return <><Title>Settings</Title><ErrorText value={error} /><Card><p className="text-xs font-bold uppercase tracking-wider text-[#80778b]">Signed in as</p><p className="mt-2 break-all text-base font-black md:text-lg">{session.user.email}</p><div className="mt-6 grid grid-cols-2 gap-3 sm:flex"><button onClick={async () => { try { await logout(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Logout failed."); } }} className="rounded-xl border border-[#ddd5e8] px-3 py-3 text-sm font-bold sm:px-5 sm:text-base">Log out</button><button onClick={async () => { if (!window.confirm("Permanently delete your PostBridge account and all associated data?")) return; try { await deleteAccount(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Account deletion failed."); } }} className="rounded-xl border border-red-200 px-3 py-3 text-sm font-bold text-red-700 sm:px-5 sm:text-base">Delete account</button></div></Card></>;
}

function AnalysisCard({ value }: { value: Prediction }) { return <Card dark><div className="grid grid-cols-2 gap-3"><Metric label="Predicted views" value={value.views} light /><Metric label="Engagement" value={`${value.engagement}%`} light /></div><p className="mt-6 leading-7 text-violet-50">{value.insights.analysis}</p><div className="mt-6 grid gap-5 md:grid-cols-2"><Insight title="Strengths" items={value.insights.strengths} /><Insight title="Recommendations" items={value.insights.recommendations} /></div></Card>; }
function Insight({ title, items }: { title: string; items: string[] }) { return <div><h3 className="font-black text-violet-300">{title}</h3><ul className="mt-2 space-y-2 text-sm leading-6 text-violet-50">{items.map((item) => <li key={item}>• {item}</li>)}</ul></div>; }
function Metric({ label, value, light = false }: { label: string; value: unknown; light?: boolean }) { return <div><p className={`font-black ${light ? "text-white" : "text-[#201633]"}`}>{value == null ? "—" : String(value)}</p><p className={`text-[10px] font-bold uppercase tracking-wide ${light ? "text-violet-300" : "text-[#80778b]"}`}>{label}</p></div>; }
function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) { return <label className="mb-4 block text-sm font-bold">{label}<input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] p-4 font-normal" /></label>; }
