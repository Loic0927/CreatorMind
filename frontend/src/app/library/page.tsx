import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";

export default function LibraryPage() {
  return (
    <AppShell active="library">
      <div className="grid gap-8 xl:grid-cols-[1.4fr_0.8fr]">
        <div className="space-y-8">
          <div className="flex items-end justify-between">
            <div>
              <p className="mb-1 text-sm font-semibold uppercase tracking-[0.2em] text-[#006780]">
                Archive
              </p>
              <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
                Content Library
              </h1>
            </div>
          </div>

          <EmptyStateCard
            eyebrow="Archive"
            title="No real content archive connected yet."
            description="Library data will appear once a backend history source is available for saved analyses, statuses, and content records."
          />
        </div>

        <aside className="space-y-6">
          <EmptyStateCard
            eyebrow="Trend Alert"
            title="Trend data is not connected yet."
            description="Trend widgets remain unavailable until a real backend source for audience or market trend signals is added."
          />

          <EmptyStateCard
            eyebrow="Quick Stats"
            title="Library statistics are unavailable."
            description="Archive-level counts and optimization summaries will be shown here once saved analysis history is implemented."
          />
        </aside>
      </div>
    </AppShell>
  );
}
