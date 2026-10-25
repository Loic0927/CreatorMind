# PostBridge product plan

Last updated: 2026-10-25
Owner: PostBridge  
Purpose: Track the work required to turn the current Instagram MVP into a multi-platform post creation, publishing, and per-post performance analysis product.

## Product audience and design guardrail

- PostBridge is a multi-tenant product for creators across all supported social media platforms. It is not designed around one owner, one account, one niche, or one creator's workflow.
- User-provided captions, screenshots, account descriptions, topics, and examples are contextual examples only. Agents must not turn them into global defaults, placeholder copy, product assumptions, scoring rules, prompt instructions, or UI structure.
- Product copy, defaults, workflows, data contracts, analysis, and recommendations must be designed from the perspective of the broad range of social media creators and content categories the app serves.
- Account Context is the per-user customization boundary. Personal creator details may influence that creator's opted-in generation or analysis, but must never become application-wide behavior or affect other users.

## Status legend

- `[x]` Complete and verified
- `[-]` In progress
- `[ ]` Not started
- `[!]` Blocked or requires an external decision/review

## Product outcome

PostBridge should let any signed-in creator:

1. Create an editable post from an uploaded/selected media asset, content brief, goal, generated caption, and hashtags.
2. Save the result as a draft before any external side effect occurs.
3. Select one or more connected social platforms and publish through a platform adapter.
4. Track each published/imported post independently.
5. Read an explanation based on that post's real metrics and content instead of a fabricated viral score.
6. Use the same account, drafts, publications, tracked posts, and analyses on web and mobile.

## Confirmed product decisions

- Instagram is the first publishing adapter; future platforms must plug into the same draft/publication contract.
- Publishing always requires an explicit user action. Generating or saving a draft never publishes automatically.
- The first creation MVP uses user-selected media plus generated caption/hashtags. AI image/video generation is a later, separate capability.
- Insights are displayed per post. The primary Insights view must not present an aggregate of unrelated posts as if it described one post.
- Content-aware analysis uses observed metrics plus available post content. It must identify unavailable inputs rather than invent them.
- `viral_score` is removed from current UI, API contracts, persisted output, documentation, and tests. Existing stored history must remain readable during migration.
- Predicted view counts are not part of the product experience. Creation returns editable copy only; performance analysis must prefer observed provider metrics and clearly labelled interpretation.
- Caption generation can target one or more selected platforms and uses both the content brief and an uploaded image. Publication capability is evaluated independently for every selected platform.
- The first multimodal creation flow supports JPG, PNG, and WebP images up to 5 MB in the web client. Video understanding remains out of scope for this phase.
- Provider credentials and access tokens remain server-side and encrypted. Client applications never receive permanent provider tokens.
- Account Context contains only account theme, account description, and target audience. These fields must remain platform-neutral and creator-specific.

## Current verified baseline

- [x] Production web, API, PostgreSQL, Nginx, HTTPS, and email login are live on OCI.
- [x] One user identity is shared between web and mobile through the same backend account.
- [x] Instagram OAuth connects a professional account and stores an encrypted long-lived token.
- [x] Instagram media can be imported and selected for tracking.
- [x] A tracked post can request and persist a fresh Instagram insight snapshot.
- [x] Caption and hashtag generation is available through the backend.
- [-] Web caption generation accepts a target platform, expanded/custom goal, and uploaded image context; production verification remains.
- [x] OCI Object Storage configuration and a private media bucket exist.

## Build checklist

- [-] **1. Apply the responsive design cleanup**
  Spec ref: `User feedback > Responsive dashboard design`
  What to build: Reduce oversized metric typography; remove page-title subtitles from Tracked posts, Create post, Analyze, Insights, and Settings; place paired mobile actions in a two-column row; separate the mobile Add a post action from the first post card; preserve usable spacing above the fixed mobile navigation.
  Acceptance: At 360px, 390px, 768px, and desktop widths, metric values do not dominate their cards, paired actions remain on one row where labels fit, the Add a post button has its own spacing block, and no requested page subtitle is rendered.
  Verify: Run `cd frontend && npm run build`, then manually inspect every dashboard tab at the four target widths.

