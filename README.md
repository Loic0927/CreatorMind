# CreatorMind AI

CreatorMind AI is a lightweight full-stack AI dashboard for predicting social content performance and generating practical creator insights.

Stack:

- Frontend: Next.js + TypeScript + Tailwind
- Backend: FastAPI
- ML artifact: `backend/models/model.pkl`
- Persistence: local JSON store at `backend/data/store.json`

## Project Setup

From the project root, install backend dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Then install frontend dependencies:

```bash
cd frontend
npm install
```

Create the frontend environment file:

```bash
copy .env.local.example .env.local
```

Set the backend YouTube Data API key if you want real public YouTube video data in the
YouTube audit flow:

```powershell
$env:YOUTUBE_API_KEY="your-youtube-data-api-key"
$env:GOOGLE_CLIENT_ID="your-google-client-id"
$env:GOOGLE_CLIENT_SECRET="your-google-client-secret"
$env:YOUTUBE_OAUTH_REDIRECT_URI="http://127.0.0.1:8000/auth/youtube/callback"
$env:FRONTEND_BASE_URL="http://localhost:3000"
```

CreatorMind uses this key only for the official YouTube Data API public `videos`
endpoint. It does not scrape YouTube pages.

## Backend

Train the model bundle:

```bash
python -m backend.models.train_model
```

Run the FastAPI server from the project root:

```bash
python -m uvicorn backend.main:app --reload
```

Available routes:

- `GET /`
- `GET /health`
- `POST /predict`
- `POST /audit-content`
- `POST /audit-youtube`
- `GET /auth/youtube/start`
- `GET /auth/youtube/callback`
- `GET /auth/youtube/status`
- `GET /dashboard/summary`
- `GET /dashboard/recent-analyses`
- `GET /dashboard/platform-status`
- `GET /history`
- `GET /docs`

To verify the API in the browser:

- Open `http://127.0.0.1:8000/docs`
- Expand `POST /predict`
- Click `Try it out`
- Submit a payload such as:

```json
{
  "platform": "TikTok",
  "contentType": "Reel",
  "captionLength": 120,
  "hashtagsCount": 6,
  "postingHour": 19
}
```

## Frontend

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Current Real Capabilities

- Real prediction requests through `POST /predict`
- Real model inference from `backend/models/model.pkl`
- Real prediction history persistence in `backend/data/store.json`
- Real dashboard summary data derived from saved prediction history
- Real recent analyses list derived from saved prediction history
- Real platform connection status responses from stored connection records

## Dashboard Data

Dashboard data is generated only from stored backend records:

- `GET /dashboard/summary`
  Returns saved prediction counts plus averages computed from persisted prediction history.
- `GET /dashboard/recent-analyses`
  Returns recent items from persisted prediction history.
- `GET /dashboard/platform-status`
  Returns real connection records when available, otherwise honest `not_connected` states.
- `GET /history`
  Returns saved prediction history entries.

If no stored data exists yet, these endpoints return empty-safe values such as `0`, `null`, or empty arrays.

## Platform Integrations

Currently supported now:

- Local prediction workflow through the CreatorMind backend
- YouTube URL audit with official public YouTube Data API fields when `YOUTUBE_API_KEY` is configured
- YouTube OAuth connection flow that stores a connected account per CreatorMind user for future advanced analytics

Prepared only, not fully integrated yet:

- Instagram: prepared for official Insights API workflows
- YouTube: prepared for OAuth-backed private Analytics API workflows
- TikTok: prepared only for official profile and video metadata import workflows

Not supported yet:

- Fabricated TikTok analytics access
- Historical platform trend sync
- Archive sync from live social platforms

## YouTube Audit

`POST /audit-youtube` can now fetch these real public fields from the official YouTube
Data API:

- `title`
- `description`
- `published_at`
- `thumbnail_url`
- `channel_title`
- public `views`
- public `likes` when available
- public `comments` when available

This is public metadata only. Advanced YouTube analytics still require OAuth-backed
YouTube Analytics API access, including fields such as:

- `averageViewDuration`
- retention / audience watch behavior
- subscriber attribution
- traffic source analytics

The OAuth connection flow is now implemented and stores the connected YouTube account
state locally per application user. Advanced analytics fetch methods are still scaffolded, so CreatorMind
stays honest and does not fabricate retention or private analytics values yet.

## Model Verification

When the trained model is being used successfully, the backend logs should include messages like:

```text
INFO:backend.main:MODEL PATH: ...\backend\models\model.pkl
INFO:backend.main:MODEL EXISTS: True
INFO:backend.main:MODEL TYPE: <class 'dict'>
INFO:backend.main:USING MODEL BUNDLE: True
INFO:backend.main:FEATURE VECTOR: [1, 2, 120, 6, 19]
INFO:backend.main:USING REAL MODEL
```

If the model cannot be loaded, the backend will log that it is using the fallback heuristic instead.
