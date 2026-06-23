#!/usr/bin/env bash
# Vigilant Enterprise Network Defense — Installation Script (Unix)

echo "========================================================"
echo "  Vigilant Enterprise Network Defense — Installer (Unix)"
echo "========================================================"
echo

# 1. Check Root Privileges (warn user but do not exit, since sniffer requires root to run, install doesn't necessarily)
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] Running install as non-root user. Note that running the sniffer"
    echo "       will require sudo/root privileges."
fi

# 2. Check Python Installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 was not found. Please install Python 3.10+."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
# Simple string/number float comparison: must be >= 3.10
if [ "$(echo "$PYTHON_VERSION < 3.10" | bc -l 2>/dev/null)" -eq 1 ]; then
    echo "[ERROR] Found Python version $PYTHON_VERSION, but 3.10+ is required."
    exit 1
fi
echo "[OK] Found Python version $PYTHON_VERSION."

# 3. Check Node.js and NPM
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js was not found. Please install Node.js (version 20 recommended)."
    exit 1
fi
if ! command -v npm &> /dev/null; then
    echo "[ERROR] NPM was not found."
    exit 1
fi
echo "[OK] Found Node.js and NPM."

# 4. Build Python Virtual Environment
echo
echo "[1/3] Building python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi
echo "[OK] Virtual environment created."

# 5. Install Backend Dependencies
echo
echo "[2/3] Installing backend dependencies..."
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install backend dependencies."
    exit 1
fi
echo "[OK] Backend dependencies installed successfully."

# 6. Install Frontend Dependencies
echo
echo "[3/3] Installing frontend dependencies..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install frontend dependencies."
    cd ..
    exit 1
fi
echo "[OK] Frontend dependencies installed successfully."
cd ..

echo
echo "========================================================"
echo "  Vigilant Installation Completed Successfully!"
echo "========================================================"
echo "  To launch the platform, run: sudo ./scripts/start.sh"
echo "========================================================"
exit 0
