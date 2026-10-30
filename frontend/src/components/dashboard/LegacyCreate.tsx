"use client";

import { useState } from "react";
import { Session, SocialPlatform, caption } from "@/lib/postbridge";

const goals = ["Grow engagement", "Educate", "Build trust", "Increase brand awareness", "Share an announcement", "Other"];
const platforms: SocialPlatform[] = ["Instagram", "Twitter", "Facebook", "Threads", "YouTube"];

export function LegacyCreate({ session }: { session: Session }) {
  const [information, setInformation] = useState("");
  const [goal, setGoal] = useState(goals[0]);
  const [customGoal, setCustomGoal] = useState("");
  const [selected, setSelected] = useState<SocialPlatform[]>(["Instagram"]);
  const [useContext, setUseContext] = useState(true);
  const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const effectiveGoal = goal === "Other" ? customGoal.trim() : goal;

  const togglePlatform = (platform: SocialPlatform) => setSelected((current) => current.includes(platform) ? current.filter((item) => item !== platform) : [...current, platform]);
  const run = async () => {
    setBusy(true); setError("");
    try { setResult(await caption(session, { information, goal: effectiveGoal, platform: selected[0] ?? "Instagram", platforms: selected, use_account_context: useContext })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Generation failed."); }
    finally { setBusy(false); }
  };

  return <>
    <h1 className="mb-7 text-2xl font-black tracking-tight md:text-3xl">Create post</h1>
    {error ? <div className="mb-5 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <section className="rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6">
        <label className="block text-sm font-bold">Social platforms</label>
        <details className="relative mt-2">
          <summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl border border-[#ddd5e8] bg-white p-4 font-bold"><span>{selected.length ? selected.join(", ") : "Choose platforms"}</span><span className="text-[#80778b]">⌄</span></summary>
          <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-[#ddd5e8] bg-white p-2 shadow-xl">{platforms.map((platform) => <label key={platform} className="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-3 hover:bg-[#f7f5ff]"><input type="checkbox" checked={selected.includes(platform)} onChange={() => togglePlatform(platform)} className="h-4 w-4 accent-violet-600" />{platform}</label>)}</div>
        </details>
        <label className="mt-5 block text-sm font-bold">Information</label>
        <textarea value={information} onChange={(event) => setInformation(event.target.value)} className="mt-2 min-h-40 w-full rounded-2xl border border-[#ddd5e8] p-4 outline-none focus:ring-2 focus:ring-violet-400" placeholder="Describe your content, audience and key message" />
        <label className="mt-5 block text-sm font-bold">Goal</label>
        <select value={goal} onChange={(event) => setGoal(event.target.value)} className="mt-2 w-full rounded-2xl border border-[#ddd5e8] bg-white p-4">{goals.map((item) => <option key={item}>{item}</option>)}</select>
        {goal === "Other" ? <input value={customGoal} onChange={(event) => setCustomGoal(event.target.value)} className="mt-3 w-full rounded-2xl border border-[#ddd5e8] p-4" placeholder="Write your goal" /> : null}
        <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl bg-[#f7f5ff] px-4 py-3 text-sm font-bold"><input type="checkbox" checked={useContext} onChange={(event) => setUseContext(event.target.checked)} className="h-4 w-4 accent-violet-600" />Use account context</label>
        <button disabled={busy || !information.trim() || !effectiveGoal || !selected.length} onClick={() => void run()} className="mt-5 w-full rounded-2xl bg-[#7c3aed] py-4 font-black text-white disabled:opacity-50">{busy ? "Creating…" : "Create caption"}</button>
      </section>
      <section className="rounded-3xl border border-[#e7e0f0] bg-white p-5 shadow-sm md:p-6">
        <h2 className="text-xl font-black">Caption</h2>
        {result ? <><textarea className="mt-4 min-h-56 w-full rounded-2xl bg-[#f7f5ff] p-4 outline-none" value={result.caption} onChange={(event) => setResult({ ...result, caption: event.target.value })} /><label className="mt-4 block text-sm font-bold">Hashtags<textarea className="mt-2 min-h-24 w-full rounded-2xl bg-[#f7f5ff] p-4 font-normal text-[#5b21b6] outline-none" value={result.hashtags} onChange={(event) => setResult({ ...result, hashtags: event.target.value })} /></label></> : <div className="mt-4 grid min-h-72 place-items-center rounded-2xl border border-dashed border-[#b9aec8] bg-[#f7f5ff] p-8 text-center"><div><p className="font-black text-[#5b21b6]">Your caption will appear here</p><p className="mt-2 text-sm leading-6 text-[#746b82]">Choose platforms, describe the post and create a caption.</p></div></div>}
      </section>
    </div>
  </>;
}
