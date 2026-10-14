#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml build app
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm app alembic upgrade head
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d --no-deps app
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d nginx
docker compose --env-file .env.oci -f docker-compose.oci.yml ps
