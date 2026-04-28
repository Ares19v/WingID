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

def run_ai_eye(shared_streaming_active: multiprocessing.Value) -> None:
    """
    ML inference daemon — spawned as a separate OS process.

    Receives *shared_streaming_active* explicitly so that the Windows
    spawn-mode child process shares the same underlying memory segment as
    the FastAPI parent process (module-level globals are NOT shared on
    Windows spawn).
    """
    import time
    import websockets as ws_lib
    import PIL.Image
    from ultralytics import YOLO
    from transformers import pipeline as hf_pipeline

    print("[WingID] Loading detection model...")
    engine_path = os.path.join(os.path.dirname(__file__), "..", "yolo11l.engine")
    pt_path = os.path.join(os.path.dirname(__file__), "..", "yolo11l.pt")

    # Prefer compiled TensorRT engine; fall back to .pt if engine not present
    model_path = engine_path if os.path.exists(engine_path) else pt_path
    print(f"[WingID] Using model: {os.path.basename(model_path)}")
    model = YOLO(model_path, task="detect")

    print("[WingID] Loading CLIP zero-shot classifier...")
    classifier = hf_pipeline(
        "zero-shot-image-classification",
        model="openai/clip-vit-base-patch32",
        device=0,
    )
    print("[WingID] Intelligence databanks online.")

    stream = VideoStream().start()

    async def process_stream() -> None:
        # Use asyncio.sleep (non-blocking) instead of time.sleep (blocks event loop)
        await asyncio.sleep(3)  # Wait for FastAPI server to be ready
        while True:
            try:
                async with ws_lib.connect(
                    "ws://127.0.0.1:8000/ws_internal",
                    max_size=None,
                ) as ws:
                    print("[WingID] ML engine secured internal handshake.")
                    while True:
                        # Pause: idle without forwarding frames
                        if not shared_streaming_active.value:
                            await asyncio.sleep(0.1)
                            continue

                        frame = stream.read()
                        if frame is None:
                            await asyncio.sleep(0.01)
                            continue

                        # Stage 1 — YOLO: detect aircraft (COCO class 4) only
                        results = model(
                            frame,
                            conf=0.85,
                            verbose=False,
                            device=0,
                            classes=[4],
                        )
                        annotated = results[0].plot()

                        telemetry: list[str] = []
                        for box in results[0].boxes:
                            try:
                                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                                h, w, _ = frame.shape
                                x1, y1 = max(0, x1), max(0, y1)
                                x2, y2 = min(w, x2), min(h, y2)
                                crop = frame[y1:y2, x1:x2]

                                if crop.size == 0:
                                    continue

                                # Stage 2 — CLIP: zero-shot aircraft type ID
                                rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                                pil_img = PIL.Image.fromarray(rgb_crop)
                                preds = classifier(
                                    pil_img,
                                    candidate_labels=TACTICAL_LABELS,
                                )
                                best_label = preds[0]["label"]
                                confidence = round(preds[0]["score"] * 100, 1)

                                # Stage 3 — Pinhole geometry: altitude estimate
                                w_px = box.xywh[0][2].item()
                                if w_px > 0:
                                    distance_m = int(
                                        (REAL_AIRCRAFT_SIZE_M * FOCAL_LENGTH_PX)
                                        / w_px
                                    )
                                    telemetry.append(
                                        f"[{best_label.upper()}]"
                                        f" | CONF:{confidence}%"
                                        f" | ALT:{distance_m}m"
                                    )
                            except Exception:
                                pass

                        _, buffer = cv2.imencode(
                            ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80]
                        )
                        img_b64 = base64.b64encode(buffer).decode("utf-8")

                        payload = json.dumps({"image": img_b64, "telemetry": telemetry})
                        await ws.send(payload)
                        await asyncio.sleep(0.001)

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
