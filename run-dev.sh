#!/usr/bin/env bash
# Local dev server with auto-reload. Copies .env.example to .env on first run.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a
mkdir -p data
exec .venv/bin/uvicorn app.main:app --reload --port "${PORT:-8000}"
