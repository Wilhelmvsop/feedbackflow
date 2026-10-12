# Development notes

## Architecture

```
widget ──POST /api/public/{slug}/feedback──┐
                                           ▼
dashboard ──Bearer token──▶ FastAPI routers ──▶ services.py ──▶ SQLAlchemy ──▶ SQLite / PostgreSQL
                                           ▲          │
MCP client ──Bearer token──▶ mcp_server.py ┘          └──▶ analysis.py (local | OpenAI-compatible)
```

- **Routers are thin.** Validation lives in `schemas.py`; workspace scoping, idempotency, and state transitions live in `services.py`, which both the HTTP API and the MCP server call. Services raise `NotFound` / `Conflict`, which `main.py` maps to 404 / 409.
- **Workspace isolation.** Every team lookup filters by the authenticated user's `workspace_id`. Tests in `tests/test_feedback.py` assert foreign IDs return 404 and are skipped by bulk updates.
- **Sessions.** Login issues a random token; only its SHA-256 digest is stored, with `expires_at` (`TOKEN_TTL_HOURS`). Expired tokens for a user are pruned on their next login.
- **Analysis.** `enqueue_analysis` is idempotent (returns the current queued/running/succeeded analysis) and versioned; retry is allowed only after failure. Work runs in a FastAPI background task with its own DB session. On startup `recover_interrupted_analyses` marks orphaned queued/running rows as failed.
- **Requirement traceability.** `requirement_sources` links requirements to feedback; a unique `feedback_id` makes draft creation idempotent. Status moves only `draft → confirmed → delivered` (`REQUIREMENT_TRANSITIONS`); delivery resolves sources.
- **Frontend data flow.** `api/client.ts` attaches the token and turns errors into `ApiError`; a 401 clears the session globally. `api/queries.ts` wraps endpoints in TanStack Query hooks; the feedback detail query polls only while its analysis is queued or running.

## Database migrations

The schema is owned by Alembic (`backend/migrations`). With `AUTO_MIGRATE=true` (default) the API upgrades to head on start; set it to `false` for processes that should not migrate (the MCP service).

```sh
make migration m="add feedback priority"   # edit the generated file, then
make migrate
```

`tests/test_migrations.py` fails if models and migrations drift, and CI runs `alembic check` against PostgreSQL.

> Upgrading from the 0.1 prototype: its tables were created with `create_all` and differ from the 0.2 schema (workspace slugs, hashed tokens, requirement link table). Start from a fresh database.

## Testing

- Backend: `cd backend && pytest` — in-memory SQLite per test; `conftest.py` provides two workspaces so isolation is exercised everywhere.
- Frontend: `cd frontend && npm test` — Vitest + Testing Library with a small `fetch` fake (`src/test/utils.tsx`).

## Conventions

- Python: `ruff format` + `ruff check` (config in `backend/pyproject.toml`).
- TypeScript: strict mode, ESLint flat config with `react-hooks`.
- Commits: conventional style (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`).
