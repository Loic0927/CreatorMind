#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEPLOY_DIR"
[[ -f .env.production ]] || { echo "Missing .env.production" >&2; exit 1; }

echo "This will run: alembic upgrade head against the configured production database."
read -r -p "Type MIGRATE to continue: " confirmation
[[ "$confirmation" == "MIGRATE" ]] || { echo "Cancelled."; exit 1; }
docker compose --env-file .env.production --profile migration run --rm migrate
