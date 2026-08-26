@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
title WingID — Aerospace Command Center

echo.
echo  ================================================================
echo    WINGID // AEROSPACE COMMAND CENTER
echo    INITIALIZING DUAL-STACK LAUNCH SEQUENCE
echo  ================================================================
echo.

echo [CHECK] Verifying frontend dependencies...
if not exist "%ROOT%frontend\node_modules\" (
    echo   node_modules not found. Installing frontend dependencies...
    cd /d "%ROOT%frontend"
    npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed. Ensure Node.js 18+ is installed.
        cd /d "%ROOT%"
        pause & exit /b 1
    )
    cd /d "%ROOT%"
    echo   Frontend dependencies installed.
)

:: ── Launch backend ────────────────────────────────────────────────────────────
set "ACT_CMD="
if exist "%ROOT%venv\Scripts\activate.bat" set "ACT_CMD=call venv\Scripts\activate && "

echo.
echo [1/3] Starting ML backend (FastAPI + uvicorn on :8000)...
start "WingID — Backend" cmd /k ^
    "cd /d "%ROOT%" && %ACT_CMD%cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: ── Launch frontend ───────────────────────────────────────────────────────────
echo [2/3] Starting Command Center UI (Vite on :5173)...
start "WingID — Frontend" cmd /k ^
    "cd /d "%ROOT%frontend" && npm run dev"

:: ── Wait then open browser ────────────────────────────────────────────────────
echo [3/3] Waiting for services to stabilize (12 seconds)...
timeout /t 12 /nobreak >nul

echo.
echo  Opening browser...
start "" "http://localhost:5173"

echo.
echo  ================================================================
echo    WINGID SYSTEM ONLINE // ALL SYSTEMS GO
echo.
echo    Backend:   http://localhost:8000
echo    Frontend:  http://localhost:5173
echo    API Docs:  http://localhost:8000/docs
echo.
echo    Click INITIALIZE SENSORS in the browser to start tracking.
echo  ================================================================
echo.
exit
