# Instagram data and insight screens

Last reviewed: 2026-10-30

## Login, syncing, and permissions

PostBridge uses Instagram API with Instagram Login for professional Business or Creator accounts. It requests the basic profile/media, media-insight, and publishing permissions. Comment reading stays behind `POSTBRIDGE_INSTAGRAM_COMMENTS_ENABLED` and the account allow-list until Meta grants the required access; enabled accounts must reconnect so the comments permission is present.

A successful login schedules one account sync in the background. The page serves cached data immediately. The sync is account-locked, skips when the previous successful sync is less than 30 minutes old, discovers and tracks new posts, refreshes lifetime metrics, backfills posts without metrics, reads comments when allowed, refreshes expiring tokens, and refreshes cached AI text only when its input hash changes. Provider calls are batched, retried with backoff, isolated per post, and idempotent.

The separately deployed tracking worker is retained only for Instagram long-lived-token maintenance. It does not discover posts, refresh metrics, or run milestone jobs. Login sync is the only automatic post refresh path; Analyze and Insights provide post-scoped manual refresh.

## Stored data and privacy

PostBridge keeps posts, media, ordinary raw Instagram metric snapshots, raw API fields including watch time, drafts, publications, account context, and username-free comments. Comment provider author IDs are used only in memory to identify owner replies; usernames are never stored or sent to the model. Comment text and captions are treated as untrusted model input.

The removed milestone, external extraction, derived analysis, account grouping, and audience-activity datasets are not part of the current schema. No image-derived analytics input is accepted.

## Analyze rules

Analyze uses the selected post and mature same-format posts from the same account. Images/carousels mature at 7 days and videos/Reels at 14 days. The selected post is excluded from its own baseline.

A baseline requires at least six comparable posts. With fewer than 15 observations the usual range is the observed minimum to maximum; from 15 observations it is the 10th to 90th percentile. Stands out lists values above the range. Weaker first lists values below it; otherwise it lists values in the lower half of the comparable rank.

Engagement rate uses only returned interaction fields:

```text
engagement rate = sum(returned likes, comments, saves, shares) / reach * 100
```

It is null without positive reach or a returned interaction value. Missing values are never converted to zero.

Summary text is generated and cached only when at least two ordinary snapshots contain a meaningful change. It describes non-obvious movement without repeating visible values, causal claims, or advice. Audience comments require at least three real non-owner comments and produce an explicit disabled, reconnect, access, sparse-data, error, or ready state.

## Insights rules

Highlights use mature same-format posts and appear only when six qualifying posts provide the relevant reach and engagement values. Ranks likewise require a six-post mature same-format comparison group.

The next-post suggestion requires at least six posts with metrics and uses only the account's highest-view, most-liked, and best-commented examples. Comments contribute only when available. The text is explicitly a suggestion, never a guarantee, and cannot introduce niche assumptions, engagement bait, invented evidence, or causal claims.

The Posts list contains only posts with metrics. A post needs refresh when it has no metrics or its latest snapshot is older than the shared 24-hour threshold. Manual refresh is post-scoped, has a one-minute cooldown, refreshes metrics then comments, and updates cached text only when inputs changed.