- [-] **2. Replace aggregate Insights with a per-post view**
  Spec ref: `User feedback > Insights per post`
  What to build: Return tracked posts with their latest snapshot and snapshot history; let the user choose a post and show only that post's metrics, timestamp, deltas, caption, and thumbnail. Keep analysis history associated with the selected post where possible.
  Acceptance: Selecting post A never displays metrics from post B. A post without a snapshot shows an explicit empty state and Refresh metrics action.
  Verify: Track two Instagram posts with different values, select each one, and confirm every displayed metric matches its own latest database snapshot.

- [-] **2a. Make the creation composer platform- and image-aware**
  Spec ref: `User feedback > Creation inputs`
  What to build: Remove the creation-time predicted views/analysis card on web and mobile; add Instagram, Twitter, Facebook, Threads, and YouTube generation targets; expand goals and provide an Other field; send validated JPG/PNG/WebP image bytes to Gemini together with the user's brief; migrate the Gemini adapter to the maintained `google-genai` SDK. Do not accept video in this phase.
  Acceptance: Generated copy reflects both visible image content and the written brief, follows the selected platform's format, accepts a non-empty custom goal, and never displays a predicted view count in the creation result.
  Verify: Run Gemini adapter tests and the frontend production build; manually generate from one image for each platform, test Other with empty/non-empty input, reject a video, and reject an image over 5 MB.

- [x] **3. Add persistent draft and publication models**
  Spec ref: `Core > Draft before publish`
  What to build: Add database migrations and repository methods for `post_drafts`, `media_assets`, and `post_publications`. A draft stores owner, media reference, content brief, goal, caption, hashtags, status, and timestamps. A publication stores draft, platform, provider media/post ID, idempotency key, status, error code, and publish timestamps.
  Acceptance: Drafts and publication attempts are account-scoped, survive restarts, support multiple platform targets, and cannot expose another user's records.
  Verify: Run backend tests and migration tests; create two users and prove cross-user reads and writes are rejected.

- [x] **4. Build the draft API**
  Spec ref: `Core > Create and edit a post`
  What to build: Add authenticated create/list/get/update/delete draft endpoints. Reuse caption generation but save the generated result only after the user accepts or edits it. Validate caption length, hashtags, media ownership, and draft state transitions.
  Acceptance: A user can generate, edit, save, reopen, and delete an unpublished draft from either client without publishing it.
  Verify: Add API tests for the happy path, invalid media, invalid state transition, expired session, and cross-user access.

- [-] **5. Make media publishable without making the bucket public**
  Spec ref: `Core > Provider-accessible media`
  What to build: Upload selected media to the private OCI bucket, persist metadata, validate MIME type and size, and create a time-limited provider-readable URL for the publishing window. Do not store a permanent public URL when a short-lived URL is sufficient.
  Acceptance: Meta can download the media during container creation, anonymous access stops after expiry, and unsupported or oversized files fail before a publication record is created.
  Verify: Upload a test image, fetch it through the temporary URL, confirm expiry behavior, and run upload/security tests.

- [x] **6. Introduce a platform publishing adapter contract**
  Spec ref: `Core > Multi-platform foundation`
  What to build: Define a server-side adapter interface with capability discovery, validation, publish, status, and normalized error methods. Register Instagram first; expose future platforms as unavailable instead of rendering fake connected options.
  Acceptance: The draft/publish service contains no Instagram-specific branching outside the Instagram adapter, and adding a new provider does not require changing the draft schema.
  Verify: Unit-test a fake adapter and the Instagram adapter against the same contract; confirm unavailable adapters cannot be selected.

- [-] **7. Implement Instagram publishing**
  Spec ref: `Core > Publish to Instagram`
  What to build: Use the connected account token and the granted content-publish permission to create an Instagram media container, poll processing status when required, publish the container, persist the provider post ID, and return normalized success/failure state. Start with one supported media type and add video/carousel only after the image flow is reliable.
  Acceptance: Repeating the same client request does not create duplicate Instagram posts, failures remain retryable where safe, and a successful provider post becomes available for tracking.
  Verify: Publish to a designated Instagram test/professional account, confirm one provider post exists, retry the request, and inspect the publication/audit record.

