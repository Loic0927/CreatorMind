"use client";

import { useState } from "react";
import Link from "next/link";
import { Session, requestCode, verifyCode } from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { Brand, ErrorBanner } from "@/components/dashboard/ui";

const inputClass = "w-full rounded-2xl bg-field px-4 py-4 text-ink outline-none focus:ring-2 focus:ring-primary/30";

export function LoginScreen({ onLogin }: { onLogin: (value: Session) => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (sent) {
        onLogin(await verifyCode(email, code));
        return;
      }
      const result = await requestCode(email);
      setSent(true);
      if (result.development_code) setCode(result.development_code);
    } catch (reason) {
      setError(errorMessage(reason, "Sign in failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen bg-ink p-5 md:grid-cols-2">
      <section className="hidden flex-col justify-between rounded-[2rem] bg-gradient-to-br from-primary to-primary-hover p-12 text-white md:flex">
        <Brand />
        <div>
          <p className="text-sm font-bold uppercase tracking-[.25em] text-white/85">One account. Every screen.</p>
          <h1 className="mt-5 max-w-lg text-5xl font-black leading-tight">Bridge every post to better results.</h1>
          <p className="mt-5 max-w-md text-white">
            Your Instagram connections, AI analyses and tracking history stay in sync across web and mobile.
          </p>
        </div>
        <span className="text-sm text-white/85">PostBridge</span>
      </section>
      <section className="grid place-items-center p-4">
        <div className="w-full max-w-md">
          <div className="mb-8 md:hidden">
            <Brand />
          </div>
          <p className="text-sm font-bold uppercase tracking-[.2em] text-white/85">Welcome</p>
          <h2 className="mt-3 text-4xl font-black text-white">Sign in to PostBridge</h2>
          <p className="mt-3 text-sm leading-6 text-white/85">
            We’ll email you a secure six-digit code. No password required.
          </p>
          <ErrorBanner message={error} />
          <div className="mt-8 space-y-4">
            <input
              className={inputClass}
              type="email"
              value={email}
              disabled={sent}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
            {sent && (
              <input
                className={inputClass}
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="6-digit code"
              />
            )}
            <button
              disabled={busy || !email || (sent && code.length !== 6)}
              onClick={() => void submit()}
              className="w-full rounded-2xl bg-primary py-4 font-black text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {busy ? "Please wait…" : sent ? "Verify and sign in" : "Email me a code"}
            </button>
          </div>
          <p className="mt-6 text-center text-sm text-white/85">
            <Link href="/privacy" className="underline underline-offset-2 hover:text-white">
              Privacy
            </Link>
            <span aria-hidden="true"> · </span>
            <Link href="/terms" className="underline underline-offset-2 hover:text-white">
              Terms
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
