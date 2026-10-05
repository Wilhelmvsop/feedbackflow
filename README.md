# FeedbackFlow

Turn scattered user feedback into traceable, reviewable product work. This repository contains a small FastAPI service, a React + TypeScript workspace, an embeddable JavaScript widget, and an MCP tool server.

## Run locally

Requirements: Python 3.11+ and Node.js 20+.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

For a single-process demo deployment, build the dashboard and start the API:

```sh
cd frontend && npm install && npm run build
cd .. && uvicorn app.main:app --app-dir backend --host 0.0.0.0
```

The static dashboard and widget are served by the API after the frontend build. `docker compose up --build` starts the app with PostgreSQL for a shareable self-hosted demo; configure a strong `DEMO_PASSWORD` first. No public hosting account is configured in this workspace.

The API creates a demo workspace on first start. Sign in with `demo@feedbackflow.local` / `feedbackflow-demo`. Change `DATABASE_URL` and `DEMO_PASSWORD` before exposing a deployment. SQLite is the zero-config local default; PostgreSQL works through `DATABASE_URL=postgresql+psycopg://...`.

Without an API key, analysis uses the bundled deterministic provider so the demo works offline. To enable model-generated suggestions, set `AI_API_KEY`, and optionally `AI_BASE_URL` / `AI_MODEL`. This sends feedback text to that configured model provider; the app does not send it anywhere by default. Responses are schema-checked, source-linked, and remain drafts for human review.

API docs are at `/docs`. Start the optional MCP tool server in a second process with `PYTHONPATH=backend python -m app.mcp_server`; it listens on `http://127.0.0.1:8001/mcp`. The widget source is `public/feedbackflow.js`; after building the frontend, the API serves it from `/feedbackflow.js`. Embed it with:

```html
<script src="https://YOUR_HOST/feedbackflow.js" data-api="https://YOUR_HOST/api" data-project="demo"></script>
```

Run backend regression tests with `PYTHONPATH=backend pytest backend/tests`.

The widget asks before including the current pathname. It never reads page text, screenshots, or form values. For production, put the API and static assets behind HTTPS and configure workspace accounts instead of relying on the seeded demo login.

## Product boundaries

- Feedback text is untrusted data. It cannot change tool permissions or system behavior.
- Analysis uses a deterministic local provider by default; an external model is called only when configured. Suggestions retain source feedback IDs and require a human to edit and confirm them.
- Workspace ownership is enforced on every resource lookup. Analysis work is idempotent per feedback item and retryable.
- The demo login is for local evaluation only. Production deployment needs managed secrets, HTTPS, account lifecycle, and a durable job queue such as Celery/Redis.

## Development phases

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the implementation sequence and checks, and [skills/feedback-to-requirement/SKILL.md](skills/feedback-to-requirement/SKILL.md) for the reusable workflow Skill. The provided environment mounts `.git` read-only, so Git commits cannot be created here.
