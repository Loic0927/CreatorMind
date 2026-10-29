# Instagram data, comments, and first-24-hour insights

Last reviewed: 2026-10-29

## Login and permissions

PostBridge uses Instagram API with Instagram Login at `graph.instagram.com` for
professional Business or Creator accounts. Its normal OAuth request contains:

- `instagram_business_basic` for the connected profile and owned media;
- `instagram_business_manage_insights` for owned-media insights;
- `instagram_business_content_publish` for the existing publishing flow.

Comment reading is off by default. When
`POSTBRIDGE_INSTAGRAM_COMMENTS_ENABLED=true`, OAuth also requests
`instagram_business_manage_comments`. Meta's Comment Moderation guide requires
Advanced Access when the app serves professional accounts the app does not own or
manage, so general availability requires App Review. Standard Access is limited to
accounts owned/managed by the app and added in the App Dashboard.

Owner/app-role testing can keep the global flag off and put comma-separated
PostBridge user IDs or Instagram account IDs in
`POSTBRIDGE_INSTAGRAM_COMMENT_ACCOUNT_ALLOWLIST`. Other accounts remain gated; an
enabled account must reconnect Instagram so its OAuth grant includes
`instagram_business_manage_comments`.

References: [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/),
[Instagram Insights](https://developers.facebook.com/docs/instagram-platform/insights/), and
[Instagram comment moderation](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/comment-moderation/).

## Followers online

The current official Instagram API with Instagram Login collection does not document
an `online_followers` insight. PostBridge therefore reports it as unsupported; no
follower minimum or API time-zone contract applies to this integration. As a fallback,
the owner can upload one account-level Instagram Audience “most active times” chart
in any Instagram UI language. PostBridge stores the source and confirmation date,
highlights the three observed peak hours, and prompts for a monthly refresh. It is
labelled as screenshot data, not a prediction or recommendation.

Official collection checked 2026-10-29: [Meta Instagram API collection](https://www.postman.com/meta/instagram/collection/6yqw8pt/instagram-api).

## Privacy and data sources

Comment ingestion stores the provider comment ID, text, like count, timestamp,
`is_owner_reply`, and fetch/classification metadata. It never persists or displays a
commenter username. The provider author ID is used in memory only to exclude the
creator's own replies. Comment text is delimited as untrusted input before model
classification.

API numbers, screenshot text values, and screenshot-curve estimates always keep
separate source labels. Unknown screenshot fields remain `null`. Higher skip rate
retains its unfavorable meaning.

For Reels/video, PostBridge requests average and total watch time when Meta returns
them. Skip rate, share rate, follower/non-follower split, and curve values may come
from a user-confirmed screenshot instead; they are not inferred from API totals.

## Durable 24-hour capture

The PostgreSQL-backed worker periodically lists recent account media, creates tracking
for each newly discovered post, and keeps one `target_hour=24` job per active tracked post
and no 1/3/6/12-hour jobs. It allows two hours for transient provider recovery and
uses locking, leases, retries, and unique constraints to prevent duplicate captures.
Long-lived Instagram token refresh remains enabled independently.

If tracking starts after the 24-hour mark, that API milestone is permanently unavailable.
Before a post is 24 hours old, screenshot upload is unavailable. After 24 hours, a
user can upload one to three private Instagram insights screenshots. A vision model
extracts nullable candidates, the user edits and confirms them, and only then is an
account-scoped `external_insight_records` row persisted. Screenshots are deleted
after confirmation unless the user opts to retain them.

Manual refreshes remain cumulative `manual_current` API snapshots and are never
presented as historical 24-hour measurements.

## Comparison rules

Post performance comparisons use mature posts of the same Instagram format. Maturity
is 7 days for images/carousels and 14 days for video/Reels.
An excluded outlier remains visible but is removed from medians, patterns, and ranks.

Engagement rate uses only returned interaction fields:

```text
engagement rate = sum(returned likes, comments, saves, shares) / reach * 100
```

It is `null` without positive reach or any returned interaction count. Missing values
are never converted to zero.
