#!/bin/sh
# Container entrypoint: migrate (as the owner role), optionally seed the demo data, then start.
set -e
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi
if [ "${SEED_ON_START:-false}" = "true" ]; then
  python scripts/seed_demo.py
fi
exec "$@"
