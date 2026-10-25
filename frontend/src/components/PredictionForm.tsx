"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { auditContent, extractScreenshotMetrics } from "@/lib/api";
import { saveStoredAnalysis } from "@/lib/analysis-session";
import AppShell from "@/components/stitch/AppShell";

type AuditFormState = {
  url: string;
  platform: string;
  caption: string;
  views: string;
  likes: string;
  comments: string;
  shares: string;
  averageWatchTime: string;
  retentionRate: string;
  assetFilename: string;
};

const initialForm: AuditFormState = {
  url: "",
  platform: "",
  caption: "",
  views: "",
  likes: "",
  comments: "",
  shares: "",
  averageWatchTime: "",
  retentionRate: "",
  assetFilename: ""
};

function toOptionalNumber(value: string) {
  return value.trim() === "" ? undefined : Number(value);
}

export default function PredictionForm() {
  const router = useRouter();
  const [formData, setFormData] = useState<AuditFormState>(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [screenshotMessage, setScreenshotMessage] = useState("");

  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleScreenshotUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      console.log("[CreatorMind] screenshotUpload:skipped-no-file");
      return;
    }

    console.log("[CreatorMind] screenshotUpload:start", file.name);
    setScreenshotMessage("Extracting candidate metrics from screenshot...");

    try {
      const extracted = await extractScreenshotMetrics(file);
      console.log("[CreatorMind] screenshotUpload:parsed", extracted);
      setScreenshotMessage(extracted.messages.join(" "));
      setFormData((prev) => ({
        ...prev,
        views:
          extracted.candidate_metrics.views !== undefined
            ? String(Math.round(extracted.candidate_metrics.views))
            : prev.views,
        likes:
          extracted.candidate_metrics.likes !== undefined
            ? String(Math.round(extracted.candidate_metrics.likes))
            : prev.likes,
        comments:
          extracted.candidate_metrics.comments !== undefined
            ? String(Math.round(extracted.candidate_metrics.comments))
            : prev.comments,
        shares:
          extracted.candidate_metrics.shares !== undefined
            ? String(Math.round(extracted.candidate_metrics.shares))
            : prev.shares,
        retentionRate:
          extracted.candidate_metrics.retention_rate !== undefined
            ? String(extracted.candidate_metrics.retention_rate)
            : prev.retentionRate
      }));
    } catch (err) {
      console.error("[CreatorMind] screenshotUpload:error", err);
      setScreenshotMessage(
        err instanceof Error ? err.message : "Screenshot parsing failed."
      );
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    console.log("[CreatorMind] existingAudit:submit-start");
    setLoading(true);
    setError("");

    const payload = {
      url: formData.url,
      platform: formData.platform || undefined,
      caption: formData.caption || undefined,
      hashtags: [],
      views: toOptionalNumber(formData.views),
      likes: toOptionalNumber(formData.likes),
      comments: toOptionalNumber(formData.comments),
      shares: toOptionalNumber(formData.shares),
      average_watch_time: toOptionalNumber(formData.averageWatchTime),
      retention_rate: toOptionalNumber(formData.retentionRate),
      asset_filename: formData.assetFilename || undefined,
      asset_type: formData.assetFilename ? "placeholder" : undefined
    };
    console.log("[CreatorMind] existingAudit:payload", payload);

    try {
      const auditResult = await auditContent(payload);
      console.log("[CreatorMind] existingAudit:response", auditResult);

      saveStoredAnalysis({
        kind: "audit",
        input: {
          url: formData.url,
          platform: formData.platform || undefined,
          caption: formData.caption || undefined,
          hashtags: []
        },
        result: auditResult,
        createdAt: new Date().toISOString()
      });
      router.push("/analysis/result");
    } catch (err) {
      console.error("[CreatorMind] existingAudit:error", err);
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      console.log("[CreatorMind] existingAudit:loading-cleared");
      setLoading(false);
    }
  }

  return (
    <AppShell active="new-analysis">
      <div className="space-y-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="space-y-2">
            <span className="inline-flex rounded-full bg-[#b7eaff]/30 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-[#006780]">
              Instagram / TikTok Metrics Audit
            </span>
            <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
              Audit Instagram or TikTok Content
            </h1>
            <p className="max-w-2xl text-sm leading-7 text-[#464555]">
              Start with a public post URL, then add any real metrics or upload an
              analytics screenshot. CreatorMind stays explicit about what comes from the
              URL, what comes from you, and where confidence is limited.
            </p>
          </div>

          <Link
            href="/analysis/new"
            className="rounded-xl bg-white px-6 py-3 text-sm font-semibold text-[#464555] shadow-sm ring-1 ring-[#e2e7ff]"
          >
            Switch Flow
          </Link>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.6fr_0.8fr]">
          <div className="space-y-6">
            <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
              <form onSubmit={handleSubmit} className="space-y-10">
                <section>
                  <h2 className="mb-6 text-xl font-bold">Post Source</h2>
                  <div className="grid gap-6">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Post URL
                      </label>
                      <input
                        required
                        name="url"
                        value={formData.url}
                        onChange={handleChange}
                        placeholder="https://www.instagram.com/reel/... or https://www.tiktok.com/..."
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Platform Override
                      </label>
                      <select
                        name="platform"
                        value={formData.platform}
                        onChange={handleChange}
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm font-medium text-[#131b2e]"
                      >
                        <option value="">Detect from URL</option>
                        <option value="Instagram">Instagram</option>
                        <option value="TikTok">TikTok</option>
                      </select>
                    </div>
                  </div>
                </section>

                <section>
                  <h2 className="mb-6 text-xl font-bold">Current Metrics</h2>
                  <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Current Views
                      </label>
                      <input
                        name="views"
                        value={formData.views}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Likes
                      </label>
                      <input
                        name="likes"
                        value={formData.likes}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Comments
                      </label>
                      <input
                        name="comments"
                        value={formData.comments}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Shares
                      </label>
                      <input
                        name="shares"
                        value={formData.shares}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Average Watch Time
                      </label>
                      <input
                        name="averageWatchTime"
                        value={formData.averageWatchTime}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Retention Rate
                      </label>
                      <input
                        name="retentionRate"
                        value={formData.retentionRate}
                        onChange={handleChange}
                        placeholder="Optional"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                  </div>
                </section>

                <section>
                  <h2 className="mb-6 text-xl font-bold">Content Context</h2>
                  <div className="grid gap-6">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Caption Text
                      </label>
                      <textarea
                        name="caption"
                        value={formData.caption}
                        onChange={handleChange}
                        rows={5}
                        placeholder="Optional. Add the visible caption text if the URL alone does not expose enough detail."
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Analytics Screenshot
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleScreenshotUpload}
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                      <p className="mt-2 text-xs text-[#464555]">
                        OCR is best-effort only. Review all extracted values and correct them
                        manually if needed.
                      </p>
                      {screenshotMessage ? (
                        <p className="mt-2 text-xs text-[#392cc1]">{screenshotMessage}</p>
                      ) : null}
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                        Asset Reference
                      </label>
                      <input
                        name="assetFilename"
                        value={formData.assetFilename}
                        onChange={handleChange}
                        placeholder="Optional filename or note"
                        className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                      />
                    </div>
                  </div>
                </section>

                {error ? (
                  <div className="rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/50 p-4 text-sm text-[#93000a]">
                    {error}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-3 rounded-[1.5rem] bg-gradient-to-br from-[#392cc1] to-[#534ad9] px-6 py-5 text-lg font-bold text-white shadow-xl shadow-[#392cc1]/30 transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <span>{loading ? "Auditing Post..." : "Run Post Audit"}</span>
                </button>
              </form>
            </div>
          </div>

          <div className="space-y-6">
            <div className="sticky top-24 rounded-[2rem] border border-white/40 bg-[rgba(226,231,255,0.4)] p-8 backdrop-blur-sm">
              <h3 className="mb-8 text-lg font-extrabold uppercase tracking-tight">
                Audit Confidence Rules
              </h3>
              <div className="space-y-6 text-sm leading-7 text-[#464555]">
                <p>
                  CreatorMind will parse the URL for platform and content context where it
                  can, but it does not pretend to fetch hidden Instagram or TikTok analytics.
                </p>
                <p>
                  If you provide views, likes, comments, shares, watch time, or retention,
                  the diagnosis becomes more specific and more trustworthy.
                </p>
                <p>
                  Screenshot extraction can suggest visible metrics when OCR works, but the
                  fields remain editable so you can correct anything it gets wrong.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
