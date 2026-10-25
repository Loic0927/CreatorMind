# Instagram data and post-publish tracking

Last reviewed: 2026-10-25

## Account type, login, and permissions

PostBridge uses Instagram API with Instagram Login at `graph.instagram.com`. The authorizing account must be an Instagram professional account (`BUSINESS` or `MEDIA_CREATOR`). Personal/consumer accounts are rejected during connection.

The OAuth request contains only capabilities used elsewhere in the product:

- `instagram_business_basic` — connected profile and owned media fields;
- `instagram_business_manage_insights` — owned-media insight metrics;
- `instagram_business_content_publish` — the existing Instagram publishing flow.

There is no hashtag-search or hashtag-analysis scope, Page token flow, `graph.facebook.com` public-content flow, or hashtag API in PostBridge.

References:

- [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/)
- [Instagram Insights](https://developers.facebook.com/docs/instagram-platform/insights/)

## Tokens

The OAuth callback exchanges the authorization code for a long-lived token. PostgreSQL stores only a Fernet-encrypted token plus its expiry, requested scopes, account type, and safe connection status. Browser/mobile sessions never receive the provider token.

Before a tracking request, the worker refreshes a long-lived token when it is within seven days of expiry and atomically replaces the encrypted value. A Meta token-invalid response changes the connection to `reconnect_required` and blocks that user's unfinished jobs. A successful reauthorization resumes only jobs still inside their real collection windows. Tokens and complete provider error bodies are never logged.

## Metrics and engagement rate

For owned media, PostBridge requests `like_count` and `comments_count`, then individually attempts the media insight metrics `reach`, `saved`, `shares`, and `views`. Metric availability varies by media/product type and current Meta API behavior. A snapshot stores only values Meta actually returned, plus a safe per-field state (`available`, `unavailable`, or `permission_required`). It never fills missing fields with zero.

The current integration does not request or persist average watch time, total watch time, retention, or skip rate. Insights therefore labels those fields as not collected instead of showing synthetic values. Adding one of these fields requires confirming that Meta exposes the metric for the connected account and media type, then extending both the API client and snapshot schema.

Each completed 1/3/6/12/24-hour milestone stores its own cumulative `views` value and actual capture time. `views` and `reach` are shown separately: views can include repeat viewing by the same account, while reach represents unique accounts when Meta supplies it. The UI may subtract two adjacent captured cumulative values, but labels that number as an increase between snapshots rather than exact hourly views. If either snapshot lacks `views`, or Meta revises the later cumulative counter below the earlier value, no increase is shown.

The displayed formula is:

```text
engagement rate = sum(returned likes, comments, saves, shares) / reach * 100
```

The numerator includes only interaction fields actually returned for that media. Calculation requires positive `reach` and at least one returned interaction count. Otherwise the value is `null` and the UI displays **Unable to calculate**. The UI also identifies partial metric coverage.

## Durable 1/3/6/12/24-hour tracking

`instagram_insight_collection_jobs` is a PostgreSQL-backed queue. Each active tracking record has one unique job for each target hour (1, 3, 6, 12, and 24), based on the media's provider `published_at`. Early milestones allow 30 minutes of execution delay; the 24-hour milestone allows two hours so a short outage or rate limit can recover. Both `scheduled_for` and the snapshot's actual `captured_at` are returned to clients.

The independent `tracking-worker` Compose service polls once per minute. It:

1. reconciles active tracking records so a web-process interruption cannot permanently omit jobs;
2. claims a small due batch with PostgreSQL `FOR UPDATE SKIP LOCKED`;
3. records a worker lease and attempt count;
4. calls Meta outside the claim transaction;
5. inserts the milestone snapshot and completes its job atomically.

Unique constraints on `(tracked_post_id, target_hour)` and `(media_id, target_hour)`, row locking, worker ownership checks, and stale-lease recovery prevent duplicate work and duplicate milestone snapshots across multiple workers.

Transient network/5xx errors retry with exponential backoff and deterministic jitter. Rate limits also honor `Retry-After` when supplied. Retries never run beyond the milestone deadline. Permission failures are held for reauthorization; deleted/inaccessible media is terminal. Stopping tracking cancels unfinished jobs. Disconnecting or deleting an account cancels/deletes its jobs and PostgreSQL cascades deletion of connected media and snapshots.

## Old posts and manual refreshes

Existing snapshots are migrated as `manual_current`. A manual refresh continues to create a current cumulative snapshot and is clearly separated from milestone data. PostBridge never reconstructs past 1/3/6/12/24-hour values from a lifetime total. If tracking starts after a target's allowed window, that milestone is `missed` and no snapshot is created. Only a real completed `target_hour=24` milestone can participate in 24-hour account comparisons.

## Insights comparison rules

Content Opportunities separate an observed fact from a data gap and a proposed test. A proposed 24-hour metric is never described as evidence until a real milestone snapshot exists. When tracking is pending, blocked for authorization, unavailable, or missed, the page states that reason and does not substitute a manual or lifetime snapshot.

Post performance ranking is restricted to posts with the same Instagram media type and a real 24-hour milestone. Posts with partial tracking or latest cumulative snapshots remain visible, but are not mixed into that ranking. Pattern confidence labels describe sample-size sufficiency only, not the probability that an observed association is correct. Untested posting windows are coverage gaps, not predicted high-performing times.
