from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import multiprocessing
import cv2
import base64
import json
import asyncio
from ultralytics import YOLO
import threading
import os

# Global flag — controls whether frames are forwarded to the frontend
streaming_active = multiprocessing.Value('b', True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

class VideoStream:
    def __init__(self):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) 
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.ret, self.frame = self.cap.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
        self.cap.release()

REAL_AIRCRAFT_SIZE_M = 35.0
FOCAL_LENGTH_PX = 800.0

def run_ai_eye():
    print("Loading Primary TensorRT Tracking Pipeline...")
    model = YOLO("yolo11l.engine", task='detect')
    
    print("Initializing Military Intelligence Databanks (CLIP)...")
    from transformers import pipeline
    import PIL.Image
    import websockets
    
    # HuggingFace Zero-Shot mapped to the RTX GPU
    classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32", device=0)
    tactical_labels = [
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
        "Private Business Jet Aircraft"
    ]
    print("Intelligence Databanks Online.")

    stream = VideoStream().start()

    async def process_stream():
        import time
        time.sleep(3)
        while True:
            try:
                async with websockets.connect("ws://127.0.0.1:8000/ws_internal", max_size=None) as ws:
                    print("ML ENGINE SECURED INTERNAL HANDSHAKE")
                    while True:
                        # If feed is paused, hold frames without sending
                        if not streaming_active.value:
                            await asyncio.sleep(0.1)
                            continue

                        frame = stream.read()
                        if frame is None:
                            await asyncio.sleep(0.01)
                            continue
                        
                        # YOLO Pass: classes=[4] tracks airplanes only
                        results = model(frame, conf=0.85, verbose=False, device=0, classes=[4])
                        annotated = results[0].plot()
                        
                        defects = []
                        for box in results[0].boxes:
                            try:
                                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                                h, w, _ = frame.shape
                                x1, y1 = max(0, x1), max(0, y1)
                                x2, y2 = min(w, x2), min(h, y2)
                                
                                crop = frame[y1:y2, x1:x2]
                                
                                if crop.size > 0:
                                    rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                                    pil_img = PIL.Image.fromarray(rgb_crop)
                                    
                                    preds = classifier(pil_img, candidate_labels=tactical_labels)
                                    best_label = preds[0]['label']
                                    
                                    w_px = box.xywh[0][2].item()
                                    if w_px > 0:
                                        distance_m = (REAL_AIRCRAFT_SIZE_M * FOCAL_LENGTH_PX) / w_px
                                        defects.append(f"[{best_label.upper()}] ALT:{int(distance_m)}m")
                            except Exception as e:
                                pass
                        
                        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        img_str = base64.b64encode(buffer).decode('utf-8')
                        
                        out_payload = {
                            "image": img_str,
                            "telemetry": defects
                        }
                        await ws.send(json.dumps(out_payload))
                        await asyncio.sleep(0.001)
            except Exception as e:
                import time
                print("ML Engine Connection Dropped. Retrying in 2 seconds...")
                time.sleep(2)

    import asyncio
    asyncio.run(process_stream())

@app.websocket("/ws")
async def websocket_frontend(websocket: WebSocket):
    await websocket.accept()
    manager.active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.websocket("/ws_internal")
async def websocket_internal(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

@app.post("/start-feed")
async def start_feed():
    streaming_active.value = True
    return JSONResponse({"status": "streaming", "active": True})

@app.post("/stop-feed")
async def stop_feed():
    streaming_active.value = False
    return JSONResponse({"status": "paused", "active": False})

@app.on_event("startup")
async def startup_event():
    p = multiprocessing.Process(target=run_ai_eye, daemon=True)
    p.start()
    print("WingID ML Engine Initialized.")
