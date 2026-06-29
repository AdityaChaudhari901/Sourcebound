#!/bin/sh
# Container start for PaaS (Render/Fly/etc.): run DB migrations, then serve.
# Free PaaS tiers have no separate pre-deploy step, so migrate at startup
# (alembic upgrade head is idempotent). Local docker-compose uses a separate
# migrate job instead, so this script is only the PaaS entrypoint.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
