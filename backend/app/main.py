"""
WingID — FastAPI Backend
Dual-WebSocket aerospace target detection server.
ML inference runs in an isolated subprocess; results are relayed to
all connected frontend clients via a WebSocket bus.
"""

import asyncio
import base64
import json
import multiprocessing
import os
import threading

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="WingID API", version="1.0.0")

# Wildcard is intentional — WingID is a local-only tool with no network exposure.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared-memory toggle flag
#
# IMPORTANT (Windows): Python uses the "spawn" start method on Windows, so
# child processes receive a *fresh* copy of every module-level variable.
# We initialise streaming_active in startup_event() and pass it explicitly
# as an argument to the child process so both processes reference the SAME
# shared-memory segment rather than independent copies.
# ---------------------------------------------------------------------------

streaming_active: multiprocessing.Value  # initialised in startup_event


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Tracks active frontend WebSocket connections and broadcasts frames."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        # NOTE: No asyncio.Lock here — creating asyncio primitives at module
        # level (before any event loop runs) is deprecated in Python 3.10+.
        # This manager is only used from within a single uvicorn event loop,
        # so plain list operations are safe.

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str) -> None:
        """Send *message* to every connected client; silently drop dead ones."""
        dead: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Threaded camera capture (rolling-buffer pattern)
# ---------------------------------------------------------------------------

class VideoStream:
    """
    Captures frames on a background thread so the ML loop always reads
    the most recent frame without blocking on I/O.
    """

    def __init__(self, camera_index: int = 0) -> None:
        # DirectShow reduces latency vs MSMF; MJPG cuts USB bandwidth ~10x
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.ret, self.frame = self.cap.read()
        self.stopped = False

    def start(self) -> "VideoStream":
        threading.Thread(target=self._update, daemon=True).start()
        return self

    def _update(self) -> None:
        while not self.stopped:
            self.ret, self.frame = self.cap.read()

    def read(self):
        return self.frame

    def stop(self) -> None:
        self.stopped = True
        self.cap.release()


# ---------------------------------------------------------------------------
# ML inference constants
# ---------------------------------------------------------------------------

REAL_AIRCRAFT_SIZE_M: float = 35.0   # Average commercial wingspan (metres)
FOCAL_LENGTH_PX: float = 800.0       # Typical 1080p webcam approximation

TACTICAL_LABELS: list[str] = [
    "Boeing 737 Commercial Passenger Jet",
    "Boeing 747 Jumbo Jet",
    "Airbus A380 Commercial Jet",
    "F-22 Raptor Stealth Fighter Jet",
    "F-35 Lightning II Stealth Fighter",
    "F-16 Fighting Falcon Military Jet",
    "F-15 Eagle Strike Fighter",
    "F/A-18 Hornet Navy Fighter Jet",
    "A-10 Warthog Ground Attack Aircraft with cannons and missiles",
    "B-2 Spirit Stealth Bomber",
    "C-130 Hercules Military Transport Plane",
    "AH-64 Apache Attack Helicopter with missiles and guns",
    "UH-60 Black Hawk Military Transport Helicopter",
    "MQ-9 Reaper Military Drone UAV with hellfires",
    "Civilian Cessna Propeller Plane",
    "Private Business Jet Aircraft",
]


# ---------------------------------------------------------------------------
# ML Engine (runs in child process)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Inference state — shared between the ML thread and the async send loop
# ---------------------------------------------------------------------------

