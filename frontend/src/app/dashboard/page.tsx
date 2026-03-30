"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";
import MetricCard from "@/components/stitch/MetricCard";
import {
  type DashboardSummary,
  type PlatformStatus,
  type RecentAnalysis,
  fetchDashboardSummary,
  fetchPlatformStatus,
  fetchRecentAnalyses
} from "@/lib/api";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recentAnalyses, setRecentAnalyses] = useState<RecentAnalysis[]>([]);
  const [platformStatus, setPlatformStatus] = useState<PlatformStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError("");

      try {
        const [summaryData, recentData, platformData] = await Promise.all([
          fetchDashboardSummary(),
          fetchRecentAnalyses(),
          fetchPlatformStatus()
        ]);

        setSummary(summaryData);
        setRecentAnalyses(recentData);
        setPlatformStatus(platformData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  const hasSummaryData = Boolean(summary && summary.total_predictions > 0);

  return (
    <AppShell active="dashboard">
      <div className="space-y-10">
        <header className="space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
            CreatorMind AI Dashboard
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-[#464555]">
            This dashboard now reads only real backend-stored data. Unsupported analytics
            areas remain empty until a real source is connected.
          </p>
        </header>

        {error ? (
          <div className="rounded-[2rem] border border-[#ffdad6] bg-[#ffdad6]/50 p-6 text-sm text-[#93000a]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <EmptyStateCard
            eyebrow="Loading"
            title="Loading real dashboard data..."
            description="CreatorMind is fetching stored prediction history and platform connection status."
          />
        ) : hasSummaryData && summary ? (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Predictions Saved" value={String(summary.total_predictions)} />
            <MetricCard
              label="Avg Engagement"
              value={summary.average_engagement !== null ? `${summary.average_engagement}%` : "N/A"}
              tone="secondary"
            />
            <MetricCard
              label="Avg Viral Score"
              value={summary.average_viral_score !== null ? String(summary.average_viral_score) : "N/A"}
              tone="tertiary"
            />
            <MetricCard
              label="Connected Accounts"
              value={String(summary.connected_accounts)}
            />
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <EmptyStateCard
              eyebrow="Analytics"
              title="No live analytics source connected yet."
              description="Dashboard summary metrics will populate after real predictions are saved or social analytics sources are connected."
            />
            <EmptyStateCard
              eyebrow="Forecasting"
              title="No stored dashboard totals are available yet."
              description="Run a real prediction to start building dashboard history, or connect platform sources when they become available."
            />
          </div>
        )}

        <div className="grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            {recentAnalyses.length > 0 ? (
              <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
                <h2 className="text-2xl font-extrabold">Recent Analyses</h2>
                <div className="mt-6 space-y-4">
                  {recentAnalyses.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-2xl bg-[#f2f3ff] p-4"
                    >
                      <div>
                        <p className="text-sm font-bold">
                          {item.platform} · {item.content_type}
                        </p>
                        <p className="text-xs text-[#464555]">
                          {new Date(item.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="font-black text-[#392cc1]">{item.viral_score}</p>
                        <p className="text-xs text-[#464555]">
                          {Intl.NumberFormat().format(item.views)} views
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyStateCard
                eyebrow="Recent Analyses"
                title="Prediction history is not available yet."
                description="Recent analysis entries will appear here once you save real predictions through the current /predict flow."
              />
            )}

            <EmptyStateCard
              eyebrow="Performance Overview"
              title="Historical trend data is not available in this version."
              description="Long-term charts remain hidden because the backend does not yet provide aggregated time-series analytics."
            />
          </div>

          <div className="space-y-6">
            <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
              <h3 className="text-xl font-extrabold">Platform Status</h3>
              <div className="mt-6 space-y-4">
                {platformStatus.map((item) => (
                  <div key={item.platform} className="rounded-2xl bg-[#f2f3ff] p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold">{item.platform}</p>
                      <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-[#464555]">
                        {item.status === "connected" ? "Connected" : "Not connected"}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-6 text-[#464555]">
                      {item.capability_note}
                    </p>
                    <p className="mt-2 text-xs font-medium text-[#777587]">
                      {item.connected_account_name
                        ? `Account: ${item.connected_account_name}`
                        : "No synced data yet"}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
              <h3 className="text-xl font-extrabold">Storage Snapshot</h3>
              <div className="mt-6 space-y-3 text-sm text-[#464555]">
                <div className="flex justify-between">
                  <span>Saved predictions</span>
                  <span className="font-bold text-[#131b2e]">
                    {summary?.total_predictions ?? 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Synced posts</span>
                  <span className="font-bold text-[#131b2e]">{summary?.synced_posts ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Analytics snapshots</span>
                  <span className="font-bold text-[#131b2e]">
                    {summary?.analytics_snapshots ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
