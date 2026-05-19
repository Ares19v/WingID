<div align="center">

# 🛩️ WingID
### Real-Time Aerospace Target Detection & Telemetry Command Center

[![CI](https://github.com/Ares19v/WingID/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Ares19v/WingID/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![PyTorch](https://img.shields.io/badge/PyTorch-Nightly-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org)
[![CUDA](https://img.shields.io/badge/CUDA-12.8-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-toolkit)
[![License](https://img.shields.io/badge/License-MIT-8b5cf6?style=flat-square)](LICENSE)

*A military-aesthetic, GPU-accelerated aircraft detection system that runs entirely on-device — no cloud, no APIs, no compromise.*

</div>

---

## 📌 What Is WingID?

WingID is a **full-stack, real-time aerospace target identification platform** built for developers and researchers interested in applied computer vision. It streams a live camera feed through a two-stage neural pipeline — first locking onto aircraft targets using a TensorRT-compiled **YOLOv11-Large** model, then performing **zero-shot optical classification** via a **HuggingFace CLIP** transformer to identify the exact aircraft designation (e.g., *F-22 Raptor*, *Boeing 737*, *MQ-9 Reaper*), and finally computing a rough **altitude/distance estimate** using pinhole camera geometry.

The entire processing chain runs locally in a **Python/FastAPI daemon** and renders in a **React Command Center UI** over a WebSocket link — achieving near-zero UI latency without any cloud dependency.

---

## ✨ Key Features

| Feature | Detail |
|---|---|
| 🎯 **YOLOv11-Large TensorRT** | NVIDIA TensorRT `.engine` compiled model, 60 FPS on RTX GPUs |
| 🧠 **Zero-Shot CLIP Classification** | `openai/clip-vit-base-patch32` — identifies 16 aircraft types without custom training data |
| 📐 **Pinhole Altitude Estimation** | Real-time distance math using bounding box pixel width and known wingspan constants |
| ⚡ **Dual WebSocket Pipeline** | Inverted producer/consumer architecture — ML daemon pushes frames, frontend listens passively |
| 🖥️ **Command Center UI** | JetBrains Mono terminal aesthetic with live telemetry, FPS counter, and detection log |
| 🔴 **Live Feed Toggle** | Start / Terminate / Resume cam feed mid-session without restarting the backend |
| 📄 **PDF Intel Dossier Export** | One-click export of the full session detection log as a formatted PDF |
| 🚀 **One-Click Launch** | `Run_WingID.bat` — pre-flight checks, both servers boot, Chrome opens automatically |

---

## 🏗️ System Architecture

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
    │       ↓ Best Label + Confidence + Altitude         │
    │  ws_internal → FastAPI → ws → React Frontend       │
    └────────────────────────────────────────────────────┘
```

For the full engineering breakdown, see **[TECHNICAL_DEEP_DIVE.md](TECHNICAL_DEEP_DIVE.md)** and **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 8, WebSocket API, jsPDF, JetBrains Mono |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, WebSockets |
| **Computer Vision** | OpenCV 4 (DirectShow, MJPG) |
| **ML Inference** | PyTorch (CUDA 12.8 Nightly), NVIDIA TensorRT, YOLOv11-Large |
| **NLP / Zero-Shot** | HuggingFace Transformers, CLIP ViT-B/32 |
| **Geometry** | Pinhole Camera Model |
| **IPC** | Python `multiprocessing`, dual WebSocket bus |
| **Containerisation** | Docker, Docker Compose, Nginx |
| **CI/CD** | GitHub Actions |

---

## 🚀 Installation & Quick Start

> **Prerequisites:** Python 3.10+, Node.js 18+, Git, an NVIDIA GPU (RTX recommended)

### Option A — Automated (Recommended)

```powershell
git clone https://github.com/Ares19v/WingID.git
cd WingID
```

Then double-click **`INSTALL.bat`** — it will:
1. Create a Python virtual environment
2. Install all Python dependencies
3. Prompt you to select your CUDA version and install PyTorch
4. Install frontend Node.js dependencies

### Option B — Manual

```powershell
# 1. Clone
git clone https://github.com/Ares19v/WingID.git
cd WingID

# 2. Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Core Python dependencies
pip install -r requirements.txt

# 4. PyTorch with CUDA (select your GPU generation)
# RTX 5000 series (Blackwell / CUDA 12.8 Nightly):
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# RTX 30/40 series (CUDA 12.1 Stable):
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 5. Frontend dependencies
cd frontend && npm install && cd ..
```

### Launch

Double-click **`Run_WingID.bat`** — both servers start and Chrome opens automatically.

Or manually:

```powershell
# Terminal 1 — Backend
.\venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Then open **http://localhost:5173** and click **INITIALIZE SENSORS**.

> **TensorRT Engine**: On first run with an NVIDIA GPU, the system auto-compiles `yolo11l.pt` → `yolo11l.engine`. This takes **3–5 minutes** but only happens once. Subsequent launches use the cached `.engine` directly.

---

## 🗂️ Project Structure

```
WingID/
├── backend/
│   ├── app/
│   │   └── main.py              # FastAPI server, WebSocket bus, ML engine process
│   ├── Dockerfile               # Backend container (NVIDIA GPU passthrough required)
│   ├── .dockerignore
│   ├── yolo11l.pt               # YOLOv11-Large weights (auto-downloaded, gitignored)
│   ├── yolo11l.engine           # TensorRT compiled engine (auto-generated, gitignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React Command Center UI
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── nginx.conf               # Nginx SPA config for container deployment
│   ├── Dockerfile               # Multi-stage build → Nginx Alpine
│   ├── .dockerignore
│   ├── package.json
│   └── vite.config.js
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions: lint + build pipeline
├── docker-compose.yml           # Full-stack container orchestration
├── requirements.txt             # Root Python requirements
├── Run_WingID.bat               # One-click local launcher
├── INSTALL.bat                  # First-time setup script
├── UNINSTALL.bat                # Space reclamation script
├── .flake8                      # Python linter configuration
├── ARCHITECTURE.md
├── TECHNICAL_DEEP_DIVE.md
├── SPACE_MANAGEMENT.md
├── .gitignore
└── README.md
```

---

## 🐳 Docker

> **Note:** Docker deployment requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU passthrough. Camera passthrough to Docker containers is Linux-native; Windows users should use `Run_WingID.bat` for local development.

```bash
# Build and start all services
docker compose up --build

# Backend only
docker compose up --build backend
```

The frontend will be served at `http://localhost:80` and the backend API at `http://localhost:8000`.

---

## 🧹 Space Management

ML projects consume significant disk space. WingID ships with dedicated scripts:

```powershell
# Free disk space (keeps all source code)
.\UNINSTALL.bat

# Reinstall everything from scratch
.\INSTALL.bat
```

See **[SPACE_MANAGEMENT.md](SPACE_MANAGEMENT.md)** for a full breakdown (~6–15 GB recoverable).

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
| `GET /health` | HTTP | Health check (CI / monitoring) |
| `GET /docs` | HTTP | Interactive API documentation (Swagger) |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with PyTorch · FastAPI · React · NVIDIA TensorRT
</div>

---
<p align="center">
  Made by Devansh Tyagi @ 2026
</p>