- [-] **8. Build platform selection and publication status UI**
  Spec ref: `Core > Choose where to publish`
  What to build: Turn Create post into a draft workflow with generated editable copy, media preview, connected-platform checkboxes, Save draft, and Publish actions. Show per-platform validation, publishing, published, and failed states.
  Acceptance: A user can save without publishing, select Instagram, confirm publication, and see a provider-specific result. Disconnected or unsupported platforms are visible only as unavailable and cannot be submitted.
  Verify: Complete save-only, successful publish, disconnected-platform, provider-failure, and retry scenarios on responsive web.

- [x] **9. Link publications to tracking automatically**
  Spec ref: `Core > Publish then track`
  What to build: After a confirmed provider publication, import/upsert the provider media record and create one account-scoped tracking record. Do not mark a publication tracked until the provider post ID is available.
  Acceptance: A successfully published Instagram post appears once in Tracked posts; retries and callbacks do not create duplicates.
  Verify: Publish one draft, confirm one media row and one tracked row, retry, and confirm row counts remain unchanged.

- [-] **10. Add single-post content-aware analysis**
  Spec ref: `Core > Explain post performance`
  What to build: Create a structured analysis service using the selected post's latest/current metric history, caption, hashtags, media type, publish time, and available thumbnail/image context. Return summary, what performed well, what underperformed, likely content reasons, and concrete next actions. Clearly label metric facts versus model interpretation.
  Acceptance: Two posts with different content and metrics receive meaningfully different responses; missing metrics or inaccessible visual content are called out; provider data is never fabricated.
  Verify: Add deterministic service tests with mocked model responses and manual tests for high/low engagement, missing reach, image, and video/thumbnail-only inputs.

- [-] **11. Add analysis persistence and post detail history**
  Spec ref: `Core > Track analysis over time`
  What to build: Persist each analysis against the tracked post and source snapshot IDs, including model/version and creation time. Show analyses inside the selected post detail rather than in a global unrelated list.
  Acceptance: Refreshing metrics can create a new analysis without overwriting the previous report, and every report identifies the snapshot it analyzed.
  Verify: Create two snapshots and two reports for one post; confirm chronological display and immutable source references.

- [-] **12. Remove viral and view prediction end to end**
  Spec ref: `Core > Remove viral prediction`
  What to build: Remove `viral_score` and predicted views from active backend response models, new persistence payloads, web/mobile types, dashboard cards, analysis history, copy, tests, and documentation. Add backward-compatible reading or a migration for old prediction history. Engagement guidance must not be presented as observed platform data.
  Acceptance: No user-facing screen or current API contract displays viral score or predicted views, old rows do not crash history pages, and a repository search finds only intentional legacy migration references.
  Verify: Run `rg -n "viral_score|Viral score|Viral Score|predicted views|Predicted views" backend frontend mobile README.md` and review every remaining match; run all backend, frontend, and mobile checks.

- [-] **13. Bring the same workflow to mobile**
  Spec ref: `Cross-platform > Web and app parity`
  What to build: Add shared draft, platform selection, publication status, tracked-post detail, refresh, and content-analysis flows to Expo. Keep mobile navigation and two-column actions usable on small screens.
  Acceptance: The same draft created on web can be edited/published on mobile, and the resulting tracked post and analysis are visible on both clients for the same account.
  Verify: Run mobile typecheck/lint/tests and manually execute the cross-device draft-to-publish-to-analysis journey.

- [ ] **14. Add safe refresh scheduling and token maintenance**
  Spec ref: `Operations > Ongoing tracking`
  What to build: Add a durable background job mechanism for active tracked posts and Instagram token refresh. Apply provider-aware intervals, retries with backoff, idempotency, locking, and failure visibility; keep manual Refresh metrics available.
  Acceptance: Restarting the API does not lose scheduled work or duplicate snapshots, expired/revoked connections become reconnect-required, and provider rate limits are respected.
  Verify: Run scheduler integration tests for restart, duplicate delivery, transient failure, token expiry, and rate-limit responses.

- [ ] **15. Complete security, observability, and production rollout**
  Spec ref: `Release > Production readiness`
  What to build: Add structured logs without tokens, publication and sync audit events, provider error dashboards, backup/migration rehearsal, rate limits, upload scanning/validation, and feature flags for publishing. Roll out first to a designated test account before general availability.
  Acceptance: Secrets never appear in logs or clients, every external side effect has an audit record, rollback steps are documented, and the production smoke test covers draft, publish, track, refresh, and analyze.
  Verify: Run the complete test matrix, deployment validation, backup/restore rehearsal, log review, and a production test-account checklist.

