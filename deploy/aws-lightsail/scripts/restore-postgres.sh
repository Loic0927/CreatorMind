#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEPLOY_DIR"
[[ $# -eq 1 ]] || { echo "Usage: $0 backups/FILE.dump" >&2; exit 2; }
backup_file="$(realpath "$1")"
backup_root="$(realpath "$DEPLOY_DIR/backups")"
[[ -f "$backup_file" && "$backup_file" == "$backup_root"/* ]] || { echo "Backup must be an existing file under $backup_root" >&2; exit 2; }
echo "WARNING: this restores $backup_file into the configured database and may replace existing objects."
read -r -p "Type RESTORE to continue: " confirmation
[[ "$confirmation" == "RESTORE" ]] || { echo "Cancelled."; exit 1; }
docker compose --env-file .env.production exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$backup_file"
