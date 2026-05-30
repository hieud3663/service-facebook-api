#!/usr/bin/env sh
set -e
export PYTHONUNBUFFERED=1

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py shell -c "from apps.retry.db import ensure_indexes; ensure_indexes()"

if [ "$RETRY_RUN_MODE" = "worker" ]; then
  exec python manage.py consume_failed_messages
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:3004 --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level "${LOG_LEVEL:-info}"