## Recommended implementation order

1. Tasks 1-2: Correct the current design and per-post mental model.
2. Tasks 3-6: Establish durable drafts, media, and provider boundaries before adding side effects.
3. Tasks 7-9: Deliver the Instagram publish-to-track vertical slice.
4. Tasks 10-12: Replace viral scoring with content-aware, evidence-based analysis.
5. Tasks 13-15: Reach cross-platform parity and production reliability.

## External prerequisites and risk notes

- Instagram publishing requires a supported professional account, the correct Meta app permissions/review state, a valid connected token, and provider-readable media during ingestion.
- Video and carousel publishing add asynchronous processing and format constraints; they should not block the first single-image vertical slice.
- A private OCI bucket is compatible with publishing only if Meta receives a temporary URL it can fetch for long enough to ingest the asset.
- Other social platforms must be enabled only after their official APIs, permissions, and review requirements are confirmed. No scraping or simulated publishing state.
- Full video-content understanding is a separate workload. The first analysis version may use caption, metrics, media metadata, and thumbnail/image context while explicitly stating that the full video was not analyzed.

## Verification matrix

| Area | Required check |
| --- | --- |
| Backend | Full pytest suite, migration upgrade on an empty and populated database, authorization/isolation tests |
| Web | `npm run build`, responsive manual review, draft/publish/track/analyze browser journey |
| Mobile | `npm run typecheck`, `npm run lint`, `npm test`, physical-device deep-link and workflow test |
| Instagram | Test-account publish, idempotent retry, insight refresh, revoked-token handling |
| OCI | Build ARM64 images, run `scripts/oci/validate.sh`, review logs, confirm backup before migration |
| Security | No client secrets/tokens in bundles or logs; private media access expires; upload validation enforced |

## Progress log

