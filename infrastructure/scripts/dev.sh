#!/usr/bin/env bash
# Runs API and web dev servers together; Ctrl+C stops both.
set -uo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] && set -a && . ./.env && set +a
trap 'kill 0' EXIT INT TERM
(cd apps/api && uv run uvicorn eyohe.main:app --reload --host 0.0.0.0 --port "${API_PORT:-8000}") &
(cd apps/web && npm run dev -- --port "${WEB_PORT:-3000}") &
wait
