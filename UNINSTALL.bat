@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
title WingID — Dependency Cleanup

echo.
echo  ================================================================
echo    WINGID // SPACE RECLAMATION PROTOCOL
echo.
echo    Removes all Python packages and compiled GPU artifacts.
echo    Source code will NOT be touched.
echo.
echo    Estimated space recovered: 6-15 GB
echo  ================================================================
echo.
set /p CONFIRM="   Type YES to proceed, anything else to abort: "
if /i not "!CONFIRM!"=="YES" (
    echo   Aborted. No changes made.
    pause & exit /b
)

:: ── Step 1 — Activate venv ──────────────────────────────────────────────────
echo.
echo [1/5] Activating virtual environment...
if not exist "%ROOT%venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at %ROOT%venv
    echo         Nothing to clean up.
    pause & exit /b 1
)
call "%ROOT%venv\Scripts\activate.bat"

:: ── Step 2 — PyTorch (largest packages) ─────────────────────────────────────
echo.
echo [2/5] Uninstalling PyTorch...
pip uninstall -y torch torchvision torchaudio 2>nul
echo   Done.

:: ── Step 3 — All other Python dependencies ──────────────────────────────────
echo.
echo [3/5] Uninstalling remaining Python dependencies...
pip uninstall -y ^
    fastapi ^
    uvicorn ^
    websockets ^
    opencv-python ^
    ultralytics ^
    transformers ^
    accelerate ^
    Pillow ^
    numpy ^
    requests ^
    tqdm ^
    pyyaml ^
    psutil ^
    tensorrt ^
    huggingface-hub ^
    safetensors ^
    tokenizers ^
    filelock ^
    packaging ^
    regex ^
    starlette ^
    anyio ^
    httptools ^
    h11 ^
    sniffio ^
    reportlab 2>nul
echo   Done.

:: ── Step 4 — TensorRT engine (arch-specific, regenerates on next run) ────────
echo.
echo [4/5] Removing compiled TensorRT engine...
if exist "%ROOT%backend\yolo11l.engine" (
    del /f /q "%ROOT%backend\yolo11l.engine"
    echo   Deleted: backend\yolo11l.engine (will regenerate on next run)
) else (
    echo   yolo11l.engine not found, skipping.
)

:: ── Step 5 — Python cache ────────────────────────────────────────────────────
echo.
echo [5/5] Clearing Python __pycache__ directories...
for /r "%ROOT%" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
echo   Done.

echo.
echo  ================================================================
echo    CLEANUP COMPLETE
echo.
echo    To reinstall everything from scratch:
echo      Double-click INSTALL.bat
echo.
echo    Files preserved:
echo      - All source code
echo      - backend\yolo11l.pt  (model weights, saves 50 MB re-download)
echo      - frontend\node_modules  (run: npm install in frontend\ if deleted)
echo  ================================================================
echo.
pause
