PY := .venv/bin/python
export PYTHONPATH := backend

.PHONY: install dev-api dev-web dev-notifier mcp migrate migration test lint format build up kind-up kind-down

install:  ## Install backend + frontend dependencies
	python3 -m venv .venv
	$(PY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci
	cd services/notifier && npm ci

dev-api:  ## API on :8000 with auto-reload (migrates + seeds demo data on start)
	$(PY) -m uvicorn app.main:app --app-dir backend --reload

dev-web:  ## Dashboard on :5173, proxying /api to :8000
	cd frontend && npm run dev

dev-notifier:  ## Notifier on :8002 (set NOTIFIER_URL=http://localhost:8002 for the API to publish to it)
	cd services/notifier && npm run dev

mcp:  ## MCP server on 127.0.0.1:8001/mcp
	$(PY) -m app.mcp_server

migrate:  ## Apply database migrations
	cd backend && ../$(PY) -m alembic upgrade head

migration:  ## Autogenerate a migration: make migration m="add foo"
	cd backend && ../$(PY) -m alembic revision --autogenerate -m "$(m)"

test:  ## Run all tests
	cd backend && ../$(PY) -m pytest
	cd frontend && npm test
	cd services/notifier && npm test

lint:  ## Lint and type-check everything
	cd backend && ../$(PY) -m ruff check . && ../$(PY) -m ruff format --check .
	cd frontend && npm run lint && npm run typecheck
	cd services/notifier && npm run typecheck

format:  ## Auto-format backend code
	cd backend && ../$(PY) -m ruff format . && ../$(PY) -m ruff check --fix .

build:  ## Build the dashboard into backend/static
	cd frontend && npm run build

up:  ## Full stack with PostgreSQL via Docker Compose
	docker compose up --build

kind-up:  ## Build images and run the stack on a local kind cluster (http://localhost:8080)
	deploy/k8s/kind-up.sh

kind-down:  ## Delete the local kind cluster
	kind delete cluster --name feedbackflow
