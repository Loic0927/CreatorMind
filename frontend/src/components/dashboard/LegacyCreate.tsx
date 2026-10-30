"use client";

import { useState } from "react";
import { CaptionMedia, Session, SocialPlatform, caption } from "@/lib/postbridge";

const goals = ["Grow engagement", "Educate", "Build trust", "Increase brand awareness", "Share an announcement", "Other"];
const platforms: SocialPlatform[] = ["Instagram", "Twitter", "Facebook", "Threads", "YouTube"];
const allowedTypes = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime"] as const;
const maxMediaBytes = 7 * 1024 * 1024;
type SelectedMedia = CaptionMedia & { name: string; preview: string; kind: "image" | "video" };

function fileData(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result) : reject(new Error("Could not read this file."));
    reader.onerror = () => reject(new Error("Could not read this file."));
    reader.readAsDataURL(file);
  });
}

function videoDuration(file: File) {
  return new Promise<number>((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => { const duration = video.duration; URL.revokeObjectURL(url); Number.isFinite(duration) ? resolve(duration) : reject(new Error("Could not read the video duration.")); };
    video.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not read this video.")); };
    video.src = url;
  });
}

export function LegacyCreate({ session }: { session: Session }) {
  const [information, setInformation] = useState("");
  const [goal, setGoal] = useState(goals[0]);
  const [customGoal, setCustomGoal] = useState("");
  const [selected, setSelected] = useState<SocialPlatform[]>(["Instagram"]);
  const [useContext, setUseContext] = useState(true);
  const [media, setMedia] = useState<SelectedMedia | null>(null);
  const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const effectiveGoal = goal === "Other" ? customGoal.trim() : goal;

  const togglePlatform = (platform: SocialPlatform) => setSelected((current) => current.includes(platform) ? current.filter((item) => item !== platform) : [...current, platform]);
  const chooseMedia = async (file?: File) => {
    if (!file) return;
    setError(""); setResult(null);
    if (!allowedTypes.includes(file.type as typeof allowedTypes[number])) { setError("Choose a JPG, PNG, WebP, MP4, WebM or MOV file."); return; }
    if (file.size > maxMediaBytes) { setError("Choose a file smaller than 7 MB."); return; }
    const kind = file.type.startsWith("video/") ? "video" : "image";
    const duration = kind === "video" ? await videoDuration(file) : undefined;
    if (duration != null && duration > 60.05) { setError("Choose a video that is one minute or shorter."); return; }
    const preview = await fileData(file);
    const data = preview.split(",", 2)[1];
    if (!data) { setError("Could not read this file."); return; }
    setMedia({ name: file.name, preview, kind, data, mime_type: file.type as CaptionMedia["mime_type"], duration_seconds: duration });
  };
  const run = async () => {
    setBusy(true); setError("");
    try {
      setResult(await caption(session, {
        information,
        goal: effectiveGoal,
        platform: selected[0] ?? "Instagram",
        platforms: selected,
        use_account_context: useContext,
        media: media ? { mime_type: media.mime_type, data: media.data, duration_seconds: media.duration_seconds } : undefined,
      }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Generation failed."); }
    finally { setBusy(false); }
  };

  return <>
    <h1 className="mb-7 text-2xl font-black tracking-tight md:text-3xl">Create post</h1>
    {error ? <div className="mb-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}
    <div className={result ? "grid items-start gap-6 lg:grid-cols-2" : "max-w-[720px]"}>
      <section className="rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6">
        <label className="block text-sm font-bold">Social platforms</label>
        <details className="relative mt-2"><summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl border border-[#ddd5e8] bg-white p-4 font-bold"><span>{selected.length ? selected.join(", ") : "Choose platforms"}</span><span className="text-[#80778b]">⌄</span></summary><div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-[#ddd5e8] bg-white p-2 shadow-xl">{platforms.map((platform) => <label key={platform} className="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-3 hover:bg-[#f7f5ff]"><input type="checkbox" checked={selected.includes(platform)} onChange={() => togglePlatform(platform)} className="h-4 w-4 accent-violet-600" />{platform}</label>)}</div></details>

        <label className="mt-5 block text-sm font-bold">Content</label>
        <label className="mt-2 grid min-h-44 cursor-pointer place-items-center overflow-hidden rounded-2xl border border-dashed border-[#b9aec8] bg-[#f7f5ff] p-4 text-center text-sm font-bold text-[#5b21b6]">
          {media?.kind === "image" ? <img src={media.preview} alt="Selected content" className="max-h-72 w-full rounded-xl object-contain" /> : media?.kind === "video" ? <video src={media.preview} controls className="max-h-72 w-full rounded-xl" /> : <div><p>Choose an image or short video</p><p className="mt-2 text-xs font-normal text-[#80778b]">JPG, PNG, WebP, MP4, WebM or MOV · video up to 1 minute · maximum 7 MB</p></div>}
          <input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime" className="hidden" onChange={(event) => void chooseMedia(event.target.files?.[0]).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not read this file."))} />
        </label>
        {media ? <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[#80778b]"><span className="truncate">{media.name}{media.duration_seconds != null ? ` · ${Math.ceil(media.duration_seconds)}s` : ""}</span><button type="button" onClick={() => { setMedia(null); setResult(null); }} className="shrink-0 font-bold text-[#5b21b6]">Remove</button></div> : null}

        <label className="mt-5 block text-sm font-bold">Information</label>
        <textarea value={information} onChange={(event) => setInformation(event.target.value)} className="mt-2 min-h-40 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Add context, audience details and the key message" />
        <label className="mt-5 block text-sm font-bold">Goal</label>
        <select value={goal} onChange={(event) => setGoal(event.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">{goals.map((item) => <option key={item}>{item}</option>)}</select>
        {goal === "Other" ? <input value={customGoal} onChange={(event) => setCustomGoal(event.target.value)} className="mt-3 w-full rounded-2xl border border-[#ddd5e8] p-4" placeholder="Write your goal" /> : null}
        <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl bg-[#f7f5ff] px-4 py-3 text-sm font-bold"><input type="checkbox" checked={useContext} onChange={(event) => setUseContext(event.target.checked)} className="h-4 w-4 accent-violet-600" />Use account context</label>
        <button disabled={busy || (!information.trim() && !media) || !effectiveGoal || !selected.length} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating…" : "Create caption"}</button>
      </section>
      {result ? <section className="rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6"><h2 className="text-xl font-black">Caption</h2><textarea className="mt-4 min-h-56 w-full rounded-2xl bg-[#f7f5ff] p-4 outline-none" value={result.caption} onChange={(event) => setResult({ ...result, caption: event.target.value })} /><label className="mt-4 block text-sm font-bold">Hashtags<textarea className="mt-2 min-h-24 w-full rounded-2xl bg-[#f7f5ff] p-4 font-normal text-[#5b21b6] outline-none" value={result.hashtags} onChange={(event) => setResult({ ...result, hashtags: event.target.value })} /></label></section> : null}
    </div>
  </>;
}
