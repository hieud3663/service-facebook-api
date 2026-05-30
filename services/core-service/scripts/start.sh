#!/usr/bin/env sh
set -e
export PYTHONUNBUFFERED=1

# Django admin tables (SQLite)
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Ensure MongoDB indexes
python manage.py shell -c "from apps.core.db import ensure_indexes; ensure_indexes()"

if [ "$CORE_RUN_MODE" = "worker" ]; then
  exec python manage.py consume_events
fi

if [ "$CORE_RUN_MODE" = "retry-worker" ]; then
  exec python manage.py consume_retry_commands
fi

# Backward-compatible default: run web + embedded consumer.
# In production, set CORE_RUN_MODE=web and run a separate worker container.
if [ "$CORE_RUN_MODE" != "web" ]; then
  python manage.py consume_events &
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:3003 --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level "${LOG_LEVEL:-info}"
