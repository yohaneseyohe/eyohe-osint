# Development

```bash
make install            # uv sync --all-extras; npm install
make dev                # API (reload) + web dev server
make test               # pytest + web typecheck/lint
make test-api           # pytest only (SQLite, offline)
EYOHE_PG_TEST=1 DATABASE_URL=postgresql+asyncpg://eyohe:eyohe@127.0.0.1:5432/eyohe make test-api
make lint / make format / make typecheck
make migration m="add column"   # autogenerate Alembic revision; review it before committing
make seed               # admin user; add --demo via: cd apps/api && uv run python -m eyohe.cli seed --demo
```

Conventions: Python 3.12, `ruff` (line length 120), `mypy --strict`, Pydantic v2 schemas for every
request/response, services own transactions, collectors never touch the DB, comments explain *why*.
Frontend: TypeScript strict, TanStack Query for server state, Zustand for UI state, shadcn-style
components in `src/components/ui`.

Tests live in `apps/api/tests/`: unit (normalisation, SSRF, confidence, classification, extraction,
query policy, dedupe), integration (API routers, search providers with `respx`, collectors with
mocked HTTP), and `test_acceptance.py` — the offline end-to-end workflow from the specification.

Adding a collector: subclass `BaseCollector`, return a `CollectResult` with provenance, register it
in `collectors/plugins.py`, add a `TASK_CATALOGUE` entry and template placement, write a mocked
test, and document it in `docs/collectors.md`.

Adding an AI tool: add a Pydantic input model and handler in `ai/tools.py` with a timeout and call
budget; validate everything the model passes in; never let it write unverified facts.
