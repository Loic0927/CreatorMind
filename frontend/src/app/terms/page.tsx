import Link from "next/link";

const sections = [
  ["Service", "TODO: legal text — describe the PostBridge service and eligibility."],
  [
    "Connected platforms",
    "TODO: legal text — explain Instagram and other platform connections, permissions, and user responsibilities.",
  ],
  ["AI features", "TODO: legal text — explain optional Google Gemini processing and user controls."],
  [
    "Data and retention",
    "TODO: legal text — describe hosting on Oracle Cloud, retention, account deletion, and Meta data deletion.",
  ],
  ["Contact", "TODO: legal text — provide a support and legal contact method."],
] as const;

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-canvas-gradient bg-fixed px-5 py-12 text-ink sm:px-8">
      <article className="mx-auto max-w-3xl rounded-3xl border border-line bg-surface p-6 shadow-soft sm:p-10">
        <Link href="/" className="text-sm font-bold text-primary-hover hover:underline">
          PostBridge
        </Link>
        <h1 className="mt-5 text-4xl font-black">Terms of Service</h1>
        <p className="mt-3 text-ink-soft">This draft is a clearly marked placeholder until legal text is approved.</p>
        <div className="mt-9 space-y-7">
          {sections.map(([title, text]) => (
            <section key={title}>
              <h2 className="text-xl font-black">{title}</h2>
              <p className="mt-2 leading-7 text-ink-soft">{text}</p>
            </section>
          ))}
        </div>
      </article>
    </main>
  );
}
