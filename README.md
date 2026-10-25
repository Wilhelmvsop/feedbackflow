

https://github.com/user-attachments/assets/1e1de164-6819-46b5-94ef-09b3fdd4d959



# FeedbackFlow

Turn scattered user feedback into traceable, reviewable product work.

FeedbackFlow collects feedback through an embeddable widget, lets a team triage it in a dashboard, drafts a requirement from each item (offline by default, optionally with an LLM), and keeps every requirement linked to the feedback it came from — through human confirmation, task breakdown, and delivery.

| Layer | Stack |
| --- | --- |
| API | FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| Dashboard | React 18 · TypeScript · TanStack Query · Vite |
| Data | SQLite (local) / PostgreSQL (Docker, production) |
| Notifier | Node.js 22 · TypeScript · Fastify · Vitest — webhook/Slack fan-out service |
| Integrations | Embeddable JS widget · MCP tool server |
| Infrastructure | Docker · Kubernetes (Kustomize, kind) · Azure Container Apps · ACR · Azure Database for PostgreSQL · Bicep |
| Quality | pytest (93% coverage) · Vitest + Testing Library · Ruff · ESLint · GitHub Actions (CI + kind e2e + CD) |

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

The image builds the dashboard, runs as a non-root user, applies migrations on start, and exposes health checks at `/api/health` (database) and `/api/health/live` (process). Compose also starts the notifier; set `WEBHOOK_URLS` to have it deliver events.

### Kubernetes and Azure

```sh
make kind-up                  # local kind cluster at http://localhost:8080, with an end-to-end smoke test
deploy/azure/bootstrap.sh     # Azure Container Apps + ACR + PostgreSQL Flexible Server (after `az login`)
```

- [docs/KUBERNETES.md](docs/KUBERNETES.md) covers the manifests, health checks and Secrets.
- [docs/DEPLOY_AZURE.md](docs/DEPLOY_AZURE.md) covers the Azure architecture, cost and GitHub OIDC continuous deployment.
- [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) is the one-click Render alternative.

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
services/notifier/       TypeScript webhook notifier (Fastify + Vitest)
deploy/k8s/              Kustomize base + kind overlay, kind-up.sh
deploy/azure/            Bicep template + bootstrap.sh
```

## Features

- **Widget intake** — `POST /api/public/{workspace}/feedback`, idempotent via a per-submission key, rate-limited per IP. The widget collects only the typed message, a category, and (with consent) the page path.
- **Triage inbox** — server-side search, filters and pagination; workspace-wide stats; bulk status changes; inline tags/assignee.
- **Analysis** — versioned and idempotent per feedback item, runs in the background, retryable after failure. Analyses interrupted by a restart are marked failed on boot so they can be retried.
- **Requirements** — one draft per feedback item, linked through a join table; editable fields; tasks; enforced lifecycle `draft → confirmed → delivered`; delivery resolves source feedback.
- **Auth** — PBKDF2 password hashes; opaque bearer tokens stored only as SHA-256 digests, with expiry; login rate limiting. Every team query is scoped to the caller's workspace.
- **Notifications** — new widget feedback and requirement status changes are published to the [notifier](services/notifier/README.md), which delivers them to Slack or HMAC-signed JSON webhooks with retries.
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

CI (`.github/workflows/ci.yml`) does the following:

- runs lint, type-checks and all three test suites;
- applies migrations against PostgreSQL with `alembic check`;
- deploys both images to a kind cluster and checks the widget → API → notifier → webhook path end to end;
- on `main`, pushes the images to Azure Container Registry and rolls them out to Azure Container Apps.

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for architecture notes and [skills/feedback-to-requirement/SKILL.md](skills/feedback-to-requirement/SKILL.md) for the agent workflow skill.

## Known limitations

- Analysis runs as an in-process background task. Multi-instance deployments should move it to a durable queue (e.g. Celery/RQ + Redis); the rate limiter is also per-process.
- There is no self-service sign-up or user management yet; the seeded demo account is for evaluation.
- The MCP server is bound to a single workspace via `MCP_WORKSPACE_SLUG`.
