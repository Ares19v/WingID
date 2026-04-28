# Space Management Guide 💾

ML projects like WingID have a large on-disk footprint due to model weights, Python packages, and compiled GPU engines. This guide covers how to safely suspend and resume the project without losing any code.

---

## What Takes Up Space

| Item | Location | Size (approx) |
|---|---|---|
| PyTorch (CUDA Nightly) | `venv/Lib/site-packages/` | ~3.5 GB |
| HuggingFace Transformers + CLIP weights | `venv/` + `.cache/` | ~1.5 GB |
| Ultralytics + OpenCV | `venv/` | ~500 MB |
| `yolo11l.pt` (YOLO weights) | `backend/` | ~50 MB |
| `yolo11l.engine` (TensorRT compiled) | `backend/` | ~51 MB |
| `node_modules/` | `frontend/` | ~250 MB |
| **Total (approx)** | | **~6–7 GB** |

---

## Quick Suspend (Free Disk Space)

Run the included uninstall script to reclaim all disk space while keeping 100% of your source code:

```powershell
# Double-click, or run in terminal:
.\UNINSTALL.bat
```

This will:
- ✅ Remove all pip packages from the venv
- ✅ Delete `backend/yolo11l.engine` (regenerates automatically on next run)
- ✅ Clear `__pycache__` directories
- ❌ Does **NOT** delete source code
- ❌ Does **NOT** delete `backend/yolo11l.pt` weights (kept to save re-download time)
- ❌ Does **NOT** delete `frontend/node_modules/` (run `npm install` if deleted)

> **Tip**: To also delete `node_modules/` run: `rd /s /q frontend\node_modules`

---

## Quick Resume (Reinstall Everything)

Double-click **`INSTALL.bat`** — it handles everything automatically.

Or manually:

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Install all Python dependencies
pip install -r requirements.txt

# Install PyTorch with CUDA support (RTX 5000 series)
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# If node_modules was deleted
cd frontend && npm install && cd ..

# Launch
.\Run_WingID.bat
```

> **Note on TensorRT Engine**: `yolo11l.engine` will be regenerated automatically the first time the backend starts. This takes **3–5 minutes** but only happens once — the result is cached to `backend/yolo11l.engine`.

---

## Minimal Keep List

If you want to keep the project folder as small as possible while retaining all code:

**Safe to delete:**
```
venv/                          ← Recreate with: python -m venv venv
frontend/node_modules/         ← Recreate with: npm install
backend/yolo11l.engine         ← Regenerates on first run (3–5 min)
**/__pycache__/                ← Always safe to delete
```

**Never delete:**
```
backend/app/main.py            ← Core ML + API logic
frontend/src/                  ← React UI source
requirements.txt               ← Dependency manifest
Run_WingID.bat                 ← Launch script
INSTALL.bat                    ← Setup script
backend/yolo11l.pt             ← YOLO weights (saves 50 MB re-download)
```

---

## Estimated Space After Cleanup

| State | Disk Usage |
|---|---|
| Fresh clone (no deps) | ~120 MB |
| After `UNINSTALL.bat` | ~200 MB |
| Fully installed | ~7 GB |
