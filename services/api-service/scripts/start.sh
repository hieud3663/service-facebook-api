#!/usr/bin/env sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

case "${API_RUN_MODE:-web}" in
  worker)
    exec python manage.py consume_reply_commands
    ;;
  web)
    exec gunicorn config.wsgi:application --bind 0.0.0.0:3002 --workers 3 --timeout 120
    ;;
  *)
    echo "Unknown API_RUN_MODE=${API_RUN_MODE}" >&2
    exit 1
    ;;
esac
