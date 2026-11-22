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

export default function DashboardPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<Tab>("home");
  const [analyzeId, setAnalyzeId] = useState("");

  useEffect(() => {
    setSession(storedSession());
    setReady(true);
  }, []);

  const updateSession = (value: Session | null) => {
    saveSession(value);
    setSession(value);
  };

  if (!ready) {
    return <div className="grid min-h-screen place-items-center bg-slate-100 text-sky-700">Loading PostBridge…</div>;
  }
  if (!session) return <LoginScreen onLogin={updateSession} />;

  const connect = async () => {
    window.location.href = (await connectInstagram(session)).authorization_url;
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white p-5 lg:flex lg:flex-col">
        <Brand />
        <nav className="-mx-5 mt-10 bg-white">
          {tabs.map((item) => (
            <button
              key={item.key}
              onClick={() => setTab(item.key)}
              className={`flex w-full items-center gap-3 px-9 py-3 text-sm font-bold ${tab === item.key ? "bg-sky-100 text-sky-700" : "text-slate-500 hover:bg-slate-100"}`}
            >
              <span className="w-5 text-center text-lg">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <p className="mt-auto break-all rounded-2xl bg-sky-100 p-4 text-sm font-bold leading-5 text-slate-500">
          {session.user.email}
        </p>
      </aside>
      <header className="sticky top-0 z-20 flex h-16 items-center border-b border-slate-200 bg-slate-100 px-5 lg:hidden">
        <Brand compact />
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-28 pt-5 lg:ml-64 lg:px-9 lg:pb-12 lg:pt-7">
        {tab === "home" && <HomeTab session={session} onConnect={connect} />}
        {tab === "create" && <CreateTab session={session} />}
        {tab === "analyze" && <AnalyzeTab session={session} initialId={analyzeId} onClear={() => setAnalyzeId("")} />}
        {tab === "insights" && (
          <InsightsTab
            session={session}
            onOpen={(id) => {
              setAnalyzeId(id);
              setTab("analyze");
            }}
          />
        )}
        {tab === "settings" && <SettingsTab session={session} onLogout={() => updateSession(null)} />}
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white lg:hidden">
        {tabs.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={`flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-bold ${tab === item.key ? "text-sky-600" : "text-slate-500"}`}
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
