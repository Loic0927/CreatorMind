import type { ReactNode } from "react";

export function PageTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h1 className={`text-2xl font-black leading-tight tracking-tight md:text-3xl ${className}`}>{children}</h1>;
}

/** Large rounded container used by Home, Create and Settings. */
export function Panel({ children }: { children: ReactNode }) {
  return <section className="rounded-3xl border border-line bg-surface p-5 shadow-soft md:p-6">{children}</section>;
}

/** Compact card used by Analyze and Insights. */
export function Card({
  children,
  compact = false,
  className = "",
}: {
  children: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border border-line bg-surface shadow-soft ${compact ? "p-4" : "p-5"} ${className}`}>
      {children}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return message ? <div className="mb-5 rounded-2xl bg-danger-bg p-4 text-sm text-danger">{message}</div> : null;
}

export function Metric({ label, value }: { label: string; value?: number | string | null }) {
  return (
    <div>
      <p className="text-[10px] font-black uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-1 font-black">{typeof value === "number" ? value.toLocaleString() : (value ?? "–")}</p>
    </div>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-3 ${compact ? "lg:hidden" : ""}`}>
      <img src="/brand/logo.png" alt="PostBridge logo" className="h-14 w-14 rounded-xl object-contain" />
      <div className="text-xl font-black">PostBridge</div>
    </div>
  );
}
