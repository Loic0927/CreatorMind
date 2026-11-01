# First-24-hour collection audit

Audited: 2026-11-01. This report contains aggregate counts and identifiers only.

## Before this change

- Login verification scheduled `run_account_sync`, which listed recent Instagram media and created tracked rows for every returned post. This meant old media could be auto-tracked at login.
- The deployed tracking worker performed token maintenance only. It did not detect media or capture metrics.
- PostBridge publication confirmation already upserted the provider media and idempotently created a tracked row.
- The existing Home `Add a post` picker called `POST /tracked-posts`, which created a tracked row but did not immediately fetch lifetime metrics.
- Durable milestone scheduling, row claiming, leases, restart recovery, retries/backoff, scheduled-versus-actual metadata, and per-milestone uniqueness existed from commit `a41d3176f1b5357a15146cfee15b944cf47b58a1`. Worker isolation and evidence rules were refined in `29fa277`. The feature and queue were removed in `151612eebb2d3ea37ec52e9095d8d4fdaf1dbd90` on 2026-10-30.

## Existing evidence count

The checked local development store has 1 account, 1 tracked post, and 1 lifetime snapshot. **0 snapshots** were captured between that media's provider publish timestamp and publish plus 24 hours. No local SQL database exists. The production PostgreSQL aggregate could not be queried from this workspace without using deployment credentials/network access, so its count is not verified here.

## Provider capability

Instagram media-insight values are lifetime/cumulative readings at request time; the API does not supply historical per-hour points. First-hour history therefore exists only when PostBridge captures it at the time. This matches `docs/instagram-insights-capabilities.md` and Meta's current media-insights references:

- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/insights/
- https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights/

The reviewed Meta references do not publish a guaranteed delay/SLA before a new post or Reel's media insights become available. Metrics can be absent or temporarily unavailable, so collection must retry within the defined grace window and must never reinterpret a later reading as an earlier one.

## Implemented boundary

`tracking_start_at` is immutable per connected account. Migration-time connections receive the migration time; new connections receive first connection time. Only media with a provider publish timestamp strictly after that boundary is auto-tracked, and detection now runs only in the worker. Old media is available only through the existing picker, which now fetches lifetime metrics immediately. Publication-confirmed media remains idempotent and is not duplicated by worker detection.

Fresh tracked posts receive jobs for 1, 3, 6, 12, and 24 hours. Grace is 30 minutes for the first two milestones and 60 minutes for the remaining three. Late starts create explicit missed rows only for expired windows; posts already older than 24 hours receive no milestone jobs and are marked unavailable. Snapshots keep `scheduled_for`, true `captured_at`, `milestone_hours`, `source=api`, and `lateness_seconds`.
