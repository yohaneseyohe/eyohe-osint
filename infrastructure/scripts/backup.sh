#!/usr/bin/env bash
# Creates backups/eyohe-<timestamp>.tar.gz containing a database dump and the evidence vault.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] && set -a && . ./.env && set +a
ts=$(date +%Y%m%d-%H%M%S)
work=$(mktemp -d)
mkdir -p backups
case "${DATABASE_URL:-}" in
  postgresql*)
    url="${DATABASE_URL/postgresql+asyncpg/postgresql}"
    if command -v pg_dump >/dev/null; then pg_dump --no-owner --format=custom "$url" > "$work/db.dump";
    else docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-eyohe}" -Fc "${POSTGRES_DB:-eyohe}" > "$work/db.dump"; fi ;;
  sqlite*)
    f="${DATABASE_URL#sqlite+aiosqlite:///}"; cp "$f" "$work/db.sqlite3" ;;
  *) echo "Unknown DATABASE_URL"; exit 1 ;;
esac
cp .env "$work/env.backup" 2>/dev/null || true
tar -czf "backups/eyohe-${ts}.tar.gz" -C "$work" . -C "$PWD" data/evidence data/reports data/screenshots
rm -rf "$work"
echo "Backup written: backups/eyohe-${ts}.tar.gz"
