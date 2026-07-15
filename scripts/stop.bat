@echo off
:: Port-Sentinel — Stop Services Script (Windows)

echo ========================================================
echo   Stopping Port-Sentinel Services...
echo ========================================================
echo.

:: 1. Stop Backend Service (listening on port 8600)
echo [*] Searching for Backend Service on port 8600...
set "backend_pid="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8600" ^| findstr "LISTENING"') do (
    set "backend_pid=%%a"
)

if defined backend_pid (
    echo [*] Stopping Backend Service (PID: %backend_pid%)...
    taskkill /f /pid %backend_pid% >nul 2>&1
    if %errorLevel% equ 0 (
        echo [OK] Backend service stopped.
    ) else (
        echo [WARNING] Failed to stop backend service (PID: %backend_pid%).
    )
) else (
    echo [OK] Backend service is not running on port 8600.
)

:: 2. Stop Frontend Dev Server (listening on port 5173)
echo [*] Searching for Frontend Server on port 5173...
set "frontend_pid="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    set "frontend_pid=%%a"
)

if defined frontend_pid (
    echo [*] Stopping Frontend Server (PID: %frontend_pid%)...
    taskkill /f /pid %frontend_pid% >nul 2>&1
    if %errorLevel% equ 0 (
        echo [OK] Frontend server stopped.
    ) else (
        echo [WARNING] Failed to stop frontend server (PID: %frontend_pid%).
    )
) else (
    echo [OK] Frontend server is not running on port 5173.
)

echo.
echo ========================================================
echo   Port-Sentinel Services Stopped!
echo ========================================================
exit /b 0
