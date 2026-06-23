@echo off
:: Vigilant Enterprise Network Defense — Start Services Script (Windows)

echo ========================================================
echo   Starting Vigilant Enterprise Network Defense...
echo ========================================================
echo.

:: Ensure logs directory exists
if not exist "logs" (
    mkdir logs
)

:: 1. Start Backend Service
echo [*] Starting Backend Service on http://127.0.0.1:8600 ...
:: Run uvicorn server in background, logging to logs\backend.log
start "Vigilant Backend" /b .venv\Scripts\python.exe -m backend.main > logs\backend.log 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Failed to start backend service.
    exit /b 1
)

:: 2. Start Frontend Dev Server
echo [*] Starting Frontend Server...
cd frontend
start "Vigilant Frontend" /b npm run dev > ..\logs\frontend.log 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Failed to start frontend server.
    cd ..
    exit /b 1
)
cd ..

echo.
echo ========================================================
echo   Vigilant Services Running in the Background!
echo ========================================================
echo   - Backend: http://127.0.0.1:8600
echo   - Interface: http://localhost:5173 (standard Vite port)
echo   - Logs: logs\backend.log and logs\frontend.log
echo.
echo   To stop the services, run: scripts\stop.bat
echo ========================================================
exit /b 0
