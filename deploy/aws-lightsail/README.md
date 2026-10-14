# AWS Lightsail deployment

This deployment runs the existing FastAPI application, PostgreSQL 17, and Caddy on one Ubuntu 24.04 Lightsail instance. It does not deploy the frontend or modify local JSON data. A 1 GB instance is the minimum target; enable a small swap file and monitor memory because image builds and PostgreSQL can briefly exceed that budget.

## Architecture and exposure

- Caddy is the only public container, on TCP 80/443 (and UDP 443 for HTTP/3).
- FastAPI listens on `0.0.0.0:8000` inside Docker and is reachable only through Caddy.
- PostgreSQL is attached only to the internal `data` network. Port 5432 is never published.
- The API joins `edge` and `data`, allowing HTTPS proxy traffic, database traffic, and required outbound Meta/Gemini calls.
- `migrate` is a manual Compose profile and never runs during normal API startup.

## 1. Create the host and network records

1. In Lightsail Sydney (`ap-southeast-2`), create an Ubuntu 24.04 LTS Linux instance and attach a Static IP.
2. Add a DNS A record such as `api.example.com` pointing to that Static IP. Wait for public DNS resolution before starting Caddy.
3. In the Lightsail firewall allow only TCP 22, 80, and 443. Restrict TCP 22 to your administrator IP where possible. Do not add public rules for 8000 or 5432.
4. Optionally allow UDP 443 for HTTP/3; HTTPS still works over TCP 443 without it.

## 2. Install Docker and clone the repository

Clone using your normal read-only/deploy credential, then from the repository root run:

```bash
sudo bash deploy/aws-lightsail/scripts/bootstrap-ubuntu.sh
```

Sign out and back in if the script adds your account to the `docker` group. The script installs Docker Engine and the Compose plugin; it does not install host PostgreSQL or change the Lightsail firewall.

## 3. Configure production

```bash
cd deploy/aws-lightsail
cp .env.example .env.production
chmod 600 .env.production
```

Generate values without placing them in shell history:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
openssl rand -base64 48
openssl rand -base64 36
```

Use the outputs for the Fernet key, OAuth state secret, and PostgreSQL password respectively. URL-encode the database password before putting the same password into `POSTBRIDGE_DATABASE_URL`; its host must be `db`, and the URL must use `postgresql+psycopg`. Set the public domain and exact HTTPS Instagram callback URI.

`.env.production` is Git- and Docker-ignored. Never commit it, paste it into issue reports, include it in terminal screenshots, or pass secrets as Docker build arguments. The template's `GEMINI_MODEL` is non-secret and selects the server-side model. `POSTGRES_*` is additionally required because the official database image uses those variables to initialize and operate the database.

Before starting, confirm placeholders are gone without printing values:

```bash
grep -n 'replace-with\|example.com' .env.production && echo 'Replace every reported placeholder'
```

## 4. Build, start, and migrate

The deployment script does not pull Git. Review and run `git pull --ff-only` yourself when you intend to update code.

```bash
bash scripts/deploy.sh
bash scripts/migrate.sh
curl --fail https://api.example.com/health
```

The migration script displays the operation and requires typing `MIGRATE`. Run it after the database is healthy and before exercising database-backed Instagram routes. It never downgrades.

Update the Meta app configuration so the valid redirect URI exactly equals `POSTBRIDGE_INSTAGRAM_REDIRECT_URI`. For the mobile app, build it with:

```bash
EXPO_PUBLIC_API_URL=https://api.example.com npm run start
```

Then test the OAuth callback, account refresh, and media list. These tests make real external calls and therefore are manual production checks, not part of repository validation.

## 5. Operations

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs --tail=200 api caddy db
docker compose --env-file .env.production restart api
bash scripts/backup-postgres.sh
bash scripts/restore-postgres.sh backups/postbridge-YYYYMMDDTHHMMSSZ.dump
```

Backups are local, mode 0600, timestamped in UTC, ignored by Git, and never uploaded. Restore accepts one explicit file under `backups/` and requires typing `RESTORE`; it can replace database objects, so take a fresh backup first.

## 6. Safe updates and rollback

For an update, take a backup, explicitly run `git pull --ff-only`, inspect the diff and migration, run `scripts/deploy.sh`, then explicitly run `scripts/migrate.sh` if required. Check `/health` and logs. Do not use floating application artifacts from an unreviewed branch.

For an application rollback, check out the previously reviewed Git revision, rebuild with `scripts/deploy.sh`, and verify `/health`. Database schema rollback is not automatic: restore the pre-deployment dump only when the older application is incompatible and after confirming the data-loss implications. Caddy certificates and PostgreSQL data remain in named volumes across container rebuilds; never remove volumes during a routine rollback.
