#!/bin/sh
set -eu
docker compose --env-file .env.oci -f docker-compose.oci.yml run --rm certbot renew --webroot -w /var/www/certbot
docker compose --env-file .env.oci -f docker-compose.oci.yml exec nginx nginx -s reload
