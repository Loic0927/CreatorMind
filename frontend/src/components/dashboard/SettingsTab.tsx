"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AccountContext,
  Connection,
  Session,
  deleteAccount,
  disconnectInstagram,
  getAccountContext,
  getConnection,
  logout,
  updateAccountContext,
} from "@/lib/postbridge";
import { errorMessage } from "@/lib/format";
import { ErrorBanner, PageTitle, Panel } from "@/components/dashboard/ui";
import { UnifiedSelect } from "@/components/ui/UnifiedSelect";

const emptyContext: AccountContext = {
  account_theme: "",
  about_this_account: "",
  target_audience: "",
  tone_keys: [],
  tone_other: "",
  content_formats: [],
  caption_language: "auto",
  primary_category: "",
  primary_category_other: "",
  audience_age_ranges: [],
  preferred_hashtags: [],
};
const asOptions = (items: ReadonlyArray<readonly [string, string]>) =>
  items.map(([value, label]) => ({ value, label }));
const toneOptions = asOptions([
  ["warm", "Warm"],
  ["direct", "Direct"],
  ["playful", "Playful"],
  ["educational", "Educational"],
  ["professional", "Professional"],
  ["conversational", "Conversational"],
  ["calm", "Calm"],
  ["bold", "Bold"],
]);
const formatOptions = asOptions([
  ["image", "Image"],
  ["carousel", "Carousel"],
  ["reel_video", "Reel / video"],
  ["story", "Story"],
  ["text", "Text"],
]);
const ageOptions = asOptions([
  ["under_18", "Under 18"],
  ["18_24", "18–24"],
  ["25_34", "25–34"],
  ["35_44", "35–44"],
  ["45_54", "45–54"],
  ["55_64", "55–64"],
  ["65_plus", "65+"],
]);
const captionLanguageOptions = asOptions([
  ["auto", "Auto"],
  ["english", "English"],
  ["traditional_chinese", "Traditional Chinese"],
  ["simplified_chinese", "Simplified Chinese"],
  ["japanese", "Japanese"],
  ["korean", "Korean"],
  ["spanish", "Spanish"],
  ["other", "Other"],
]);
const categoryOptions = asOptions([
  ["", "Not set"],
  ["education", "Education"],
  ["entertainment", "Entertainment"],
  ["inspiration", "Inspiration"],
  ["personal", "Personal"],
  ["product_service", "Product / service"],
  ["news_commentary", "News / commentary"],
  ["community", "Community"],
  ["other", "Other"],
]);
const contextFields = [
  [
    "about_this_account",
    "About This Account",
    3000,
    "Describe the purpose of your social media account and the content you create.",
  ],
  ["target_audience", "Target Audience", 2000, "Describe the audience you want to attract."],
] as const;
const maxHashtags = 10;
const fieldClass =
  "w-full rounded-2xl border border-line bg-field p-4 outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60";

