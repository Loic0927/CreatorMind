#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml build app frontend
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm app alembic upgrade head
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d --no-deps app frontend
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d nginx
docker compose --env-file .env.oci -f docker-compose.oci.yml ps
