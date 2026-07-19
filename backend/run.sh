#!/usr/bin/env bash
# Launch the Reelie API locally. Zero external services: SQLite + dev auth.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [ -f "$HERE/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HERE/.venv/bin/activate"
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "▶ Reelie API  →  http://$HOST:$PORT   (docs at /docs)"
exec python -m uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
