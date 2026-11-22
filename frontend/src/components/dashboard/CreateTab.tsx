"use client";

import { useEffect, useRef, useState } from "react";
import {
  CaptionMedia,
  PublicationResult,
  PublishingCapability,
  Session,
  SocialPlatform,
  caption,
  getPublishingCapabilities,
  publishPost,
} from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { LoadingState } from "@/components/dashboard/LoadingState";
import { ErrorBanner, PageTitle, Panel } from "@/components/dashboard/ui";
import { UnifiedSelect } from "@/components/ui/UnifiedSelect";

const goals = [
  "Grow engagement",
  "Educate",
  "Build trust",
  "Increase brand awareness",
  "Share an announcement",
  "Other",
];
const platforms: SocialPlatform[] = ["Instagram", "Twitter", "Facebook", "Threads", "YouTube"];
const asOptions = (values: string[]) => values.map((value) => ({ value, label: value }));
const hashtagOptions = asOptions(Array.from({ length: 11 }, (_, count) => String(count)));
const allowedTypes = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime"];
const maxMediaBytes = 7 * 1024 * 1024;
const textareaClass = "w-full rounded-2xl bg-slate-100 p-4 outline-none";
type SelectedMedia = CaptionMedia & { name: string; preview: string; kind: "image" | "video" };
type ImageMimeType = "image/jpeg" | "image/png" | "image/webp";

function readDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    const fail = () => reject(new Error("Could not read this file."));
    reader.onload = () => (typeof reader.result === "string" ? resolve(reader.result) : fail());
    reader.onerror = fail;
    reader.readAsDataURL(file);
  });
}

function readVideoDuration(file: File) {
  return new Promise<number>((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      if (Number.isFinite(video.duration)) resolve(video.duration);
      else reject(new Error("Could not read the video duration."));
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read this video."));
    };
    video.src = url;
  });
}