export function SettingsTab({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [context, setContext] = useState<AccountContext>(emptyContext);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [hashtagInput, setHashtagInput] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getConnection(session), getAccountContext(session)])
      .then(([nextConnection, nextContext]) => {
        setConnection(nextConnection);
        setContext(nextContext);
      })
      .catch((reason) => setError(errorMessage(reason, "Could not load settings.")))
      .finally(() => setLoading(false));
  }, [session]);

  const edit = (changes: Partial<AccountContext>) => {
    setContext({ ...context, ...changes });
    setSaved(false);
  };

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      setContext(await updateAccountContext(session, context));
      setSaved(true);
    } catch (reason) {
      setError(errorMessage(reason, "Could not save settings."));
    } finally {
      setSaving(false);
    }
  };

  const signOut = async () => {
    await logout(session);
    onLogout();
  };

  const removeAccount = async () => {
    if (!window.confirm("Permanently delete your PostBridge account and all associated data?")) return;
    await deleteAccount(session);
    onLogout();
  };

  const instagramLogout = async () => {
    if (
      !window.confirm("Log out of Instagram? PostBridge will stop tracking this connection until you connect it again.")
    ) {
      return;
    }
    try {
      await disconnectInstagram(session);
      setConnection({ connected: false, configured: true });
    } catch (reason) {
      setError(errorMessage(reason, "Could not log out of Instagram."));
    }
  };

  const addHashtag = () => {
    const cleaned = hashtagInput
      .trim()
      .replace(/^#+/, "")
      .replace(/[^\p{L}\p{N}_-]/gu, "");
    if (!cleaned) return;
    const hashtag = `#${cleaned}`;
    const exists = context.preferred_hashtags.some((item) => item.toLowerCase() === hashtag.toLowerCase());
    if (!exists && context.preferred_hashtags.length < maxHashtags) {
      edit({ preferred_hashtags: [...context.preferred_hashtags, hashtag] });
    }
    setHashtagInput("");
  };

  const hashtagsFull = context.preferred_hashtags.length >= maxHashtags;

  return (
    <div className="mx-auto w-full lg:w-[80%]">
      <PageTitle className="mb-5 md:mb-7">Settings</PageTitle>
      <ErrorBanner message={error} />
      <div className="space-y-5">
        <Panel>
          <p className="text-xs font-bold uppercase tracking-wider text-muted">Signed in as</p>
          <p className="mt-2 break-all text-base font-black md:text-lg">{session.user.email}</p>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:flex">
            <button
              onClick={() => void signOut()}
              className="rounded-xl border border-line px-3 py-3 text-sm font-bold hover:bg-subtle sm:px-5 sm:text-base"
            >
              Log out
            </button>
            <button
              onClick={() => void removeAccount()}
              className="rounded-xl border border-danger-line px-3 py-3 text-sm font-bold text-danger hover:bg-danger-bg"
            >
              Delete account
            </button>
          </div>
        </Panel>

        <Panel>
          <h2 className="text-lg font-black">Quick setup</h2>
          <div className="mt-5 grid min-w-0 gap-5 sm:grid-cols-2">
            <UnifiedSelect
              label="Tone"
              helper="(choose up to 3)"
              options={toneOptions}
              values={context.tone_keys}
              onValuesChange={(tone_keys) => setContext({ ...context, tone_keys })}
              multiple
              max={3}
              placeholder="Choose tone"
            />
            <UnifiedSelect
              label="Content format"
              options={formatOptions}
              values={context.content_formats}
              onValuesChange={(content_formats) => setContext({ ...context, content_formats })}
              multiple
              placeholder="Choose content format"
            />
            <UnifiedSelect
              label="Caption language"
              options={captionLanguageOptions}
              value={context.caption_language}
              onChange={(caption_language) => setContext({ ...context, caption_language })}
            />
            <UnifiedSelect
              label="Primary category"
              options={categoryOptions}
              value={context.primary_category}
              onChange={(primary_category) =>
                setContext({
                  ...context,
                  primary_category,
                  primary_category_other: primary_category === "other" ? context.primary_category_other : "",
                })
              }
              otherOptionValue="other"
              otherValue={context.primary_category_other}
              onOtherValueChange={(primary_category_other) => setContext({ ...context, primary_category_other })}
              otherPlaceholder="Write your category"
            />
            <div className="min-w-0 sm:col-span-2">
              <UnifiedSelect
                label="Audience age range"
                options={ageOptions}
                values={context.audience_age_ranges}
                onValuesChange={(audience_age_ranges) => setContext({ ...context, audience_age_ranges })}
                multiple
                placeholder="Choose audience age range"
              />
            </div>
          </div>
        </Panel>

        <Panel>
          <h2 className="text-lg font-black">Account context</h2>
          <div className="mt-5 grid gap-4">
            {contextFields.map(([key, label, maxLength, placeholder]) => (
              <label key={key}>
                <span className="text-sm font-bold">{label}</span>
                <textarea
                  disabled={loading || saving}
                  maxLength={maxLength}
                  value={context[key]}
                  placeholder={placeholder}
                  onChange={(event) => edit({ [key]: event.target.value })}
                  className={`mt-2 min-h-28 placeholder:text-muted ${fieldClass}`}
                />
                <span className="mt-1 block text-right text-[11px] text-muted">
                  {context[key].length}/{maxLength}
                </span>
              </label>
            ))}
            <div>
              <label htmlFor="preferred-hashtag" className="text-sm font-bold">
                Preferred hashtags
              </label>
              <input
                id="preferred-hashtag"
                disabled={loading || saving || hashtagsFull}
                value={hashtagInput}
                onChange={(event) => setHashtagInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter") return;
                  event.preventDefault();
                  addHashtag();
                }}
                placeholder={hashtagsFull ? "Maximum of 10 hashtags reached" : "Type a hashtag and press Enter"}
                className={`mt-2 ${fieldClass}`}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                {context.preferred_hashtags.map((hashtag) => (
                  <span
                    key={hashtag}
                    className="inline-flex items-center gap-2 rounded-full bg-selected py-2 pl-4 pr-2 text-sm font-bold text-selected-ink"
                  >
                    {hashtag}
                    <button
                      type="button"
                      aria-label={`Remove ${hashtag}`}
                      onClick={() =>
                        edit({ preferred_hashtags: context.preferred_hashtags.filter((item) => item !== hashtag) })
                      }
                      className="grid h-6 w-6 place-items-center rounded-full text-base hover:bg-surface"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button
              disabled={loading || saving}
              onClick={() => void save()}
              className="rounded-xl bg-primary px-5 py-3 text-sm font-black text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {saving ? "Saving…" : saved ? "Saved" : "Save settings"}
            </button>
          </div>
        </Panel>

        <Panel>
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted">Instagram connection</p>
              <h2 className="mt-1 text-lg font-black">
                {connection?.connected
                  ? `@${connection.username || "Instagram account"}`
                  : connection
                    ? "Instagram is not connected"
                    : "Loading Instagram connection…"}
              </h2>
            </div>
            {connection?.connected ? (
              <button
                onClick={() => void instagramLogout()}
                className="rounded-xl border border-danger-line px-5 py-3 text-sm font-black text-danger hover:bg-danger-bg"
              >
                Log out
              </button>
            ) : null}
          </div>
        </Panel>
      </div>
      <p className="pb-3 pt-7 text-center text-sm text-muted">
        <Link href="/privacy" className="font-bold text-primary-hover underline underline-offset-2">
          Privacy
        </Link>
        <span aria-hidden="true"> · </span>
        <Link href="/terms" className="font-bold text-primary-hover underline underline-offset-2">
          Terms
        </Link>
      </p>
    </div>
  );
}
