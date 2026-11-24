"use client";

export type DashboardPlatform = "Instagram" | "TikTok";

const platforms: DashboardPlatform[] = ["Instagram", "TikTok"];

/** Shared social-network switcher used by data-led dashboard pages. */
export function PlatformNavigator({
  value,
  onChange,
  className = "",
}: {
  value: DashboardPlatform;
  onChange: (platform: DashboardPlatform) => void;
  className?: string;
}) {
  return (
    <nav aria-label="Social platform" className={`flex border-b border-line ${className}`}>
      {platforms.map((platform) => {
        const active = value === platform;
        return (
          <button
            key={platform}
            type="button"
            aria-current={active ? "page" : undefined}
            onClick={() => onChange(platform)}
            className={`relative min-h-11 px-4 text-sm font-black transition-colors sm:px-5 ${
              active ? "text-primary" : "text-muted hover:text-ink"
            }`}
          >
            {platform}
            {active ? (
              <span aria-hidden className="absolute inset-x-4 bottom-0 h-0.5 rounded-full bg-primary sm:inset-x-5" />
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
