#!/usr/bin/env bash
# Restores a backup created by backup.sh. Usage: restore.sh backups/eyohe-<ts>.tar.gz
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] && set -a && . ./.env && set +a
f="${1:?backup file required}"
work=$(mktemp -d)
tar -xzf "$f" -C "$work"
echo "This will overwrite the current database and evidence vault. Type RESTORE to continue:"
read -r confirm; [ "$confirm" = "RESTORE" ] || { echo "aborted"; exit 1; }
case "${DATABASE_URL:-}" in
  postgresql*)
    url="${DATABASE_URL/postgresql+asyncpg/postgresql}"
    if command -v pg_restore >/dev/null; then pg_restore --clean --if-exists --no-owner -d "$url" "$work/db.dump";
    else docker compose exec -T postgres pg_restore --clean --if-exists --no-owner -U "${POSTGRES_USER:-eyohe}" -d "${POSTGRES_DB:-eyohe}" < "$work/db.dump"; fi ;;
  sqlite*)
    cp "$work/db.sqlite3" "${DATABASE_URL#sqlite+aiosqlite:///}" ;;
esac
rsync -a --delete "$work/data/evidence/" data/evidence/ 2>/dev/null || cp -r "$work/data/evidence/." data/evidence/
rsync -a "$work/data/reports/" data/reports/ 2>/dev/null || true
rsync -a "$work/data/screenshots/" data/screenshots/ 2>/dev/null || true
rm -rf "$work"
echo "Restore complete."
