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

:: ── Pre-flight checks ────────────────────────────────────────────────────────
echo [CHECK] Verifying virtual environment...
if not exist "%ROOT%venv\Scripts\activate.bat" (
    echo.
    echo  [ERROR] Virtual environment not found.
    echo.
    echo  Run INSTALL.bat first to set up the project:
    echo    Double-click INSTALL.bat
    echo.
    pause & exit /b 1
)

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
echo.
echo [1/3] Starting ML backend (FastAPI + uvicorn on :8000)...
start "WingID — Backend" cmd /k ^
    "cd /d "%ROOT%" && call venv\Scripts\activate && cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: ── Launch frontend ───────────────────────────────────────────────────────────
echo [2/3] Starting Command Center UI (Vite on :5173)...
start "WingID — Frontend" cmd /k ^
    "cd /d "%ROOT%frontend" && npm run dev"

:: ── Wait then open browser ────────────────────────────────────────────────────
echo [3/3] Waiting for services to stabilize (12 seconds)...
timeout /t 12 /nobreak >nul

echo.
echo  Opening browser...
where chrome >nul 2>&1
if not errorlevel 1 (
    start "" "chrome" --new-window "http://localhost:5173"
    goto :launched
)

set "CHROME64=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME32=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

if exist "%CHROME64%" (
    start "" "%CHROME64%" --new-window "http://localhost:5173"
    goto :launched
)
if exist "%CHROME32%" (
    start "" "%CHROME32%" --new-window "http://localhost:5173"
    goto :launched
)

:: Fall back to default system browser
start "" "http://localhost:5173"

:launched
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
