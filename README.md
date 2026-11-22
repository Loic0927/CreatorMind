# PostBridge

PostBridge is a full-stack creator app. One email-based account is shared by the responsive
Next.js web app and the Expo mobile app. Creators connect Instagram, generate captions with
Gemini, publish image posts, and track per-post Instagram insights.

- Production deployment (OCI, `postbridge.dev`): `docs/oci-deployment.md`
- Backup and restore: `docs/oci-backup-restore.md`
- Product plan and progress log: `plan.md`
- Archived YouTube analysis (not deployed): `archive/youtube/README.md`

## Stack

| Part | Technology |
| --- | --- |
| Web | Next.js + TypeScript + Tailwind (`frontend/`) |
| Mobile | Expo / React Native (`mobile/`) |
| API | FastAPI (`backend/`), Alembic migrations |
| Storage | PostgreSQL in production, SQLite locally; private OCI Object Storage for media |
| AI | Gemini, server-side only |

## Environment files

FastAPI, Next.js, Expo, and the OCI deployment load different files. Only the templates belong
in Git; copy the one you need and fill in real values. Client files must never contain provider
secrets, OAuth client secrets, database credentials, or permanent access tokens.

| Runtime | Template | Runtime file |
| --- | --- | --- |
| FastAPI | `backend/.env.example` | `backend/.env` |
| Next.js | `frontend/.env.local.example` | `frontend/.env.local` |
| Expo | `mobile/.env.example` | `mobile/.env.local` |
| OCI production | `.env.oci.example` | `.env.oci` |

## Local development

```bash
# API (from the repository root)
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload     # http://127.0.0.1:8000/docs

# Web
cd frontend && npm install && npm run dev       # http://localhost:3000

# Mobile
cd mobile && npm install && npx expo start
```

The web app expects `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`.

## Checks

CI (`.github/workflows/ci.yml`) runs the same commands on every push and pull request:

| Area | Commands |
| --- | --- |
| Backend | `ruff check`, `ruff format --check`, `python -m pytest backend` |
| Web | `npm run format:check`, `npm test`, `npm run build` |
| Mobile | `npm run format:check`, `npm run typecheck`, `npm run lint`, `npm test` |

Use `ruff format` and `npm run format` to fix formatting.

## API overview

All routes except sign-in and health checks require `Authorization: Bearer <session token>`.

| Area | Routes |
| --- | --- |
| Auth | `POST /auth/request-code`, `POST /auth/verify-code`, `GET /auth/session`, `POST /auth/logout`, `DELETE /auth/account`, `GET/POST/DELETE /auth/ai-processing-consent` |
| Account context | `GET/PATCH /auth/account-context`, `GET /auth/account-context/suggest`, `POST /auth/account-context/preview` |
| Instagram | `/api/instagram/connection`, `/api/instagram/connect/start`, `/api/instagram/connect/callback`, `/api/instagram/account`, `/api/instagram/media` |
| Tracking and insights | `/tracked-posts`, `/tracked-posts/{id}`, `/tracked-posts/{id}/refresh`, `/insights/account`, `/insights/instagram` |
| Create and publish | `POST /mobile/caption`, `POST /media-assets`, `/drafts`, `/drafts/{id}/publish`, `GET /publishing/capabilities`, `POST /publications` |
| Health | `GET /`, `GET /health` |

The public Meta callbacks are deliberately unauthenticated: `POST /api/instagram/deauthorize`,
`POST /api/instagram/data-deletion`, and `GET /api/instagram/data-deletion/status?code=...`.
They validate Meta's signed request before acting; never send a signed request through a client route.

## App Review sign-in

For an App Store or Meta reviewer, set both `POSTBRIDGE_REVIEW_LOGIN_EMAIL` and
`POSTBRIDGE_REVIEW_LOGIN_CODE_HASH` in the backend runtime. The code hash is a SHA-256 hash of
the six-digit reviewer code. When (and only when) the incoming email matches that mailbox
case-insensitively, the normal rate-limited sign-in flow accepts the configured code without
mailing it. The code is never logged. Leave either variable empty to fully disable this path.

## AI-processing consent

Before Gemini is used, web and mobile ask the creator to opt in to sending selected media,
captions, audience comments, and performance facts to Google Gemini for the requested feature.
They can decline or revoke consent in Settings. Revocation clears generated text caches;
non-AI deterministic summaries may still be produced from stored performance facts.

## Abuse protection

- Sign-in codes: 60-second cooldown, 5 attempts per code, and at most `POSTBRIDGE_LOGIN_CODES_PER_DAY`
  (default 10) codes per email per 24 hours. Nginx also limits the sign-in routes per IP.
- Caption generation: `POSTBRIDGE_CAPTION_LIMIT_PER_HOUR` (default 30) per user per API worker.
- Gemini features require explicit per-user AI-processing consent; caption generation returns
  `consent_required` until the user grants it.
- Deleting an account removes the user's database rows and their private media in OCI.
