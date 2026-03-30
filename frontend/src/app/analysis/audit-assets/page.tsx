import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";

export default function AuditAssetsPage() {
  return (
    <AppShell active="new-analysis">
      <div className="space-y-8">
        <div className="space-y-2">
          <span className="inline-flex rounded-full bg-[#eaddff] px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-[#5c00ca]">
            Content Asset Audit
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
            Audit the Content Asset
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-[#464555]">
            Provide the asset context now, then expand into deeper media-aware review as
            backend support grows.
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
                  Asset Reference
                </label>
                <input
                  placeholder="Filename or draft reference"
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Draft Caption
                </label>
                <textarea
                  rows={5}
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                  placeholder="Add the draft caption you want reviewed."
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  Hashtags
                </label>
                <input
                  placeholder="#ai #creator #marketing"
                  className="w-full rounded-xl bg-[#f2f3ff] px-5 py-4 text-sm text-[#131b2e]"
                />
              </div>
              <div className="md:col-span-2 rounded-2xl border border-dashed border-[#c7c4d8] bg-[#f2f3ff] p-6 text-sm text-[#464555]">
                Image and video upload analysis is coming soon. This page is structurally
                ready for that workflow, but no deep media inference is connected yet.
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <EmptyStateCard
              eyebrow="Coming Soon"
              title="Deep image and video review is not connected yet."
              description="Caption and hashtag-aware asset audit is structurally ready, but media-specific AI analysis still needs backend support."
            />
            <EmptyStateCard
              eyebrow="Current Scope"
              title="Use this page to prepare asset context."
              description="Today this route works as a clean scaffold for future upload-driven audits without pretending media analysis already exists."
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