export function CreateTab({ session }: { session: Session }) {
  const [information, setInformation] = useState("");
  const [goal, setGoal] = useState(goals[0]);
  const [customGoal, setCustomGoal] = useState("");
  const [selected, setSelected] = useState<SocialPlatform[]>(["Instagram"]);
  const [useContext, setUseContext] = useState(true);
  const [hashtagCount, setHashtagCount] = useState(5);
  const [media, setMedia] = useState<SelectedMedia | null>(null);
  const [result, setResult] = useState<{ caption: string; hashtags: string } | null>(null);
  const [capabilities, setCapabilities] = useState<PublishingCapability[]>([]);
  const [sharing, setSharing] = useState<SocialPlatform | null>(null);
  const [publicationResults, setPublicationResults] = useState<PublicationResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);
  const shouldScrollToResult = useRef(false);
  const effectiveGoal = goal === "Other" ? customGoal.trim() : goal;

  useEffect(() => {
    getPublishingCapabilities(session)
      .then(({ items }) => setCapabilities(items))
      .catch(() => setCapabilities([]));
  }, [session]);

  useEffect(() => {
    if (busy || !result || !shouldScrollToResult.current) return;
    shouldScrollToResult.current = false;
    const frame = window.requestAnimationFrame(() => {
      resultRef.current?.querySelector("section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [busy, result]);

  const chooseMedia = async (file?: File) => {
    if (!file) return;
    setError("");
    setResult(null);
    if (!allowedTypes.includes(file.type)) return setError("Choose a JPG, PNG, WebP, MP4, WebM or MOV file.");
    if (file.size > maxMediaBytes) return setError("Choose a file smaller than 7 MB.");
    const kind = file.type.startsWith("video/") ? "video" : "image";
    const duration = kind === "video" ? await readVideoDuration(file) : undefined;
    if (duration != null && duration > 60.05) return setError("Choose a video that is one minute or shorter.");
    const preview = await readDataUrl(file);
    const data = preview.split(",", 2)[1];
    if (!data) return setError("Could not read this file.");
    setMedia({
      name: file.name,
      preview,
      kind,
      data,
      mime_type: file.type as CaptionMedia["mime_type"],
      duration_seconds: duration,
    });
  };

  const generate = async () => {
    shouldScrollToResult.current = true;
    setBusy(true);
    setError("");
    try {
      setResult(
        await caption(session, {
          information,
          goal: effectiveGoal,
          platform: selected[0] ?? "Instagram",
          platforms: selected,
          use_account_context: useContext,
          hashtag_count: hashtagCount,
          media: media
            ? { mime_type: media.mime_type, data: media.data, duration_seconds: media.duration_seconds }
            : undefined,
        }),
      );
    } catch (reason) {
      shouldScrollToResult.current = false;
      setError(errorMessage(reason, "Generation failed."));
    } finally {
      setBusy(false);
    }
  };

  const share = async (platform: SocialPlatform) => {
    if (!result || !media || media.kind !== "image") return;
    setSharing(platform);
    setError("");
    setPublicationResults([]);
    try {
      const response = await publishPost(session, {
        platforms: [platform],
        caption: result.caption,
        hashtags: result.hashtags,
        image: { mime_type: media.mime_type as ImageMimeType, data: media.data },
      });
      setPublicationResults(response.results);
    } catch (reason) {
      setError(errorMessage(reason, `Could not share to ${platform}.`));
    } finally {
      setSharing(null);
    }
  };

  const shareBlocker = (platform: SocialPlatform) => {
    const capability = capabilities.find((item) => item.platform === platform);
    if (media?.kind === "video") return "Direct sharing currently supports image posts.";
    if (!media) return "Add an image before sharing.";
    if (!capability?.available) return capability?.reason || `${platform} publishing is not connected yet.`;
    return null;
  };

  return (
    <>
      <PageTitle className="mb-5 md:mb-7">Create post</PageTitle>
      <ErrorBanner message={error} />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Panel>
          <UnifiedSelect
            label="Social platforms"
            options={asOptions(platforms)}
            values={selected}
            onValuesChange={(next) => setSelected(next as SocialPlatform[])}
            multiple
            placeholder="Choose platforms"
          />

          <label className="mt-5 block text-sm font-bold">Content</label>
          <label className="mt-2 grid min-h-44 cursor-pointer place-items-center overflow-hidden rounded-2xl border border-dashed border-sky-200 bg-slate-100 p-4 text-center text-sm font-bold text-sky-700">
            {media?.kind === "image" ? (
              <img src={media.preview} alt="Selected content" className="max-h-72 w-full rounded-xl object-contain" />
            ) : media?.kind === "video" ? (
              <video src={media.preview} controls className="max-h-72 w-full rounded-xl" />
            ) : (
              <div>
                <p>Choose an image or short video</p>
                <p className="mt-2 text-xs font-normal text-slate-500">
                  JPG, PNG, WebP, MP4, WebM or MOV · video up to 1 minute · maximum 7 MB
                </p>
              </div>
            )}
            <input
              type="file"
              accept={allowedTypes.join(",")}
              className="hidden"
              onChange={(event) =>
                void chooseMedia(event.target.files?.[0]).catch((reason) =>
                  setError(errorMessage(reason, "Could not read this file.")),
                )
              }
            />
          </label>
          {media ? (
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span className="truncate">
                {media.name}
                {media.duration_seconds != null ? ` · ${Math.ceil(media.duration_seconds)}s` : ""}
              </span>
              <button
                type="button"
                onClick={() => {
                  setMedia(null);
                  setResult(null);
                }}
                className="shrink-0 font-bold text-sky-700"
              >
                Remove
              </button>
            </div>
          ) : null}

          <label className="mt-5 block text-sm font-bold">Information</label>
          <textarea
            value={information}
            onChange={(event) => setInformation(event.target.value)}
            className="mt-2 min-h-40 w-full rounded-2xl border border-slate-200 p-4 outline-none focus:ring-2 focus:ring-sky-400"
            placeholder="Tell me about your post so we can generate content that fits it better."
          />
          <div className="mt-4">
            <UnifiedSelect
              label="Hashtag count"
              options={hashtagOptions}
              value={String(hashtagCount)}
              onChange={(next) => setHashtagCount(Number(next))}
            />
          </div>
          <div className="mt-5">
            <UnifiedSelect
              label="Goal"
              options={asOptions(goals)}
              value={goal}
              onChange={setGoal}
              otherOptionValue="Other"
              otherValue={customGoal}
              onOtherValueChange={setCustomGoal}
              otherPlaceholder="Write your goal"
            />
          </div>
          <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl bg-slate-100 px-4 py-3 text-sm font-bold">
            <input
              type="checkbox"
              checked={useContext}
              onChange={(event) => setUseContext(event.target.checked)}
              className="h-4 w-4 accent-sky-600"
            />
            Use account context
          </label>
          <button
            disabled={busy || (!information.trim() && !media) || !effectiveGoal || !selected.length}
            onClick={() => void generate()}
            className="mt-5 w-full rounded-2xl bg-sky-600 py-4 font-black text-white disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create caption"}
          </button>
        </Panel>
        {busy ? <LoadingState label="Creating your post" /> : null}
        <div ref={resultRef} className="contents">
          {result ? (
            <Panel>
              <h2 className="text-xl font-black">Caption</h2>
              <textarea
                className={`mt-4 min-h-56 ${textareaClass}`}
                value={result.caption}
                onChange={(event) => setResult({ ...result, caption: event.target.value })}
              />
              <label className="mt-4 block text-sm font-bold">
                Hashtags
                <textarea
                  className={`mt-2 min-h-24 font-normal text-sky-700 ${textareaClass}`}
                  value={result.hashtags}
                  onChange={(event) => setResult({ ...result, hashtags: event.target.value })}
                />
              </label>
              <div className="mt-5 grid gap-2 sm:grid-cols-2">
                {selected.map((platform) => {
                  const blocker = shareBlocker(platform);
                  return (
                    <button
                      key={platform}
                      type="button"
                      disabled={Boolean(blocker) || Boolean(sharing)}
                      title={blocker ?? undefined}
                      onClick={() => void share(platform)}
                      className="min-h-12 rounded-2xl bg-sky-600 px-4 py-3 text-sm font-black text-white disabled:bg-sky-100 disabled:text-slate-500"
                    >
                      {sharing === platform ? "Sharing…" : `Share to ${platform}`}
                    </button>
                  );
                })}
              </div>
              {publicationResults.map((item) => (
                <p
                  key={item.platform}
                  className={`mt-3 text-sm font-semibold ${item.status === "published" ? "text-green-700" : "text-red-700"}`}
                >
                  {item.message}
                </p>
              ))}
            </Panel>
          ) : null}
        </div>
      </div>
    </>
  );
}
