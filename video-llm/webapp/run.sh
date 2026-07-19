#!/usr/bin/env bash
# Launch the demo app. Run from anywhere; paths are resolved relative to the repo.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

# Prefer the project venv if present.
if [ -f "$ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

HOST="${HOST:-0.0.0.0}"     # 0.0.0.0 so you can open it from your phone on the same wifi
PORT="${PORT:-8000}"

echo "▶ routine demo  →  http://localhost:$PORT   (phone: http://<your-mac-ip>:$PORT)"
# server.py lives in webapp/, and adds the repo root to sys.path itself.
exec python -m uvicorn server:app --app-dir "$HERE" --host "$HOST" --port "$PORT" "$@"
