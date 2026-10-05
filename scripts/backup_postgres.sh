#!/usr/bin/env bash
# VigilantEye PostgreSQL backup (non-destructive).
# Uses DATABASE_URL or POSTGRES_* env vars — never hardcode passwords.
#
# Example (Compose):
#   ./scripts/backup_postgres.sh
#
# Retention (operator policy): keep daily for 14 days, weekly for 8 weeks.
# Store encrypted off-host; verify with restore test monthly.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/vigilanteye_${STAMP}.dump"

if [[ -n "${DATABASE_URL:-}" ]]; then
  # Strip SQLAlchemy driver prefix for pg_dump
  PGURL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
  pg_dump --format=custom --file="$OUT_FILE" "$PGURL"
elif docker compose ps db --status running >/dev/null 2>&1; then
  docker compose exec -T db \
    pg_dump -U "${POSTGRES_USER:-vigilant}" -d "${POSTGRES_DB:-vigilant_eye}" -Fc \
    > "$OUT_FILE"
else
  echo "Set DATABASE_URL or run against a live Compose db service." >&2
  exit 1
fi

echo "Backup written: $OUT_FILE"
ls -lh "$OUT_FILE"
