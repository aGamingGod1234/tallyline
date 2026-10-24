#!/bin/zsh

set -e
PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
elif [[ -x "$HOME/.local/bin/uv" ]]; then
  UV_BIN="$HOME/.local/bin/uv"
else
  echo "Tallyline needs uv: https://docs.astral.sh/uv/getting-started/installation/"
  read -r "?Press Return to close..."
  exit 1
fi

"$UV_BIN" sync --locked
open "http://127.0.0.1:8000"
echo "Tallyline is running at http://127.0.0.1:8000"
echo "Keep this window open while using the demo. Press Control-C to stop."
exec "$UV_BIN" run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
