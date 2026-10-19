#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml config --quiet
docker compose --env-file .env.oci -f docker-compose.oci.yml build app frontend
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d db app frontend
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm app alembic upgrade head
echo "Database, API, and web app are ready. Run scripts/oci/init-https.sh for the first certificate."
