# WingID — System Architecture 📡

> For a full engineering breakdown including algorithms, GPU stack, and performance data, see **[TECHNICAL_DEEP_DIVE.md](TECHNICAL_DEEP_DIVE.md)**.

---

## Stack Overview

| Layer | Technology |
|---|---|
| **Frontend** | Vite + React 19 + WebSocket API |
| **Backend** | FastAPI + Uvicorn (ASGI) |
| **ML Stage 1** | YOLOv11-Large via TensorRT (.engine) |
| **ML Stage 2** | HuggingFace CLIP (zero-shot image classification) |
| **ML Stage 3** | Pinhole Camera Geometry (altitude estimation) |
| **Camera** | OpenCV DirectShow (MJPG, 60fps) |
| **IPC** | Python `multiprocessing` + dual WebSocket bus |

---

## Process Map

```
┌──────────────────────────────────────────────────────────┐
│                    Run_WingID.bat                         │
│   Spawns backend terminal + frontend terminal            │
│   Waits 10s → Opens Chrome at localhost:5173             │
└────────────┬─────────────────────────────────────────────┘
             │
    ┌────────▼──────────┐          ┌────────────────────┐
    │  FastAPI :8000     │◄────────►│  React UI :5173    │
    │                   │  ws://   │                    │
    │  /ws              │          │  Live feed + logs  │
    │  /ws_internal     │          │  Feed toggle btns  │
    │  POST /start-feed │          │                    │
    │  POST /stop-feed  │          └────────────────────┘
    └────────┬──────────┘
             │ multiprocessing.Process (daemon)
    ┌────────▼──────────────────────────────────────────┐
    │                  ML Engine                         │
    │                                                    │
    │  VideoStream thread ──► OpenCV DirectShow          │
    │       ↓ Frame (BGR)                                │
    │  YOLOv11l.engine (TensorRT, CUDA:0)                │
    │       ↓ Aircraft BBoxes only (class=4)             │
    │  OpenCV surgical crop per detection                │
    │       ↓ Aircraft pixel crop                        │
    │  CLIP ViT-B/32 (HuggingFace, CUDA:0)              │
    │       ↓ Best label (16 tactical types)             │
    │  Altitude = (wingspan × focal_px) / bbox_w_px     │
    │       ↓ JSON { image, telemetry[] }                │
    │  ws_internal → FastAPI → broadcast → /ws           │
    └────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Child Process for ML Engine
The ML inference daemon runs as a separate OS process (`multiprocessing.Process`), not a thread. This bypasses Python's GIL for true parallelism and gives each CUDA context its own isolated scope.

### 2. Inverted Dual-WebSocket Bus
FastAPI WebSocket objects cannot be passed across process boundaries. Instead, the ML daemon opens a WebSocket **client** connection back to the same FastAPI server (`/ws_internal`), which relays frames to all connected frontend clients. This is the canonical pattern for cross-process real-time streaming in Python async applications.

### 3. Direct `img.src` Mutation
React's state system is too slow for 60fps video. The camera frame `<img>` element is updated via a `useRef` direct DOM mutation — bypassing the React reconciler entirely for the hot render path.

### 4. Shared Memory Toggle
The `streaming_active = multiprocessing.Value('b', True)` flag is a C-type in shared memory, atomically readable from both the FastAPI HTTP handler (parent process) and the ML inference loop (child process). This enables instant start/stop without restarting either process.

---

*See [TECHNICAL_DEEP_DIVE.md](TECHNICAL_DEEP_DIVE.md) for the full algorithm, performance data, and future roadmap.*
