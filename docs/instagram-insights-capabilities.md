# Instagram data and insight screens

Last reviewed: 2026-11-23

## Boundaries

PostBridge uses Instagram API with Instagram Login for connected professional accounts. Access
tokens remain server-side and encrypted. Per-media insight reads use Instagram Login's documented
lifetime metrics and are stored as ordinary snapshots; an unavailable metric remains unavailable,
never a fabricated zero.

`GET /tracked-posts/{id}` and `GET /insights/account` are cache-only reads. They do not download
media, call Instagram, or call Gemini. A Summary has `ready`, `pending`, or `none` status so the
client can explain a background refresh without pretending a result exists.

The following write-side jobs may refresh derived text caches after persisted data changes:

- a user explicitly tracks or refreshes a post;
- successful login/account sync;
- a tracking-worker snapshot capture.

The account sync is locked and has a 30-minute success cooldown. It refreshes already-tracked
posts only. The tracking worker separately discovers current provider media and captures the
scheduled milestones. Neither flow makes an old provider post tracked without a user action.

## Data and deletion

Stored Instagram data is scoped to the PostBridge user and connection: provider media identifiers,
captions, media URLs supplied by Meta, snapshots, tracking state, privacy-safe comments, and
generated-text caches. Comment author names are not returned to clients or included in AI prompts.

Meta can call the public deauthorize and data-deletion routes with a signed request. The request
is verified with the app secret before its app-scoped `user_id` is trusted. Deauthorization marks
the matching connection disconnected and clears its token. Data deletion removes the connection,
media, snapshots, tracked posts, comments, generated-text caches, AI logs, collection jobs, and
OAuth state while retaining the PostBridge account; a confirmation code status remains available
without storing the raw signed request.

## Compare a post

Images and carousels become mature after seven days; video/Reel posts after fourteen. Mature posts
use their lifetime snapshot and state `comparison_basis: lifetime`. A younger post uses its latest
age and compares each same-format peer at that peer's closest snapshot of the same age, only when
the difference is within max(25% of the selected age, three hours); it states
`comparison_basis: same_age`.

At least six same-format peers are required. If that is not met, comparison sections are hidden
and the neutral reason is `too_early` for young posts or `too_few_posts` for mature posts. A
metric is marked weaker only when it falls below the account range; there is no lower-half
fallback. Returned interaction fields are used to calculate engagement rate only with positive
reach.

## Generated text and consent

Gemini processing always requires the creator's explicit consent. The consent screen describes
that selected media, captions, comment text, and performance facts may be sent to Google Gemini.
New users accept this together with the Privacy Policy and Terms before their account is created.
The backend revocation endpoint clears generated-text caches; Settings does not expose a separate
AI-processing container.

- **Summary** is based on validated performance facts and, after consent, may receive bounded
  media content. Without consent it uses only a deterministic fact template.
- **Audience summary** may receive up to the permitted stored comment text after consent. The
  client can still show the latest privacy-safe raw comment items; its AI state is
  `consent_required` until opt-in.
- **Next-post suggestion** uses mature rate-based comparisons, selected captions and up to eight
  untrusted comment texts per selected post after consent. It compares the largest eligible format
  group, sends at most three top and two distinct bottom examples, and asks for one observable
  difference, one optional experiment, and brief uncertainty.

Prompts and validators prohibit invented values, causal or predictive claims, engagement bait,
niche assumptions, and posting-time claims. Model failures and invalid responses retain a
previous valid cache instead of overwriting it.

## Comments and insights

Comment ingestion is separately feature/permission gated. When enabled, Analyze exposes at most
20 newest non-owner comments as `{text, like_count, timestamp}`; no username, author ID, or
provider ID reaches web or mobile. The same safe items are available even when there are too few
comments for an audience summary.

Media insight calls request the documented comma-separated batch where supported: feed/Reel
metrics include `views`, `reach`, `saved`, `shares`, and `comments`; Reels additionally request
`ig_reels_avg_watch_time` and `ig_reels_video_view_total_time`; Stories request `views`, `reach`,
and `shares`. A non-retryable batch rejection falls back to one metric at a time; retryable errors
remain retryable.
