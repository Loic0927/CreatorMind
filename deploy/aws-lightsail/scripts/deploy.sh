#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEPLOY_DIR"

[[ -f .env.production ]] || { echo "Missing $DEPLOY_DIR/.env.production" >&2; exit 1; }
docker compose --env-file .env.production build api
docker compose --env-file .env.production up -d db api caddy
docker compose --env-file .env.production ps

domain="$(sed -n 's/^POSTBRIDGE_DOMAIN=//p' .env.production | tail -n 1)"
if [[ -n "$domain" ]]; then
  curl --fail --silent --show-error --retry 6 --retry-delay 5 "https://${domain}/health"
  echo
fi
