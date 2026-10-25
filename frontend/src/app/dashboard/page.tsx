"use client";

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  AccountContext, AccountInsights, Connection, ContentOpportunity, PatternInsight, PerformancePost, PostAnalysis, PostDraft, PublicationResult, PublishingCapability, Session, SocialPlatform, TrackedPost, analyzeTrackedPost, caption, connectInstagram,
  createDraft, deleteAccount, getAccountContext, getAccountInsights, getConnection, getDrafts, getInstagramMedia, getPublishingCapabilities, getTrackedPost, getTrackedPosts, logout,
  publishDraft, refreshTrackedPost, requestCode, saveSession, storedSession, trackInstagramPost, updateAccountContext, updateDraft, uploadMediaAsset, verifyCode,
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
      const items = (await getInstagramMedia(session)).items;
      const trackedMediaIds = new Set(posts.map((post) => post.media.id));
      setMedia(items.filter((item) => !trackedMediaIds.has(item.id)));
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
    {choosing && <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-black">Choose an Instagram post</h2><button disabled={addingMediaId !== null} onClick={() => setChoosing(false)} className="text-sm font-bold text-[#5b21b6] disabled:opacity-50">Close</button></div>{media.length ? <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{media.map((item) => <button key={item.id} disabled={addingMediaId !== null} onClick={() => void addPost(item.id)} className="overflow-hidden rounded-2xl bg-[#eee8fa] text-left disabled:cursor-wait disabled:opacity-60">{(item.thumbnail_url || item.media_url) ? <img alt="Instagram post" src={item.thumbnail_url || item.media_url} className="aspect-square w-full object-cover" /> : <div className="aspect-square" />}<p className="line-clamp-2 p-3 text-xs font-bold">{addingMediaId === item.id ? "Adding and loading metrics…" : item.caption || "Instagram post"}</p></button>)}</div> : <p className="py-8 text-center text-sm font-bold text-[#746b82]">All Instagram posts are already tracked.</p>}</Card>}
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
  const [useAccountContext, setUseAccountContext] = useState(true);
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
    setUseAccountContext(true);
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
    setUseAccountContext(true);
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
        use_account_context: useAccountContext,
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
    <div className="grid items-start gap-6 lg:grid-cols-2">
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

        <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl bg-[#f7f5ff] px-4 py-3 text-sm font-bold"><input type="checkbox" checked={useAccountContext} onChange={(event) => setUseAccountContext(event.target.checked)} className="h-4 w-4 accent-violet-600" />Use account context</label>

        <button disabled={busy || !information.trim() || !image || !effectiveGoal || selectedPlatforms.length === 0} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating..." : "Create caption"}</button>
      </Card>
      <div className="space-y-6">
        {result && <Card>
          <h2 className="text-xl font-black">Caption</h2>
          <textarea className="mt-4 min-h-40 w-full rounded-xl bg-[#f7f5ff] p-4" value={result.caption} onChange={(event) => { setResult({ ...result, caption: event.target.value }); setPublishKey(""); }} />
          {result.hashtags ? <label className="mt-3 block text-sm font-bold">Existing draft hashtags (preserved)<textarea className="mt-2 min-h-20 w-full rounded-xl bg-[#f7f5ff] p-4 text-[#5b21b6]" value={result.hashtags} onChange={(event) => { setResult({ ...result, hashtags: event.target.value }); setPublishKey(""); }} /></label> : null}
          <div className="mt-5 grid grid-cols-2 gap-3">
            <button disabled={saving || publishing} onClick={() => void saveOnly()} className="rounded-2xl bg-[#eee8fa] py-4 font-black text-[#5b21b6] disabled:opacity-50">{saving ? "Saving..." : "Save draft"}</button>
            <button disabled={publishing || saving || publishablePlatforms.length === 0 || (!image && !mediaAssetId)} onClick={() => void publish()} className="rounded-2xl bg-[#201633] py-4 font-black text-white disabled:opacity-50">{publishing ? "Publishing..." : `Publish (${publishablePlatforms.length})`}</button>
          </div>
          {selectedPlatforms.some((platform) => !publishablePlatforms.includes(platform)) && <p className="mt-3 text-xs text-amber-700">Unavailable or disconnected platforms remain generation targets but will not be submitted for publishing.</p>}
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
  const [useAccountContext, setUseAccountContext] = useState(true);
  const [error, setError] = useState("");

  const loadDetail = useCallback(async (trackedId: string) => {
    if (!trackedId) return;
    setSelected(await getTrackedPost(session, trackedId));
  }, [session]);

  useEffect(() => {
    setLoading(true);
    getTrackedPosts(session)
      .then(({ items }) => {
        setPosts(items);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load tracked posts."))
      .finally(() => setLoading(false));
  }, [loadDetail, session]);

  const choose = async (trackedId: string) => {
    setSelectedId(trackedId);
    setSelected(null);
    setViewingAnalysisId("");
    setError("");
    try {
      await loadDetail(trackedId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this post.");
    }
  };
  const goBack = () => {
    setSelectedId("");
    setSelected(null);
    setViewingAnalysisId("");
    setError("");
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
      const result = await analyzeTrackedPost(session, selectedId, useAccountContext);
      setSelected((current) => current ? { ...current, analyses: [result, ...(current.analyses ?? [])] } : current);
      setViewingAnalysisId(result.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not analyze this post.");
    } finally {
      setWorking(null);
    }
  };

  if (loading) return <><Title>Choose one post to analyze</Title><Card>Loading tracked posts…</Card></>;
  if (posts.length === 0) return <><Title>Choose one post to analyze</Title><Card><p className="font-bold">Track an Instagram post first.</p></Card></>;
  if (!selectedId) return <>
    <Title>Choose one post to analyze</Title>
    <ErrorText value={error} />
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{posts.map((post) => <button key={post.tracking.id} onClick={() => void choose(post.tracking.id)} className="text-left"><Card>{(post.media.thumbnail_url || post.media.media_url) && <img alt="Instagram post" src={post.media.thumbnail_url || post.media.media_url} className="mb-4 aspect-video w-full rounded-2xl object-cover" />}<p className="line-clamp-2 font-bold">{post.media.caption || "Instagram post"}</p><div className="mt-5 grid grid-cols-3 gap-2 text-sm"><Metric label="Likes" value={post.latest?.likes} /><Metric label="Reach" value={post.latest?.reach} /><Metric label="Engagement" value={post.latest?.engagement_rate == null ? undefined : `${post.latest.engagement_rate}%`} /></div></Card></button>)}</div>
  </>;
  const displayedAnalysis = selected?.analyses?.find((item) => item.id === viewingAnalysisId) ?? selected?.analyses?.[0];
  return <>
    <div className="mx-auto w-full lg:w-[70%]">
      <div className="mb-7 flex items-center justify-between gap-4"><Title className="mb-0">Analyze a tracked post</Title><button onClick={goBack} className="shrink-0 rounded-xl bg-[#eee8fa] px-4 py-3 text-sm font-black text-[#5b21b6]">Back</button></div>
      <ErrorText value={error} />
      {!selected ? <Card>Loading post…</Card> : <div className="space-y-6">
        <Card>
          <h2 className="text-lg font-black">Latest cumulative Instagram metrics</h2>
          <p className="mt-1 text-xs leading-5 text-[#746b82]">This is the latest available lifetime total. It is separate from the scheduled first-24-hour milestones below.</p>
          <div>
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
            {selected.latest?.metric_status && Object.values(selected.latest.metric_status).some((value) => value === "permission_required") ? <p className="mt-3 rounded-xl bg-red-50 p-3 text-xs font-bold text-red-800">Some Instagram insight fields require renewed Insights permission. Reconnect the account to grant access.</p> : null}
            {selected.latest?.metric_status && !Object.values(selected.latest.metric_status).includes("permission_required") && Object.values(selected.latest.metric_status).some((value) => value === "unavailable") ? <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs font-bold text-amber-900">This media type returned only partial metrics; unavailable values are not shown as zero.</p> : null}
            <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-xl bg-[#f7f5ff] px-4 py-3 text-sm font-bold"><input type="checkbox" checked={useAccountContext} onChange={(event) => setUseAccountContext(event.target.checked)} className="h-4 w-4 accent-violet-600" />Use account context</label>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <button disabled={working !== null} onClick={() => void refresh()} className="rounded-xl bg-[#eee8fa] px-3 py-3 text-sm font-bold text-[#5b21b6] disabled:opacity-50">{working === "refresh" ? "Refreshing…" : "Refresh metrics"}</button>
              <button disabled={working !== null || !selected.latest} onClick={() => void analyze()} className="rounded-xl bg-[#7c3aed] px-3 py-3 text-sm font-bold text-white disabled:opacity-50">{working === "analyze" ? "Analyzing…" : "Analyze post"}</button>
            </div>
          </div>
        </Card>
        <PostPublishTrackingBlock tracking={selected.post_publish_tracking} />
        {displayedAnalysis ? <PostAnalysisCard analysis={displayedAnalysis} /> : <Card><p className="font-bold">No saved analysis for this post yet.</p><p className="mt-2 text-sm leading-6 text-[#746b82]">Refresh the metrics, then analyze this post.</p></Card>}
        {selected.analyses?.length ? <AnalysisTimeline analyses={selected.analyses} selectedId={displayedAnalysis?.id} onSelect={setViewingAnalysisId} /> : null}
      </div>}
    </div>
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
    {!insights && !error ? <Card><p className="text-sm text-[#746b82]">Loading insights…</p></Card> : insights ? <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-black">{insights.heading}</p><p className="mt-1 text-sm text-[#746b82]">{insights.sample_notice}</p><p className="mt-2 text-xs leading-5 text-[#80778b]">{insights.confidence_explanation}</p><p className="mt-1 text-xs text-[#80778b]">Period {insights.observation_period.start ? new Date(insights.observation_period.start).toLocaleDateString() : "not available"} - {insights.observation_period.end ? new Date(insights.observation_period.end).toLocaleDateString() : "not available"} · {insights.observation_period.timezone}</p></div><p className={`rounded-full px-3 py-1 text-xs font-black ${insights.enough_data ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>{insights.enough_data ? "OBSERVATIONAL EVIDENCE" : "LIMITED SAMPLE"}</p></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Progress label="Analyzed posts" value={insights.progress.patterns} required={insights.required_sample_size} />
          <Progress label="Complete 24h snapshots" value={insights.progress.posting_times} required={insights.required_sample_size} />
        </div>
      </Card>
      <Card><h2 className="text-lg font-black">Content opportunities</h2><div className="mt-4 grid gap-4 lg:grid-cols-2">{insights.content_opportunities.length ? insights.content_opportunities.map((item) => <Opportunity key={item.title} item={item} />) : <p className="text-sm text-[#746b82]">Analyze more varied posts to generate a testable opportunity.</p>}</div></Card>
      <PostPerformance insights={insights} />
      <InsightRanking title={insights.enough_data ? "Observed content patterns" : "Content patterns to validate"} items={insights.patterns} showCategory />
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <InsightRanking title={insights.posting_time_metadata.complete_posts >= insights.required_sample_size ? "Historical 24-hour performance by time" : "Observed posting-time results"} items={insights.posting_time_insights} subtitle={`${insights.posting_time_metadata.timezone} · ${insights.posting_time_metadata.complete_posts} complete posts · ${insights.posting_time_metadata.metric}${insights.posting_time_metadata.period_start && insights.posting_time_metadata.period_end ? ` · ${new Date(insights.posting_time_metadata.period_start).toLocaleDateString()}–${new Date(insights.posting_time_metadata.period_end).toLocaleDateString()}` : ""}`} />
        <Card><h2 className="text-lg font-black">Untested posting windows</h2><p className="mt-2 text-xs leading-5 text-[#746b82]">{insights.posting_time_metadata.timezone} · These are coverage gaps, not predicted best times.</p><div className="mt-4 flex flex-wrap gap-2">{insights.untested_posting_windows.map((window) => <span key={window} className="rounded-full bg-[#f7f5ff] px-4 py-2 text-sm font-bold">{window}</span>)}</div><div className="mt-5 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-950"><p className="font-black">24-hour data: {insights.tracking_24h.complete_posts}/{insights.tracking_24h.total_posts} posts</p><p className="mt-1">{insights.tracking_24h.message}</p></div></Card>
      </div>
      {insights.tested_combination && <Card dark><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-black text-white">Pattern to validate</h2><p className="rounded-full bg-white/10 px-4 py-2 text-xs font-black text-violet-100">{insights.tested_combination.confidence_label}</p></div><p className="mt-5 text-lg font-black text-white">{insights.tested_combination.label}</p><p className="mt-2 text-sm text-violet-100">Average Post Score {insights.tested_combination.average_score} · {insights.tested_combination.posts} posts · baseline {insights.tested_combination.baseline_score}</p><p className="mt-3 text-xs leading-5 text-violet-300">{insights.tested_combination.caution}</p></Card>}
    </div> : null}
  </>;
}

function InsightRanking({ title, items, showCategory = false, subtitle }: { title: string; items: PatternInsight[]; showCategory?: boolean; subtitle?: string }) {
  return <Card><h2 className="text-lg font-black">{title}</h2>{subtitle && <p className="mt-1 text-xs leading-5 text-[#746b82]">{subtitle}</p>}<p className="mt-2 text-xs leading-5 text-[#80778b]">Confidence describes sample-size sufficiency, not the probability that the conclusion is correct.</p><div className="mt-4 divide-y divide-[#eee8fa]">{items.length ? items.map((item) => <div key={`${item.category ?? title}-${item.label}`} className="py-4 first:pt-0 last:pb-0"><div className="flex items-start justify-between gap-4"><div className="min-w-0">{showCategory && item.category && <p className="text-[10px] font-bold uppercase tracking-wider text-[#80778b]">{item.category}</p>}<p className="font-black">{item.label}</p><p className="mt-1 text-xs text-[#80778b]">{item.evidence}</p></div><div className="shrink-0 text-right"><p className="text-2xl font-black">{item.average_score}{item.metric_label.toLowerCase().includes("engagement") ? "%" : ""}</p><p className="text-[10px] font-bold uppercase text-[#80778b]">Average {item.metric_label}</p></div></div><div className="mt-3 flex flex-wrap items-center gap-2 text-xs"><span className={`rounded-full px-2 py-1 font-black ${item.confidence === "LOW" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-800"}`}>{item.confidence_label.toUpperCase()}</span><span className="font-bold text-[#5b5168]">{item.difference_from_baseline >= 0 ? "+" : ""}{item.difference_from_baseline} vs baseline {item.baseline_score}</span></div><p className="mt-2 text-xs font-bold text-[#5b5168]">{item.difference_interpretation}</p><p className="mt-1 text-[11px] text-[#80778b]">Distribution: {item.distribution.minimum} min · {item.distribution.median} median · {item.distribution.maximum} max</p><p className="mt-1 text-[11px] text-[#80778b]">Comparison: {item.benchmark}</p></div>) : <p className="py-2 text-sm text-[#746b82]">Not enough repeated examples to compare yet.</p>}</div></Card>;
}

function MetricValue({ value, suffix = "" }: { value?: number | null; suffix?: string }) {
  return <span>{value == null ? "API not provided / not captured" : `${value.toLocaleString()}${suffix}`}</span>;
}

function PostPerformance({ insights }: { insights: AccountInsights }) {
  return <Card>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-black">Post performance</h2><p className="mt-1 max-w-3xl text-xs leading-5 text-[#746b82]">Posts are ranked only inside the same media format with a true 24-hour milestone and the same metric. Partial windows and lifetime totals are listed, but never mixed into that ranking.</p></div><span className="rounded-full bg-[#eee8fa] px-3 py-1 text-[10px] font-black text-[#5b21b6]">VERIFIABLE DATA</span></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2"><p className="rounded-xl bg-[#f7f5ff] p-3 text-xs leading-5"><b>Views:</b> {insights.metric_capabilities.definitions.views}</p><p className="rounded-xl bg-[#f7f5ff] p-3 text-xs leading-5"><b>Reach:</b> {insights.metric_capabilities.definitions.reach}</p></div>
    <div className="mt-5 space-y-4">{insights.performance_posts.length ? insights.performance_posts.map((post) => <PerformancePostCard key={post.tracked_post_id ?? post.instagram_media_id} post={post} />) : <p className="text-sm text-[#746b82]">No tracked Instagram post data is available yet.</p>}</div>
    <div className="mt-5 rounded-xl bg-amber-50 p-4 text-xs leading-5 text-amber-950"><p className="font-black">Current integration limits</p><p className="mt-1">Average watch time, total watch time, retention and skip rate are not requested or persisted by the current integration, so PostBridge does not invent values for them. They require confirmation of media-level availability from Meta plus client and storage changes. Current access requires a professional Business or Creator account and <code>{insights.metric_capabilities.required_scope}</code>.</p></div>
  </Card>;
}

function PerformancePostCard({ post }: { post: PerformancePost }) {
  const metric = post.metrics;
  return <details className="group rounded-2xl border border-[#eee8fa] p-4" open={post.comparison?.rank === 1}>
    <summary className="cursor-pointer list-none"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap gap-2"><span className="rounded-full bg-violet-100 px-2 py-1 text-[10px] font-black text-violet-900">{post.media_type_label}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-black text-slate-700">{post.topic}</span>{post.comparison ? <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-black text-emerald-800">#{post.comparison.rank} OF {post.comparison.group_size} BY {post.comparison.metric.toUpperCase()}</span> : null}</div><p className="mt-2 max-w-2xl truncate font-black">{post.caption_excerpt || "Instagram post"}</p><p className="mt-1 text-[11px] leading-5 text-[#746b82]">Published {new Date(post.published_at).toLocaleString()} · {post.posting_window}<br />Observation: {post.observation_kind}{post.snapshot_captured_at ? ` · captured ${new Date(post.snapshot_captured_at).toLocaleString()} · ${post.tracking_period_hours}h after publishing` : ""}</p></div><span className="text-xs font-black text-[#5b21b6] group-open:hidden">View data</span></div></summary>
    <div className="mt-4 grid grid-cols-2 gap-3 rounded-2xl bg-[#f7f5ff] p-4 sm:grid-cols-3 lg:grid-cols-6"><TrackingMetric label="Views" value={metric?.views} placeholder="API not provided / not captured" featured /><TrackingMetric label="Reach" value={metric?.reach} placeholder="API not provided / not captured" /><TrackingMetric label="Likes" value={metric?.likes} placeholder="API not provided / not captured" /><TrackingMetric label="Comments" value={metric?.comments} placeholder="API not provided / not captured" /><TrackingMetric label="Shares" value={metric?.shares} placeholder="API not provided / not captured" /><TrackingMetric label="Saves" value={metric?.saves} placeholder="API not provided / not captured" /></div>
    {post.comparison ? <p className="mt-3 text-xs font-bold text-emerald-800">Comparable group: {post.comparison.group}. No other media type or observation period is included.</p> : <p className="mt-3 text-xs font-bold text-amber-900">Not ranked: this post does not yet have enough same-format posts on the same 24-hour basis.</p>}
    <div className="mt-4 grid gap-2 sm:grid-cols-5">{post.milestones.map((milestone) => <div key={milestone.target_hour} className="rounded-xl border border-[#eee8fa] p-3"><div className="flex items-center justify-between"><b>{milestone.target_hour}h</b><span className="text-[9px] font-bold uppercase text-[#80778b]">{milestone.status.replaceAll("_", " ")}</span></div><p className="mt-2 text-xs font-bold">Views: <MetricValue value={milestone.metrics?.views} /></p><p className="mt-1 text-xs">Reach: <MetricValue value={milestone.metrics?.reach} /></p>{milestone.views_since_previous_snapshot != null ? <p className="mt-2 text-[10px] font-bold text-blue-800">+{milestone.views_since_previous_snapshot.toLocaleString()} between snapshots</p> : null}<p className="mt-2 text-[10px] leading-4 text-[#80778b]">Scheduled {milestone.scheduled_for ? new Date(milestone.scheduled_for).toLocaleString() : "not scheduled"}<br />Actual {milestone.captured_at ? new Date(milestone.captured_at).toLocaleString() : "not captured"}</p></div>)}</div>
    <p className="mt-3 text-[11px] leading-5 text-[#80778b]">An increase is the difference between adjacent captured cumulative snapshots, not exact hourly views. Missing fields remain unavailable and are never converted to zero.</p>
    {post.permalink ? <a href={post.permalink} target="_blank" rel="noreferrer" className="mt-3 inline-flex rounded-xl bg-[#eee8fa] px-4 py-2 text-xs font-black text-[#5b21b6]">Open original Instagram post</a> : <p className="mt-3 text-xs text-[#80778b]">Original post link was not returned by Instagram.</p>}
  </details>;
}

function Progress({ label, value, required }: { label: string; value: number; required: number }) { return <div className="rounded-2xl bg-[#f7f5ff] p-4"><div className="flex justify-between gap-3"><p className="text-sm font-bold">{label}</p><p className="text-sm font-black">{value}/{required}</p></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-[#e8e0f7]"><div className="h-full rounded-full bg-[#7c3aed]" style={{ width: `${Math.min(100, value / required * 100)}%` }} /></div></div>; }
function Opportunity({ item }: { item: ContentOpportunity }) {
  const period = item.observation_period.start && item.observation_period.end ? `${new Date(item.observation_period.start).toLocaleDateString()} - ${new Date(item.observation_period.end).toLocaleDateString()}` : "No observation period yet";
  return <div className="rounded-2xl border border-[#eee8fa] p-4"><div className="flex items-center justify-between gap-3"><p className="font-black">{item.priority}. {item.title}</p><span className={`rounded-full px-2 py-1 text-[10px] font-black ${item.status === "DATA_GAP" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>{item.status.replace("_", " ")}</span></div><p className="mt-2 text-[11px] text-[#80778b]">{item.sample_size} eligible post(s) · {period}</p><p className="mt-3 text-sm leading-6"><b>Current observation:</b> {item.current_observation}</p><p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950"><b>Data gap:</b> {item.data_gap}</p><p className="mt-3 text-sm leading-6"><b>Suggested test:</b> {item.suggested_test}</p><p className="mt-2 text-sm leading-6"><b>Change only:</b> {item.primary_variable}</p><p className="mt-2 text-sm leading-6"><b>Track:</b> {item.tracking_metric} {item.capture_timing}</p><p className="mt-2 text-sm leading-6"><b>Decision:</b> {item.decision_method}</p><p className="mt-3 text-xs font-bold text-[#80778b]">{item.effect_estimate_label}</p></div>;
}

function TrackingMetric({ label, value, placeholder = "Unavailable", featured = false }: { label: string; value?: number | null; placeholder?: string; featured?: boolean }) {
  const display = value == null ? placeholder : value.toLocaleString();
  return <div className={featured ? "rounded-xl bg-violet-100 p-2" : ""}><p className={`font-black ${featured ? "text-violet-950" : "text-[#201633]"}`}>{display}</p><p className="text-[10px] font-bold uppercase tracking-wide text-[#80778b]">{label}</p></div>;
}

function PostPublishTrackingBlock({ tracking }: { tracking?: TrackedPost["post_publish_tracking"] }) {
  if (!tracking?.automatic_collection) return <Card><h2 className="text-lg font-black">Post-publish tracking</h2><p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-950">Automatic milestone collection is unavailable in this environment. Manual refreshes remain current cumulative snapshots and are not treated as historical 24-hour results.</p></Card>;
  const statusMessage = tracking.status === "blocked_reauthorization"
    ? "Instagram authorization expired. Reconnect the account to resume milestones that are still within their collection window."
    : tracking.status === "permission_required"
      ? "Instagram did not grant the insight permission required for automatic collection. Reauthorize the account and grant Insights access."
      : tracking.status === "complete"
        ? "The first-24-hour tracking window is complete."
        : tracking.next_capture_at
          ? `Tracking is active. Next attempt: ${new Date(tracking.next_capture_at).toLocaleString()}.`
          : "Tracking is active.";
  const statusTone = tracking.status === "blocked_reauthorization" || tracking.status === "permission_required" ? "bg-red-50 text-red-800" : tracking.status === "complete" ? "bg-emerald-50 text-emerald-800" : "bg-violet-50 text-violet-900";
  const label: Record<string, string> = {
    pending: "Scheduled", running: "Capturing", retry: "Retry scheduled", completed: "Captured",
    missed: "Missed — no historical data created", cancelled: "Cancelled",
    blocked_reauthorization: "Reconnect required", permission_required: "Insights permission required",
    unavailable: "Post unavailable",
  };
  return <Card>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-black">Post-publish tracking</h2><p className="mt-1 text-xs text-[#746b82]">Separate cumulative snapshots at 1h, 3h, 6h, 12h and 24h after publishing.</p></div><span className="rounded-full bg-[#eee8fa] px-3 py-1 text-xs font-black text-[#5b21b6]">FIRST 24 HOURS</span></div>
    <p className={`mt-4 rounded-xl p-3 text-sm ${statusTone}`}>{statusMessage}</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{tracking.milestones.map((milestone) => {
      const snapshot = milestone.snapshot;
      const partial = snapshot?.metric_status && Object.values(snapshot.metric_status).some((value) => value !== "available");
      const awaitingCapture = ["pending", "running", "retry", "blocked_reauthorization", "permission_required"].includes(milestone.status);
      const metricPlaceholder = snapshot ? "Unavailable" : awaitingCapture ? "Not captured yet" : "No snapshot";
      return <div key={milestone.target_hour} className={`rounded-2xl border p-4 ${milestone.target_hour === 24 ? "border-violet-400 bg-violet-50/50" : "border-[#eee8fa]"}`}>
        <div className="flex items-center justify-between gap-2"><p className="text-xl font-black">{milestone.target_hour}h</p><span className={`rounded-full px-2 py-1 text-[10px] font-black ${milestone.status === "completed" ? "bg-emerald-100 text-emerald-800" : milestone.status === "pending" || milestone.status === "retry" || milestone.status === "running" ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-700"}`}>{label[milestone.status] ?? milestone.status}</span></div>
        <p className="mt-3 text-[11px] leading-5 text-[#746b82]">Scheduled {new Date(milestone.scheduled_for).toLocaleString()}</p>
        <p className="text-[11px] leading-5 text-[#746b82]">Actual {milestone.actual_captured_at ? new Date(milestone.actual_captured_at).toLocaleString() : "—"}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs"><TrackingMetric label="Views" value={snapshot?.views} placeholder={metricPlaceholder} featured /><TrackingMetric label="Reach" value={snapshot?.reach} placeholder={metricPlaceholder} />{snapshot ? <><Metric label="Likes" value={snapshot.likes} /><Metric label="Comments" value={snapshot.comments} /><Metric label="Saves" value={snapshot.saves} /><Metric label="Shares" value={snapshot.shares} /><div className="col-span-2"><Metric label="Engagement rate" value={snapshot.engagement_rate == null ? "Unable to calculate" : `${snapshot.engagement_rate}%`} /></div></> : null}</div>
        {milestone.views_since_previous_snapshot != null ? <p className="mt-3 rounded-lg bg-blue-50 p-2 text-[11px] font-bold text-blue-900">+{milestone.views_since_previous_snapshot.toLocaleString()} views — increase between snapshots</p> : null}
        {partial ? <p className="mt-3 text-[11px] font-bold text-amber-800">{Object.values(snapshot?.metric_status ?? {}).includes("permission_required") ? "Partial metrics: reconnect Instagram and grant Insights permission for restricted fields." : "Partial metrics: fields unavailable for this media type remain blank."}</p> : null}
      </div>;
    })}</div>
    <p className="mt-4 text-[11px] leading-5 text-[#746b82]"><b>Views</b> are cumulative at the actual capture time and may include repeat views from the same Instagram account. <b>Reach</b> is shown separately and represents unique accounts when Meta returns it. Any increase shown is only the difference between two captured snapshots, not exact per-hour views.</p>
    <p className="mt-4 text-[11px] leading-5 text-[#746b82]">Engagement rate = the sum of interaction counts actually returned (likes, comments, saves and shares) ÷ reach × 100. Unavailable fields are excluded, never treated as zero. Without positive reach or any returned interaction count, it is shown as unable to calculate.</p>
  </Card>;
}

function Settings({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [error, setError] = useState("");
  const emptyContext: AccountContext = { account_theme: "", about_this_account: "", target_audience: "" };
  const [accountContext, setAccountContext] = useState<AccountContext>(emptyContext);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    getAccountContext(session)
      .then(setAccountContext)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load account context."))
      .finally(() => setLoading(false));
  }, [session]);
  const saveContext = async () => {
    setSaving(true); setSaved(false); setError("");
    try {
      const result = await updateAccountContext(session, accountContext);
      setAccountContext(result); setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save account context.");
    } finally { setSaving(false); }
  };
  const fields: Array<{ key: keyof AccountContext; label: string; placeholder: string; maxLength: number }> = [
    { key: "account_theme", label: "Account Theme", placeholder: "what's your account topic", maxLength: 300 },
    { key: "about_this_account", label: "About This Account", placeholder: "Describe the content, formats and creator identity.", maxLength: 3000 },
    { key: "target_audience", label: "Target Audience", placeholder: "Who this account is for", maxLength: 2000 },
  ];
  return <><Title>Settings</Title><ErrorText value={error} /><div className="space-y-5"><Card><h2 className="text-lg font-black">Account context</h2><div className="mt-5 grid gap-4 lg:grid-cols-2">{fields.map((field) => <label key={field.key} className={field.key === "account_theme" ? "" : "lg:col-span-2"}><span className="text-sm font-bold">{field.label}</span><textarea disabled={loading || saving} maxLength={field.maxLength} value={accountContext[field.key]} onChange={(event) => { setAccountContext((current) => ({ ...current, [field.key]: event.target.value })); setSaved(false); }} className="mt-2 min-h-28 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400 disabled:opacity-60" placeholder={field.placeholder} /><span className="mt-1 block text-right text-[11px] text-[#80778b]">{accountContext[field.key].length}/{field.maxLength}</span></label>)}</div><div className="mt-4 flex justify-end"><button disabled={loading || saving} onClick={() => void saveContext()} className="rounded-xl bg-[#7c3aed] px-5 py-3 text-sm font-black text-white disabled:opacity-50">{saving ? "Saving..." : saved ? "Saved" : "Save"}</button></div></Card><Card><p className="text-xs font-bold uppercase tracking-wider text-[#80778b]">Signed in as</p><p className="mt-2 break-all text-base font-black md:text-lg">{session.user.email}</p><div className="mt-6 grid grid-cols-2 gap-3 sm:flex"><button onClick={async () => { try { await logout(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Logout failed."); } }} className="rounded-xl border border-[#ddd5e8] px-3 py-3 text-sm font-bold sm:px-5 sm:text-base">Log out</button><button onClick={async () => { if (!window.confirm("Permanently delete your PostBridge account and all associated data?")) return; try { await deleteAccount(session); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : "Account deletion failed."); } }} className="rounded-xl border border-red-200 px-3 py-3 text-sm font-bold text-red-700 sm:px-5 sm:text-base">Delete account</button></div></Card></div></>;
}

function PostAnalysisCard({ analysis }: { analysis: PostAnalysis }) {
  const output = analysis.output_payload;
  if (!output.score) return <Card><p className="font-black">Legacy analysis</p><p className="mt-2 text-sm text-[#746b82]">{output.summary ?? "Run a new analysis to generate the creator intelligence dashboard."}</p></Card>;
  const tone = (value: number) => value >= 75 ? "bg-emerald-500" : value >= 50 ? "bg-amber-500" : "bg-red-500";
  const difference = output.score_context?.points_difference;
  const context = difference == null
    ? output.score_context?.percentile_label
    : `${difference >= 0 ? "↑" : "↓"} ${Math.abs(difference)} points ${difference >= 0 ? "above" : "below"} account average`;
  const scoreLabel = (name: string) => name === "interaction_quality" ? "Interaction per reach" : name.replaceAll("_", " ");
  const formatDate = (value: string | null) => value ? new Date(value).toLocaleDateString() : "Unavailable";
  return <div className="space-y-5">
    <Card dark>
      <div className="flex flex-wrap items-end justify-between gap-5"><div><p className="text-xs font-black uppercase tracking-widest text-violet-300">Post score</p><p className="mt-2 text-5xl font-black text-white">{output.score.overall}<span className="text-xl text-violet-300"> / 100</span></p>{context && <p className="mt-2 text-sm font-bold text-violet-200">{context}</p>}{output.score_context && output.score_context.total > 1 && <p className="mt-1 text-xs text-violet-300">Ranked #{output.score_context.rank} of {output.score_context.total}</p>}</div><div className="rounded-2xl bg-white/10 px-5 py-3 text-center"><p className="text-xs text-violet-300">Grade</p><p className="text-3xl font-black text-white">{output.score.grade}</p></div></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">{Object.entries(output.score.categories).map(([name, value]) => <div key={name}><div className="mb-1 flex justify-between text-xs font-bold text-violet-100"><span className="capitalize">{scoreLabel(name)}</span><span>{value}</span></div><div className="h-2 overflow-hidden rounded-full bg-white/10"><div className={`h-full ${tone(value)}`} style={{ width: `${value}%` }} /></div><p className="mt-1 text-[11px] leading-4 text-violet-300">{output.score?.category_meanings?.[name]}</p></div>)}</div>
      {output.score.method && <p className="mt-5 rounded-xl bg-white/10 p-3 text-xs leading-5 text-violet-100"><b>How scoring works:</b> {output.score.method}</p>}
      {output.executive_summary?.length ? <div className="mt-6 border-t border-white/10 pt-5"><p className="font-black text-white">Summary</p><ul className="mt-3 grid gap-2 text-sm text-violet-100 sm:grid-cols-2">{output.executive_summary.slice(0, 4).map((item) => <li key={item} className="flex gap-2"><span className="text-violet-300">•</span><span>{item}</span></li>)}</ul></div> : null}
    </Card>
    {output.baseline && <DashboardSection title="Comparison basis"><div className={`rounded-2xl p-4 ${output.baseline.limited_sample ? "bg-amber-50 text-amber-950" : "bg-[#f7f5ff]"}`}><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-black">{output.baseline.label}</p><p className="rounded-full bg-white px-3 py-1 text-xs font-black">{output.baseline.sample_size} comparison posts</p></div><p className="mt-2 text-sm leading-6">{output.baseline.sample_notice}</p><p className="mt-2 text-xs">Published range: {formatDate(output.baseline.published_range.start)} – {formatDate(output.baseline.published_range.end)}</p><p className="mt-1 text-xs">Metric snapshot range: {formatDate(output.baseline.snapshot_range.start)} – {formatDate(output.baseline.snapshot_range.end)}</p><p className="mt-1 text-xs">Primary comparison: median · Mean shown as a secondary reference</p></div><ul className="mt-3 space-y-1 text-xs leading-5 text-[#746b82]">{output.baseline.limitations.map((item) => <li key={item}>• {item}</li>)}</ul></DashboardSection>}
    <DashboardSection title="Top insights">{output.top_insights?.map((item) => <p key={item.text} className="rounded-xl bg-[#f7f5ff] p-3 text-sm font-bold">{item.status === "strong" ? "✅" : item.status === "attention" ? "⚠️" : "ℹ️"} {item.text}</p>)}</DashboardSection>
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <DashboardSection title="Possible explanations"><p className="mb-3 text-xs leading-5 text-[#746b82]">These are hypotheses suggested by the available content and metrics, not proven causes.</p>{!output.why_it_worked?.length && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950">There is not enough supporting evidence for a content explanation. No hook, pacing, or retention diagnosis was added.</p>}<div className="grid gap-3">{output.why_it_worked?.slice(0, 3).map((item, index) => <div key={item.title ?? item.factor ?? index} className="rounded-2xl border border-[#eee8fa] p-4"><p className="text-[10px] font-black uppercase tracking-wide text-[#7c3aed]">{item.classification ?? "Possible explanation"}</p><p className="mt-1 font-black">{item.title ?? item.factor}</p>{item.evidence ? <><p className="mt-3 text-xs font-black uppercase tracking-wide text-[#80778b]">Observed evidence</p><p className="mt-1 text-sm leading-6">{item.evidence}</p><p className="mt-3 text-xs font-black uppercase tracking-wide text-[#80778b]">Hypothesis</p><p className="mt-1 text-sm leading-6">{item.interpretation}</p><p className="mt-3 text-xs font-black uppercase tracking-wide text-[#80778b]">How to use it</p><p className="mt-1 text-sm leading-6 text-[#5b21b6]">{item.why_it_matters}</p></> : <p className="mt-2 text-sm leading-6 text-[#746b82]">{item.explanation}</p>}</div>)}</div></DashboardSection>
      <DashboardSection title="Risks">{output.risks?.length ? output.risks.map((item) => <p key={item} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">⚠️ {item}</p>) : <p className="text-sm text-[#746b82]">No evidence-backed risk was detected.</p>}</DashboardSection>
    </div>
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <DashboardSection title="Recommended experiment"><div className="space-y-3">{output.recommendations.map((item, index) => typeof item === "string" ? <p key={item}>{item}</p> : <div key={`${item.action}-${index}`} className="rounded-2xl border border-[#eee8fa] p-4"><p className="text-xs font-black uppercase tracking-wide text-[#7c3aed]">One primary variable</p><p className="mt-2 font-black">{item.test_variable ?? `Experiment ${index + 1}`}</p><p className="mt-1 text-sm leading-6">{item.action}</p><p className="mt-3 text-sm text-[#746b82]"><b>Why test it:</b> {item.reason}</p>{item.metric_to_watch && <p className="mt-2 text-sm"><b>Watch:</b> {item.metric_to_watch}</p>}{item.comparison && <p className="mt-2 text-sm"><b>Compare:</b> {item.comparison}</p>}<p className="mt-2 text-sm font-bold text-[#6d28d9]"><b>Decision:</b> {item.expected_outcome ?? item.expected_impact}</p></div>)}</div></DashboardSection>
      <DashboardSection title="Benchmark details"><div className="grid gap-3 sm:grid-cols-2">{output.benchmarks?.filter((item) => item.current != null).map((item) => <div key={item.metric} className="rounded-2xl bg-[#f7f5ff] p-4"><p className="text-xs font-bold uppercase text-[#80778b]">{item.metric.replaceAll("_", " ")}</p><p className="mt-1 text-2xl font-black">{item.current}</p><p className={`mt-1 text-xs font-bold ${item.percent_change != null && item.percent_change >= 0 ? "text-emerald-700" : "text-red-700"}`}>{item.percent_change == null ? "Baseline unavailable" : `${item.percent_change >= 0 ? "↑" : "↓"} ${Math.abs(item.percent_change)}% ${item.direction} median`}</p><p className="mt-2 text-xs text-[#746b82]">Median {item.median ?? "—"} · Mean {item.average ?? "—"} · n={item.sample_size ?? 0}</p></div>)}</div></DashboardSection>
    </div>
    {output.trend && <DashboardSection title="Post metric history"><p className="rounded-xl bg-[#f7f5ff] p-3 text-sm leading-6">{output.trend.summary}</p><p className="mt-2 text-xs text-[#746b82]">{output.trend.observation_count} observations · {output.trend.span_hours} hours · This does not measure account growth.</p></DashboardSection>}
    {output.evidence_quality ? <DashboardSection title="Evidence quality"><div className="flex flex-wrap items-end gap-4"><p className="text-4xl font-black">{output.evidence_quality.score}<span className="text-lg"> / 100</span></p><p className="pb-1 text-lg font-black text-[#6d28d9]">{output.evidence_quality.level}</p></div><p className="mt-2 text-sm leading-6 text-[#746b82]">{output.evidence_quality.meaning}</p><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{output.evidence_quality.inputs.map((item) => <div key={item.name} className="rounded-xl bg-[#f7f5ff] px-3 py-2 text-sm"><div className="flex justify-between gap-2"><span>{item.available ? "✓" : "—"} {item.name}</span><span className="font-bold text-[#80778b]">{item.earned}/{item.weight}</span></div>{item.detail && <p className="mt-1 text-xs text-[#80778b]">{item.detail}</p>}</div>)}</div></DashboardSection> : output.confidence && <DashboardSection title="Legacy AI confidence"><p className="text-sm text-[#746b82]">This older report used input availability as a confidence score. Run a new analysis for evidence quality.</p></DashboardSection>}
    {output.data_gaps?.length ? <DashboardSection title="Missing evidence"><div className="space-y-2">{output.data_gaps.map((item) => <p key={item} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950">— {item}</p>)}</div></DashboardSection> : null}
    <p className="text-[11px] text-[#80778b]">Snapshot {analysis.source_snapshot_id.slice(0, 8)} · {new Date(analysis.created_at).toLocaleString()} · {analysis.model_name}{analysis.content_payload.account_context_relevance ? ` · Account context: ${analysis.content_payload.account_context_relevance}` : ""}</p>
  </div>;
}
function DashboardSection({ title, children }: { title: string; children: ReactNode }) { return <Card><h3 className="mb-4 text-lg font-black">{title}</h3><div className="space-y-2">{children}</div></Card>; }
function AnalysisTimeline({ analyses, selectedId, onSelect }: { analyses: PostAnalysis[]; selectedId?: string; onSelect: (id: string) => void }) { return <section className="mt-8"><h2 className="mb-4 text-lg font-black">Analysis history</h2><div className="flex gap-3 overflow-x-auto pb-2">{[...analyses].reverse().map((analysis, index, ordered) => { const score = analysis.output_payload.score?.overall; const previous = index > 0 ? ordered[index - 1].output_payload.score?.overall : undefined; const direction = score != null && previous != null ? score > previous ? "↑" : score < previous ? "↓" : "→" : ""; return <button key={analysis.id} onClick={() => onSelect(analysis.id)} className={`min-w-44 rounded-2xl border bg-white p-4 text-left ${selectedId === analysis.id ? "border-violet-500 ring-2 ring-violet-200" : "border-[#e7e0f0]"}`}><p className="text-xs text-[#80778b]">{new Date(analysis.created_at).toLocaleDateString()}</p><p className="mt-1 text-2xl font-black">{score == null ? "Legacy" : `${score} ${direction}`}</p><p className="mt-2 text-xs text-[#80778b]">Post score snapshot</p></button>; })}</div></section>; }
function Metric({ label, value, light = false }: { label: string; value: unknown; light?: boolean }) { return <div><p className={`font-black ${light ? "text-white" : "text-[#201633]"}`}>{value == null ? "—" : String(value)}</p><p className={`text-[10px] font-bold uppercase tracking-wide ${light ? "text-violet-300" : "text-[#80778b]"}`}>{label}</p></div>; }
