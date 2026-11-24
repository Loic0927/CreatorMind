"use client";

import { useEffect, useState } from "react";
import { Session, connectInstagram, saveSession, storedSession } from "@/lib/postbridge";
import { AnalyzeTab } from "@/components/dashboard/AnalyzeTab";
import { CreateTab } from "@/components/dashboard/CreateTab";
import { HomeTab } from "@/components/dashboard/HomeTab";
import { InsightsTab } from "@/components/dashboard/InsightsTab";
import { LoginScreen } from "@/components/dashboard/LoginScreen";
import { SettingsTab } from "@/components/dashboard/SettingsTab";
import { Brand } from "@/components/dashboard/ui";

type Tab = "home" | "create" | "analyze" | "insights" | "settings";
const tabs: Array<{ key: Tab; label: string; icon: string }> = [
  { key: "home", label: "Home", icon: "⌂" },
  { key: "create", label: "Create", icon: "+" },
  { key: "analyze", label: "Analyze", icon: "◎" },
  { key: "insights", label: "Insights", icon: "↗" },
  { key: "settings", label: "Settings", icon: "⚙" },
];

const isTab = (value: string | null): value is Tab => tabs.some((item) => item.key === value);

export function dashboardLocation(): { tab: Tab; analyzeId: string } {
  const params = new URLSearchParams(window.location.search);
  const requestedTab = params.get("tab");
  const tab = isTab(requestedTab) ? requestedTab : "home";
  return { tab, analyzeId: tab === "analyze" ? (params.get("post") ?? "") : "" };
}

export default function DashboardPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<Tab>("home");
  const [analyzeId, setAnalyzeId] = useState("");

  useEffect(() => {
    setSession(storedSession());
    const syncLocation = () => {
      const location = dashboardLocation();
      setTab(location.tab);
      setAnalyzeId(location.analyzeId);
    };
    syncLocation();
    window.addEventListener("popstate", syncLocation);
    setReady(true);
    return () => window.removeEventListener("popstate", syncLocation);
  }, []);

  const updateSession = (value: Session | null) => {
    saveSession(value);
    setSession(value);
  };

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas-gradient bg-fixed text-primary-hover">
        Loading PostBridge…
      </div>
    );
  }
  if (!session) return <LoginScreen onLogin={updateSession} />;

  const connect = async () => {
    window.location.href = (await connectInstagram(session)).authorization_url;
  };

  const navigate = (nextTab: Tab, nextAnalyzeId = "") => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", nextTab);
    if (nextTab === "analyze" && nextAnalyzeId) url.searchParams.set("post", nextAnalyzeId);
    else url.searchParams.delete("post");
    window.history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
    setTab(nextTab);
    setAnalyzeId(nextTab === "analyze" ? nextAnalyzeId : "");
  };

  return (
    <div className="min-h-screen bg-canvas-gradient bg-fixed text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-sidebar p-5 lg:flex lg:flex-col">
        <Brand />
        <nav className="-mx-5 mt-10 bg-sidebar">
          {tabs.map((item) => (
            <button
              key={item.key}
              onClick={() => navigate(item.key)}
              className={`flex w-full items-center gap-3 px-9 py-3 text-sm font-bold ${tab === item.key ? "bg-selected text-selected-ink" : "text-muted hover:bg-subtle"}`}
            >
              <span className="w-5 text-center text-lg">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <p className="mt-auto break-all rounded-2xl bg-selected p-4 text-sm font-bold leading-5 text-muted">
          {session.user.email}
        </p>
      </aside>
      <header className="sticky top-0 z-20 flex h-16 items-center border-b border-line bg-canvas px-5 lg:hidden">
        <Brand compact />
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-28 pt-5 lg:ml-64 lg:px-9 lg:pb-12 lg:pt-7">
        {tab === "home" && <HomeTab session={session} onConnect={connect} />}
        {tab === "create" && <CreateTab session={session} />}
        {tab === "analyze" && (
          <AnalyzeTab
            session={session}
            initialId={analyzeId}
            onOpen={(id) => navigate("analyze", id)}
            onClear={() => navigate("analyze")}
          />
        )}
        {tab === "insights" && <InsightsTab session={session} onOpen={(id) => navigate("analyze", id)} />}
        {tab === "settings" && <SettingsTab session={session} onLogout={() => updateSession(null)} />}
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-sidebar lg:hidden">
        {tabs.map((item) => (
          <button
            key={item.key}
            onClick={() => navigate(item.key)}
            className={`flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-bold ${tab === item.key ? "text-primary" : "text-muted"}`}
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
