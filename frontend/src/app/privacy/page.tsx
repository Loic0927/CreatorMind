import Link from "next/link";

const sections = [
  ["Data we collect", "TODO: legal text — describe account, connected-platform, post, and performance data."],
  [
    "Instagram data use",
    "TODO: legal text — explain how Instagram Login data is used to provide connection, publishing, tracking, and analysis features.",
  ],
  [
    "AI processing",
    "TODO: legal text — explain optional Google Gemini processing of post media, captions, comment text, and performance facts.",
  ],
  ["Hosting", "TODO: legal text — explain Oracle Cloud hosting and applicable service providers."],
  ["Retention and deletion", "TODO: legal text — explain account deletion and Meta data-deletion callback handling."],
  ["Contact", "TODO: legal text — provide the privacy contact method."],
] as const;

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-canvas-gradient bg-fixed px-5 py-12 text-ink sm:px-8">
      <article className="mx-auto max-w-3xl rounded-3xl border border-line bg-surface p-6 shadow-soft sm:p-10">
        <Link href="/" className="text-sm font-bold text-primary-hover hover:underline">
          PostBridge
        </Link>
        <h1 className="mt-5 text-4xl font-black">Privacy Policy</h1>
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
