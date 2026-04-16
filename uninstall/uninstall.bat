@echo off
title WINGID — Dependency Cleanup
set "PROJECT_ROOT=%~dp0"

echo.
echo =============================================================
echo   WINGID — SPACE RECLAMATION PROTOCOL
echo   This will remove all Python packages and model weights.
echo   Your source code will NOT be touched.
echo =============================================================
echo.
echo   Estimated space recovered: 8–15 GB
echo.
set /p CONFIRM="   Type YES to proceed, anything else to abort: "
if /i not "%CONFIRM%"=="YES" (
    echo Aborted. No changes made.
    pause
    exit /b
)

echo.
echo [1/5] Activating virtual environment...
call "%PROJECT_ROOT%venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate venv. Is it created? Run: python -m venv venv
    pause
    exit /b 1
)

echo.
echo [2/5] Uninstalling PyTorch (largest packages)...
pip uninstall -y torch torchvision torchaudio 2>nul

echo.
echo [3/5] Uninstalling all other Python dependencies...
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
    sniffio 2>nul

echo.
echo [4/5] Removing compiled TensorRT engine (regenerates on next run)...
if exist "%PROJECT_ROOT%backend\yolo11l.engine" (
    del /f /q "%PROJECT_ROOT%backend\yolo11l.engine"
    echo   Deleted: yolo11l.engine
) else (
    echo   yolo11l.engine not found, skipping.
)

echo.
echo [5/5] Clearing Python __pycache__ directories...
for /r "%PROJECT_ROOT%" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)

echo.
echo =============================================================
echo   CLEANUP COMPLETE.
echo.
echo   To reinstall and run again:
echo     1. Run_WingID.bat           (auto-installs on first run)
echo   OR manually:
echo     .\venv\Scripts\activate
echo     pip install -r requirements.txt
echo     pip install --pre torch torchvision torchaudio ^
echo         --index-url https://download.pytorch.org/whl/nightly/cu128
echo =============================================================
echo.
pause
