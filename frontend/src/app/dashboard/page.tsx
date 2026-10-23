"use client";

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  AccountInsights, Connection, PatternInsight, PostAnalysis, PostDraft, PublicationResult, PublishingCapability, Session, SocialPlatform, TrackedPost, analyzeTrackedPost, caption, connectInstagram,
  createDraft, deleteAccount, getAccountInsights, getConnection, getDrafts, getInstagramMedia, getPublishingCapabilities, getTrackedPost, getTrackedPosts, logout,
  publishDraft, refreshTrackedPost, requestCode, saveSession, storedSession, trackInstagramPost, updateDraft, uploadMediaAsset, verifyCode,
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
  const [selectedPlatforms, setSelectedPlatforms] = useState<SocialPlatform[]>(["Instagram"]);
  const [capabilities, setCapabilities] = useState<PublishingCapability[]>([]);
  const [drafts, setDrafts] = useState<PostDraft[]>([]);
  const [activeDraftId, setActiveDraftId] = useState("");
  const [mediaAssetId, setMediaAssetId] = useState<string | null>(null);
  const [image, setImage] = useState<SelectedImage | null>(null);
  const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishKey, setPublishKey] = useState("");
  const [publicationResults, setPublicationResults] = useState<PublicationResult[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const effectiveGoal = goal === "Other" ? customGoal.trim() : goal;
  const publishablePlatforms = selectedPlatforms.filter((platform) => capabilities.some((item) => item.platform === platform && item.available));

  useEffect(() => {
    Promise.all([getPublishingCapabilities(session), getDrafts(session)])
      .then(([capabilityResult, draftResult]) => {
        setCapabilities(capabilityResult.items);
        setDrafts(draftResult);
      })
      .catch(() => {
        setCapabilities([]);
        setDrafts([]);
      });
  }, [session]);

  const togglePlatform = (item: SocialPlatform) => {
    setSelectedPlatforms((current) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item]);
    setResult(null);
    setPublishKey("");
    setPublicationResults([]);
  };

  const upsertDraftState = (draft: PostDraft) => {
    setDrafts((current) => [draft, ...current.filter((item) => item.id !== draft.id)]);
  };

  const newDraft = () => {
    setActiveDraftId("");
    setMediaAssetId(null);
    setInformation("");
    setGoal("Grow engagement");
    setCustomGoal("");
    setSelectedPlatforms(["Instagram"]);
    setImage(null);
    setResult(null);
    setPublicationResults([]);
    setPublishKey("");
    setNotice("");
    setError("");
  };

  const openDraft = (draftId: string) => {
    const draft = drafts.find((item) => item.id === draftId);
    if (!draft) return;
    setActiveDraftId(draft.id);
    setMediaAssetId(draft.media_asset_id ?? null);
    setInformation(draft.content_brief);
    if (goals.includes(draft.goal)) {
      setGoal(draft.goal);
      setCustomGoal("");
    } else {
      setGoal("Other");
      setCustomGoal(draft.goal);
    }
    setSelectedPlatforms(draft.target_platforms);
    setImage(null);
    setResult(draft.caption || draft.hashtags.length ? { caption: draft.caption, hashtags: draft.hashtags.join(" ") } : null);
    setPublicationResults([]);
    setPublishKey("");
    setNotice("Draft reopened. Its private image remains attached.");
    setError("");
  };

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
    setMediaAssetId(null);
    setPublishKey("");
    setPublicationResults([]);
    setNotice("");
  };

  const run = async () => {
    if (!image || !effectiveGoal) return;
    setBusy(true);
    setError("");
    try {
      setResult(await caption(session, {
        information,
        goal: effectiveGoal,
        platform: selectedPlatforms[0] ?? "Instagram",
        platforms: selectedPlatforms,
        image: { mime_type: image.mimeType, data: image.data },
      }));
      setPublishKey("");
      setPublicationResults([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  };

  const save = async (): Promise<PostDraft> => {
    if (!effectiveGoal || selectedPlatforms.length === 0) throw new Error("Choose a platform and goal before saving.");
    setSaving(true);
    setError("");
    setNotice("");
    try {
      let nextMediaAssetId = mediaAssetId;
      if (image && !nextMediaAssetId) {
        const asset = await uploadMediaAsset(session, {
          filename: image.name,
          mime_type: image.mimeType,
          data: image.data,
        });
        nextMediaAssetId = asset.id;
        setMediaAssetId(asset.id);
      }
      const payload = {
        media_asset_id: nextMediaAssetId,
        target_platforms: selectedPlatforms,
        content_brief: information.trim(),
        goal: effectiveGoal,
        caption: result?.caption ?? "",
        hashtags: (result?.hashtags ?? "").split(/\s+/).filter(Boolean),
      };
      const saved = activeDraftId
        ? await updateDraft(session, activeDraftId, payload)
        : await createDraft(session, payload);
      setActiveDraftId(saved.id);
      upsertDraftState(saved);
      setNotice("Draft saved. Nothing has been published.");
      return saved;
    } finally {
      setSaving(false);
    }
  };

  const saveOnly = async () => {
    try {
      await save();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this draft.");
    }
  };

  const publish = async () => {
    if (!result || publishablePlatforms.length === 0) return;
    if (!window.confirm(`Publish this draft to ${publishablePlatforms.join(", ")}?`)) return;
    setPublishing(true);
    setError("");
    setPublicationResults([]);
    try {
      const draft = await save();
      const idempotencyKey = publishKey || globalThis.crypto.randomUUID();
      setPublishKey(idempotencyKey);
      const response = await publishDraft(session, draft.id, {
        platforms: publishablePlatforms,
        idempotency_key: idempotencyKey,
      });
      setPublicationResults(response.results);
      upsertDraftState(response.draft);
      setNotice(response.draft.status === "published" ? "Publication completed and tracking was added." : "Publication finished with one or more failures.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Publishing failed.");
    } finally {
      setPublishing(false);
    }
  };

  return <>
    <Title>Create post</Title>
    <ErrorText value={error} />
    {notice && <p className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">{notice}</p>}
    {drafts.some((item) => item.status === "draft" || item.status === "failed") && <Card>
      <div className="flex items-center justify-between gap-3">
        <div><h2 className="font-black">Saved drafts</h2><p className="mt-1 text-xs text-[#80778b]">Reopen a saved draft without publishing it.</p></div>
        <button type="button" onClick={newDraft} className="rounded-xl bg-[#eee8fa] px-4 py-2 text-sm font-bold text-[#5b21b6]">New draft</button>
      </div>
      <select value={activeDraftId} onChange={(event) => openDraft(event.target.value)} className="mt-4 w-full rounded-xl border border-[#ddd5e8] bg-white p-3">
        <option value="">Choose a saved draft</option>
        {drafts.filter((item) => item.status === "draft" || item.status === "failed").map((draft) => <option key={draft.id} value={draft.id}>{draft.content_brief.slice(0, 70) || "Untitled draft"} - {draft.status}</option>)}
      </select>
    </Card>}
    <div className={result ? "grid gap-6 xl:grid-cols-[1fr_.9fr]" : ""}>
      <Card>
        <label className="text-sm font-bold">Image</label>
        <label className="mt-2 grid min-h-44 cursor-pointer place-items-center overflow-hidden rounded-2xl border border-dashed border-[#b9aec8] bg-[#f7f5ff] text-sm font-bold text-[#5b21b6]">
          {image ? <img src={image.preview} alt="Selected post" className="h-full max-h-80 w-full object-cover" /> : mediaAssetId ? "Private draft image attached - choose a file to replace it" : "Choose an image"}
          <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => void chooseImage(e.target.files?.[0]).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not read this image."))} />
        </label>
        {image && <p className="mt-2 truncate text-xs text-[#80778b]">{image.name}</p>}

        <label className="mt-5 block text-sm font-bold">Social platforms</label>
        <details className="relative mt-2">
          <summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl border border-[#ddd5e8] bg-white p-4 font-bold">
            <span>{selectedPlatforms.length ? selectedPlatforms.join(", ") : "Choose platforms"}</span><span className="text-[#80778b]">⌄</span>
          </summary>
          <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-[#ddd5e8] bg-white p-2 shadow-xl">
            {platforms.map((item) => {
              const capability = capabilities.find((value) => value.platform === item);
              return <label key={item} className="flex cursor-pointer items-center justify-between rounded-xl px-3 py-3 hover:bg-[#f7f5ff]">
                <span className="flex items-center gap-3"><input type="checkbox" checked={selectedPlatforms.includes(item)} onChange={() => togglePlatform(item)} className="h-4 w-4 accent-violet-600" />{item}</span>
                {capability && !capability.available && <span className="text-xs text-[#80778b]">Unavailable</span>}
              </label>;
            })}
          </div>
        </details>

        <label className="mt-5 block text-sm font-bold">Information</label>
        <textarea value={information} onChange={(e) => setInformation(e.target.value)} className="mt-2 min-h-32 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Describe your content, audience and key message" />

        <label className="mt-5 block text-sm font-bold">Goal</label>
        <select value={goal} onChange={(e) => setGoal(e.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">
          {goals.map((item) => <option key={item}>{item}</option>)}
        </select>
        {goal === "Other" && <input value={customGoal} onChange={(e) => setCustomGoal(e.target.value)} maxLength={200} className="mt-3 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Write your goal" />}

        <button disabled={busy || !information.trim() || !image || !effectiveGoal || selectedPlatforms.length === 0} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating..." : "Create caption"}</button>
      </Card>
      <div className="space-y-6">
        {result && <Card>
          <h2 className="text-xl font-black">Caption</h2>
          <textarea className="mt-4 min-h-40 w-full rounded-xl bg-[#f7f5ff] p-4" value={result.caption} onChange={(event) => { setResult({ ...result, caption: event.target.value }); setPublishKey(""); }} />
          <textarea className="mt-3 min-h-20 w-full rounded-xl bg-[#f7f5ff] p-4 text-[#5b21b6]" value={result.hashtags} onChange={(event) => { setResult({ ...result, hashtags: event.target.value }); setPublishKey(""); }} />
          <div className="mt-5 grid grid-cols-2 gap-3">
            <button disabled={saving || publishing} onClick={() => void saveOnly()} className="rounded-2xl bg-[#eee8fa] py-4 font-black text-[#5b21b6] disabled:opacity-50">{saving ? "Saving..." : "Save draft"}</button>
            <button disabled={publishing || saving || publishablePlatforms.length === 0 || (!image && !mediaAssetId)} onClick={() => void publish()} className="rounded-2xl bg-[#201633] py-4 font-black text-white disabled:opacity-50">{publishing ? "Publishing..." : `Publish (${publishablePlatforms.length})`}</button>
          </div>
          {selectedPlatforms.some((platform) => !publishablePlatforms.includes(platform)) && <p className="mt-3 text-xs text-amber-700">Unavailable or disconnected platforms remain generation targets but will not be submitted for publishing.</p>}
          {image && image.mimeType !== "image/jpeg" && <p className="mt-2 text-xs text-amber-700">Instagram publishing currently requires a JPEG. This image can still be saved and used to generate copy.</p>}
          {publicationResults.length > 0 && <div className="mt-4 space-y-2">{publicationResults.map((item) => <div key={`${item.platform}-${item.publication_id ?? item.status}`} className={`rounded-xl p-3 text-sm ${item.status === "published" ? "bg-emerald-50 text-emerald-800" : item.status === "failed" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"}`}><p className="font-black">{item.platform} - {item.status}</p><p className="mt-1">{item.message}</p>{item.permalink && <a className="mt-1 inline-block font-bold underline" href={item.permalink} target="_blank" rel="noreferrer">View post</a>}</div>)}</div>}
        </Card>}
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
    <div className="grid items-start gap-6 lg:grid-cols-[.95fr_1.05fr]">
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
      {displayedAnalysis ? <PostAnalysisCard analysis={displayedAnalysis} /> : <Card><p className="font-bold">No saved analysis for this post yet.</p><p className="mt-2 text-sm leading-6 text-[#746b82]">Refresh the metrics, then analyze this post.</p></Card>}
    </div>
    {selected?.analyses?.length ? <AnalysisTimeline analyses={selected.analyses} selectedId={displayedAnalysis?.id} onSelect={setViewingAnalysisId} /> : null}
  </>;
}

function Insights({ session }: { session: Session }) {
  const [insights, setInsights] = useState<AccountInsights | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getAccountInsights(session)
      .then(setInsights)
      .catch((e) => setError(e instanceof Error ? e.message : "Insights failed."));
  }, [session]);
  return <>
    <Title>Insights</Title>
    <ErrorText value={error} />
    {!insights && !error ? <Card><p className="text-sm text-[#746b82]">Loading insights…</p></Card> : insights && insights.sample_size < insights.required_sample_size ? <Card>
      <p className="font-black">Analyze more posts to unlock pattern insights.</p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Progress label="Topics" value={insights.progress.topics} required={insights.required_sample_size} />
        <Progress label="Hashtags" value={insights.progress.hashtags} required={insights.required_sample_size} />
        <Progress label="Thumbnails" value={insights.progress.thumbnails} required={insights.required_sample_size} />
        <Progress label="Posting times" value={insights.progress.posting_times} required={insights.required_sample_size} />
      </div>
    </Card> : insights ? <div className="grid items-start gap-5 lg:grid-cols-2">
      <InsightRanking title="Top performing patterns" items={insights.top_patterns} showCategory />
      <InsightRanking title="Top hashtags" items={insights.top_hashtags} />
      <InsightRanking title="Thumbnail insights" items={insights.thumbnail_insights} />
      <InsightRanking title="Best posting times" items={insights.best_posting_times} />
      {insights.winning_formula && <div className="lg:col-span-2"><Card dark>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-black text-white">Winning formula</h2><p className="rounded-full bg-white/10 px-4 py-2 text-sm font-black text-violet-100">{insights.winning_formula.confidence}% confidence</p></div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <FormulaValue label="Topic" value={insights.winning_formula.topic} />
          <FormulaValue label="Thumbnail" value={insights.winning_formula.thumbnail} />
          <FormulaValue label="Caption" value={insights.winning_formula.caption} />
          <FormulaValue label="CTA" value={insights.winning_formula.cta} />
          <FormulaValue label="Posting time" value={insights.winning_formula.posting_time} />
        </div>
      </Card></div>}
    </div> : null}
  </>;
}

function InsightRanking({ title, items, showCategory = false }: { title: string; items: PatternInsight[]; showCategory?: boolean }) {
  return <Card><h2 className="text-lg font-black">{title}</h2><div className="mt-4 divide-y divide-[#eee8fa]">{items.length ? items.map((item, index) => <div key={`${item.category ?? title}-${item.label}`} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#eee8fa] text-sm font-black text-[#6d28d9]">{index + 1}</span><div className="min-w-0 flex-1">{showCategory && item.category && <p className="text-[10px] font-bold uppercase tracking-wider text-[#80778b]">{item.category}</p>}<p className="truncate font-black">{item.label}</p><p className="mt-1 text-xs text-[#80778b]">{item.posts} posts</p></div><div className="text-right"><p className="text-2xl font-black">{item.average_score}</p><p className={`text-xs font-bold ${item.difference_from_baseline >= 0 ? "text-emerald-700" : "text-red-700"}`}>{item.difference_from_baseline >= 0 ? "+" : ""}{item.difference_from_baseline} vs average</p></div></div>) : <p className="py-2 text-sm text-[#746b82]">More varied posts are needed.</p>}</div></Card>;
}

function Progress({ label, value, required }: { label: string; value: number; required: number }) { return <div className="rounded-2xl bg-[#f7f5ff] p-4"><div className="flex justify-between gap-3"><p className="text-sm font-bold">{label}</p><p className="text-sm font-black">{value}/{required}</p></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-[#e8e0f7]"><div className="h-full rounded-full bg-[#7c3aed]" style={{ width: `${Math.min(100, value / required * 100)}%` }} /></div></div>; }
function FormulaValue({ label, value }: { label: string; value?: string | null }) { return <div><p className="text-[10px] font-bold uppercase tracking-wider text-violet-300">{label}</p><p className="mt-1 font-black text-white">{value || "—"}</p></div>; }

function Settings({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [error, setError] = useState("");
  return <><Title>Settings</Title><ErrorText value={error} /><Card><p className="text-xs font-bold uppercase tracking-wider text-[#80778b]">Signed in as</p><p className="mt-2 break-all text-base font-black md:text-lg">{session.user.email}</p><div className="mt-6 grid grid-cols-2 gap-3 sm:flex"><button onClick={async () => { try { await logout(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Logout failed."); } }} className="rounded-xl border border-[#ddd5e8] px-3 py-3 text-sm font-bold sm:px-5 sm:text-base">Log out</button><button onClick={async () => { if (!window.confirm("Permanently delete your PostBridge account and all associated data?")) return; try { await deleteAccount(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Account deletion failed."); } }} className="rounded-xl border border-red-200 px-3 py-3 text-sm font-bold text-red-700 sm:px-5 sm:text-base">Delete account</button></div></Card></>;
}

function PostAnalysisCard({ analysis }: { analysis: PostAnalysis }) {
  const output = analysis.output_payload;
  if (!output.score) return <Card><p className="font-black">Legacy analysis</p><p className="mt-2 text-sm text-[#746b82]">{output.summary ?? "Run a new analysis to generate the creator intelligence dashboard."}</p></Card>;
  const tone = (value: number) => value >= 75 ? "bg-emerald-500" : value >= 50 ? "bg-amber-500" : "bg-red-500";
  return <div className="space-y-5">
    <Card dark>
      <div className="flex flex-wrap items-end justify-between gap-5"><div><p className="text-xs font-black uppercase tracking-widest text-violet-300">Post score</p><p className="mt-2 text-5xl font-black text-white">{output.score.overall}<span className="text-xl text-violet-300"> / 100</span></p></div><div className="rounded-2xl bg-white/10 px-5 py-3 text-center"><p className="text-xs text-violet-300">Grade</p><p className="text-3xl font-black text-white">{output.score.grade}</p></div></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">{Object.entries(output.score.categories).map(([name, value]) => <div key={name}><div className="mb-1 flex justify-between text-xs font-bold text-violet-100"><span className="capitalize">{name}</span><span>{value}</span></div><div className="h-2 overflow-hidden rounded-full bg-white/10"><div className={`h-full ${tone(value)}`} style={{ width: `${value}%` }} /></div></div>)}</div>
    </Card>
    <DashboardSection title="Top insights">{output.top_insights?.map((item) => <p key={item.text} className="rounded-xl bg-[#f7f5ff] p-3 text-sm font-bold">{item.status === "strong" ? "✅" : item.status === "attention" ? "⚠️" : "ℹ️"} {item.text}</p>)}</DashboardSection>
    <DashboardSection title="Why it worked"><div className="grid gap-3">{output.why_it_worked?.map((item) => <div key={item.factor} className="rounded-2xl border border-[#eee8fa] p-4"><div className="flex justify-between gap-3"><p className="font-black">{item.factor}</p><span className="shrink-0 text-sm font-black text-emerald-700">{item.estimated_impact}</span></div><p className="mt-2 text-sm leading-6 text-[#746b82]">{item.explanation}</p></div>)}</div></DashboardSection>
    <DashboardSection title="Compared with your average"><div className="grid gap-3 sm:grid-cols-2">{output.benchmarks?.filter((item) => item.current != null).map((item) => <div key={item.metric} className="rounded-2xl bg-[#f7f5ff] p-4"><p className="text-xs font-bold uppercase text-[#80778b]">{item.metric.replaceAll("_", " ")}</p><p className="mt-1 text-2xl font-black">{item.current}</p><p className={`mt-1 text-xs font-bold ${item.percent_change != null && item.percent_change >= 0 ? "text-emerald-700" : "text-red-700"}`}>{item.percent_change == null ? "More posts needed for a baseline" : `${item.percent_change >= 0 ? "↑" : "↓"} ${Math.abs(item.percent_change)}% ${item.direction} average`}</p></div>)}</div></DashboardSection>
    <DashboardSection title="Risks">{output.risks?.length ? output.risks.map((item) => <p key={item} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">⚠️ {item}</p>) : <p className="text-sm text-[#746b82]">No evidence-backed risk was detected from the available signals.</p>}</DashboardSection>
    <DashboardSection title="Next post recommendations"><div className="space-y-3">{output.recommendations.map((item, index) => typeof item === "string" ? <p key={item}>{item}</p> : <div key={`${item.action}-${index}`} className="rounded-2xl border border-[#eee8fa] p-4"><p className="font-black">{item.action}</p><p className="mt-2 text-sm text-[#746b82]"><b>Reason:</b> {item.reason}</p><p className="mt-2 text-sm font-bold text-[#6d28d9]"><b>Expected impact:</b> {item.expected_impact}</p></div>)}</div></DashboardSection>
    <DashboardSection title="AI confidence"><div className="flex items-center gap-4"><p className="text-4xl font-black">{output.confidence?.score ?? 0}%</p><p className="text-sm text-[#746b82]">Confidence reflects available inputs, not certainty that a recommendation will work.</p></div><div className="mt-4 grid gap-2 sm:grid-cols-2">{output.confidence?.inputs.map((item) => <p key={item.name} className="text-sm">{item.available ? "✅" : "❌"} {item.name}{item.detail ? ` · ${item.detail}` : ""}</p>)}</div></DashboardSection>
    <DashboardSection title="Content pattern winners"><div className="grid gap-3 sm:grid-cols-2">{output.content_patterns?.length ? output.content_patterns.map((item) => <div key={item.pattern} className="rounded-2xl bg-[#f7f5ff] p-4"><p className="font-black">{item.pattern}</p><p className="mt-1 text-2xl font-black text-[#6d28d9]">{item.average_score}</p><p className="text-xs text-[#746b82]">Average score · {item.sample_size} post{item.sample_size === 1 ? "" : "s"} · {item.difference_from_baseline >= 0 ? "+" : ""}{item.difference_from_baseline} vs baseline</p></div>) : <p className="text-sm text-[#746b82]">Track more posts to detect repeatable formats.</p>}</div></DashboardSection>
    <p className="text-[11px] text-[#80778b]">Snapshot {analysis.source_snapshot_id.slice(0, 8)} · {new Date(analysis.created_at).toLocaleString()} · {analysis.model_name}</p>
  </div>;
}
function DashboardSection({ title, children }: { title: string; children: ReactNode }) { return <Card><h3 className="mb-4 text-lg font-black">{title}</h3><div className="space-y-2">{children}</div></Card>; }
function AnalysisTimeline({ analyses, selectedId, onSelect }: { analyses: PostAnalysis[]; selectedId?: string; onSelect: (id: string) => void }) { return <section className="mt-8"><h2 className="mb-4 text-lg font-black">Analysis history</h2><div className="flex gap-3 overflow-x-auto pb-2">{[...analyses].reverse().map((analysis, index, ordered) => { const score = analysis.output_payload.score?.overall; const previous = index > 0 ? ordered[index - 1].output_payload.score?.overall : undefined; const direction = score != null && previous != null ? score > previous ? "↑" : score < previous ? "↓" : "→" : ""; const plateau = analysis.output_payload.risks?.some((item) => item.toLowerCase().includes("stalled")); return <button key={analysis.id} onClick={() => onSelect(analysis.id)} className={`min-w-44 rounded-2xl border bg-white p-4 text-left ${selectedId === analysis.id ? "border-violet-500 ring-2 ring-violet-200" : "border-[#e7e0f0]"}`}><p className="text-xs text-[#80778b]">{new Date(analysis.created_at).toLocaleDateString()}</p><p className="mt-1 text-2xl font-black">{score == null ? "Legacy" : `${score} ${direction}`}</p>{plateau && <p className="mt-2 text-xs font-bold text-amber-700">Growth plateau detected</p>}</button>; })}</div></section>; }
function Metric({ label, value, light = false }: { label: string; value: unknown; light?: boolean }) { return <div><p className={`font-black ${light ? "text-white" : "text-[#201633]"}`}>{value == null ? "—" : String(value)}</p><p className={`text-[10px] font-bold uppercase tracking-wide ${light ? "text-violet-300" : "text-[#80778b]"}`}>{label}</p></div>; }
