#!/usr/bin/env bash
# Port-Sentinel — Update Script (Unix)

echo "========================================================"
echo "  Updating Port-Sentinel (Unix)..."
echo "========================================================"
echo

# 1. Git Pull
echo "[*] Pulling latest changes from repository..."
git pull
if [ $? -ne 0 ]; then
    echo "[WARNING] git pull failed or repository not using git. Continuing anyway..."
else
    echo "[OK] Repository updated."
fi

# 2. Update Backend Dependencies
echo
echo "[*] Updating backend dependencies..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip install -e .
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to update backend dependencies."
        exit 1
    fi
    echo "[OK] Backend dependencies updated."
else
    echo "[WARNING] Virtual environment (.venv) not found. Run scripts/install.sh first."
fi

# 3. Update Frontend Dependencies
echo
echo "[*] Updating frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to update frontend dependencies."
        cd ..
        exit 1
    fi
    echo "[OK] Frontend dependencies updated."
    cd ..
else
    echo "[ERROR] frontend directory not found."
    exit 1
fi

echo
echo "========================================================"
echo "  Port-Sentinel Update Completed Successfully!"
echo "========================================================"
echo "  To launch the updated services, run: sudo ./scripts/start.sh"
echo "========================================================"
exit 0
