#!/bin/sh
set -eu
umask 077
mkdir -p backups
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="backups/creatormind-${timestamp}.dump"
docker compose --env-file .env.oci -f docker-compose.oci.yml exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$backup"
# The dump is intentionally created with mode 0600. Run the one-shot upload
# container as the invoking host user so it can read the bind-mounted file
# without making a production database backup world-readable.
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm --no-deps --user "$(id -u):$(id -g)" app python -m scripts.oci.upload_backup "/$backup" --prefix "${OCI_BACKUP_PREFIX:-database-backups}"
find backups -type f -name '*.dump' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
echo "Backup created and upload requested: $backup"
