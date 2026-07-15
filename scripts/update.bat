@echo off
:: Port-Sentinel — Update Script (Windows)

echo ========================================================
echo   Updating Port-Sentinel...
echo ========================================================
echo.

:: 1. Git Pull
echo [*] Pulling latest changes from repository...
git pull
if %errorLevel% neq 0 (
    echo [WARNING] git pull failed or repository not using git. Continuing anyway...
) else (
    echo [OK] Repository updated.
)

:: 2. Update Backend Dependencies
echo.
echo [*] Updating backend dependencies...
if exist ".venv" (
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -e .
    if %errorLevel% neq 0 (
        echo [ERROR] Failed to update backend dependencies.
        exit /b 1
    )
    echo [OK] Backend dependencies updated.
) else (
    echo [WARNING] Virtual environment (.venv) not found. Run scripts\install.bat first.
)

:: 3. Update Frontend Dependencies
echo.
echo [*] Updating frontend dependencies...
if exist "frontend" (
    cd frontend
    call npm install
    if %errorLevel% neq 0 (
        echo [ERROR] Failed to update frontend dependencies.
        cd ..
        exit /b 1
    )
    echo [OK] Frontend dependencies updated.
    cd ..
) else (
    echo [ERROR] frontend directory not found.
    exit /b 1
)

echo.
echo ========================================================
echo   Port-Sentinel Update Completed Successfully!
echo ========================================================
echo   To launch the updated services, run: scripts\start.bat
echo ========================================================
exit /b 0
