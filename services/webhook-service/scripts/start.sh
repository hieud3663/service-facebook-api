#!/usr/bin/env sh
set -e
export PYTHONUNBUFFERED=1

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:3001 --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level "${LOG_LEVEL:-info}"
