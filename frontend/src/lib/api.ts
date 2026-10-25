const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type PredictionRequest = {
  platform: string;
  contentType: string;
  captionLength: number;
  postingHour: number;
};

export type AnalyzeUrlRequest = {
  url: string;
};

export type AuditContentRequest = {
  url: string;
  platform?: string;
  caption?: string;
  views?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  average_watch_time?: number;
  retention_rate?: number;
  asset_filename?: string;
  asset_type?: string;
};

export type InsightResult = {
  analysis: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
};

export type PredictionResponse = {
  views: number;
  viral_score: number;
  engagement: number;
  insights: InsightResult;
};

export type DashboardSummary = {
  total_predictions: number;
  average_views: number | null;
  average_engagement: number | null;
  average_viral_score: number | null;
  connected_accounts: number;
  synced_posts: number;
  analytics_snapshots: number;
};

export type RecentAnalysis = {
  id: string;
  created_at: string;
  platform: string;
  content_type: string;
  views: number;
  viral_score: number;
  engagement: number;
};

export type PlatformStatus = {
  platform: string;
  status: string;
  supported_now: boolean;
  capability_note: string;
  connected_account_name: string | null;
  last_sync_at: string | null;
};

export type AuditMetricsSummary = {
  platform: string;
  content_type: string;
  source_url: string;
  provided_metrics: Record<string, number | null>;
  missing_metrics: string[];
  caption_length: number;
  hashtags: string[];
};

export type ContentDiagnosis = {
  what_is_working: string[];
  underperforming: string[];
  likely_cause: string[];
  recommended_changes: string[];
  confidence_notes: string[];
};

export type AuditContentResponse = {
  metrics_summary: AuditMetricsSummary;
  content_diagnosis: ContentDiagnosis;
  prediction_signal: PredictionResponse | null;
};

export type ScreenshotMetricsResponse = {
  candidate_metrics: Record<string, number>;
  confidence_level: string;
  messages: string[];
  raw_text: string;
  filename: string;
};

export type YouTubeAuditResponse = {
  connection_required: boolean;
  platform: string;
  video_id: string;
  title: string | null;
  description: string | null;
  published_at: string | null;
  thumbnail_url: string | null;
  channel_title: string | null;
  real_metrics_summary: Record<string, number | null>;
  missing_inputs: string[];
  confidence_level: string;
  diagnosis: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  connection_message: string;
  advanced_analytics_message: string;
  connected_account_name?: string | null;
};

export type YouTubeConnectionStatus = {
  connected: boolean;
  account_name: string | null;
  channel_id: string | null;
  token_scope: string | null;
  public_data_enabled: boolean;
  oauth_configured: boolean;
  advanced_analytics_ready: boolean;
  message: string;
};

export type DisconnectResponse = {
  disconnected: boolean;
  message: string;
};

async function handleJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    let message = fallbackMessage;
    try {
      const errorData = await response.json();
      if (errorData?.detail) {
        message = typeof errorData.detail === "string" ? errorData.detail : message;
      }
    } catch {
      // Keep fallback message when the server does not return JSON.
    }
    throw new Error(message);
  }

  return response.json();
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs = 20000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The request took too long to complete. Please try again.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function predictContent(
  payload: PredictionRequest
): Promise<PredictionResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch {
    throw new Error("Unable to reach the CreatorMind AI API. Check that the backend is running.");
  }

  return handleJsonResponse<PredictionResponse>(response, "Prediction request failed");
}

export async function analyzeContentUrl(
  payload: AnalyzeUrlRequest
): Promise<PredictionResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/analyze-url`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch {
    throw new Error("Unable to reach the CreatorMind AI API. Check that the backend is running.");
  }

  return handleJsonResponse<PredictionResponse>(response, "URL analysis request failed");
}

export async function auditContent(
  payload: AuditContentRequest
): Promise<AuditContentResponse> {
  let response: Response;

  console.log("[CreatorMind] auditContent:start", payload);

  try {
    console.log("[CreatorMind] auditContent:endpoint", `${API_BASE_URL}/audit-content`);
    response = await fetchWithTimeout(`${API_BASE_URL}/audit-content`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    console.log("[CreatorMind] auditContent:response-status", response.status);
  } catch (error) {
    console.error("[CreatorMind] auditContent:error", error);
    throw error instanceof Error
      ? error
      : new Error("Unable to reach the CreatorMind AI API. Check that the backend is running.");
  }

  const data = await handleJsonResponse<AuditContentResponse>(
    response,
    "Content audit request failed"
  );
  console.log("[CreatorMind] auditContent:response-data", data);
  return data;
}

export async function extractScreenshotMetrics(file: File): Promise<ScreenshotMetricsResponse> {
  const formData = new FormData();
  formData.append("file", file);

  console.log("[CreatorMind] extractScreenshotMetrics:start", {
    name: file.name,
    size: file.size,
    type: file.type
  });

  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/extract-screenshot-metrics`,
      {
        method: "POST",
        body: formData
      },
      15000
    );
    console.log("[CreatorMind] extractScreenshotMetrics:response-status", response.status);
    const data = await handleJsonResponse<ScreenshotMetricsResponse>(
      response,
      "Screenshot metric extraction failed"
    );
    console.log("[CreatorMind] extractScreenshotMetrics:response-data", data);
    return data;
  } catch (error) {
    console.error("[CreatorMind] extractScreenshotMetrics:error", error);
    throw error;
  }
}

export async function auditYouTubeUrl(url: string, userId: string): Promise<YouTubeAuditResponse> {
  let response: Response;

  try {
    response = await fetchWithTimeout(`${API_BASE_URL}/audit-youtube`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ url, user_id: userId, hashtags: [] })
    });
  } catch {
    throw new Error("Unable to reach the CreatorMind AI API. Check that the backend is running.");
  }

  return handleJsonResponse<YouTubeAuditResponse>(response, "YouTube audit request failed");
}

export function getYouTubeConnectUrl(userId: string): string {
  return `${API_BASE_URL}/auth/youtube/start?user_id=${encodeURIComponent(userId)}`;
}

export async function fetchYouTubeConnectionStatus(userId: string): Promise<YouTubeConnectionStatus> {
  const response = await fetch(`${API_BASE_URL}/auth/youtube/status?user_id=${encodeURIComponent(userId)}`, {
    cache: "no-store"
  });

  return handleJsonResponse<YouTubeConnectionStatus>(
    response,
    "Failed to load YouTube connection status"
  );
}

export async function disconnectYouTubeConnection(userId: string): Promise<DisconnectResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/youtube/disconnect?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });

  return handleJsonResponse<DisconnectResponse>(response, "Failed to disconnect YouTube");
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const response = await fetch(`${API_BASE_URL}/dashboard/summary`, {
    cache: "no-store"
  });

  return handleJsonResponse<DashboardSummary>(response, "Failed to load dashboard summary");
}

export async function fetchRecentAnalyses(): Promise<RecentAnalysis[]> {
  const response = await fetch(`${API_BASE_URL}/dashboard/recent-analyses`, {
    cache: "no-store"
  });

  return handleJsonResponse<RecentAnalysis[]>(response, "Failed to load recent analyses");
}

export async function fetchPlatformStatus(): Promise<PlatformStatus[]> {
  const response = await fetch(`${API_BASE_URL}/dashboard/platform-status`, {
    cache: "no-store"
  });

  return handleJsonResponse<PlatformStatus[]>(response, "Failed to load platform status");
}
