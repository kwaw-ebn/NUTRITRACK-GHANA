#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Single-instance pilot: complete schema updates before accepting HTTP requests.
python -m alembic upgrade head
python -m app.seed
python -m app.worker --once
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
