export const errorMessage = (reason: unknown, fallback: string) =>
  reason instanceof Error ? reason.message : fallback;

export const formatNumber = (value: number | null | undefined) =>
  value == null ? "–" : Number(value).toLocaleString();

export const formatRate = (value: number | null | undefined) => (value == null ? "–" : `${Number(value).toFixed(1)}%`);

export const formatMetric = (metric: string, value: number | null | undefined) =>
  metric === "engagement_rate" ? formatRate(value) : formatNumber(value);

export const metricLabel: Record<string, string> = {
  views: "Views",
  reach: "Reach",
  engagement_rate: "Engagement",
  shares: "Shares",
  saves: "Saves",
  comments: "Comments",
};
