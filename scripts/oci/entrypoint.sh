#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${POSTBRIDGE_RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi

exec gunicorn backend.main:app \
  --bind "0.0.0.0:${PORT:-8000}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${POSTBRIDGE_GUNICORN_WORKERS:-2}" \
  --timeout "${POSTBRIDGE_GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  --capture-output
