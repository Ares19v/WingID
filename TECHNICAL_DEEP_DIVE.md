# WingID — Technical Deep Dive 🔬

This document provides a comprehensive, engineering-level breakdown of every system, algorithm, and design decision inside WingID. It is intended for developers, ML engineers, and technical recruiters who want to understand how the system actually works — not just what it does.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Backend Architecture — FastAPI + IPC](#2-backend-architecture--fastapi--ipc)
3. [Camera Capture — DirectShow Pipeline](#3-camera-capture--directshow-pipeline)
4. [Stage 1: Object Detection — YOLOv11-Large + TensorRT](#4-stage-1-object-detection--yolov11-large--tensorrt)
5. [Stage 2: Zero-Shot Classification — CLIP](#5-stage-2-zero-shot-classification--clip)
6. [Stage 3: Altitude Estimation — Pinhole Geometry](#6-stage-3-altitude-estimation--pinhole-geometry)
7. [Dual WebSocket Architecture](#7-dual-websocket-architecture)
8. [Frontend — React Command Center](#8-frontend--react-command-center)
9. [Feed Toggle Control Plane](#9-feed-toggle-control-plane)
10. [GPU Stack — CUDA 12.8 + Blackwell SM_12.0](#10-gpu-stack--cuda-128--blackwell-sm_120)
11. [Performance Characteristics](#11-performance-characteristics)
12. [Known Limitations & Future Work](#12-known-limitations--future-work)

---

## 1. System Overview

WingID is a **three-stage, fully local neural inference pipeline** delivered inside a full-stack web application. The system was designed around a single constraint: **zero cloud dependency**. Every byte of computation happens on the local machine.

```
Camera Hardware (USB / Built-in)
        │  DirectShow (CAP_DSHOW) @ 60fps MJPG
        ▼
OpenCV VideoCapture (Background Thread)
        │  Raw BGR Frame
        ▼
YOLOv11-Large (TensorRT .engine)
        │  class=4 (airplane) detections only
        │  Bounding box coordinates (xyxy, xywh)
        ▼
OpenCV Surgical Crop (frame[y1:y2, x1:x2])
        │  Isolated aircraft pixel array
        ▼
HuggingFace CLIP (openai/clip-vit-base-patch32, CUDA:0)
        │  Zero-shot label scores across 16 tactical designations
        ▼
Altitude Math (Pinhole Camera Model)
        │  distance_m = (REAL_AIRCRAFT_SIZE_M * FOCAL_LENGTH_PX) / w_px
        ▼
JSON Payload: { image: base64, telemetry: [...] }
        │  ws_internal WebSocket
        ▼
FastAPI ConnectionManager.broadcast()
        │  ws:// public WebSocket
        ▼
React Frontend — Live Video + Combat Logs
```

---

## 2. Backend Architecture — FastAPI + IPC

### Why FastAPI?

FastAPI was chosen over Flask or Django because:
- **Native async/await** support via Starlette — essential for non-blocking WebSocket servers
- **WebSocket protocol** built into the framework (no third-party libraries needed)
- **Pydantic** validation for future endpoint expansion
- **ASGI** standard enables Uvicorn to use high-performance libuv event loop

### Process Isolation via `multiprocessing`

The ML inference engine runs in a **separate OS process** via `multiprocessing.Process`, not a thread. This is a critical design decision:

```python
p = multiprocessing.Process(target=run_ai_eye, daemon=True)
p.start()
```

**Why a process, not a thread?**

- **GIL (Global Interpreter Lock)**: Python's GIL prevents true parallel CPU execution across threads. A subprocess bypasses the GIL entirely.
- **CUDA Context Isolation**: PyTorch and TensorRT CUDA contexts are not safely shareable across threads in the same process. A separate process gets its own CUDA context.
- **Crash Isolation**: If the ML engine throws an unhandled exception (OOM, CUDA error), it dies without taking down the FastAPI HTTP server. The WebSocket reconnects automatically.

### Global Streaming Flag

A `multiprocessing.Value('b', True)` shared memory primitive is used to pass the start/stop signal across the process boundary:

```python
streaming_active = multiprocessing.Value('b', True)
```

`multiprocessing.Value` wraps a C-type in shared memory that is atomically readable/writable from both the parent (HTTP request handler) and child (ML daemon) processes — critical for thread-safe cross-process signalling without locks.

---

## 3. Camera Capture — DirectShow Pipeline

```python
self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
self.cap.set(cv2.CAP_PROP_FPS, 60)
```

**`cv2.CAP_DSHOW`** (DirectShow) is used instead of the default MSMF (Media Foundation) backend on Windows because:

- DirectShow allows **MJPG hardware compression** at the camera sensor level, reducing USB bandwidth by ~10x vs raw YUV
- MSMF adds a software decode pass that introduces ~120ms of latency
- DirectShow grants lower-level buffer access needed for 60fps without frame-drop

**The `VideoStream` threading model** decouples capture from inference:

```python
def update(self):
    while not self.stopped:
        self.ret, self.frame = self.cap.read()
```

A dedicated background thread continuously overwrites `self.frame` in place, so the ML loop always reads the **latest available frame** without blocking on I/O. This is a classic "rolling buffer" pattern for real-time CV systems.

---

## 4. Stage 1: Object Detection — YOLOv11-Large + TensorRT

### Model Selection

**YOLOv11-Large** (`yolo11l`) was selected over smaller variants because:
- The `l` variant achieves a strong balance between mAP and FPS on RTX hardware
- Aircraft are visually small, low-contrast targets — LR models miss them at typical distances
- COCO class `4` (airplane) is well-trained in the base model; no fine-tuning required

### TensorRT Compilation

On first run, `ultralytics` auto-exports from `.pt` → `.engine`:

```python
model = YOLO("yolo11l.engine", task='detect')
```

TensorRT applies:
- **INT8 / FP16 quantization** — halves memory bandwidth at minimal accuracy cost
- **Layer fusion** — consecutive Conv+BN+ReLU layers are fused into single CUDA kernels
- **Kernel autotuning** — TensorRT profiles multiple kernel implementations and picks the fastest for the exact GPU

**Result**: ~2–4x throughput improvement over standard PyTorch `model.forward()`.

### Class Filter

```python
results = model(frame, conf=0.85, verbose=False, device=0, classes=[4])
```

`classes=[4]` hard gates the detector to only emit airplane detections (COCO class index 4). This is more efficient than post-filtering because: YOLO's NMS (Non-Maximum Suppression) stage operates on a smaller candidate set, reducing compute.

A high confidence threshold of `conf=0.85` eliminates ghost detections at the cost of some distant/occluded targets — acceptable for this use case.

---

## 5. Stage 2: Zero-Shot Classification — CLIP

### Architecture

CLIP (Contrastive Language-Image Pre-Training) from OpenAI learns a joint embedding space between images and natural language text. During inference:

1. The aircraft crop is encoded by a **Vision Transformer (ViT-B/32)** → 512-dim image embedding
2. Each of the 16 candidate label strings is encoded by a **text transformer** → 512-dim text embeddings
3. Cosine similarity is computed between the image embedding and all text embeddings
4. The label with the highest cosine similarity is the predicted aircraft type

### Why Zero-Shot?

Training a custom military aircraft classifier requires:
- Thousands of labelled images per class
- Careful data augmentation for scale, lighting, and angle variance
- Full training infrastructure

CLIP eliminates this entirely. By writing descriptive natural language labels, the classifier generalises to aircraft it has never explicitly seen:

```python
tactical_labels = [
    "Boeing 737 Commercial Passenger Jet",
    "F-22 Raptor Stealth Fighter Jet",
    "AH-64 Apache Attack Helicopter with missiles and guns",
    "MQ-9 Reaper Military Drone UAV with hellfires",
    # ... 12 more
]
```

The richness of the label text directly improves classification accuracy — "AH-64 Apache Attack Helicopter **with missiles and guns**" performs measurably better than just "Apache Helicopter".

### GPU Binding

```python
classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32", device=0)
```

`device=0` binds CLIP directly to CUDA:0 (the primary GPU), sharing the GPU with YOLO without context conflicts because they run sequentially within the same ML process.

---

## 6. Stage 3: Altitude Estimation — Pinhole Geometry

### The Model

The system uses the **pinhole camera model** to estimate object distance:

```
distance = (real_width * focal_length) / pixel_width
```

In code:
```python
REAL_AIRCRAFT_SIZE_M = 35.0   # Approximate commercial aircraft wingspan (metres)
FOCAL_LENGTH_PX = 800.0       # Estimated focal length in pixels for a typical webcam

w_px = box.xywh[0][2].item()  # Pixel width of the bounding box
distance_m = (REAL_AIRCRAFT_SIZE_M * FOCAL_LENGTH_PX) / w_px
```

### Assumptions & Accuracy

| Parameter | Value | Notes |
|---|---|---|
| `REAL_AIRCRAFT_SIZE_M` | 35.0 m | Average commercial wingspan; fighter jets are ~10–13m |
| `FOCAL_LENGTH_PX` | 800.0 px | Typical 1080p webcam approximation |
| Output | Metres | Rough estimate; ±30% error expected |

This is intentionally simplified. Accurate distance estimation requires camera calibration matrices (intrinsic parameters), known target wingspan per-class, and atmospheric correction. Those are straightforward extensions for a V2.

---

## 7. Dual WebSocket Architecture

### The Problem with Single-WS Designs

A naive design would have the ML daemon write directly to connected frontend WebSocket clients. This fails because:
- FastAPI WebSocket objects are **not picklable** — they cannot be passed to a child process
- Even if shared, the event loop lives in the parent process; the child cannot `await` on it

### The Solution: WS Bus Pattern

WingID uses an **inverted dual-WebSocket bus**:

```
ML Daemon (child process)
    │
    │  ws://127.0.0.1:8000/ws_internal    (internal loopback)
    ▼
FastAPI /ws_internal handler
    │  receives JSON payload
    │  calls manager.broadcast(data)
    ▼
All connected frontend clients  (/ws)
```

The child process acts as a **WebSocket client** connecting to the same FastAPI server it lives inside. FastAPI's `/ws_internal` endpoint acts as the relay, forwarding every received frame to all connected frontend clients via `ConnectionManager.broadcast()`.

**Advantages:**
- Process boundary crossed cleanly using the network stack (no IPC primitives needed)
- `max_size=None` on the `websockets.connect` call prevents large Base64 frames from being truncated
- Auto-reconnect logic handles the 2–3 second window between server startup and ML engine ready state

---

## 8. Frontend — React Command Center

### Stack

| Tool | Version | Role |
|---|---|---|
| React | 19 | UI component tree |
| Vite | 8 | Dev server + HMR bundler |
| WebSocket API | Native | Browser WebSocket client |
| JetBrains Mono | Google Fonts | Terminal aesthetic typeface |

### Frame Rendering

```jsx
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.image && displayImageRef.current) {
    displayImageRef.current.src = "data:image/jpeg;base64," + data.image;
  }
};
```

Frames are rendered by **directly mutating `img.src`** on a `ref`-attached `<img>` element — bypassing React's reconciler entirely. This avoids the overhead of setState → re-render → DOM commit on every frame (60 times per second), which would cause significant jank.

### FPS Counter

```jsx
const now = Date.now();
setFps(Math.round(1000 / (now - lastFrameTime.current)));
lastFrameTime.current = now;
```

Measures the actual **frame delivery rate** at the frontend, accounting for network + processing latency. This is the real-world throughput number, not an artificial counter.

---

## 9. Feed Toggle Control Plane

The toggle system has three layers:

### Layer 1 — HTTP Control Endpoints (FastAPI)
```python
@app.post("/start-feed")
async def start_feed():
    streaming_active.value = True

@app.post("/stop-feed")
async def stop_feed():
    streaming_active.value = False
```

### Layer 2 — Shared Memory Gate (ML Daemon)
```python
if not streaming_active.value:
    await asyncio.sleep(0.1)
    continue
```

When stopped, the ML engine idles in a 100ms sleep loop. The camera thread **keeps running** (no cold restart needed) and CLIP + YOLO stay loaded in VRAM. Resume is instant.

### Layer 3 — UI State (React)
```jsx
const handleToggleFeed = async () => {
  if (isFeedActive) {
    await fetch('http://127.0.0.1:8000/stop-feed', { method: 'POST' });
    setIsFeedActive(false);
  } else {
    await fetch('http://127.0.0.1:8000/start-feed', { method: 'POST' });
    setIsFeedActive(true);
  }
};
```

The React state mirrors the backend state, updating UI labels (`TRACKING_ACTIVE` / `FEED_SUSPENDED`) and button styling (grey `▶ RESUME FEED` vs red `■ TERMINATE FEED`) immediately without waiting for a WebSocket round-trip.

---

## 10. GPU Stack — CUDA 12.8 + Blackwell SM_12.0

WingID was developed and tested on an **NVIDIA RTX 5060 (Blackwell architecture, SM_12.0)**. Key considerations:

- **PyTorch Nightly** is used because stable PyTorch does not yet support SM_12.0 compute capability at time of writing
- TensorRT engine files are **architecture-specific** — a `.engine` compiled on an RTX 5060 will not run on an RTX 3080
- If the `.engine` file is missing, `ultralytics` falls back to `.pt` with standard PyTorch CUDA inference
- CPU fallback is implicit — if no CUDA device is found, all operations fall to CPU (significant FPS reduction)

### VRAM Budget (Estimated)

| Component | VRAM |
|---|---|
| YOLOv11-Large (FP16 TensorRT) | ~2.0 GB |
| CLIP ViT-B/32 | ~0.6 GB |
| Frame buffers + overhead | ~0.3 GB |
| **Total** | **~3.0 GB** |

---

## 11. Performance Characteristics

| Metric | RTX 5060 (TensorRT) | RTX 3080 (TensorRT) | CPU Only |
|---|---|---|---|
| Camera Capture | 60 fps | 60 fps | 60 fps |
| YOLO Inference | ~50–60 fps | ~45–55 fps | ~3–5 fps |
| CLIP (per detection) | ~30–50 ms | ~40–70 ms | ~500 ms+ |
| E2E latency (UI) | ~80–120 ms | ~100–150 ms | >1000 ms |

CLIP is the primary bottleneck — it runs once **per detected aircraft** per frame. If 3 aircraft are in frame simultaneously, CLIP runs 3 times sequentially. Batching CLIP calls would be a high-impact optimisation.

---

## 12. Known Limitations & Future Work

| Limitation | Planned Fix |
|---|---|
| Single camera source only | Multi-camera support via camera index selector UI |
| CLIP runs serially per detection | Batch images for single CLIP forward pass |
| Fixed altitude constants | Per-class wingspan lookup table; camera calibration |
| No auth on WebSocket | Token-based WS auth for network deployment |
| PDF export button is a stub | `reportlab` or `jsPDF` integration |
| Engine tied to GPU architecture | Provide fallback `.onnx` for cross-platform compat |
| No logging to disk | Structured JSON log file with rotation |

---

*WingID — Built entirely on-device. No cloud. No compromise.*
