#!/bin/sh
# What the container runs: bring the database up to date, then serve.
set -e

python manage.py migrate --noinput

# One process: safe for SQLite, and plenty for one person (DECISIONS #12).
# --no-proxy-headers: who the visitor is and whether they used https is decided
# in Django's settings (CLIENT_IP_HEADER, BASE_URL), in one place.
# --timeout-graceful-shutdown: Claude Code keeps one request open for events;
# don't wait for it on a restart.
exec uvicorn config.asgi:application \
    --host 0.0.0.0 --port 8000 \
    --no-proxy-headers \
    --timeout-graceful-shutdown 5
