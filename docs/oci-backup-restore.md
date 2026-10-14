# OCI PostgreSQL backup and restore

Backups are PostgreSQL custom-format dumps written to the untracked `backups/` directory and uploaded to the configured private OCI bucket through the official OCI Python SDK. Database port 5432 remains internal.

## Create and upload

From the repository root on the VM, load `.env.oci` into the shell without displaying values and run:

```sh
set -a
. ./.env.oci
set +a
sh scripts/oci/backup-postgres.sh
```

The script uses `pg_dump -Fc`, mode-restrictive output, OCI object prefix `OCI_BACKUP_PREFIX/YYYY/MM/DD/`, and deletes local dumps older than `BACKUP_RETENTION_DAYS`. It does not delete remote objects. Schedule it with a systemd timer or cron under the deployment user. Alert on non-zero exit and periodically compare local logs with bucket objects.

## Restore test

Download the selected object through the OCI Console/CLI to `backups/` without committing it. Verify file size and checksum from the backup record. Prefer testing in an isolated database/VM. For the production database, stop application traffic, take a fresh backup, then run:

```sh
sh scripts/oci/restore-postgres.sh backups/creatormind-YYYYMMDDTHHMMSSZ.dump
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm app alembic upgrade head
docker compose --env-file .env.oci -f docker-compose.oci.yml restart app
```

The restore requires typing `RESTORE` and uses `pg_restore --clean --if-exists --no-owner`. Validate `/health`, record counts, Instagram connections, migration revision, and a non-destructive write/read. A health response alone does not prove data correctness.

Keep an encrypted off-instance recovery copy and define retention/RPO/RTO appropriate to the product. OCI bucket encryption at rest does not replace tight IAM, key protection, and restore drills. API signing keys, `.env.oci`, dumps, and checksums that reveal sensitive names must stay outside Git.
