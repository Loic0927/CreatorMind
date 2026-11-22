"use client";

import Link from "next/link";

export function AiConsentDialog({
  open,
  busy = false,
  onAccept,
  onNotNow,
}: {
  open: boolean;
  busy?: boolean;
  onAccept: () => void | Promise<void>;
  onNotNow: () => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/50 p-5"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onNotNow();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-consent-title"
        className="w-full max-w-lg rounded-3xl bg-surface p-6 shadow-float sm:p-8"
      >
        <p className="text-xs font-black uppercase tracking-[.12em] text-primary-hover">Optional AI features</p>
        <h2 id="ai-consent-title" className="mt-2 text-2xl font-black text-ink">
          Review AI data use
        </h2>
        <p className="mt-4 text-sm leading-6 text-ink-soft">
          If you choose to use an AI feature, PostBridge sends the relevant data to the Google Gemini API to create a
          caption, summary, comment summary, or next-post suggestion.
        </p>
        <p className="mt-4 text-sm font-bold text-ink">This can include:</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-ink-soft">
          <li>post media and captions;</li>
          <li>audience comment text; and</li>
          <li>performance facts about your posts.</li>
        </ul>
        <p className="mt-4 text-sm leading-6 text-ink-soft">
          AI processing is optional. You can revoke consent at any time in Settings.
        </p>
        <p className="mt-3 text-sm text-ink-soft">
          <Link href="/privacy" className="font-bold text-primary-hover underline underline-offset-2">
            Privacy
          </Link>
          <span aria-hidden="true"> · </span>
          <Link href="/terms" className="font-bold text-primary-hover underline underline-offset-2">
            Terms
          </Link>
        </p>
        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={busy}
            onClick={onNotNow}
            className="min-h-11 rounded-xl border border-line px-5 text-sm font-bold text-ink-soft hover:bg-subtle disabled:opacity-50"
          >
            Not now
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onAccept()}
            className="min-h-11 rounded-xl bg-primary px-5 text-sm font-black text-white hover:bg-primary-hover disabled:opacity-50"
          >
            {busy ? "Saving…" : "Accept"}
          </button>
        </div>
      </section>
    </div>
  );
}
