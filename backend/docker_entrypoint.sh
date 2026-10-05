#!/bin/sh
set -e

echo "=== VigilantEye API entrypoint ==="
python /app/backend/dev_bootstrap.py

echo "Backend: starting uvicorn…"
exec uvicorn main:app --host 0.0.0.0 --port 8000