- 2026-10-20: Created this plan from the live OCI/Instagram MVP and current responsive UI feedback.
- 2026-10-20: Confirmed existing Instagram OAuth, media import, tracking refresh, and caption-generation foundations.
- 2026-10-20: Implemented the first responsive web cleanup, changed Insights from aggregate totals to per-post cards, and removed viral score from the current dashboard UI. Production build passed; responsive visual review and backend/legacy viral cleanup remain.
- 2026-10-22: Removed creation-time prediction output, added target-platform and expanded/custom goal inputs, added image-aware Gemini caption generation, and migrated the isolated adapter from deprecated `google-generativeai` to `google-genai`.
- 2026-10-22: The frontend production build, Python syntax checks, and Gemini adapter text/image behavior passed locally. Full backend pytest remains pending because the local Windows Python environment is unavailable and Docker Desktop is not running.
- 2026-10-22: Brought the same creation changes to Expo: platform selection, expanded/custom goals, image payloads, and no prediction card. Mobile typecheck, direct ESLint, and both Jest suites passed.
- 2026-10-22: Replaced the dashboard's generic caption-length prediction form with tracked-post analysis based on real Instagram snapshots, metric deltas, caption, publish time, and available image/thumbnail context.
- 2026-10-22: Added account-scoped `tracked_post_analyses` persistence tied to tracked posts and source snapshots, plus chronological analysis history on web and mobile post detail. Production migration and live Gemini verification remain.
- 2026-10-22: Added multi-select generation and per-platform publication results on web and Expo. Instagram JPEG publishing now uploads to the private OCI bucket, creates a one-hour object-read URL for Meta, publishes through the official API, and automatically creates the tracked-post record. Other platforms explicitly return unavailable until their official OAuth/publishing adapters exist. Durable drafts, publication records, idempotency, production verification, and adapter extraction remain.
- 2026-10-22: Upgraded tracked-post analysis to creator intelligence v2: deterministic post/category scores, creator-average benchmarking, concise top insights, evidence-backed risks, structured next-post actions, input-based AI confidence, content-pattern detection, and score history on web and mobile. Existing v1 reports render as legacy history instead of breaking.
- 2026-10-22: Added durable account-scoped `media_assets`, `post_drafts`, and `post_publications` models with Alembic migration, idempotent publication attempts, and controlled state transitions. Added authenticated draft CRUD/list/history APIs with media ownership, platform caption, hashtag, and immutable-state validation. Extracted publishing behind a shared adapter registry with Instagram and explicit unavailable-provider adapters. Empty/populated migration tests and the complete backend suite passed locally.
- 2026-10-22: Connected the durable vertical slice on web: validated JPG/PNG/WebP uploads are stored privately with metadata and checksums, drafts can be saved and reopened, publishing requires confirmation and submits only available connected platforms, and Instagram receives a one-hour object-read URL for the stored asset. Publication attempts now persist provider IDs, failures, timestamps, and idempotency state. Successful Instagram results upsert media and create exactly one tracked post; an integration test proved that repeating the same request produces one provider call, one media row, and one tracked row. Live OCI expiry, responsive browser review, and designated Instagram test-account publishing remain.
- 2026-10-23: Simplified Create post with a collapsible platform selector and result-on-success layout. Restored the desktop Analyze split view and added a deterministic evidence-based fallback so missing, unavailable, or malformed Gemini output no longer prevents an analysis. Rebuilt Insights as an account-level pattern dashboard with a 10-post unlock threshold, ranked topics/hashtags/thumbnail styles/posting windows, and a confidence-labelled winning formula; individual post metrics were removed. Full backend suite (77 passed, 1 skipped) and frontend production build passed.
- 2026-10-23: Filtered Home's Add a post picker to untracked Instagram media only. Changed Analyze into a tracked-post selection screen followed by a centered, single-column detail flow at 70% desktop width, with the post selector removed and a Back action added. Reconfirmed Meta's Content Publishing API requires JPEG for image posts; PNG remains valid for drafts and caption generation but is not sent directly to Instagram.
- 2026-10-23: Added server-side PNG/WebP-to-JPEG conversion for Instagram publishing, including alpha flattening, EXIF orientation, private-object download, and converted private upload while preserving the original draft asset. Refactored single-post analysis with evidence/interpretation/importance explanations, weighted input confidence, account score context, a four-line executive summary, and testable experiment recommendations. Removed account pattern winners from Analyze and retained pattern intelligence in Insights. Frontend production build and production-image backend suite (78 passed, 1 skipped) passed.
- 2026-10-24: Added persistent, account-scoped content context in Settings and optional default-on context controls for caption generation and tracked-post analysis. The server injects saved context as bounded background reference only when enabled. Create now keeps a fixed 50/50 desktop composition before and after generation, and the Insights progress label clarifies that thumbnail analysis groups visual styles. Frontend production build and production-image backend/migration suite (85 passed, 1 skipped) passed.
- 2026-10-24: Removed thumbnail pattern tracking from Insights, including unlock progress, rankings, and the Winning formula, while preserving post thumbnails in tracked-post and Analyze views. Frontend production build and full production-image backend suite (85 passed, 1 skipped) passed.
- 2026-10-24: Reworked account Insights around evidence-labelled observations, centralized sample/confidence thresholds, testable Content Opportunities, account-history versus context-only hashtag suggestions, and posting-time comparisons that accept only real 23–26 hour snapshots with reach. Replaced the cross-category Winning Formula with an observed combination shown only after repeated co-occurrence. Structured Account Context into theme/about/audience/voice/analysis/creation fields while retaining the existing user-scoped Text storage and legacy-value compatibility; caption generation reduces unrelated context to voice, while post analysis ignores unrelated context and never treats it as metric evidence. Documented current Instagram Login and scheduling boundaries. Full backend suite (90 passed, 1 skipped) and frontend production build passed.
- 2026-10-24: Removed hashtag rankings, performance interpretation, recommendations, hashtag-based opportunities, prediction weighting, audit diagnosis, and automatic hashtag generation while preserving hashtag text already stored in captions and drafts. Added durable PostgreSQL-backed Instagram post-publish jobs for 1/3/6/12/24 hours, nullable evidence-based engagement rates, actual-versus-scheduled capture metadata, token refresh/reconnect handling, retry/lease/locking semantics, an independent OCI Compose tracking worker, and a responsive tracking timeline. Backend suite (103 passed, 1 skipped), migration round-trip, frontend production build, Alembic head, and Compose template validation passed.
- 2026-10-25: Established a product-wide guardrail that PostBridge serves creators across social platforms and must not generalize from one user's examples. Reduced Account Context to platform-neutral account theme, account description, and target audience fields; personal examples remain user-scoped context rather than product defaults.
