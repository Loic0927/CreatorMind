"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Connection, PostAnalysis, Session, SocialPlatform, TrackedPost, analyzeTrackedPost, caption, connectInstagram,
  deleteAccount, getConnection, getInstagramMedia, getTrackedPost, getTrackedPosts, logout,
  refreshTrackedPost, requestCode, saveSession, storedSession, trackInstagramPost, verifyCode,
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
  type ImageMimeType = "image/jpeg" | "image/png" | "image/webp";
  type SelectedImage = { preview: string; data: string; mimeType: ImageMimeType; name: string };
  const goals = [
    "Grow engagement",
    "Educate",
    "Build trust",
    "Drive conversions",
    "Increase brand awareness",
    "Promote a product or service",
    "Start a conversation",
    "Share an announcement",
    "Celebrate a milestone",
    "Other",
  ];
  const platforms: SocialPlatform[] = ["Instagram", "Twitter", "Facebook", "Threads", "YouTube"];
  const [information, setInformation] = useState("");
  const [goal, setGoal] = useState("Grow engagement");
  const [customGoal, setCustomGoal] = useState("");
  const [platform, setPlatform] = useState<SocialPlatform>("Instagram");
  const [image, setImage] = useState<SelectedImage | null>(null);
  const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const effectiveGoal = goal === "Other" ? customGoal.trim() : goal;

  const chooseImage = async (file?: File) => {
    if (!file) return;
    setError("");
    const supportedTypes: ImageMimeType[] = ["image/jpeg", "image/png", "image/webp"];
    if (!supportedTypes.includes(file.type as ImageMimeType)) {
      setImage(null);
      setError("Choose a JPG, PNG or WebP image. Video is not supported yet.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setImage(null);
      setError("Choose an image smaller than 5 MB.");
      return;
    }
    const preview = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => typeof reader.result === "string" ? resolve(reader.result) : reject(new Error("Could not read this image."));
      reader.onerror = () => reject(new Error("Could not read this image."));
      reader.readAsDataURL(file);
    });
    const data = preview.split(",", 2)[1];
    if (!data) throw new Error("Could not read this image.");
    setImage({ preview, data, mimeType: file.type as ImageMimeType, name: file.name });
  };

  const run = async () => {
    if (!image || !effectiveGoal) return;
    setBusy(true);
    setError("");
    try {
      setResult(await caption(session, {
        information,
        goal: effectiveGoal,
        platform,
        image: { mime_type: image.mimeType, data: image.data },
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  };

  return <>
    <Title>Create post</Title>
    <ErrorText value={error} />
    <div className="grid gap-6 xl:grid-cols-[1fr_.9fr]">
      <Card>
        <label className="text-sm font-bold">Image</label>
        <label className="mt-2 grid min-h-44 cursor-pointer place-items-center overflow-hidden rounded-2xl border border-dashed border-[#b9aec8] bg-[#f7f5ff] text-sm font-bold text-[#5b21b6]">
          {image ? <img src={image.preview} alt="Selected post" className="h-full max-h-80 w-full object-cover" /> : "Choose an image"}
          <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => void chooseImage(e.target.files?.[0]).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not read this image."))} />
        </label>
        {image && <p className="mt-2 truncate text-xs text-[#80778b]">{image.name}</p>}

        <label className="mt-5 block text-sm font-bold">Social platform</label>
        <select value={platform} onChange={(e) => setPlatform(e.target.value as SocialPlatform)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">
          {platforms.map((item) => <option key={item}>{item}</option>)}
        </select>

        <label className="mt-5 block text-sm font-bold">Information</label>
        <textarea value={information} onChange={(e) => setInformation(e.target.value)} className="mt-2 min-h-32 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Describe your content, audience and key message" />

        <label className="mt-5 block text-sm font-bold">Goal</label>
        <select value={goal} onChange={(e) => setGoal(e.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">
          {goals.map((item) => <option key={item}>{item}</option>)}
        </select>
        {goal === "Other" && <input value={customGoal} onChange={(e) => setCustomGoal(e.target.value)} maxLength={200} className="mt-3 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Write your goal" />}

        <button disabled={busy || !information.trim() || !image || !effectiveGoal} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating…" : "Create caption"}</button>
      </Card>
      <div className="space-y-6">
        {result ? <Card><h2 className="text-xl font-black">Caption</h2><textarea className="mt-4 min-h-40 w-full rounded-xl bg-[#f7f5ff] p-4" value={result.caption} onChange={(e) => setResult({ ...result, caption: e.target.value })} /><textarea className="mt-3 min-h-20 w-full rounded-xl bg-[#f7f5ff] p-4 text-[#5b21b6]" value={result.hashtags} onChange={(e) => setResult({ ...result, hashtags: e.target.value })} /></Card> : <Card><p className="text-sm text-[#746b82]">Your editable caption and hashtags will appear here.</p></Card>}
      </div>
    </div>
  </>;
}

function Analyze({ session }: { session: Session }) {
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<TrackedPost | null>(null);
  const [viewingAnalysisId, setViewingAnalysisId] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<"refresh" | "analyze" | null>(null);
  const [error, setError] = useState("");

  const loadDetail = useCallback(async (trackedId: string) => {
    if (!trackedId) return;
    setSelected(await getTrackedPost(session, trackedId));
  }, [session]);

  useEffect(() => {
    setLoading(true);
    getTrackedPosts(session)
      .then(async ({ items }) => {
        setPosts(items);
        const nextId = items[0]?.tracking.id || "";
        setSelectedId(nextId);
        if (nextId) await loadDetail(nextId);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load tracked posts."))
      .finally(() => setLoading(false));
  }, [loadDetail, session]);

  const choose = async (trackedId: string) => {
    setSelectedId(trackedId);
    setViewingAnalysisId("");
    setError("");
    try {
      await loadDetail(trackedId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this post.");
    }
  };
  const refresh = async () => {
    if (!selectedId) return;
    setWorking("refresh");
    setError("");
    try {
      setSelected(await refreshTrackedPost(session, selectedId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not refresh metrics.");
    } finally {
      setWorking(null);
    }
  };
  const analyze = async () => {
    if (!selectedId) return;
    setWorking("analyze");
    setError("");
    try {
      const result = await analyzeTrackedPost(session, selectedId);
      setSelected((current) => current ? { ...current, analyses: [result, ...(current.analyses ?? [])] } : current);
      setViewingAnalysisId(result.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not analyze this post.");
    } finally {
      setWorking(null);
    }
  };

  if (loading) return <><Title>Analyze a tracked post</Title><Card>Loading tracked posts…</Card></>;
  if (posts.length === 0) return <><Title>Analyze a tracked post</Title><Card><p className="font-bold">Track an Instagram post first.</p><p className="mt-2 text-sm text-[#746b82]">PostBridge needs real post metrics before it can explain performance.</p></Card></>;
  const displayedAnalysis = selected?.analyses?.find((item) => item.id === viewingAnalysisId) ?? selected?.analyses?.[0];
  return <>
    <Title>Analyze a tracked post</Title>
    <ErrorText value={error} />
    <div className="grid gap-6 xl:grid-cols-[.85fr_1.15fr]">
      <div className="space-y-6">
        <Card>
          <label className="text-sm font-bold">Tracked post</label>
          <select value={selectedId} onChange={(event) => void choose(event.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">
            {posts.map((post) => <option key={post.tracking.id} value={post.tracking.id}>{post.media.caption?.slice(0, 70) || "Instagram post"}</option>)}
          </select>
          {selected && <div className="mt-5">
            {(selected.media.thumbnail_url || selected.media.media_url) && <img alt="Selected Instagram post" src={selected.media.thumbnail_url || selected.media.media_url} className="aspect-video w-full rounded-2xl object-cover" />}
            <p className="mt-4 line-clamp-4 text-sm leading-6">{selected.media.caption || "No caption"}</p>
            <p className="mt-2 text-xs text-[#80778b]">Published {new Date(selected.media.published_at).toLocaleString()}</p>
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Metric label="Reach" value={selected.latest?.reach} />
              <Metric label="Views" value={selected.latest?.views} />
              <Metric label="Likes" value={selected.latest?.likes} />
              <Metric label="Comments" value={selected.latest?.comments} />
              <Metric label="Saves" value={selected.latest?.saves} />
              <Metric label="Shares" value={selected.latest?.shares} />
            </div>
            <p className="mt-4 text-xs text-[#80778b]">{selected.latest ? `Metrics captured ${new Date(selected.latest.captured_at).toLocaleString()}` : "Refresh metrics before analyzing this post."}</p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <button disabled={working !== null} onClick={() => void refresh()} className="rounded-xl bg-[#eee8fa] px-3 py-3 text-sm font-bold text-[#5b21b6] disabled:opacity-50">{working === "refresh" ? "Refreshing…" : "Refresh metrics"}</button>
              <button disabled={working !== null || !selected.latest} onClick={() => void analyze()} className="rounded-xl bg-[#7c3aed] px-3 py-3 text-sm font-bold text-white disabled:opacity-50">{working === "analyze" ? "Analyzing…" : "Analyze post"}</button>
            </div>
          </div>}
        </Card>
      </div>
      {displayedAnalysis ? <PostAnalysisCard analysis={displayedAnalysis} /> : <Card><p className="font-bold">No saved analysis for this post yet.</p><p className="mt-2 text-sm leading-6 text-[#746b82]">Refresh the metrics, then PostBridge will interpret this post's real performance and content. It will not predict views or assign a viral score.</p></Card>}
    </div>
    {selected?.analyses?.length ? <section className="mt-8"><h2 className="mb-4 text-lg font-black">Analysis history</h2><div className="space-y-3">{selected.analyses.map((analysis) => <button key={analysis.id} onClick={() => setViewingAnalysisId(analysis.id)} className={`w-full rounded-3xl border bg-white p-5 text-left shadow-sm ${displayedAnalysis?.id === analysis.id ? "border-violet-500 ring-2 ring-violet-200" : "border-[#e7e0f0]"}`}><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-bold">{analysis.output_payload.summary}</p><p className="mt-2 text-xs text-[#80778b]">{new Date(analysis.created_at).toLocaleString()} · {analysis.model_name}</p></div><p className="text-xs font-bold text-[#6d28d9]">Snapshot {analysis.source_snapshot_id.slice(0, 8)}</p></div></button>)}</div></section> : null}
  </>;
}

function Insights({ session }: { session: Session }) {
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    getTrackedPosts(session)
      .then((tracked) => setPosts(tracked.items))
      .catch((e) => setError(e instanceof Error ? e.message : "Insights failed."));
  }, [session]);
  return <>
    <Title>Insights</Title>
    <ErrorText value={error} />
    <h2 className="mb-4 text-lg font-black">Post performance</h2>
    {posts.length === 0 ? <Card><p className="text-sm text-[#746b82]">Track an Instagram post to see its individual metrics here.</p></Card> : <div className="grid gap-5 md:grid-cols-2">{posts.map((post) => <Card key={post.tracking.id}><div className="flex gap-4">{(post.media.thumbnail_url || post.media.media_url) && <img alt="Instagram post" src={post.media.thumbnail_url || post.media.media_url} className="h-20 w-20 shrink-0 rounded-xl object-cover" />}<div className="min-w-0"><p className="line-clamp-2 text-sm font-black">{post.media.caption || "Instagram post"}</p><p className="mt-1 text-[11px] text-[#80778b]">{post.latest?.captured_at ? `Updated ${new Date(post.latest.captured_at).toLocaleString()}` : "Metrics have not been loaded yet."}</p></div></div><div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3"><Metric label="Reach" value={post.latest?.reach} /><Metric label="Views" value={post.latest?.views} /><Metric label="Likes" value={post.latest?.likes} /><Metric label="Comments" value={post.latest?.comments} /><Metric label="Saves" value={post.latest?.saves} /><Metric label="Shares" value={post.latest?.shares} /><Metric label="Engagement" value={post.latest?.engagement_rate == null ? undefined : `${post.latest.engagement_rate}%`} /></div></Card>)}</div>}
  </>;
}

function Settings({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [error, setError] = useState("");
  return <><Title>Settings</Title><ErrorText value={error} /><Card><p className="text-xs font-bold uppercase tracking-wider text-[#80778b]">Signed in as</p><p className="mt-2 break-all text-base font-black md:text-lg">{session.user.email}</p><div className="mt-6 grid grid-cols-2 gap-3 sm:flex"><button onClick={async () => { try { await logout(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Logout failed."); } }} className="rounded-xl border border-[#ddd5e8] px-3 py-3 text-sm font-bold sm:px-5 sm:text-base">Log out</button><button onClick={async () => { if (!window.confirm("Permanently delete your PostBridge account and all associated data?")) return; try { await deleteAccount(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Account deletion failed."); } }} className="rounded-xl border border-red-200 px-3 py-3 text-sm font-bold text-red-700 sm:px-5 sm:text-base">Delete account</button></div></Card></>;
}

function PostAnalysisCard({ analysis }: { analysis: PostAnalysis }) {
  const output = analysis.output_payload;
  return <Card dark>
    <p className="text-xs font-bold uppercase tracking-widest text-violet-300">Model interpretation</p>
    <p className="mt-3 text-lg font-bold leading-8 text-white">{output.summary}</p>
    <div className="mt-6">
      <p className="mb-3 text-xs font-bold uppercase tracking-widest text-violet-300">Observed provider data</p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {Object.entries(analysis.observed_metrics).map(([name, value]) => <div key={name}><Metric label={name.replaceAll("_", " ")} value={value} light />{analysis.metric_deltas[name] != null && <p className="mt-1 text-[10px] text-violet-200">Δ {formatDelta(analysis.metric_deltas[name])}</p>}</div>)}
      </div>
    </div>
    <div className="mt-7 grid gap-6 md:grid-cols-2">
      <AnalysisList title="What performed well" items={output.strengths} />
      <AnalysisList title="Needs attention" items={output.concerns} />
      <AnalysisList title="Next actions" items={output.recommendations} />
      <AnalysisList title="Unavailable inputs" items={output.missing_inputs} />
    </div>
    <p className="mt-7 border-t border-white/10 pt-4 text-[11px] text-violet-200">Based on snapshot {analysis.source_snapshot_id.slice(0, 8)} · {new Date(analysis.created_at).toLocaleString()} · {analysis.model_name}</p>
  </Card>;
}
function AnalysisList({ title, items }: { title: string; items: string[] }) { return <div><h3 className="font-black text-violet-300">{title}</h3>{items.length ? <ul className="mt-2 space-y-2 text-sm leading-6 text-violet-50">{items.map((item) => <li key={item}>• {item}</li>)}</ul> : <p className="mt-2 text-sm text-violet-200">No item reported.</p>}</div>; }
function formatDelta(value: number | null) { if (value == null) return "—"; return value > 0 ? `+${value}` : String(value); }
function Metric({ label, value, light = false }: { label: string; value: unknown; light?: boolean }) { return <div><p className={`font-black ${light ? "text-white" : "text-[#201633]"}`}>{value == null ? "—" : String(value)}</p><p className={`text-[10px] font-bold uppercase tracking-wide ${light ? "text-violet-300" : "text-[#80778b]"}`}>{label}</p></div>; }
