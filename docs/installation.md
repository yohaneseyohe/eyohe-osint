# Installation

Eyohe OSINT is designed for a single analyst workstation (tested on Kali Linux, 16 GB RAM).

## Requirements

| Component | Required | Notes |
|---|---|---|
| Python 3.12 + [uv](https://astral.sh/uv) | yes | `uv` installs 3.12 automatically |
| Node.js ≥ 20 + npm | yes | web UI |
| PostgreSQL 16 | recommended | SQLite fallback for development: `DATABASE_URL=sqlite+aiosqlite:///./data/eyohe.sqlite3` |
| Docker + Compose | optional | easiest way to run PostgreSQL, Redis, SearXNG, Neo4j |
| Redis 7 | optional | query cache, rate-limit counters, event relay, arq worker |
| Ollama | optional | local AI (planning, research loop, analyst). Pull a model: `ollama pull qwen3:8b` |
| Chromium or WeasyPrint | optional | PDF reports / screenshots (Chromium is preinstalled on Kali) |

## Steps

```bash
make setup           # dependency detection + .env with a generated SECRET_KEY
make install
docker compose up -d postgres redis       # skip if using SQLite / native services
docker compose --profile search up -d     # SearXNG on http://127.0.0.1:8080 (JSON API enabled)
make migrate
make seed            # creates the admin user (or use the web first-run wizard)
make dev
```

Services:

- API: http://127.0.0.1:8000 — OpenAPI docs at `/api/docs`
- Web: http://localhost:3000
- Metrics: http://127.0.0.1:8000/api/v1/metrics (blocked by Caddy in production)

## Full Docker deployment

```bash
cp .env.example .env && edit .env            # set SECRET_KEY, COOKIE_SECURE=true behind TLS
docker compose up -d --build                 # postgres, redis, api, web, caddy
docker compose --profile search up -d        # SearXNG
docker compose --profile worker up -d        # arq worker (set JOB_BACKEND=arq)
docker compose --profile neo4j up -d         # Neo4j (set GRAPH_BACKEND=neo4j)
```

Caddy serves the UI on port 80 and proxies `/api/*` to the API. Point a hostname at the machine and
replace `:80` in `infrastructure/caddy/Caddyfile` to get automatic TLS.

## Resource notes

- Ollama on CPU is slow: `qwen3:8b` generates ~2 tokens/s on a laptop CPU. AI planning therefore
  runs in the background and the plan falls back to the template on timeout. Smaller models
  (`qwen3:4b`, `llama3.2:3b`) are much faster; set `OLLAMA_MODEL` accordingly.
- Neo4j needs ~1 GB RAM; the PostgreSQL graph backend is the default and is sufficient for
  thousands of entities.
- The evidence vault grows with snapshots. Use `EVIDENCE_RETENTION_DAYS` and `make backup`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Health shows Ollama OFFLINE although `ollama serve` runs | `localhost` resolves to `::1` on some hosts; Eyohe rewrites `localhost` to `127.0.0.1`, but check `OLLAMA_URL` |
| Search task skipped: "No search provider is configured" | start SearXNG (`docker compose --profile search up -d`) or set an API key in `.env` |
| SearXNG returns 403 | JSON output disabled; the bundled `infrastructure/docker/searxng/settings.yml` enables it |
| PDF report FAILED | install WeasyPrint extras (`uv sync --extra pdf`) or set `CHROMIUM_PATH` |
| GitHub collector "rate limit" | unauthenticated API allows 60 req/h; set `GITHUB_TOKEN` (also enables code search) |
