# Eyohe OSINT task runner
SHELL := /bin/bash
API := apps/api
WEB := apps/web
UV  := cd $(API) && uv

.PHONY: help install dev dev-api dev-web test test-api test-web lint format typecheck migrate migration seed \
        docker-up docker-down docker-logs backup restore health setup clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Detect dependencies and prepare .env
	@bash infrastructure/scripts/setup.sh

install: ## Install API and web dependencies
	$(UV) sync --all-extras
	cd $(WEB) && npm install

dev: ## Run API and web dev servers together
	@bash infrastructure/scripts/dev.sh

dev-api: ## Run the API with reload
	$(UV) run uvicorn eyohe.main:app --reload --host 0.0.0.0 --port $${API_PORT:-8000}

dev-web: ## Run the Next.js dev server
	cd $(WEB) && npm run dev

worker: ## Run the arq background worker (JOB_BACKEND=arq)
	$(UV) run arq eyohe.worker.WorkerSettings

test: test-api test-web ## Run all tests

test-api: ## Run Python tests
	$(UV) run pytest -q

test-web: ## Run web type-check and lint as the test gate
	cd $(WEB) && npm run typecheck && npm run lint

lint: ## Lint Python and TypeScript
	$(UV) run ruff check .
	cd $(WEB) && npm run lint

format: ## Format Python and TypeScript
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	cd $(WEB) && npx prettier --write "src/**/*.{ts,tsx,css}" >/dev/null 2>&1 || true

typecheck: ## Type-check Python (mypy) and TypeScript (tsc)
	$(UV) run mypy eyohe
	cd $(WEB) && npm run typecheck

migrate: ## Apply database migrations
	$(UV) run alembic upgrade head

migration: ## Create a new migration: make migration m="add foo"
	$(UV) run alembic revision --autogenerate -m "$(m)"

seed: ## Create the admin user and optional demo case (DEMO DATA)
	$(UV) run python -m eyohe.cli seed

health: ## Print system health from the running API
	@curl -s http://localhost:$${API_PORT:-8000}/api/v1/health | python3 -m json.tool

docker-up: ## Start core services with Docker Compose
	docker compose up -d --build

docker-down: ## Stop Docker Compose services
	docker compose down

docker-logs: ## Tail Docker Compose logs
	docker compose logs -f --tail=200

backup: ## Back up database and evidence vault to ./backups
	@bash infrastructure/scripts/backup.sh

restore: ## Restore from a backup: make restore f=backups/eyohe-YYYYmmdd-HHMMSS.tar.gz
	@bash infrastructure/scripts/restore.sh "$(f)"

clean: ## Remove caches and build output
	rm -rf $(API)/.pytest_cache $(API)/.ruff_cache $(API)/.mypy_cache $(WEB)/.next
