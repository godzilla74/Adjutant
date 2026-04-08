#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kill any existing instance
pkill -f "uvicorn backend.main" 2>/dev/null && echo "Stopped existing server." || true

# Python venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

if [ ! -f ".venv/bin/uvicorn" ]; then
    echo "Installing Python dependencies..."
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found."
    exit 1
fi

# Build React UI (skip with --no-build)
if [[ "$*" != *--no-build* ]]; then
    if [ -d "ui/node_modules" ]; then
        echo "Building UI..."
        cd ui && npm run build && cd ..
    else
        echo "WARNING: ui/node_modules not found. Run 'cd ui && npm install' first."
    fi
fi

PORT=${HANNAH_PORT:-8001}
echo "Starting Hannah on http://0.0.0.0:$PORT"
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
