#!/usr/bin/env bash
# Vigilant Enterprise Network Defense — Stop Services Script (Unix)

echo "========================================================"
echo "  Stopping Vigilant Enterprise Network Defense Services..."
echo "========================================================"
echo

if [ "$EUID" -ne 0 ]; then
    echo "[WARNING] Running stop script as non-root. Some services might fail to stop if"
    echo "          they were started with sudo/root privileges."
fi

# Stop utility using lsof or fuser
stop_port() {
    local port=$1
    local name=$2
    
    echo "[*] Searching for $name on port $port..."
    if command -v lsof &> /dev/null; then
        local pid=$(lsof -t -i:$port -sTCP:LISTEN)
        if [ ! -z "$pid" ]; then
            echo "[*] Stopping $name (PID: $pid)..."
            kill -15 $pid 2>/dev/null
            sleep 1
            if kill -0 $pid 2>/dev/null; then
                kill -9 $pid 2>/dev/null
            fi
            echo "[OK] Stopped $name."
            return 0
        fi
    elif command -v fuser &> /dev/null; then
        echo "[*] Using fuser to stop port $port..."
        fuser -k $port/tcp &>/dev/null
        echo "[OK] Stopped $name."
        return 0
    fi
    
    echo "[OK] $name is not running on port $port."
    return 1
}

# 1. Stop Backend (8600)
stop_port 8600 "Backend Service"

# 2. Stop Frontend (5173)
stop_port 5173 "Frontend Server"

echo
echo "========================================================"
echo "  Vigilant Services Stopped!"
echo "========================================================"
exit 0
