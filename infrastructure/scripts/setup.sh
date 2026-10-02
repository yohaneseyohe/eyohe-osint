#!/usr/bin/env bash
# Eyohe OSINT setup: detects required tooling, explains what is missing, prepares .env.
set -uo pipefail
cd "$(dirname "$0")/../.."

ok()   { printf "  \033[32m✔\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✘\033[0m %s\n" "$1"; }

echo "Eyohe OSINT — environment check"
echo

missing=0
if command -v python3 >/dev/null; then ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"; else bad "Python 3 not found (apt install python3)"; missing=1; fi
if command -v uv >/dev/null; then ok "uv $(uv --version | cut -d' ' -f2)"; else bad "uv not found: curl -LsSf https://astral.sh/uv/install.sh | sh"; missing=1; fi
if command -v node >/dev/null; then
  v=$(node --version | tr -d v | cut -d. -f1); if [ "$v" -ge 20 ]; then ok "Node $(node --version)"; else bad "Node >= 20 required (found $(node --version))"; missing=1; fi
else bad "Node.js not found (https://nodejs.org)"; missing=1; fi
if command -v npm >/dev/null; then ok "npm $(npm --version)"; else bad "npm not found"; missing=1; fi
if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then ok "Docker $(docker --version | cut -d' ' -f3 | tr -d ,) (daemon running)"; else warn "Docker installed but daemon not reachable (sudo systemctl start docker)"; fi
else warn "Docker not found — you can still run PostgreSQL/Redis natively or use the SQLite fallback"; fi
if command -v ollama >/dev/null; then
  if curl -fsS --max-time 2 "${OLLAMA_URL:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
    models=$(curl -fsS --max-time 3 "${OLLAMA_URL:-http://localhost:11434}/api/tags" | python3 -c 'import sys,json;print(", ".join(m["name"] for m in json.load(sys.stdin)["models"]) or "none")' 2>/dev/null)
    ok "Ollama running — models: ${models}"
  else warn "Ollama installed but not running (ollama serve). AI features will show OFFLINE."; fi
else warn "Ollama not found (https://ollama.com). AI planning/analysis will be unavailable; collectors still work."; fi
if command -v chromium >/dev/null || command -v chromium-browser >/dev/null || command -v google-chrome >/dev/null; then ok "Chromium available (screenshots, PDF fallback)"; else warn "Chromium not found — screenshots disabled, PDF needs WeasyPrint"; fi
if command -v psql >/dev/null; then ok "psql client present"; else warn "psql client not found (optional; needed for native backups)"; fi

echo
if [ ! -f .env ]; then
  cp .env.example .env
  secret=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${secret}|" .env
  ok "Created .env with a generated SECRET_KEY"
else
  ok ".env already exists (left unchanged)"
fi
mkdir -p data/evidence data/reports data/screenshots data/exports data/cache
ok "Data directories ready under ./data"

echo
if [ "$missing" -eq 1 ]; then
  bad "Some required dependencies are missing. Install them and re-run: make setup"
  exit 1
fi
echo "Next steps:"
echo "  make install          # install API + web dependencies"
echo "  docker compose up -d postgres redis   # or set DATABASE_URL to the SQLite fallback in .env"
echo "  make migrate && make seed"
echo "  make dev              # http://localhost:3000"
