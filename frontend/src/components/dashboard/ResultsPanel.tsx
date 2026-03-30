import { PredictionResponse } from "@/lib/api";
import KpiCard from "./KpiCard";
import RecommendationCard from "./RecommendationCard";

type ResultsPanelProps = {
  result: PredictionResponse | null;
  loading: boolean;
  error: string;
};

export default function ResultsPanel({
  result,
  loading,
  error
}: ResultsPanelProps) {
  function formatMetric(value: number, kind: "views" | "score" | "engagement") {
    if (kind === "views") {
      return Intl.NumberFormat().format(value);
    }

    if (kind === "engagement") {
      return `${value}%`;
    }

    return value;
  }

  if (loading) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-medium text-gray-700">Generating prediction...</p>
        <p className="mt-2 text-sm text-gray-500">
          The model is analyzing your content inputs and preparing creator insights.
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-red-900">Request failed</h2>
        <p className="mt-2 text-sm text-red-700">{error}</p>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="rounded-2xl border border-dashed border-gray-300 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">Results Panel</h2>
        <p className="mt-2 text-sm text-gray-500">
          Submit content details to view prediction metrics and practical recommendations.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
          Prediction Ready
        </p>
        <p className="mt-1 text-sm text-blue-900">
          The API returned a successful prediction and insight package.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard label="Predicted Views" value={formatMetric(result.views, "views")} />
        <KpiCard label="Viral Score" value={formatMetric(result.viral_score, "score")} />
        <KpiCard label="Engagement" value={formatMetric(result.engagement, "engagement")} />
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">AI Analysis</h2>
        <p className="mt-3 text-sm leading-7 text-gray-600">
          {result.insights.analysis}
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <RecommendationCard title="Strengths" items={result.insights.strengths} />
        <RecommendationCard title="Weaknesses" items={result.insights.weaknesses} />
        <RecommendationCard
          title="Recommendations"
          items={result.insights.recommendations}
        />
      </div>
    </section>
  );
}
