@echo off
REM ============================================================
REM  Port Sentinel — Build .exe Script
REM  
REM  This script:
REM    1. Builds the React frontend (npm run build)
REM    2. Installs PyInstaller if needed
REM    3. Builds the .exe using sentinel.spec
REM
REM  Run from the project root: build_exe.bat
REM  PyInstaller 6.x+: run from a normal (non-Administrator) terminal.
REM  Building as Admin is deprecated; PyInstaller 7.0 will block it.
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Port Sentinel — EXE Builder
echo ========================================
echo.

REM --- Step 1: Build the Frontend ---
echo [1/3] Building React frontend...
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo      Installing npm dependencies...
    call npm install
    if !errorlevel! neq 0 (
        echo ERROR: npm install failed!
        cd ..
        exit /b 1
    )
)

REM Build the frontend
call npm run build
if !errorlevel! neq 0 (
    echo ERROR: Frontend build failed!
    cd ..
    exit /b 1
)
cd ..

REM Verify dist was created
if not exist "frontend\dist\index.html" (
    echo ERROR: frontend/dist/index.html not found after build!
    exit /b 1
)
echo      Frontend built successfully.
echo.

REM --- Step 2: Ensure PyInstaller is installed ---
echo [2/3] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo      Installing PyInstaller...
    pip install pyinstaller
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install PyInstaller!
        exit /b 1
    )
)
echo      PyInstaller is ready.
echo.

REM Also ensure python-dotenv is available (used by launcher)
pip show python-dotenv >nul 2>&1
if !errorlevel! neq 0 (
    echo      Installing python-dotenv...
    pip install python-dotenv
)

REM --- Step 3: Build the .exe ---
echo [3/3] Building PortSentinel.exe...
echo      This may take a few minutes...
echo.
net session >nul 2>&1
if not errorlevel 1 (
    echo      WARNING: Elevated shell detected. Use a non-admin Command Prompt
    echo      for PyInstaller ^(see script header^).
    echo.
)
pyinstaller sentinel.spec --noconfirm --clean
if !errorlevel! neq 0 (
    echo.
    echo ERROR: PyInstaller build failed!
    exit /b 1
)

REM Remove Mark-of-the-Web so Windows does not treat the new .exe as an untrusted download
if exist "dist\PortSentinel.exe" (
    powershell -NoProfile -Command "Unblock-File -LiteralPath 'dist\PortSentinel.exe' -ErrorAction SilentlyContinue" >nul 2>&1
)

echo.
echo ========================================
echo   BUILD SUCCESSFUL!
echo ========================================
echo.
echo   Output: dist\PortSentinel.exe
echo.
echo   To run:
echo     1. Right-click dist\PortSentinel.exe
echo     2. Select "Run as administrator"
echo     3. Browser will open automatically
echo.
echo   NOTE: Npcap must be installed on the
echo   target machine for full packet capture.
echo   Download: https://npcap.com/
echo ========================================
echo.

endlocal
