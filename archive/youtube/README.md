# Archived: YouTube analysis

Archived on 2026-11-22. Nothing in this folder is imported, built, deployed, or tested.

| File | Original location |
| --- | --- |
| `backend/youtube_service.py` | `backend/services/youtube.py` |
| `backend/youtube_routes.py` | YouTube routes and models from `backend/main.py` |
| `backend/social_connection_store.py` | YouTube helpers from `backend/storage/json_store.py` and `models.py` |
| `frontend/YouTubeAuditForm.tsx` | `frontend/src/components/YouTubeAuditForm.tsx` |
| `frontend/api.ts` | `frontend/src/lib/api.ts` (YouTube client plus retired prediction client) |
| `frontend/app-user.ts`, `AppShell.tsx`, `EmptyStateCard.tsx` | `frontend/src/lib`, `frontend/src/components/stitch` |

Environment variables that only this feature used: `YOUTUBE_API_KEY`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `YOUTUBE_OAUTH_REDIRECT_URI`.

## Required before restoring

The archived code has known security problems. Fix them instead of restoring it as is:

1. **Authentication**: every route takes `user_id` from the query or body. Use
   `Depends(require_user)` and follow the Instagram pattern: an authenticated
   `POST /api/youtube/connect/start` returns `authorization_url`, and the browser follows it.
2. **Storage**: OAuth state lives in process memory and tokens are stored unencrypted in a JSON
   file. Add an Alembic migration for a `youtube_connections` table, encrypt tokens with
   `backend/storage/token_store.py`, and store OAuth state in `oauth_states`.
3. **Account scope**: never list connections across users; always filter by the authenticated user.
4. **UI**: build the screen inside the dashboard with `frontend/src/lib/postbridge.ts`
   (`authRequest`) instead of the archived `api.ts`, `app-user.ts`, and `AppShell.tsx`.
5. Add the router in `backend/main.py`, plus tests for cross-user isolation.
