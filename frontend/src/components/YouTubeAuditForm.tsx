"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  auditYouTubeUrl,
  disconnectYouTubeConnection,
  fetchYouTubeConnectionStatus,
  getYouTubeConnectUrl,
  type YouTubeAuditResponse,
  type YouTubeConnectionStatus,
} from "@/lib/api";
import { getOrCreateAppUserId } from "@/lib/app-user";
import AppShell from "@/components/stitch/AppShell";
import EmptyStateCard from "@/components/stitch/EmptyStateCard";

export default function YouTubeAuditForm() {
  const searchParams = useSearchParams();
  const resultSectionRef = useRef<HTMLDivElement | null>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<YouTubeAuditResponse | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<YouTubeConnectionStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [userId, setUserId] = useState("");

  useEffect(() => {
    let cancelled = false;
    const currentUserId = getOrCreateAppUserId();
    setUserId(currentUserId);

    async function loadStatus() {
      try {
        const status = await fetchYouTubeConnectionStatus(currentUserId);
        if (!cancelled) {
          setConnectionStatus(status);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load YouTube connection status");
        }
      } finally {
        if (!cancelled) {
          setStatusLoading(false);
        }
      }
    }

    loadStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const youtubeState = searchParams.get("youtube");
    const message = searchParams.get("message");
    const accountName = searchParams.get("account_name");

    if (youtubeState === "connected") {
      setConnecting(false);
      setError("");
      setConnectionStatus((current) => ({
        connected: true,
        account_name: accountName ?? current?.account_name ?? "YouTube Account",
        channel_id: current?.channel_id ?? null,
        token_scope: current?.token_scope ?? null,
        public_data_enabled: current?.public_data_enabled ?? false,
        oauth_configured: current?.oauth_configured ?? true,
        advanced_analytics_ready: current?.advanced_analytics_ready ?? false,
        message: accountName
          ? `Connected as ${accountName}.`
          : "YouTube connected successfully."
      }));
    }

    if (youtubeState === "error") {
      setConnecting(false);
      setError(message ? `YouTube connection failed: ${message}` : "YouTube connection failed.");
    }
  }, [searchParams]);

  useEffect(() => {
    if (!result) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      resultSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });

      window.setTimeout(() => {
        resultHeadingRef.current?.focus({ preventScroll: true });
      }, 450);
    });

    return () => {
      window.cancelAnimationFrame(frameId);
    };
  }, [result]);

  function handleConnectYouTube() {
    if (!connectionStatus?.oauth_configured) {
      setError("Google OAuth is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the backend first.");
      return;
    }

    if (!userId) {
      setError("CreatorMind could not create a local user session yet. Please refresh and try again.");
      return;
    }

    setConnecting(true);
    window.location.href = getYouTubeConnectUrl(userId);
  }

  async function handleDisconnectYouTube() {
    if (!userId) {
      setError("CreatorMind could not determine the current user session.");
      return;
    }

    setDisconnecting(true);
    setError("");
    try {
      const response = await disconnectYouTubeConnection(userId);
      setConnectionStatus((current) => ({
        connected: false,
        account_name: null,
        channel_id: null,
        token_scope: null,
        public_data_enabled: current?.public_data_enabled ?? false,
        oauth_configured: current?.oauth_configured ?? false,
        advanced_analytics_ready: false,
        message: response.message
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect YouTube.");
    } finally {
      setDisconnecting(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (!userId) {
        throw new Error("CreatorMind could not determine the current user session.");
      }
      const response = await auditYouTubeUrl(url, userId);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell active="new-analysis">
      <div className="space-y-8">
        <div className="space-y-2">
          <span className="inline-flex rounded-full bg-[#e3dfff] px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-[#392cc1]">
            YouTube URL Audit
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#131b2e]">
            Audit a YouTube Video
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-[#464555]">
            CreatorMind now uses the official YouTube Data API for public video metadata
            and public engagement counts. Private analytics still stay clearly marked as
            OAuth-only.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
          <div className="rounded-[2rem] bg-white p-5 shadow-sm ring-1 ring-[#e2e7ff] sm:p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="block min-w-0 flex-1 text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                  YouTube URL
                  <input
                    required
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="https://www.youtube.com/watch?v=..."
                    className="mt-2 w-full rounded-xl bg-[#f2f3ff] px-4 py-3 text-sm text-[#131b2e]"
                  />
                </label>

                <button
                  type="submit"
                  disabled={loading}
                  className="h-12 shrink-0 rounded-[1.25rem] bg-[#392cc1] px-5 text-sm font-bold text-white shadow-lg shadow-[#392cc1]/20 disabled:opacity-70 sm:min-w-[190px]"
                >
                  {loading ? "Checking YouTube..." : "Run YouTube Audit"}
                </button>
              </div>

              {error ? (
                <div className="rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/50 p-3 text-sm text-[#93000a]">
                  {error}
                </div>
              ) : null}
            </form>
          </div>

          <div className="space-y-6">
            <EmptyStateCard
              eyebrow="Official Path"
              title="Public YouTube data is available without scraping."
              description="CreatorMind uses the official YouTube Data API for title, description, publish date, thumbnail, and public statistics. Deeper retention analytics still require OAuth."
            />
            <div className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-[#e2e7ff]">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                YouTube Connection
              </p>
              <p className="mt-3 text-sm leading-7 text-[#464555]">
                {statusLoading
                  ? "Checking connection status..."
                  : connecting
                    ? "Redirecting to Google to connect your YouTube account..."
                  : connectionStatus?.message ?? "YouTube is not connected yet."}
              </p>
              <p className="mt-2 text-sm text-[#464555]">
                {connectionStatus?.connected
                  ? `Connected account: ${connectionStatus.account_name ?? "YouTube Account"}`
                  : "Connect your own YouTube account to prepare advanced analytics access."}
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleConnectYouTube}
                  disabled={connecting}
                  className="inline-flex rounded-[1.25rem] bg-[#131b2e] px-5 py-3 text-sm font-bold text-white disabled:opacity-70"
                >
                  {connecting ? "Connecting..." : connectionStatus?.connected ? "Reconnect YouTube" : "Connect YouTube"}
                </button>
                {connectionStatus?.connected ? (
                  <button
                    type="button"
                    onClick={handleDisconnectYouTube}
                    disabled={disconnecting}
                    className="inline-flex rounded-[1.25rem] bg-[#f2f3ff] px-5 py-3 text-sm font-bold text-[#131b2e] disabled:opacity-70"
                  >
                    {disconnecting ? "Disconnecting..." : "Disconnect"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {result ? (
          <div
            ref={resultSectionRef}
            className="grid gap-8 scroll-mt-24 lg:grid-cols-[1.2fr_0.8fr]"
          >
            <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
              <h2
                ref={resultHeadingRef}
                tabIndex={-1}
                className="text-2xl font-extrabold outline-none"
              >
                YouTube Audit Status
              </h2>

              {result.title ? (
                <p className="mt-4 text-lg font-semibold leading-8 text-[#131b2e]">
                  {result.title}
                </p>
              ) : null}

              {result.thumbnail_url ? (
                <div className="mt-6 overflow-hidden rounded-[1.5rem] bg-[#f2f3ff]">
                  <img
                    src={result.thumbnail_url}
                    alt={result.title ?? "YouTube thumbnail"}
                    className="h-56 w-full object-cover"
                  />
                </div>
              ) : null}

              <div className="mt-6 grid gap-4 md:grid-cols-3">
                <div className="rounded-[1.5rem] bg-[#f7f8ff] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">Views</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#131b2e]">
                    {result.real_metrics_summary.views?.toLocaleString() ?? "Unavailable"}
                  </p>
                </div>
                <div className="rounded-[1.5rem] bg-[#f7f8ff] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">Likes</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#131b2e]">
                    {result.real_metrics_summary.likes?.toLocaleString() ?? "Unavailable"}
                  </p>
                </div>
                <div className="rounded-[1.5rem] bg-[#f7f8ff] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">Comments</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#131b2e]">
                    {result.real_metrics_summary.comments?.toLocaleString() ?? "Unavailable"}
                  </p>
                </div>
              </div>

              {result.description ? (
                <div className="mt-6 rounded-[1.5rem] bg-[#f7f8ff] p-5 text-sm leading-7 text-[#464555]">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">
                    Public Description
                  </p>
                  <p className="mt-3 whitespace-pre-line">
                    {result.description.length > 500
                      ? `${result.description.slice(0, 500)}...`
                      : result.description}
                  </p>
                </div>
              ) : null}

              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <div className="rounded-[1.5rem] bg-[#f7fff7] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#2c6f35]">Strengths</p>
                  <ul className="mt-3 space-y-2 text-sm leading-7 text-[#464555]">
                    {result.strengths.length ? result.strengths.map((item) => (
                      <li key={item}>{item}</li>
                    )) : <li>No strong positive public signals were available yet.</li>}
                  </ul>
                </div>
                <div className="rounded-[1.5rem] bg-[#fff8f6] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#8a3a26]">Weaknesses</p>
                  <ul className="mt-3 space-y-2 text-sm leading-7 text-[#464555]">
                    {result.weaknesses.length ? result.weaknesses.map((item) => (
                      <li key={item}>{item}</li>
                    )) : <li>No public weaknesses were detected from the current inputs.</li>}
                  </ul>
                </div>
              </div>

              <div className="mt-6 rounded-[1.5rem] bg-[#f7f8ff] p-5">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#464555]">Diagnosis</p>
                <ul className="mt-3 space-y-2 text-sm leading-7 text-[#464555]">
                  {result.diagnosis.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 rounded-[1.5rem] bg-[#fffdf3] p-5">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#7a5a00]">Recommendations</p>
                <ul className="mt-3 space-y-2 text-sm leading-7 text-[#464555]">
                  {result.recommendations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="space-y-6">
              <EmptyStateCard
                eyebrow="Current Limits"
                title={result.connection_required ? "Connect YouTube for advanced analytics." : "Public data is connected."}
                description={result.advanced_analytics_message}
              />
              <Link
                href="/analysis/new"
                className="inline-flex rounded-[1.25rem] bg-[#e3dfff] px-6 py-3 text-sm font-bold text-[#100069]"
              >
                Back to Audit Modes
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
