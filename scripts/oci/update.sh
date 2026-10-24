#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml build app frontend
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm app alembic upgrade head
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d --no-deps --wait app frontend
# Re-resolve the recreated app/frontend container addresses. Nginx otherwise
# keeps the previous Docker DNS results and returns 502 until it is restarted.
docker compose --env-file .env.oci -f docker-compose.oci.yml restart nginx
docker compose --env-file .env.oci -f docker-compose.oci.yml ps
