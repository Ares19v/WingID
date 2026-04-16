@echo off
set "PROJECT_ROOT=%~dp0"
title WINGID TELEMETRY SYSTEM

echo =======================================================
echo   WINGID // AEROSPACE COMMAND CENTER
echo   INITIALIZING DUAL-STACK LAUNCH SEQUENCE
echo   ROOT: %PROJECT_ROOT%
echo =======================================================

echo [1/3] IGNITING RTX 5060 ML BACKEND...
start "WINGID_BACKEND" cmd /k "cd /d "%PROJECT_ROOT%" && call venv\Scripts\activate && cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] STARTING COMMAND CENTER UI...
start "WINGID_FRONTEND" cmd /k "cd /d "%PROJECT_ROOT%\frontend" && npm run dev"

echo [3/3] WAITING FOR SYSTEMS TO STABILIZE...
timeout /t 10 /nobreak > nul

echo [LAUNCH] OPENING CHROME COMMAND CENTER...
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
    echo [WARN] Chrome not found at default path. Falling back to default browser.
    start http://localhost:5173
) else (
    start "" "%CHROME%" --new-window "http://localhost:5173"
)

echo =======================================================
echo   WINGID SYSTEM ONLINE // ALL SYSTEMS GO
echo =======================================================
exit
