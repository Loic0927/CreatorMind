# Instagram data and insight screens

Last reviewed: 2026-11-01

## Login, syncing, and permissions

PostBridge uses Instagram API with Instagram Login for professional Business or Creator accounts. It requests the basic profile/media, media-insight, and publishing permissions. Comment reading stays behind `POSTBRIDGE_INSTAGRAM_COMMENTS_ENABLED` and the account allow-list until Meta grants the required access; enabled accounts must reconnect so the comments permission is present.

A successful login schedules one account sync in the background. The page serves cached data immediately. The sync is account-locked, skips when the previous successful sync is less than 30 minutes old, refreshes only already-tracked posts, reads comments when allowed, refreshes expiring tokens, and refreshes cached Summary text only when its fact hash changes. Login never discovers or tracks old posts.

The separately deployed tracking worker maintains tokens, lists recent media once per connected account every `NEW_MEDIA_POLL_SECONDS`, tracks only media published after the account's immutable `tracking_start_at`, and runs durable first-24-hour milestone jobs. Instagram returns lifetime totals rather than per-hour history, so the 1, 3, 6, 12, and 24 hour rows are point-in-time captures made by PostBridge. Meta documents no guaranteed availability delay; transiently absent insights are retried only inside each milestone's grace window.

## Stored data and privacy

PostBridge keeps posts, media, ordinary raw Instagram metric snapshots, raw API fields including watch time, drafts, publications, account context, and username-free comments. Comment provider author IDs are used only in memory to identify owner replies; usernames are never stored or sent to the model. Comment text and captions are treated as untrusted model input.

Milestone snapshots and their scheduling evidence are stored. Screenshot extraction, retired derived analysis, account grouping, and audience-activity datasets remain absent. No image-derived analytics input is accepted.

## Analyze rules

Analyze uses the selected post and mature same-format posts from the same account. Images/carousels mature at 7 days and videos/Reels at 14 days. The selected post is excluded from its own baseline.

A baseline requires at least six comparable posts. With fewer than 15 observations the usual range is the observed minimum to maximum; from 15 observations it is the 10th to 90th percentile. Stands out lists values above the range. Weaker first lists values below it; otherwise it lists values in the lower half of the comparable rank.

Engagement rate uses only returned interaction fields:

```text
engagement rate = sum(returned likes, comments, saves, shares) / reach * 100
```

It is null without positive reach or a returned interaction value. Missing values are never converted to zero.

Summary facts are computed in pure code from snapshot history and mature same-format account peers. Only qualifying, novel facts are sent to a feedback provider. Gemini output is strict JSON and validated against fact IDs and safety wording; invalid output falls through to deterministic evidence-safe templates. Captions, media, comments, usernames, Account Context, hashtags, and comment text are never model inputs. Opening Analyze reads the cache and never calls a model.

## Insights rules

Highlights use mature same-format posts and appear only when six qualifying posts provide the relevant reach and engagement values. Ranks likewise require a six-post mature same-format comparison group.

The next-post suggestion requires at least six posts with metrics and uses only the account's highest-view, most-liked, and best-commented examples. Comments contribute only when available. The text is explicitly a suggestion, never a guarantee, and cannot introduce niche assumptions, engagement bait, invented evidence, or causal claims.

The Posts list contains only posts with metrics. A post needs refresh when it has no metrics or its latest snapshot is older than the shared 24-hour threshold. Manual refresh is post-scoped, has a one-minute cooldown, refreshes metrics then comments, and updates cached text only when inputs changed.
