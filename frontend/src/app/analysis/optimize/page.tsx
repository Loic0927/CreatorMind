import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";

export default function OptimizeAnalysisPage() {
  return (
    <AppShell active="new-analysis">
      <div className="space-y-8">
        <div className="space-y-2">
          <span className="inline-flex rounded-full bg-[#eaddff] px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-[#5c00ca]">
            Pre-Post Content Optimizer
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
            Improve Content Before Posting
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-[#464555]">
            Structure your draft and planning inputs here. This workflow is prepared for
            future AI planning support and stays honest about what is not connected yet.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
          <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Platform
                </label>
                <select className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm font-medium text-[#131b2e]">
                  <option>Instagram</option>
                  <option>TikTok</option>
                  <option>YouTube</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Content Goal
                </label>
                <select className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm font-medium text-[#131b2e]">
                  <option>Drive reach</option>
                  <option>Increase engagement</option>
                  <option>Grow authority</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Draft Caption
                </label>
                <textarea
                  rows={5}
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                  placeholder="Paste your working caption or draft message here."
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Audience
                </label>
                <input
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                  placeholder="e.g. startup founders"
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Keywords
                </label>
                <input
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                  placeholder="e.g. AI, creator growth"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Media Upload
                </label>
                <div className="rounded-2xl border border-dashed border-[#c7c4d8] bg-[#f2f3ff] p-6 text-sm text-[#464555]">
                  Upload workflows are not connected yet. This placeholder is here for
                  future image and video planning support.
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <EmptyStateCard
              eyebrow="Upcoming"
              title="Optimization suggestions are not connected yet."
              description="This page is prepared for future planning and advisory features. It does not currently generate real AI recommendations from the backend."
            />
            <EmptyStateCard
              eyebrow="Strategy"
              title="Use this page to prepare inputs only."
              description="You can outline goals, audience, and draft messaging here today, but the backend does not yet provide a dedicated optimizer endpoint."
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
