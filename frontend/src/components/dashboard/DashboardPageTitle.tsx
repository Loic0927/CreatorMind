import type { ReactNode } from "react";

export function DashboardPageTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h1 className={`text-2xl font-black leading-tight tracking-tight md:text-3xl ${className}`}>{children}</h1>;
}
