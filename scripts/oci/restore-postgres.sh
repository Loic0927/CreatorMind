#!/bin/sh
set -eu
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "Usage: $0 backups/file.dump" >&2
  exit 2
fi
printf 'This replaces data in the configured database. Type RESTORE to continue: '
read -r confirmation
[ "$confirmation" = "RESTORE" ] || { echo "Cancelled"; exit 1; }
docker compose --env-file .env.oci -f docker-compose.oci.yml exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$1"
echo "Restore completed; run the health and application checks now."
