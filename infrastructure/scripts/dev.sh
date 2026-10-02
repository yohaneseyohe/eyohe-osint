#!/usr/bin/env bash
# Runs API and web dev servers together; Ctrl+C stops both.
# .env is read by the apps themselves (pydantic-settings); here we only need the ports.
set -uo pipefail
cd "$(dirname "$0")/../.."
port_from_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '"' ; }
API_PORT="${API_PORT:-$(port_from_env API_PORT)}"; API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-$(port_from_env WEB_PORT)}"; WEB_PORT="${WEB_PORT:-3000}"
for p in "$API_PORT" "$WEB_PORT"; do
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}$"; then
    echo "Port ${p} is already in use (pid: $(fuser "${p}/tcp" 2>/dev/null | tr -s ' ')). Stop that process or set API_PORT/WEB_PORT in .env." >&2
    exit 1
  fi
done
trap 'kill 0' EXIT INT TERM
(cd apps/api && uv run uvicorn eyohe.main:app --reload --host 0.0.0.0 --port "${API_PORT}") &
(cd apps/web && npm run dev -- --port "${WEB_PORT}") &
wait
