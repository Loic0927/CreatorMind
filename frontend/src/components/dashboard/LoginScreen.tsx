"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthIntent, Session, requestCode, verifyCode } from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { ErrorBanner } from "@/components/dashboard/ui";

const inputClass =
  "mt-2 w-full rounded-2xl border border-line bg-[#eaf2ff] px-5 py-4 text-base text-ink outline-none placeholder:text-muted/65 focus:border-primary focus:ring-4 focus:ring-primary/10 disabled:opacity-65";

export function LoginScreen({ onLogin }: { onLogin: (value: Session) => void }) {
  const [intent, setIntent] = useState<AuthIntent>("sign_in");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registrationOpen, setRegistrationOpen] = useState(false);

  const changeIntent = (next: AuthIntent) => {
    setIntent(next);
    setSent(false);
    setCode("");
    setError("");
    setRegistrationOpen(false);
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (sent && intent === "sign_up") {
      setRegistrationOpen(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (sent) {
        onLogin(await verifyCode(email.trim(), code.trim(), { intent: "sign_in" }));
        return;
      }
      const result = await requestCode(email.trim(), intent);
      setSent(true);
      if (result.development_code) setCode(result.development_code);
    } catch (reason) {
      setError(errorMessage(reason, intent === "sign_up" ? "Could not create your account." : "Sign in failed."));
    } finally {
      setBusy(false);
    }
  };

  const completeRegistration = async () => {
    setBusy(true);
    setError("");
    try {
      onLogin(
        await verifyCode(email.trim(), code.trim(), {
          intent: "sign_up",
          privacyTermsAccepted: true,
          aiProcessingConsent: true,
        }),
      );
    } catch (reason) {
      setError(errorMessage(reason, "Could not create your account."));
      setRegistrationOpen(false);
    } finally {
      setBusy(false);
    }
  };

  const title = intent === "sign_up" ? "Create account" : "Sign in";

  return (
    <main className="min-h-screen overflow-y-auto bg-canvas-gradient px-5 py-8 sm:px-8 sm:py-12">
      <div className="mx-auto flex min-h-[calc(100vh-6rem)] max-w-2xl items-center justify-center py-8">
        <section className="w-full rounded-[1.75rem] border border-white/80 bg-white/95 px-6 py-8 shadow-float sm:px-12 sm:py-10">
          <Image
            src="/loginpage.png"
            width={220}
            height={220}
            priority
            alt="PostBridge fox holding a glowing idea bulb"
            className="mx-auto h-40 w-40 object-contain sm:h-48 sm:w-48"
          />
          <h1 className="mt-1 text-center text-4xl font-black tracking-tight text-ink sm:text-5xl">{title}</h1>

          <div className="my-7 flex items-center gap-4 text-sm font-bold text-muted">
            <span className="h-px flex-1 bg-line" />
            secure email verification
            <span className="h-px flex-1 bg-line" />
          </div>

          <ErrorBanner message={error} />
          <form className="mt-5 space-y-5" onSubmit={(event) => void submit(event)}>
            <label className="block text-sm font-bold text-ink">
              Email
              <input
                className={inputClass}
                type="email"
                value={email}
                disabled={sent || busy}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@company.com"
                autoComplete="email"
                required
              />
            </label>
            {sent ? (
              <label className="block text-sm font-bold text-ink">
                Verification code
                <input
                  className={inputClass}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  disabled={busy}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                  placeholder="6-digit code"
                  required
                />
              </label>
            ) : null}
            <button
              type="submit"
              disabled={busy || !email.trim() || (sent && code.length !== 6)}
              className="min-h-14 w-full rounded-2xl bg-gradient-to-r from-[#4f8cff] to-[#7553ff] px-5 py-4 text-base font-black text-white shadow-[0_12px_30px_rgba(86,105,255,0.25)] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy
                ? "Please wait…"
                : sent
                  ? intent === "sign_up"
                    ? "Review and create account"
                    : "Verify and sign in"
                  : "Email me a code"}
            </button>
          </form>

          {sent ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setSent(false);
                setCode("");
                setError("");
              }}
              className="mt-5 text-sm font-bold text-primary hover:text-primary-hover disabled:opacity-50"
            >
              Use a different email
            </button>
          ) : null}

          <p className="mt-8 text-center text-sm text-muted">
            {intent === "sign_up" ? "Already have an account?" : "Don’t have an account?"}{" "}
            <button
              type="button"
              onClick={() => changeIntent(intent === "sign_up" ? "sign_in" : "sign_up")}
              className="font-bold text-primary hover:text-primary-hover"
            >
              {intent === "sign_up" ? "Sign in" : "Create account"}
            </button>
          </p>
        </section>
      </div>

      {registrationOpen ? (
        <RegistrationConsentDialog
          busy={busy}
          error={error}
          onCancel={() => setRegistrationOpen(false)}
          onConfirm={completeRegistration}
        />
      ) : null}
    </main>
  );
}

