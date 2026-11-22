"use client";

import { useState } from "react";
import { Session, requestCode, verifyCode } from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { Brand, ErrorBanner } from "@/components/dashboard/ui";

const inputClass = "w-full rounded-2xl bg-white px-4 py-4 text-slate-900";

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
    <main className="grid min-h-screen bg-slate-900 p-5 md:grid-cols-2">
      <section className="hidden flex-col justify-between rounded-[2rem] bg-gradient-to-br from-sky-600 to-sky-700 p-12 text-white md:flex">
        <Brand />
        <div>
          <p className="text-sm font-bold uppercase tracking-[.25em] text-sky-200">One account. Every screen.</p>
          <h1 className="mt-5 max-w-lg text-5xl font-black leading-tight">Bridge every post to better results.</h1>
          <p className="mt-5 max-w-md text-sky-100">
            Your Instagram connections, AI analyses and tracking history stay in sync across web and mobile.
          </p>
        </div>
        <span className="text-sm text-sky-200">PostBridge</span>
      </section>
      <section className="grid place-items-center p-4">
        <div className="w-full max-w-md">
          <div className="mb-8 md:hidden">
            <Brand />
          </div>
          <p className="text-sm font-bold uppercase tracking-[.2em] text-sky-300">Welcome</p>
          <h2 className="mt-3 text-4xl font-black text-white">Sign in to PostBridge</h2>
          <p className="mt-3 text-sm leading-6 text-sky-200">
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
              className="w-full rounded-2xl bg-sky-600 py-4 font-black text-white disabled:opacity-50"
            >
              {busy ? "Please wait…" : sent ? "Verify and sign in" : "Email me a code"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
