<div align="center">

# 🛩️ WingID
### Real-Time Aerospace Target Detection & Telemetry Command Center

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![PyTorch](https://img.shields.io/badge/PyTorch-Nightly-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![CUDA](https://img.shields.io/badge/CUDA-12.8-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-toolkit)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

*A military-aesthetic, GPU-accelerated aircraft detection system that runs entirely on-device — no cloud, no APIs, no compromise.*

</div>

---

## 📌 What Is WingID?

WingID is a **full-stack, real-time aerospace target identification platform** built for developers and researchers interested in applied computer vision on constrained hardware. It streams a live camera feed through a two-stage neural pipeline — first locking onto aircraft targets using a TensorRT-compiled **YOLOv11-Large** model, then performing **zero-shot optical classification** via a **HuggingFace CLIP** transformer to identify the exact aircraft designation (e.g., *F-22 Raptor*, *Boeing 737*, *MQ-9 Reaper*), and finally computing a rough **altitude/distance estimate** using pinhole camera geometry.

The entire processing chain runs locally in a **Python/FastAPI daemon** and renders in a **React Command Center UI** over a WebSocket link — achieving near-zero UI latency without any browser media API overhead.

---

## ✨ Key Features

| Feature | Detail |
|---|---|
| 🎯 **YOLOv11-Large TensorRT Inference** | NVIDIA TensorRT `.engine` compiled model, 60 FPS on RTX GPUs |
| 🧠 **Zero-Shot CLIP Classification** | HuggingFace `openai/clip-vit-base-patch32` — identifies 16 aircraft types without custom training data |
| 📐 **Pinhole Altitude Estimation** | Real-time distance math using bounding box pixel width and known wingspan constants |
| ⚡ **Dual WebSocket Pipeline** | Inverted producer/consumer WebSocket architecture — ML daemon pushes frames, frontend listens passively |
| 🖥️ **Command Center UI** | JetBrains Mono terminal aesthetic with live telemetry logs, FPS counter, and feed toggle |
| 🔴 **Live Feed Toggle** | Start / Terminate / Resume cam feed mid-session from the UI without restarting the backend |
| 📄 **PDF Intel Dossier Export** *(in progress)* | One-click export of the session's combat log |
| 🚀 **One-Click Launch** | Double-click `Run_WingID.bat` — both servers boot and Chrome opens automatically |

---

## 🏗️ System Architecture (High Level)

```
┌─────────────────────────────────────────────────────────┐
│                    Run_WingID.bat                        │
│         Boots FastAPI backend + Vite frontend            │
│            Opens Chrome at localhost:5173                │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────▼─────────┐          ┌──────────────────────┐
    │  FastAPI Backend  │◄────────►│   React Command      │
    │  (uvicorn :8000)  │  ws://   │   Center UI (:5173)  │
    └────────┬──────────┘          └──────────────────────┘
             │ multiprocessing.Process
    ┌────────▼──────────────────────────────────────────┐
    │              ML Engine (Python Daemon)             │
    │  OpenCV DirectShow → YOLOv11l.engine (TensorRT)   │
    │       ↓ Detected Aircraft Crop                     │
    │  CLIP Zero-Shot Classifier (HuggingFace)           │
    │       ↓ Best Label + Altitude Estimate             │
    │  ws_internal → FastAPI → ws → React Frontend       │
    └────────────────────────────────────────────────────┘
```

For the full deep-dive, see **[TECHNICAL_DEEP_DIVE.md](TECHNICAL_DEEP_DIVE.md)**.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 8, WebSocket API, JetBrains Mono |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, WebSockets |
| **Computer Vision** | OpenCV 4 (DirectShow, MJPG), YOLOv11-Large |
| **ML Inference** | PyTorch (CUDA 12.8 Nightly), NVIDIA TensorRT |
| **NLP / Zero-Shot** | HuggingFace Transformers, CLIP ViT-B/32 |
| **Geometry** | Pinhole Camera Model (focal-length + wingspan math) |
| **IPC** | Python `multiprocessing`, dual WebSocket bus |

---

## 🚀 Installation & Quick Start

> **Prerequisites:** Python 3.10+, Node.js 18+, Git, an NVIDIA GPU (RTX recommended)

### Step 1 — Clone the repository

```bash
git clone https://github.com/yourusername/WingID.git
cd WingID
```

### Step 2 — Create the Python virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3 — Install Python dependencies

```powershell
# Core dependencies
pip install -r requirements.txt

# PyTorch Nightly with CUDA 12.8 (RTX 5000 series / Blackwell SM_12.0)
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# For RTX 30/40 series (CUDA 11.8 / 12.1), use the stable channel instead:
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 4 — Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### Step 5 — Download the YOLO model weights

The YOLOv11-Large `.pt` weights are downloaded automatically by `ultralytics` on first run. To pre-download:

```powershell
python -c "from ultralytics import YOLO; YOLO('yolo11l.pt')"
```

> **TensorRT Engine**: On first run with an NVIDIA GPU, the system will auto-compile `yolo11l.pt` → `yolo11l.engine`. This takes **3–5 minutes** but only happens once. Subsequent launches use the cached `.engine` file directly.

### Step 6 — Launch

```powershell
# Option A: Double-click Run_WingID.bat (opens Chrome automatically)

# Option B: Manual
.\venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# In a second terminal:
cd frontend
npm run dev
```

Then open **http://localhost:5173** and click **INITIALIZE SENSORS**.

---

## 🗂️ Project Structure

```
WingID/
├── backend/
│   ├── app/
│   │   └── main.py            # FastAPI app, WebSocket server, ML engine process
│   ├── yolo11l.pt             # YOLOv11-Large weights (auto-downloaded)
│   ├── yolo11l.engine         # TensorRT compiled engine (auto-generated)
│   └── requirements.txt       # Backend-only pip deps
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # React Command Center UI
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── venv/                      # Python virtual environment (gitignored)
├── requirements.txt           # Root pip requirements
├── Run_WingID.bat             # One-click launch script
├── uninstall.bat              # Removes all heavy deps to free disk space
├── TECHNICAL_DEEP_DIVE.md     # Full architecture + algorithm documentation
├── ARCHITECTURE.md            # Architecture overview
├── .gitignore
└── README.md
```

---

## 🧹 Space Management (Laptop Friendly)

ML projects consume massive disk space. WingID ships with a dedicated **uninstall script** so you can wipe all heavy dependencies between sessions and reinstall when needed.

```powershell
# To free disk space (keeps all source code intact)
.\uninstall.bat

# To reinstall everything from scratch
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

See **[uninstall.bat](uninstall.bat)** and **[SPACE_MANAGEMENT.md](SPACE_MANAGEMENT.md)** for detailed guidance.

---

## 📸 System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.10 | 3.11 |
| GPU | NVIDIA GTX 1060 | NVIDIA RTX 3080+ |
| VRAM | 6 GB | 12 GB+ |
| RAM | 16 GB | 32 GB |
| Storage | 8 GB free | 15 GB free |
| Camera | Any USB/built-in | 1080p 60fps |

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `ws://localhost:8000/ws` | WebSocket | Frontend frame + telemetry stream |
| `ws://localhost:8000/ws_internal` | WebSocket | Internal ML → FastAPI bridge |
| `POST /start-feed` | HTTP | Resume frame broadcasting |
| `POST /stop-feed` | HTTP | Pause frame broadcasting |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with PyTorch · FastAPI · React · NVIDIA TensorRT
</div>
