#!/bin/sh
set -eu

ENV_FILE=${ENV_FILE:-.env.oci}
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE" >&2; exit 1; }

read_env_value() {
  value=$(sed -n "s/^${1}=//p" "$ENV_FILE" | tail -n 1)
  case "$value" in
    \"*\") value=${value#\"}; value=${value%\"} ;;
    \'*\') value=${value#\'}; value=${value%\'} ;;
  esac
  printf '%s' "$value"
}

POSTBRIDGE_WEB_DOMAIN=${POSTBRIDGE_WEB_DOMAIN:-$(read_env_value POSTBRIDGE_WEB_DOMAIN)}
POSTBRIDGE_WWW_DOMAIN=${POSTBRIDGE_WWW_DOMAIN:-$(read_env_value POSTBRIDGE_WWW_DOMAIN)}
POSTBRIDGE_API_DOMAIN=${POSTBRIDGE_API_DOMAIN:-$(read_env_value POSTBRIDGE_API_DOMAIN)}
CERTBOT_EMAIL=${CERTBOT_EMAIL:-$(read_env_value CERTBOT_EMAIL)}

: "${POSTBRIDGE_WEB_DOMAIN:?set POSTBRIDGE_WEB_DOMAIN in $ENV_FILE}"
: "${POSTBRIDGE_WWW_DOMAIN:?set POSTBRIDGE_WWW_DOMAIN in $ENV_FILE}"
: "${POSTBRIDGE_API_DOMAIN:?set POSTBRIDGE_API_DOMAIN in $ENV_FILE}"
: "${CERTBOT_EMAIL:?set CERTBOT_EMAIL in $ENV_FILE}"
docker compose --env-file "$ENV_FILE" -f docker-compose.oci.yml stop nginx >/dev/null 2>&1 || true
docker compose --env-file "$ENV_FILE" -f docker-compose.oci.yml --profile certbot run --rm --service-ports certbot certonly \
  --standalone --non-interactive --agree-tos --no-eff-email \
  --cert-name "$POSTBRIDGE_WEB_DOMAIN" --email "$CERTBOT_EMAIL" \
  -d "$POSTBRIDGE_WEB_DOMAIN" \
  -d "$POSTBRIDGE_WWW_DOMAIN" \
  -d "$POSTBRIDGE_API_DOMAIN"
docker compose --env-file "$ENV_FILE" -f docker-compose.oci.yml up -d nginx
