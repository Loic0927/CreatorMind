import Link from "next/link";
import type { ReactNode } from "react";

type NavKey = "dashboard" | "new-analysis" | "library" | "results";

type AppShellProps = {
  active: NavKey;
  children: ReactNode;
};

const navItems = [
  { key: "dashboard", label: "Dashboard", href: "/dashboard", icon: "D" },
  { key: "new-analysis", label: "New Analysis", href: "/analysis/new", icon: "N" },
  { key: "library", label: "Library", href: "/library", icon: "L" }
] as const;

export default function AppShell({ active, children }: AppShellProps) {
  return (
    <div className="flex min-h-screen bg-[#faf8ff] text-[#131b2e]">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-[#f2f3ff] px-4 py-6 lg:flex">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#392cc1] text-sm font-bold text-white shadow-lg shadow-[#392cc1]/20">
            AI
          </div>
          <div>
            <div className="text-xl font-bold">CreatorMind</div>
            <div className="text-[10px] font-medium uppercase tracking-[0.25em] text-[#464555]">
              The Digital Curator
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          {navItems.map((item) => {
            const isActive =
              item.key === active ||
              (active === "results" && item.key === "new-analysis");

            return (
              <Link
                key={item.key}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[#e3dfff] text-[#100069]"
                    : "text-[#464555] hover:bg-[#eaedff]"
                }`}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/60 text-xs font-bold">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}

          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-medium text-[#464555] hover:bg-[#eaedff]"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/60 text-xs font-bold">
              T
            </span>
            <span>Trends</span>
          </button>

          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-medium text-[#464555] hover:bg-[#eaedff]"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/60 text-xs font-bold">
              S
            </span>
            <span>Settings</span>
          </button>
        </nav>

        <div className="mt-auto space-y-3 pt-6">
          <div className="rounded-2xl bg-gradient-to-br from-[#392cc1] to-[#534ad9] p-4 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-80">
              Pro Plan
            </p>
            <p className="mt-1 text-sm font-semibold">Unlock advanced creator insights.</p>
            <button
              type="button"
              className="mt-3 w-full rounded-lg bg-white py-2 text-xs font-bold text-[#392cc1]"
            >
              Upgrade to Pro
            </button>
          </div>

          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl px-4 py-2 text-left text-sm font-medium text-[#464555] hover:bg-[#eaedff]"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/60 text-xs font-bold">
              ?
            </span>
            <span>Support</span>
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between bg-[#faf8ff]/80 px-6 backdrop-blur-md lg:px-8">
          <div className="w-full max-w-md">
            <div className="rounded-full bg-[#f2f3ff] px-4 py-2 text-sm text-[#777587]">
              Search analysis history...
            </div>
          </div>
          <div className="ml-4 flex items-center gap-4">
            <Link
              href="/analysis/new"
              className="rounded-full bg-[#f2f3ff] px-5 py-2 text-sm font-semibold text-[#392cc1]"
            >
              Create New
            </Link>
            <div className="hidden text-right sm:block">
              <p className="text-sm font-bold">Alex Rivera</p>
              <p className="text-[10px] font-medium text-[#464555]">Digital Strategist</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-[#dae2fd] bg-white text-sm font-bold">
              AR
            </div>
          </div>
        </header>

        <div className="p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}
