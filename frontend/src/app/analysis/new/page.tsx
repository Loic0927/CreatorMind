import Link from "next/link";
import AppShell from "@/components/stitch/AppShell";

export default function NewAnalysisSelectorPage() {
  return (
    <AppShell active="new-analysis">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="space-y-2">
          <span className="inline-flex rounded-full bg-[#b7eaff]/30 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-[#006780]">
            New Analysis
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
            Choose Your Analysis Flow
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-[#464555]">
            Start with the analysis flow that matches where your content is in the
            creation process.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
            <p className="text-xs font-black uppercase tracking-[0.2em] text-[#392cc1]">
              YouTube URL Audit
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[#131b2e]">
              Audit a YouTube video through the official connector path
            </h2>
            <p className="mt-4 text-sm leading-7 text-[#464555]">
              Paste a YouTube URL, extract the video ID, and prepare for official
              analytics-backed auditing when YouTube is connected.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-[#464555]">
              <li>Video ID extraction is functional now</li>
              <li>Official YouTube auth path is scaffolded</li>
              <li>No fake YouTube analytics are generated</li>
            </ul>
            <Link
              href="/analysis/youtube"
              className="mt-8 inline-flex rounded-[1.25rem] bg-[#392cc1] px-6 py-3 text-sm font-bold text-white shadow-lg shadow-[#392cc1]/20"
            >
              Open YouTube Audit
            </Link>
          </div>

          <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
            <p className="text-xs font-black uppercase tracking-[0.2em] text-[#006780]">
              Instagram / TikTok Metrics Audit
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[#131b2e]">
              Audit a post with manual metrics plus screenshot help
            </h2>
            <p className="mt-4 text-sm leading-7 text-[#464555]">
              Paste the post URL, add any known metrics, and upload analytics screenshots
              to extract candidate numbers for review.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-[#464555]">
              <li>Manual metrics stay editable</li>
              <li>Screenshot parsing suggests candidate values when possible</li>
              <li>No unsupported automatic Instagram or TikTok analytics access</li>
            </ul>
            <Link
              href="/analysis/existing"
              className="mt-8 inline-flex rounded-[1.25rem] bg-[#b7eaff] px-6 py-3 text-sm font-bold text-[#001f28]"
            >
              Open Metrics Audit
            </Link>
          </div>

          <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
            <p className="text-xs font-black uppercase tracking-[0.2em] text-[#7531e6]">
              Content Asset Audit
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[#131b2e]">
              Audit the actual content asset
            </h2>
            <p className="mt-4 text-sm leading-7 text-[#464555]">
              Prepare image, video, caption, and hashtag inputs for deeper content-specific
              review. Where media AI is not connected yet, the UI stays explicit about it.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-[#464555]">
              <li>Asset upload structure is ready</li>
              <li>Caption and hashtag audit can still be captured</li>
              <li>Unsupported media analysis is clearly marked as coming soon</li>
            </ul>
            <Link
              href="/analysis/audit-assets"
              className="mt-8 inline-flex rounded-[1.25rem] bg-[#e3dfff] px-6 py-3 text-sm font-bold text-[#100069]"
            >
              Open Asset Audit
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
