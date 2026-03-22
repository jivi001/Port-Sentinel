@echo off
setlocal EnableDelayedExpansion
REM Port Sentinel - DEBUG Startup Script
cd /d "%~dp0"

echo [1/4] Validating Prerequisites...

echo Checking Python...
python --version
if errorlevel 1 (
    echo [!] 'python' not found, trying 'py'...
    py --version
    if errorlevel 1 (
        echo ERROR: Python is not installed.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)

echo Checking NPM...
call npm --version
if errorlevel 1 (
    echo ERROR: npm is not installed or not in PATH.
    pause
    exit /b 1
)

REM --- Environment Check & Repair ---
echo.
echo [2/4] Verifying Environment...
if exist ".venv" (
    echo Found .venv. Checking if path is valid for %CD%...
    if exist ".venv\pyvenv.cfg" (
        findstr /C:"%CD%" ".venv\pyvenv.cfg" >nul
        if errorlevel 1 (
            echo [!] PATH MISMATCH: .venv is from another folder. Deleting for repair...
            rmdir /s /q .venv
        )
    )
)

if not exist ".venv" (
    echo Creating fresh virtual environment...
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv.
        pause
        exit /b 1
    )
)

echo [3/4] Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -e ".[dev]"
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo Installing frontend modules...
    pushd frontend
    call npm ci
    popd
)

echo.
echo [4/4] Starting Services...
echo Dashboard will be at: http://localhost:5173
echo.

REM Start backend in a separate terminal so we can see its logs
start "Sentinel_Backend" cmd /k ".venv\Scripts\python.exe -m backend.main"

REM Start frontend in this terminal
pushd frontend
call npm run dev -- --host 0.0.0.0
popd

echo.
echo Closing backend...
taskkill /FI "WINDOWTITLE eq Sentinel_Backend*" /T /F >nul 2>&1
pause
