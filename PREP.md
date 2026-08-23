# PREP — WingID (From-Scratch Study Guide)

Welcome to the beginner-friendly developer study guide for **WingID**! This guide is tailored to help you understand advanced computer vision integration, real-time Python multiprocessing architectures, and high-performance React UI optimizations.

---

## 1. The Three-Stage Computer Vision & ML Pipeline

WingID uses a highly modular three-stage vision pipeline to transform raw camera pixels into rich tactical aerospace telemetry:

```
┌─────────────┐   Frame   ┌──────────────┐   BBox Crop   ┌─────────────┐   Label/Distance   ┌───────────────┐
│ Camera Feed ├──────────►│ YOLO Detection├─────────────►│    CLIP     ├───────────────────►│ Pinhole Model │
│  (60 fps)   │           │   (Find plane)│              │(Classify plane)                │  (Estimate d) │
└─────────────┘           └──────────────┘               └─────────────┘                └───────────────┘
```

### Stage 1: Object Detection (YOLOv11)
* **What it does**: Scanning the active frame to detect objects matching the category `airplane` (class 4 in the COCO dataset).
* **How it's optimized**: Uses **NVIDIA TensorRT** (`.engine`). TensorRT takes the standard PyTorch model and compiles it to fuse layers, quantize numeric precision (FP16/INT8), and auto-tune GPU kernels, accelerating performance by 2x to 4x.

### Stage 2: Zero-Shot Classification (CLIP)
* **What it does**: Once YOLO spots an airplane and provides its bounding box coordinates, OpenCV performs a pixel-level crop. This small image is sent to **CLIP** (Contrastive Language-Image Pre-training) by OpenAI.
* **Why it's cool**: Unlike normal classifiers that must be trained on thousands of labeled images, CLIP is a **zero-shot** model. It takes an image and a list of text labels (e.g. "AH-64 Apache Helicopter", "Boeing 747 Commercial Airliner") and maps them to a shared embedding space to see which text label best matches the visual context.

### Stage 3: Distance Estimation (Pinhole Camera Model)
* **What it does**: Using camera geometry to estimate the distance to the target.
* **The Mathematics**:
  $$\text{Distance (meters)} = \frac{\text{Real Wingspan (meters)} \times \text{Focal Length (pixels)}}{\text{Bounding Box Width (pixels)}}$$
  By knowing the average size of a commercial plane (approx. 35m) and estimating the focal length (approx. 800px), we can use the size of the box on the screen to deduce distance in 3D space.

---

## 2. Multi-processing & Bypassing the Python GIL

In Python, the **Global Interpreter Lock (GIL)** prevents multiple threads from executing Python bytecodes simultaneously. If we ran camera fetching, YOLO inference, CLIP classification, and a FastAPI web server in a single process, the CPU and GPU would constantly bottleneck.

### Process Isolation Solution
WingID moves the entire ML inference loop into a separate **OS child process** using `multiprocessing.Process`.
* Each process has its own GIL, allowing true parallel CPU core execution.
* Each process maintains an isolated **NVIDIA CUDA Context**, keeping GPU memory operations completely separate from the web API.

### Shared Memory Flags
To let the web server control the ML process instantly without process restart overhead, we use **shared memory**:
```python
import multiprocessing

# Allocate an atomic, thread-safe boolean in C shared memory
streaming_active = multiprocessing.Value('b', True)
```
Both the FastAPI handler and the ML process read/write to this shared byte instantly.

---

## 3. The Inverted Dual-WebSocket Bus

FastAPI web socket objects cannot be passed across process boundaries. To solve this, WingID uses an elegant, inverted dual-websocket bus:

1. The **FastAPI Backend** acts as a web server listening on port `8000`.
2. The **ML Daemon** (child process) acts as a **WebSocket client**, opening a local connection to `ws://localhost:8000/ws_internal`.
3. When the ML daemon processes a frame, it streams the image (Base64) and findings down `ws_internal`.
4. FastAPI intercepts this stream and immediately broadcasts it to the frontend clients connected at `ws://localhost:8000/ws`.

---

## 4. Direct DOM Manipulation in React

React's reconciliation engine uses a Virtual DOM. If you change a component's state 60 times a second using `useState(frame)`, React will trigger re-evaluation overhead, garbage collection spikes, and visible visual lag (jank).

### Bypassing the React Reconciler
To render live 60fps video frames smoothly:
1. Reference the raw HTML image tag directly using a React **`useRef`**.
2. Mutate the `src` attribute imperatively without notifying React.

```jsx
import { useRef, useEffect } from 'react';

function LiveFeed({ socket }) {
  const imgRef = useRef(null);

  useEffect(() => {
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Mutate raw HTML element directly for 60fps fluid rendering
      if (imgRef.current) {
        imgRef.current.src = `data:image/jpeg;base64,${data.image}`;
      }
    };
  }, [socket]);

  return <img ref={imgRef} alt="Tactical Feed" className="w-full h-auto border" />;
}
```

---

## 5. Exercises & Self-Guided Challenges

1. **Implement CLIP Crop Batching**: The current pipeline processes crops serially. Re-write the classification layer to collect multiple bounding boxes in a frame and feed them into CLIP as a single tensor batch to maximize CUDA parallelism.
2. **Dynamic Wingspan Lookup**: Enhance the distance estimation algorithm by looking up the actual wingspan based on the CLIP classification output (e.g. F-16 = 10m vs. Boeing 747 = 64m) to improve distance calculations.
3. **Build the PDF Intel Dossier**: Locate the stubbed function in the frontend code, and integrate `jsPDF` to generate a formatted PDF document containing the active screen frame and associated aircraft metadata logs.
