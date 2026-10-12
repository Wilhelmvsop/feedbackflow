# FeedbackFlow

Turn scattered user feedback into traceable, reviewable product work.

FeedbackFlow collects feedback through an embeddable widget, lets a team triage it in a dashboard, drafts a requirement from each item (offline by default, optionally with an LLM), and keeps every requirement linked to the feedback it came from — through human confirmation, task breakdown, and delivery.

| Layer | Stack |
| --- | --- |
| API | FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| Dashboard | React 18 · TypeScript · TanStack Query · Vite |
| Data | SQLite (local) / PostgreSQL (Docker, production) |
| Integrations | Embeddable JS widget · MCP tool server |
| Quality | pytest (92% coverage) · Vitest + Testing Library · Ruff · ESLint · GitHub Actions |

## Quick start

Requirements: Python 3.11+, Node.js 20+.

```sh
make install     # .venv + backend deps, frontend deps
make dev-api     # http://localhost:8000  (migrates DB, seeds demo workspace)
make dev-web     # http://localhost:5173  (proxies /api to :8000)
```

Sign in with `demo@feedbackflow.local` / `feedbackflow-demo`. API docs live at <http://localhost:8000/docs>.

Configuration is read from environment variables or a `.env` file — see [`.env.example`](.env.example) for every option.

### With Docker (PostgreSQL)

```sh
export DEMO_PASSWORD='choose-a-strong-password'
docker compose up --build                                   # app on :8000
MCP_ACCESS_TOKEN=$(openssl rand -hex 24) docker compose --profile mcp up --build   # + MCP on :8001
```

The image builds the dashboard, runs as a non-root user, applies migrations on start, and exposes a health check at `/api/health`. See [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) for a one-click Render deployment.

## Project layout

```
backend/
  app/
    main.py          app factory, lifespan (migrate → recover → seed), error mapping
    config.py        typed settings (pydantic-settings)
    models.py        SQLAlchemy models + status enums / allowed transitions
    schemas.py       request/response models (drive the OpenAPI schema)
    services.py      workspace-scoped business logic shared by API and MCP
    analysis.py      offline analyzer + optional OpenAI-compatible provider
    routers/         auth · public (widget intake) · feedback · requirements
    deps.py          DB session, bearer auth, rate limiters
    mcp_server.py    MCP tools over the same services
  migrations/        Alembic
  tests/             pytest suite
frontend/src/
  api/               fetch client, typed endpoints, React Query hooks
  components/        inbox, drawers, requirements, widget setup
  lib/               auth context, toasts, formatting
public/feedbackflow.js   embeddable widget
```

## Features

- **Widget intake** — `POST /api/public/{workspace}/feedback`, idempotent via a per-submission key, rate-limited per IP. The widget collects only the typed message, a category, and (with consent) the page path.
- **Triage inbox** — server-side search, filters and pagination; workspace-wide stats; bulk status changes; inline tags/assignee.
- **Analysis** — versioned and idempotent per feedback item, runs in the background, retryable after failure. Analyses interrupted by a restart are marked failed on boot so they can be retried.
- **Requirements** — one draft per feedback item, linked through a join table; editable fields; tasks; enforced lifecycle `draft → confirmed → delivered`; delivery resolves source feedback.
- **Auth** — PBKDF2 password hashes; opaque bearer tokens stored only as SHA-256 digests, with expiry; login rate limiting. Every team query is scoped to the caller's workspace.
- **MCP** — `list_feedback`, `get_feedback`, `create_requirement_draft`, `get_requirement`, bound to one workspace and bearer-protected when exposed beyond localhost.

### Embedding the widget

```html
<script src="https://YOUR_HOST/feedbackflow.js" data-api="https://YOUR_HOST/api" data-project="demo"></script>
```

`data-project` is the workspace slug. The dashboard's **Widget setup** dialog generates this snippet for you. When embedding on another origin, add it to `CORS_ORIGINS`.

### Model-generated drafts (optional)

By default analysis uses a deterministic local provider and nothing leaves the server. Setting `AI_API_KEY` (plus optionally `AI_BASE_URL` / `AI_MODEL`) sends the feedback text — and only that — to an OpenAI-compatible endpoint. The response is schema-validated; invalid output becomes a retryable failure. Feedback is passed as a JSON data value and treated as untrusted input.

## Development

```sh
make test        # pytest + vitest
make lint        # ruff + eslint + tsc
make format      # ruff format + autofix
make migration m="describe change"   # autogenerate an Alembic revision
```

CI (`.github/workflows/ci.yml`) runs lint, type-checks, both test suites, applies migrations against PostgreSQL with `alembic check`, and builds the Docker image.

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for architecture notes and [skills/feedback-to-requirement/SKILL.md](skills/feedback-to-requirement/SKILL.md) for the agent workflow skill.

## Known limitations

- Analysis runs as an in-process background task. Multi-instance deployments should move it to a durable queue (e.g. Celery/RQ + Redis); the rate limiter is also per-process.
- There is no self-service sign-up or user management yet; the seeded demo account is for evaluation.
- The MCP server is bound to a single workspace via `MCP_WORKSPACE_SLUG`.
