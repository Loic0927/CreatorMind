#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml config --quiet
docker compose --env-file .env.oci -f docker-compose.oci.yml ps
curl --fail --silent --show-error "https://${POSTBRIDGE_DOMAIN}/health"
echo
