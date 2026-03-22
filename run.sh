#!/usr/bin/env bash
# Port Sentinel Startup Script for Unix/Linux/macOS
# Starts backend + frontend development servers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not installed"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm is not installed"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing/updating Python dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -e ".[dev]" >/dev/null

if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd frontend && npm ci)
fi

cleanup() {
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

echo "Starting backend at http://localhost:8600 ..."
python -m backend.main &
BACKEND_PID=$!

echo "Starting frontend at http://localhost:5173 ..."
(cd frontend && npm run dev -- --host 0.0.0.0) &
FRONTEND_PID=$!

echo "Press Ctrl+C to stop both services."
wait "$BACKEND_PID" "$FRONTEND_PID"
