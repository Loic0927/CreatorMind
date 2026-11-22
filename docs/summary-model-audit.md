# Summary model audit

Audited: 2026-11-23.

## Active implementation

PostBridge has no trained Summary model and no numeric-prediction fallback. The retired predictor and
its provider-selection branch were removed. `FEEDBACK_PROVIDER` accepts `auto` or `gemini`; unsupported
values safely use the Gemini path.

Summary generation is evidence-first:

- it builds validated facts from persisted Instagram snapshots;
- it uses Gemini only after a user has granted AI-processing consent;
- without consent it stores a deterministic fact-template Summary instead;
- it validates Gemini JSON against the supplied fact identifiers and falls back to the same template;
- it records provider, model, prompt version, input hash, latency, status, and available token usage in
  the bounded AI-generation log.

The cache input uses stable persisted media identifiers (internal media id, provider media id, media type,
and provider timestamp), not downloaded bytes. A cache hit therefore performs no Meta CDN download or
Gemini request. Media is downloaded only by a write-side refresh on a cache miss.

## Remaining external verification

This repository cannot prove a production Gemini model is enabled or that the configured account has
permission to submit media to it. Before release, verify the configured model in the production project,
review the generation logs without exposing prompt content, and test the consent/revocation journey on a
non-production account.