function RegistrationConsentDialog({
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  busy: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}) {
  const [legalAccepted, setLegalAccepted] = useState(false);
  const [aiAccepted, setAiAccepted] = useState(false);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-ink/55 p-4 sm:p-6"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="registration-consent-title"
        className="my-auto max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-[1.75rem] bg-surface p-6 shadow-float sm:p-8"
      >
        <p className="text-xs font-black uppercase tracking-[.15em] text-primary-hover">
          Before we create your account
        </p>
        <h2 id="registration-consent-title" className="mt-2 text-2xl font-black text-ink sm:text-3xl">
          Privacy, Terms & AI processing
        </h2>
        <p className="mt-3 text-sm leading-6 text-ink-soft">
          Please review these notices on this page. Your account is not created until you confirm both choices below.
        </p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <article className="rounded-2xl bg-subtle p-4">
            <h3 className="font-black text-ink">Privacy</h3>
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              PostBridge stores your account details and the Instagram data you choose to connect so it can provide
              publishing, tracking, and analysis features. You can request account deletion from Settings.
            </p>
            <Link
              href="/privacy"
              target="_blank"
              className="mt-3 inline-block text-sm font-bold text-primary underline"
            >
              Read the full Privacy Policy
            </Link>
          </article>
          <article className="rounded-2xl bg-subtle p-4">
            <h3 className="font-black text-ink">Terms</h3>
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              Use PostBridge lawfully, keep your account access secure, and review AI-generated content before using or
              publishing it. Connected services remain subject to their own terms.
            </p>
            <Link href="/terms" target="_blank" className="mt-3 inline-block text-sm font-bold text-primary underline">
              Read the full Terms
            </Link>
          </article>
        </div>

        <article className="mt-4 rounded-2xl border border-line bg-[#f7f9ff] p-4">
          <h3 className="font-black text-ink">AI processing</h3>
          <p className="mt-2 text-sm leading-6 text-ink-soft">
            To create captions, summaries, comment summaries, and suggestions, PostBridge may send relevant post media,
            captions, audience comment text, and performance facts to Google Gemini. Do not submit data you are not
            allowed to share.
          </p>
        </article>

        <div className="mt-5 space-y-3">
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-4 text-sm font-bold text-ink">
            <input
              type="checkbox"
              checked={legalAccepted}
              onChange={(event) => setLegalAccepted(event.target.checked)}
              className="mt-0.5 h-5 w-5 flex-none accent-primary"
            />
            <span>I have read and agree to the Privacy Policy and Terms.</span>
          </label>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-4 text-sm font-bold text-ink">
            <input
              type="checkbox"
              checked={aiAccepted}
              onChange={(event) => setAiAccepted(event.target.checked)}
              className="mt-0.5 h-5 w-5 flex-none accent-primary"
            />
            <span>I agree to the AI processing described above, including processing by Google Gemini.</span>
          </label>
        </div>

        {error ? (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        ) : null}
        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="min-h-12 rounded-xl border border-line px-5 text-sm font-bold text-ink-soft hover:bg-subtle disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !legalAccepted || !aiAccepted}
            onClick={() => void onConfirm()}
            className="min-h-12 rounded-xl bg-gradient-to-r from-[#4f8cff] to-[#7553ff] px-6 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Creating account…" : "Agree and create account"}
          </button>
        </div>
      </section>
    </div>
  );
}
