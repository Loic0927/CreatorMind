import type {
  AuditContentResponse,
  PredictionRequest,
  PredictionResponse
} from "@/lib/api";

const STORAGE_KEY = "creatormind-analysis-result";

export type StoredPredictionAnalysis = {
  kind: "prediction";
  input: PredictionRequest;
  result: PredictionResponse;
  createdAt: string;
};

export type StoredAuditAnalysis = {
  kind: "audit";
  input: {
    url: string;
    platform?: string;
    caption?: string;
    hashtags: string[];
  };
  result: AuditContentResponse;
  createdAt: string;
};

export type StoredAnalysis = StoredPredictionAnalysis | StoredAuditAnalysis;

export function saveStoredAnalysis(payload: StoredAnalysis) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function getStoredAnalysis(): StoredAnalysis | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as StoredAnalysis;
  } catch {
    return null;
  }
}
