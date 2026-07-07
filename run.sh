#!/usr/bin/env bash
# Vigilant Startup Script for Unix/Linux/macOS
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

# --- Environment Setup ---
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing/updating Python dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -e ".[dev]" >/dev/null

if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd frontend && npm ci)
fi

# --- Cleanup Handler ---
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" >/dev/null 2>&1 || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# --- Start Services ---
echo ""
if command -v docker-compose >/dev/null 2>&1; then
    echo "Starting observability stack (Grafana/InfluxDB)..."
    docker-compose up -d influxdb grafana || echo "Warning: docker-compose failed."
else
    echo "Warning: docker-compose not found. Telemetry won't be saved."
fi

echo ""
echo "Starting backend at http://localhost:8600 ..."
python -m backend.main &
BACKEND_PID=$!

echo "Starting frontend at http://localhost:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo "Grafana Observability at http://localhost:3000 ..."

echo ""
echo "Press Ctrl+C to stop both services."
wait "$BACKEND_PID" "$FRONTEND_PID"
