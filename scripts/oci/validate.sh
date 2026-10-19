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

: "${POSTBRIDGE_WEB_DOMAIN:?set POSTBRIDGE_WEB_DOMAIN in $ENV_FILE}"
: "${POSTBRIDGE_WWW_DOMAIN:?set POSTBRIDGE_WWW_DOMAIN in $ENV_FILE}"
: "${POSTBRIDGE_API_DOMAIN:?set POSTBRIDGE_API_DOMAIN in $ENV_FILE}"
docker compose --env-file "$ENV_FILE" -f docker-compose.oci.yml config --quiet
docker compose --env-file "$ENV_FILE" -f docker-compose.oci.yml ps
curl --fail --silent --show-error --output /dev/null "https://${POSTBRIDGE_WEB_DOMAIN}/"
curl --fail --silent --show-error --location --output /dev/null "https://${POSTBRIDGE_WWW_DOMAIN}/"
curl --fail --silent --show-error "https://${POSTBRIDGE_API_DOMAIN}/health"
echo
