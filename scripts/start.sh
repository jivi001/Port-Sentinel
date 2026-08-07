#!/usr/bin/env bash
# Port-Sentinel — Start Services Script (Unix)

echo "========================================================"
echo "  Starting Port-Sentinel (Unix)..."
echo "========================================================"
echo

# Require sudo/root privileges because raw packet sniffing requires binding to raw sockets
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] This start script requires root privileges for raw packet capturing."
    echo "        Please run with sudo: sudo ./scripts/start.sh"
    exit 1
fi

# Ensure logs directory exists
mkdir -p logs

# 1. Start Backend Service
echo "[*] Starting Backend Service on http://127.0.0.1:8600 ..."
# Run uvicorn server in background, logging to logs/backend.log
# We preserve the virtualenv environment using the absolute executable path
.venv/bin/python3 -m backend > logs/backend.log 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 $BACKEND_PID &> /dev/null; then
    echo "[ERROR] Failed to start backend service. Check logs/backend.log."
    exit 1
fi

# 2. Start Frontend Dev Server
echo "[*] Starting Frontend Server..."
cd frontend
# Run vite server in background, logging to logs/frontend.log
# Note: npm runs as the calling sudo user or root
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 2
if ! kill -0 $FRONTEND_PID &> /dev/null; then
    echo "[ERROR] Failed to start frontend server. Check logs/frontend.log."
    exit 1
fi

echo
echo "========================================================"
echo "  Port-Sentinel Services Running in the Background!"
echo "========================================================"
echo "  - Backend (PID: $BACKEND_PID): http://127.0.0.1:8600"
echo "  - Interface (PID: $FRONTEND_PID): http://localhost:5173"
echo "  - Logs: logs/backend.log and logs/frontend.log"
echo
echo "  To stop the services, run: sudo ./scripts/stop.sh"
echo "========================================================"
exit 0
