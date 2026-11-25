# AI text generation boundaries

Updated: 2026-11-25.

This document describes the active PostBridge behavior. Historical `post_summary`, `post_feedback`, and
`_feedback_media` paths were removed; they are available only in Git history.

## Consent and execution boundary

Before Gemini receives any data, the account must explicitly grant AI-processing consent. The consent
dialog explains that selected media, captions, comment text, and performance facts can be sent to Google
Gemini. Revocation removes the user's generated-text cache.

Generation runs only from background/write-side workflows: account/login sync, a tracked-post refresh,
new tracking, or worker snapshot capture. `GET /tracked-posts/{id}` and `GET /insights/account` only read
persisted metrics and generated-text caches; they do not download media or call Gemini.

## Summary

`backend/services/feedback.py` builds qualifying facts from snapshot history and same-format account
comparisons. The fact set includes growth stage, accumulation pace, historical comparisons, reach/engagement
relationships, watch time when supplied by Instagram, and separate same-format peer comparisons for views,
saves, shares, and comments. Each interaction fact carries its peer count and percentile; unavailable signals
are explicitly `unknown`. An additional `interaction_outlier` fact names a high/low split such as
`views_high_comments_low` when the evidence supports one. No per-second retention or other unavailable API
data is inferred.

Gemini receives those structured facts and, on a cache miss, optionally one bounded media input. Its response
is a JSON object with `diagnosis`, an `evidence` array of `{fact_id, statement}` items, `hypothesis`,
`experiment`, `measure`, and `do_not_change`. Evidence must cite qualifying fact ids. Numbers may be
restated only when present in the fact payload; causal explanations must be labelled hypotheses, and invented
numbers, guarantees, and causation stated as fact are rejected. No consent produces the same structured shape
from a deterministic fact template before it is rendered for the existing Summary text field.

The Summary cache key contains the fact payload, selected provider signature, prompt version, and stable
media identity. It does not contain downloaded media bytes.

## Audience summary

`backend/services/insight_texts.py::audience_description` receives only bounded, non-owner, stored
comment text after comment permission and AI consent are both present. It never receives commenter names
or provider IDs. Analyze may still display up to 20 privacy-safe raw comment items (`text`, `like_count`,
`timestamp`) without author information. Without consent, its state is `consent_required` and raw items
remain available where comment access is enabled.

## Next-post suggestion

`next_post_suggestion` uses only mature posts with usable rate signals, selects the largest same-format
group, and passes at most three distinct top and two distinct bottom posts. The input contains bounded,
untrusted captions, caption length, relative rate signals, optional video watch-time buckets, and clustered
non-owner comment themes. Each theme includes a label, count, and a small number of representative texts;
raw comment lists, usernames, and provider IDs are not passed. Example themes include `asking_how`,
`guessing_the_method`, `praise`, and `asking_next_video`. It requests a concise, uncertain optional
experiment; the prompt forbids values, causation, engagement bait, niche assumptions, and posting-time advice.

## Reliability and audit

Gemini calls use the maintained `google-genai` SDK with a system instruction, temperature, maximum output
tokens, optional JSON response schema, and SDK timeout. If a provider/configuration error or output
validation failure occurs, audience and suggestion caches keep their last known-good text. Summary falls
back to a deterministic validated template. Persistent AI-generation logs retain bounded raw response
text and token-usage metadata for 30 days.
