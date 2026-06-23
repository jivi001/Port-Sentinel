@echo off
REM ============================================================
REM  Vigilant — Build .exe Script
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
echo   Vigilant — EXE Builder
echo ========================================
echo.

REM --- Determine Python command ---
where py >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo ERROR: Python is not installed or not in PATH.
        exit /b 1
    )
)
echo      Using Python: !PYTHON_CMD!

REM --- Ensure virtual environment exists ---
if not exist ".venv" (
    echo      Creating virtual environment...
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create virtual environment!
        exit /b 1
    )
)

REM --- Use venv Python/pip for all operations ---
set "VENV_PYTHON=.venv\Scripts\python.exe"
set "VENV_PIP=.venv\Scripts\pip.exe"

REM --- Step 1: Build the Frontend ---
echo [1/3] Building React frontend...
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo      Installing npm dependencies...
    call npm ci
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

REM --- Step 2: Ensure build dependencies are installed in venv ---
echo [2/3] Checking build dependencies...
%VENV_PIP% install --quiet -e ".[dev]"
%VENV_PIP% show pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo      Installing PyInstaller...
    %VENV_PIP% install pyinstaller
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install PyInstaller!
        exit /b 1
    )
)
echo      Build dependencies ready.
echo.

REM Also ensure python-dotenv is available (used by launcher)
%VENV_PIP% show python-dotenv >nul 2>&1
if !errorlevel! neq 0 (
    echo      Installing python-dotenv...
    %VENV_PIP% install python-dotenv
)

REM --- Step 3: Build the .exe ---
echo [3/3] Building Vigilant.exe...
echo      This may take a few minutes...
echo.
net session >nul 2>&1
if not errorlevel 1 (
    echo      WARNING: Elevated shell detected. Use a non-admin Command Prompt
    echo      for PyInstaller ^(see script header^).
    echo.
)
%VENV_PYTHON% -m PyInstaller sentinel.spec --noconfirm --clean
if !errorlevel! neq 0 (
    echo.
    echo ERROR: PyInstaller build failed!
    exit /b 1
)

REM Remove Mark-of-the-Web so Windows does not treat the new .exe as an untrusted download
if exist "dist\Vigilant.exe" (
    powershell -NoProfile -Command "Unblock-File -LiteralPath 'dist\Vigilant.exe' -ErrorAction SilentlyContinue" >nul 2>&1
)

echo.
echo ========================================
echo   BUILD SUCCESSFUL!
echo ========================================
echo.
echo   Output: dist\Vigilant.exe
echo.
echo   To run:
echo     1. Right-click dist\Vigilant.exe
echo     2. Select "Run as administrator"
echo     3. Browser will open automatically
echo.
echo   NOTE: Npcap must be installed on the
echo   target machine for full packet capture.
echo   Download: https://npcap.com/
echo ========================================
echo.

endlocal
