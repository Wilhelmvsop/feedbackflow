# Development notes

## Delivery phases

1. **Foundation:** FastAPI, SQLAlchemy models, demo workspace, local/PostgreSQL configuration, and run instructions.
2. **Feedback intake and isolation:** public widget endpoint plus workspace-scoped authenticated feedback search, edits, and detail.
3. **Analysis and traceability:** queued/versioned analysis, retry after failure, source-linked requirements, and human confirmation/delivery.
4. **Team workflow:** React + TypeScript dashboard with feedback triage, requirement editing, acceptance criteria, and tasks.
5. **Integrations and handoff:** MCP tools, reusable `skills/feedback-to-requirement/SKILL.md`, widget install instructions, and deployment notes.

Suggested commit boundaries: `feat: scaffold API and workspace login`; `feat: add feedback widget and triage`; `feat: add traceable requirement analysis`; `feat: build requirement workflow dashboard`; `feat: expose MCP tools and self-hosted demo`.

Git history could not be recorded in this environment: `.git` is mounted read-only (`git init` fails while creating `.git/hooks`). Create these commits after opening the workspace with a writable Git metadata directory.

## Architecture and constraints

- SQLAlchemy accepts PostgreSQL through `DATABASE_URL`; SQLite is the local default.
- Authentication uses salted PBKDF2 password hashes and opaque bearer tokens. Every team API resource query includes the authenticated workspace ID.
- Analysis runs as a FastAPI background task and stores a unique version per feedback item. This is process-local, not a durable queue; production should move to a persistent queue.
- The default analysis provider creates conservative deterministic suggestions offline. When configured, a model provider receives only the feedback message and returns schema-checked suggestions; model use is opt-in through environment configuration. Similar feedback suggestions use shared wording, category, and page path; all results retain source IDs and remain drafts.
- MCP exposes four workspace-scoped tools. The initial tools bind to the seeded demo workspace; replace this with per-client credentials before multi-workspace MCP hosting.
- The widget collects only the typed message, selected category, and an explicitly opted-in pathname. It does not inspect page contents, screenshots, or form fields.
- Docker Compose starts PostgreSQL and the combined API/dashboard for a self-hosted demo. No public hosting account is configured in this workspace.

## Verification

Run `PYTHONPATH=backend pytest backend/tests` for workspace isolation, login, widget submission idempotency, analysis retry/versioning, source traceability, delivery updates, and untrusted input checks. Build the frontend with `cd frontend && npm install && npm run build`.
