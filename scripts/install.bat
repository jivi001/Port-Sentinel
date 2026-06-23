@echo off
:: Vigilant Enterprise Network Defense — Installation Script (Windows)
:: Requires Administrator privileges.

echo ========================================================
echo   Vigilant Enterprise Network Defense — Installer
echo ========================================================
echo.

:: 1. Check Administrator Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer requires Administrator privileges.
    echo         Please right-click on cmd.exe and select "Run as Administrator".
    pause
    exit /b 1
)
echo [OK] Administrator privileges confirmed.

:: 2. Check Python Installation
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python was not found in path. Please install Python 3.10+ and check "Add to PATH".
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%I in ('python --version') do set py_ver=%%I
echo [OK] Found Python version %py_ver% (minimum 3.10 required).

:: 3. Check Node.js and NPM
where node >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Node.js was not found. Please install Node.js (version 20 recommended).
    pause
    exit /b 1
)
where npm >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] NPM was not found.
    pause
    exit /b 1
)
echo [OK] Found Node.js and NPM.

:: 4. Build Python Virtual Environment
echo.
echo [1/3] Building python virtual environment...
if not exist ".venv" (
    python -m venv .venv
    if %errorLevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
      )
)
echo [OK] Virtual environment created.

:: 5. Install Backend Dependencies
echo.
echo [2/3] Installing backend dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
if %errorLevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)
echo [OK] Backend dependencies installed successfully.

:: 6. Install Frontend Dependencies
echo.
echo [3/3] Installing frontend dependencies...
cd frontend
call npm install
if %errorLevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies.
    cd ..
    pause
    exit /b 1
)
echo [OK] Frontend dependencies installed successfully.

cd ..
echo.
echo ========================================================
echo   Vigilant Installation Completed Successfully!
echo ========================================================
echo   To launch the platform, run: scripts\start.bat
echo ========================================================
pause
exit /b 0
