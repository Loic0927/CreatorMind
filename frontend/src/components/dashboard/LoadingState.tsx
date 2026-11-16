"use client";

import { useEffect, useRef } from "react";

const loadingFrames = Array.from({ length: 10 }, (_, index) => index + 1);

type LoadingStateProps = {
  label: string;
  description?: string;
};

export function LoadingState({ label, description }: LoadingStateProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousOverscroll = document.body.style.overscrollBehavior;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const keepFocusInDialog = (event: KeyboardEvent) => {
      if (event.key === "Tab") event.preventDefault();
    };

    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "none";
    dialogRef.current?.focus({ preventScroll: true });
    window.addEventListener("keydown", keepFocusInDialog, true);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.body.style.overscrollBehavior = previousOverscroll;
      window.removeEventListener("keydown", keepFocusInDialog, true);
      previousFocus?.focus({ preventScroll: true });
    };
  }, []);

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={label}
      aria-live="polite"
      tabIndex={-1}
      className="fixed inset-0 z-[2000] grid place-items-center bg-[#c7cedd]/70 px-4 py-8 backdrop-blur-md focus:outline-none"
    >
      <div className="flex min-h-[320px] w-full max-w-xl flex-col items-center justify-center rounded-[2rem] border border-white/80 bg-[#f8faff]/95 px-6 py-10 text-center shadow-[0_28px_80px_rgba(30,22,51,.28)] sm:min-h-[390px] sm:px-12 sm:py-14">
        <div className="relative h-40 w-40 sm:h-48 sm:w-48" aria-hidden="true">
          {loadingFrames.map((frame) => (
            <img
              key={frame}
              src={`/loading/fps${frame}.png`}
              alt=""
              className="loading-frame absolute inset-0 h-full w-full object-contain"
              style={{ "--loading-frame": frame - 1 } as React.CSSProperties}
            />
          ))}
        </div>
        <h2 className="mt-5 text-xl font-black text-[#201633] sm:text-2xl">{label}</h2>
        <div className="mt-5 flex items-center justify-center gap-3" aria-hidden="true">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
        {description ? <p className="mt-5 max-w-sm text-sm leading-6 text-[#5f587a]">{description}</p> : null}
      </div>
    </div>
  );
}
