"use client";

import { useEffect, useState } from "react";
import AnalysisResults from "@/components/AnalysisResults";
import type { AuditContentResponse, PredictionRequest, PredictionResponse } from "@/lib/api";
import { getStoredAnalysis } from "@/lib/analysis-session";

export default function AnalysisResultPage() {
  const [input, setInput] = useState<PredictionRequest | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [auditInput, setAuditInput] = useState<{
    url: string;
    platform?: string;
    caption?: string;
    hashtags: string[];
  } | null>(null);
  const [auditResult, setAuditResult] = useState<AuditContentResponse | null>(null);

  useEffect(() => {
    const stored = getStoredAnalysis();
    if (!stored) {
      return;
    }

    if (stored.kind === "audit") {
      setAuditInput(stored.input);
      setAuditResult(stored.result);
      return;
    }

    setInput(stored.input);
    setResult(stored.result);
  }, []);

  return (
    <AnalysisResults
      input={input}
      result={result}
      auditInput={auditInput}
      auditResult={auditResult}
    />
  );
}
