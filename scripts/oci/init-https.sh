#!/bin/sh
set -eu
: "${POSTBRIDGE_DOMAIN:?export POSTBRIDGE_DOMAIN after loading .env.oci}"
: "${CERTBOT_EMAIL:?export CERTBOT_EMAIL after loading .env.oci}"
docker compose --env-file .env.oci -f docker-compose.oci.yml stop nginx >/dev/null 2>&1 || true
docker compose --env-file .env.oci -f docker-compose.oci.yml --profile certbot run --rm --service-ports certbot certonly \
  --standalone --non-interactive --agree-tos --no-eff-email \
  --email "$CERTBOT_EMAIL" -d "$POSTBRIDGE_DOMAIN"
docker compose --env-file .env.oci -f docker-compose.oci.yml up -d nginx
