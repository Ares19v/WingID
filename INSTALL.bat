@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
title WingID — First-Time Setup

echo.
echo  ================================================================
echo    WINGID // AEROSPACE COMMAND CENTER
echo    FIRST-TIME INSTALLATION SCRIPT
echo  ================================================================
echo.
echo  This script will:
echo    [1] Create a Python virtual environment
echo    [2] Install all Python dependencies
echo    [3] Install PyTorch with CUDA support
echo    [4] Install frontend Node dependencies
echo.
echo  Prerequisites: Python 3.10+, Node.js 18+, Git, NVIDIA GPU
echo.
pause

:: ── Step 0 — Verify Python and Node are available ───────────────────────────
echo.
echo [CHECK] Verifying Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org and try again.
    pause & exit /b 1
)

echo [CHECK] Verifying Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org and try again.
    pause & exit /b 1
)

:: ── Step 1 — Python virtual environment ─────────────────────────────────────
echo.
echo [1/4] Creating Python virtual environment...
if exist "%ROOT%venv\" (
    echo   Virtual environment already exists, skipping creation.
) else (
    python -m venv "%ROOT%venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause & exit /b 1
    )
    echo   Virtual environment created successfully.
)

:: ── Step 2 — Python core dependencies ───────────────────────────────────────
echo.
echo [2/4] Installing Python dependencies (requirements.txt)...
call "%ROOT%venv\Scripts\activate.bat"
pip install --upgrade pip --quiet
pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause & exit /b 1
)

:: ── Step 3 — PyTorch with CUDA ───────────────────────────────────────────────
echo.
echo [3/4] Installing PyTorch with CUDA support...
echo.
echo  Select your GPU generation:
echo    [1] RTX 5000 series / Blackwell (CUDA 12.8 Nightly)  ^<-- default^>
echo    [2] RTX 30 / 40 series (CUDA 12.1 Stable)
echo    [3] RTX 20 / older (CUDA 11.8 Stable)
echo    [4] Skip (CPU only — inference will be very slow)
echo.
set /p GPU_CHOICE="  Enter 1, 2, 3, or 4 [default: 1]: "
if "!GPU_CHOICE!"=="" set GPU_CHOICE=1

if "!GPU_CHOICE!"=="1" (
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
) else if "!GPU_CHOICE!"=="2" (
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
) else if "!GPU_CHOICE!"=="3" (
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
) else if "!GPU_CHOICE!"=="4" (
    echo   Skipping PyTorch GPU install. The system will fall back to CPU inference.
) else (
    echo   Invalid choice. Defaulting to CUDA 12.8 Nightly.
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
)

if errorlevel 1 (
    echo [WARN] PyTorch install reported an error. Check the output above.
)

:: ── Step 4 — Frontend Node dependencies ─────────────────────────────────────
echo.
echo [4/4] Installing frontend Node.js dependencies...
cd /d "%ROOT%frontend"
npm install
if errorlevel 1 (
    echo [ERROR] npm install failed. Ensure Node.js 18+ is installed.
    cd /d "%ROOT%"
    pause & exit /b 1
)
cd /d "%ROOT%"

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo  ================================================================
echo    INSTALLATION COMPLETE
echo.
echo    On first launch, WingID will auto-download YOLO weights and
echo    compile the TensorRT engine (~3-5 min, one-time only).
echo.
echo    To start WingID:
echo      Double-click Run_WingID.bat
echo  ================================================================
echo.
pause