class _InferenceState:
    """Thread-safe container for the latest ML detection results."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.boxes: list[tuple] = []     # (x1,y1,x2,y2,label,conf,dist_m)
        self.telemetry: list[str] = []   # formatted strings for the UI

    def update(self, boxes, telemetry) -> None:
        with self._lock:
            self.boxes = boxes
            self.telemetry = telemetry

    def read(self) -> tuple[list, list]:
        with self._lock:
            return list(self.boxes), list(self.telemetry)


def _draw_detections(frame, boxes: list[tuple]):
    """
    Overlay the latest bounding boxes onto *frame* in-place.
    Uses OpenCV directly so we can annotate the CURRENT camera frame
    rather than the (potentially stale) frame from the last inference pass.
    """
    for (x1, y1, x2, y2, label, conf, dist_m) in boxes:
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Label background + text
        short = label[:24]
        tag = f"{short}  {conf:.0f}%  {dist_m}m"
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cy = max(y1 - 4, th + 6)
        cv2.rectangle(frame, (x1, cy - th - 6), (x1 + tw + 8, cy + 2), (0, 200, 0), -1)
        cv2.putText(frame, tag, (x1 + 4, cy - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return frame


def _inference_worker(
    stream: "VideoStream",
    model,
    classifier,
    device,
    state: "_InferenceState",
    shared_streaming_active: multiprocessing.Value,
) -> None:
    """
    Runs YOLO + CLIP continuously on a background thread.
    Processes frames as fast as hardware allows and stores results in *state*.
    The async send loop reads *state* independently at 30 FPS.
    """
    import time
    import PIL.Image

    while True:
        if not shared_streaming_active.value:
            time.sleep(0.05)
            continue

        frame = stream.read()
        if frame is None:
            time.sleep(0.01)
            continue

        try:
            results = model(frame, conf=0.85, verbose=False,
                            device=device, classes=[4])
            boxes: list[tuple] = []
            telemetry: list[str] = []

            for box in results[0].boxes:
                try:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    h, w = frame.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue

                    # Stage 2 — CLIP zero-shot classification
                    rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    pil_img = PIL.Image.fromarray(rgb_crop)
                    preds = classifier(pil_img, candidate_labels=TACTICAL_LABELS)
                    label = preds[0]["label"]
                    conf = round(preds[0]["score"] * 100, 1)

                    # Stage 3 — Pinhole altitude estimate
                    w_px = box.xywh[0][2].item()
                    dist_m = (int((REAL_AIRCRAFT_SIZE_M * FOCAL_LENGTH_PX) / w_px)
                               if w_px > 0 else 0)

                    boxes.append((x1, y1, x2, y2, label, conf, dist_m))
                    telemetry.append(
                        f"[{label.upper()}] | CONF:{conf}% | ALT:{dist_m}m"
                    )
                except Exception:
                    pass

            state.update(boxes, telemetry)

        except Exception:
            pass


def run_ai_eye(shared_streaming_active: multiprocessing.Value) -> None:
    """
    ML inference daemon — spawned as a separate OS process.

    Architecture:
      • _inference_worker() runs YOLO+CLIP on a background thread at
        whatever FPS the hardware allows (1 FPS CPU / 60 FPS GPU).
      • process_stream() async loop reads the CURRENT camera frame at
        30 FPS and overlays the latest detection boxes — giving smooth
        video regardless of inference speed.
    """
    import time
    import websockets as ws_lib
    import torch
    from ultralytics import YOLO
    from transformers import pipeline as hf_pipeline

    # ── Device detection ────────────────────────────────────────────────────
    cuda_available = torch.cuda.is_available()
    device = 0 if cuda_available else "cpu"
    print(f"[WingID] Device: {'CUDA:0 (GPU)' if cuda_available else 'CPU — inference thread decoupled from stream'}")

    # TensorRT .engine is GPU-only
    engine_path = os.path.join(os.path.dirname(__file__), "..", "yolo11l.engine")
    pt_path     = os.path.join(os.path.dirname(__file__), "..", "yolo11l.pt")
    model_path  = (engine_path if (cuda_available and os.path.exists(engine_path))
                   else pt_path)
    print(f"[WingID] Loading model: {os.path.basename(model_path)}")
    model = YOLO(model_path, task="detect")

    print("[WingID] Loading CLIP zero-shot classifier...")
    classifier = hf_pipeline(
        "zero-shot-image-classification",
        model="openai/clip-vit-base-patch32",
        device=device,
    )
    print("[WingID] Intelligence databanks online.")

    stream = VideoStream().start()
    state  = _InferenceState()

    # Start ML inference on a background thread (non-blocking relative to send loop)
    inf_thread = threading.Thread(
        target=_inference_worker,
        args=(stream, model, classifier, device, state, shared_streaming_active),
        daemon=True,
    )
    inf_thread.start()
    print("[WingID] Inference thread started.")

    # ── Async send loop — always runs at ~30 FPS ────────────────────────────
    async def process_stream() -> None:
        await asyncio.sleep(3)   # wait for FastAPI server to be ready
        while True:
            try:
                async with ws_lib.connect(
                    "ws://127.0.0.1:8000/ws_internal",
                    max_size=None,
                ) as ws:
                    print("[WingID] ML engine secured internal handshake.")
                    while True:
                        if not shared_streaming_active.value:
                            await asyncio.sleep(0.05)
                            continue

                        frame = stream.read()
                        if frame is None:
                            await asyncio.sleep(0.01)
                            continue

                        # Overlay latest ML boxes onto the CURRENT frame
                        frame = frame.copy()
                        boxes, telemetry = state.read()
                        if boxes:
                            _draw_detections(frame, boxes)

                        _, buffer = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                        )
                        img_b64 = base64.b64encode(buffer).decode("utf-8")
                        payload = json.dumps({"image": img_b64, "telemetry": telemetry})
                        await ws.send(payload)

                        # ~30 FPS cap — keeps bandwidth reasonable
                        await asyncio.sleep(1 / 30)

            except Exception as exc:
                print(f"[WingID] ML engine connection dropped: {exc}. Retrying in 2s...")
                await asyncio.sleep(2)

    asyncio.run(process_stream())


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_frontend(websocket: WebSocket) -> None:
    """Public WebSocket — frontend connects here to receive live frames."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.websocket("/ws_internal")
async def websocket_internal(websocket: WebSocket) -> None:
    """Internal WebSocket — ML engine connects here to push frames upstream."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP control endpoints
# ---------------------------------------------------------------------------

@app.post("/start-feed")
async def start_feed() -> JSONResponse:
    """Resume broadcasting frames to connected frontend clients."""
    streaming_active.value = True
    return JSONResponse({"status": "streaming", "active": True})


@app.post("/stop-feed")
async def stop_feed() -> JSONResponse:
    """Pause frame broadcasting without stopping the camera or unloading models."""
    streaming_active.value = False
    return JSONResponse({"status": "paused", "active": False})


@app.get("/health")
async def health() -> JSONResponse:
    """Health-check endpoint for CI / monitoring."""
    return JSONResponse({"status": "ok", "streaming": bool(streaming_active.value)})


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    global streaming_active  # noqa: PLW0603
    streaming_active = multiprocessing.Value("b", True)

    # Pass the Value explicitly so Windows spawn-mode child shares the same
    # shared-memory segment rather than creating an independent copy.
    p = multiprocessing.Process(
        target=run_ai_eye,
        args=(streaming_active,),
        daemon=True,
    )
    p.start()
    print("[WingID] ML engine process started.")
