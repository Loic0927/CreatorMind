"use client";

import Link from "next/link";
import type { AuditContentResponse, PredictionRequest, PredictionResponse } from "@/lib/api";
import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";
import InsightSectionCard from "@/components/stitch/InsightSectionCard";
import MetricCard from "@/components/stitch/MetricCard";

type AnalysisResultsProps = {
  input: PredictionRequest | null;
  result: PredictionResponse | null;
  auditInput?: {
    url: string;
    platform?: string;
    caption?: string;
    hashtags: string[];
  } | null;
  auditResult?: AuditContentResponse | null;
};

function formatViews(value: number) {
  return Intl.NumberFormat().format(value);
}

export default function AnalysisResults({
  input,
  result,
  auditInput,
  auditResult
}: AnalysisResultsProps) {
  if (auditResult) {
    return (
      <AppShell active="results">
        <div className="space-y-8">
          <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-bold text-[#392cc1]">
                <span className="rounded-full bg-[#e3dfff] px-3 py-1 uppercase tracking-[0.2em]">
                  Post Metrics Audit
                </span>
              </div>
              <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
                {auditResult.metrics_summary.platform} Content Audit
              </h1>
              <p className="mt-2 text-sm text-[#464555]">
                Audit built from the submitted URL plus any real metrics you provided.
              </p>
            </div>
            <Link
              href="/analysis/existing"
              className="rounded-xl bg-[#392cc1] px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-[#392cc1]/20"
            >
              Audit Another Post
            </Link>
          </div>

          <div className="grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-8">
              <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff] md:p-10">
                <div className="grid gap-4 md:grid-cols-2">
                  <MetricCard
                    label="Current Views"
                    value={
                      auditResult.metrics_summary.provided_metrics.views !== null
                        ? formatViews(auditResult.metrics_summary.provided_metrics.views)
                        : "Not provided"
                    }
                    tone="primary"
                  />
                  <MetricCard
                    label="Caption Length"
                    value={String(auditResult.metrics_summary.caption_length)}
                    tone="secondary"
                  />
                </div>

                <div className="mt-8 rounded-[1.5rem] bg-[#f2f3ff] p-6">
                  <p className="text-xs font-black uppercase tracking-[0.2em] text-[#392cc1]">
                    Metrics Summary
                  </p>
                  <div className="mt-4 space-y-3 text-sm text-[#131b2e]">
                    <p>
                      <span className="font-bold">URL:</span> {auditResult.metrics_summary.source_url}
                    </p>
                    <p>
                      <span className="font-bold">Content Type:</span> {auditResult.metrics_summary.content_type}
                    </p>
                    <p>
                      <span className="font-bold">Missing Inputs:</span>{" "}
                      {auditResult.metrics_summary.missing_metrics.length > 0
                        ? auditResult.metrics_summary.missing_metrics.join(", ")
                        : "None"}
                    </p>
                  </div>
                </div>
              </div>

              <InsightSectionCard
                title="What Is Working"
                items={auditResult.content_diagnosis.what_is_working}
                accentClass="text-[#006780]"
              />
              <InsightSectionCard
                title="What Is Underperforming"
                items={auditResult.content_diagnosis.underperforming}
                accentClass="text-[#ba1a1a]"
              />
            </div>

            <div className="space-y-8">
              <InsightSectionCard
                title="Likely Cause"
                items={auditResult.content_diagnosis.likely_cause}
                accentClass="text-[#7531e6]"
              />
              <InsightSectionCard
                title="Recommended Changes"
                items={auditResult.content_diagnosis.recommended_changes}
                accentClass="text-[#392cc1]"
              />

              {auditResult.content_diagnosis.confidence_notes.length > 0 ? (
                <InsightSectionCard
                  title="Confidence Notes"
                  items={auditResult.content_diagnosis.confidence_notes}
                  accentClass="text-[#464555]"
                />
              ) : null}

              {auditResult.prediction_signal ? (
                <div className="rounded-[2rem] border border-[#c7c4d8]/30 bg-[rgba(218,226,253,0.4)] p-8 backdrop-blur-xl">
                  <h2 className="text-xl font-extrabold text-[#131b2e]">Secondary Prediction Signal</h2>
                  <p className="mt-3 text-sm leading-7 text-[#464555]">
                    The predictive model is kept as a secondary signal, not the primary
                    audit conclusion.
                  </p>
                  <div className="mt-6 grid gap-4 md:grid-cols-3">
                    <MetricCard
                      label="Predicted Views"
                      value={formatViews(auditResult.prediction_signal.views)}
                      tone="primary"
                    />
                    <MetricCard
                      label="Predicted Viral Score"
                      value={String(auditResult.prediction_signal.viral_score)}
                      tone="secondary"
                    />
                    <MetricCard
                      label="Predicted Engagement"
                      value={`${auditResult.prediction_signal.engagement}%`}
                      tone="tertiary"
                    />
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!result) {
    return (
      <AppShell active="results">
        <div className="mx-auto max-w-4xl space-y-6">
          <div className="rounded-[2rem] bg-white p-10 shadow-sm ring-1 ring-[#e2e7ff]">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-[#006780]">
              Analysis Detail
            </p>
            <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-[#131b2e]">
              No analysis result available
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[#464555]">
              Run a new analysis first so CreatorMind can show the report and
              recommendations.
            </p>
            <Link
              href="/analysis/existing"
              className="mt-8 inline-flex rounded-2xl bg-[#392cc1] px-6 py-3 text-sm font-bold text-white"
            >
              Audit Existing Content
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell active="results">
      <div className="space-y-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-bold text-[#392cc1]">
              <span className="rounded-full bg-[#e3dfff] px-3 py-1 uppercase tracking-[0.2em]">
                Prediction Result
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
              {input?.platform ?? "CreatorMind"} Performance Analysis
            </h1>
            <p className="mt-2 text-sm text-[#464555]">
              Generated from the real `/predict` API response for the current content setup.
            </p>
          </div>
          <Link
            href="/analysis/existing"
            className="rounded-xl bg-[#392cc1] px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-[#392cc1]/20"
          >
            Audit Existing Content
          </Link>
        </div>

        <div className="grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-8">
            <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff] md:p-10">
              <div className="grid gap-4 md:grid-cols-3">
                <MetricCard label="Predicted Views" value={formatViews(result.views)} tone="primary" />
                <MetricCard label="Viral Score" value={String(result.viral_score)} tone="secondary" />
                <MetricCard label="Engagement" value={`${result.engagement}%`} tone="tertiary" />
              </div>

              <div className="mt-8 rounded-[1.5rem] bg-[#f2f3ff] p-6">
                <p className="text-xs font-black uppercase tracking-[0.2em] text-[#392cc1]">
                  Main Analysis
                </p>
                <p className="mt-3 text-sm leading-7 text-[#131b2e]">
                  {result.insights.analysis}
                </p>
              </div>
            </div>

            <EmptyStateCard
              eyebrow="Comparison"
              title="No comparable content history connected yet."
              description="Similar past content will appear here once saved analysis history and comparison data are available from a real backend source."
            />
          </div>

          <div className="space-y-8">
            <InsightSectionCard
              title="Strengths"
              items={result.insights.strengths}
              accentClass="text-[#006780]"
            />
            <InsightSectionCard
              title="Weaknesses"
              items={result.insights.weaknesses}
              accentClass="text-[#ba1a1a]"
            />
            <InsightSectionCard
              title="Recommendations"
              items={result.insights.recommendations}
              accentClass="text-[#392cc1]"
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
