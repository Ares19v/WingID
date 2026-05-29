# EVAL — WingID

> **Evaluation Date:** 2026-05-29  
> **Evaluator:** Automated Portfolio Review  
> **Maturity Level:** Production-Ready

---

## 1. Project Purpose & Problem Statement

WingID is a full-stack, real-time aerospace target identification platform that processes a live camera feed through a three-stage neural pipeline — detection, zero-shot classification, and distance estimation — entirely on-device with no cloud dependency. The target audience is computer vision developers, ML engineers, and technical researchers interested in applied aerospace object detection.

The zero-cloud constraint is the defining architectural choice: all inference runs locally, making the system viable in network-denied environments and eliminating the latency of cloud API round-trips. The project demonstrates a sophisticated integration of three distinct ML systems (YOLOv11-Large TensorRT, CLIP zero-shot classification, pinhole camera geometry) in a production-quality full-stack application.

---

## 2. Technical Architecture

The system has three computational layers:

**Layer 1 — ML Engine (multiprocessing.Process):**
- OpenCV DirectShow camera capture (CAP_DSHOW, MJPG, 60fps) in a background thread — decoupled from inference via a rolling frame buffer
- YOLOv11-Large TensorRT `.engine` — class=4 (airplane) filter, conf=0.85, NMS operating on pre-filtered candidates
- Per-detection: OpenCV surgical crop → CLIP ViT-B/32 zero-shot classification over 16 aircraft designations
- Pinhole camera geometry for distance estimation
- JSON payload via `ws_internal` WebSocket to FastAPI relay

**Layer 2 — FastAPI Backend (Uvicorn, port 8000):**
- Dual WebSocket pattern: `ws://8000/ws` (public frontend stream), `ws://8000/ws_internal` (ML daemon receiver)
- `multiprocessing.Value('b', True)` shared memory for atomic cross-process feed toggle
- `POST /start-feed` and `POST /stop-feed` HTTP endpoints — frontend calls these; ML daemon polls the shared flag
- `GET /health` and Swagger docs

**Layer 3 — React Command Center (Vite 8, port 5173):**
- Direct `img.src` mutation via React `ref` for 60fps frame rendering (bypasses reconciler entirely)
- Real-time FPS counter measuring actual frame delivery rate
- Live detection log with aircraft designation, CLIP confidence, and altitude estimate
- PDF intel dossier export via jsPDF
- JetBrains Mono terminal aesthetic

**Infrastructure:** Docker Compose, Nginx, GitHub Actions CI.

---

## 3. Model / Algorithm Details

**Stage 1 — YOLOv11-Large:**
- Architecture: YOLOv11l (Large variant) — chosen over smaller variants because aircraft are small, low-contrast targets at typical camera distances
- TensorRT compilation: INT8/FP16 quantization + layer fusion + kernel autotuning → 2–4x throughput vs standard PyTorch forward pass
- Auto-compiles from `.pt` on first run; `.engine` is architecture-specific (gitignored)
- Graceful `.pt` fallback if `.engine` absent
- Pre-trained on COCO (class 4 = airplane); no fine-tuning required

**Stage 2 — CLIP Zero-Shot Classification:**
- Model: `openai/clip-vit-base-patch32` (ViT-B/32 image encoder + text transformer)
- 16 aircraft label strings with deliberately rich descriptions (e.g., "AH-64 Apache Attack Helicopter with missiles and guns" vs simply "Apache Helicopter") — the label richness directly improves classification accuracy
- Zero-shot: no custom training data required; generalizes via shared image-text embedding space
- Bound to CUDA:0; runs sequentially per detection (batching is identified as the primary optimization opportunity)

**Stage 3 — Pinhole Camera Model:**
- `distance_m = (real_width_m × focal_length_px) / bounding_box_width_px`
- Fixed constants: 35m wingspan (commercial aircraft average), 800px focal length estimate
- Acknowledged ±30% error; requires camera calibration and per-class wingspan lookup for accuracy
- Intentionally simplified; documented as a known limitation

**Performance (RTX 5060 TensorRT):**
| Metric | Value |
|---|---|
| Camera capture | 60 fps |
| YOLO inference | ~50–60 fps |
| CLIP per detection | ~30–50 ms |
| End-to-end UI latency | ~80–120 ms |
| VRAM budget | ~3.0 GB total |

---

## 4. Strengths

- **Three-stage neural pipeline** — YOLO → CLIP → geometry is an elegant and technically ambitious design for a portfolio project.
- **Process isolation for the ML daemon** — separate `multiprocessing.Process` with its own CUDA context prevents GIL contention and provides crash isolation from the HTTP server. The TECHNICAL_DEEP_DIVE.md explains this design decision explicitly.
- **Dual WebSocket bus pattern** — the inverted architecture (ML daemon acts as WS client to its own server) elegantly crosses the process boundary without IPC primitives. The `max_size=None` and auto-reconnect logic show attention to production edge cases.
- **Direct `img.src` mutation** — bypassing React reconciler for 60fps frame rendering is the correct optimization; setState on every frame would cause jank.
- **Rich label strings for CLIP** — explicit documentation of why label text richness matters for zero-shot accuracy shows genuine model understanding.
- **Feed toggle with instant resume** — camera thread keeps running during pause; YOLO and CLIP stay loaded in VRAM. Resume is instant, not a cold restart.
- **TECHNICAL_DEEP_DIVE.md (15KB)** — one of the most thorough technical documents in the portfolio, covering every system with code examples and design rationale.
- **ARCHITECTURE.md + SPACE_MANAGEMENT.md** — comprehensive supplementary documentation.
- **Docker Compose + Nginx** — containerized deployment with frontend proxy.
- **GitHub Actions CI** — lint + build pipeline.

---

## 5. Limitations & Known Gaps

- **Single camera source.** Multi-camera support is roadmapped but absent. An aerospace detection system would realistically need to support multiple sensor inputs.
- **CLIP runs serially per detection.** If 3 aircraft are in frame simultaneously, CLIP runs 3 times sequentially. Batching crops into a single CLIP forward pass would significantly reduce latency at high detection counts.
- **Pinhole geometry is heavily approximated.** ±30% distance error with fixed 35m wingspan and uncalibrated 800px focal length makes the altitude readout decorative rather than operational. A camera calibration step and per-class wingspan lookup are the documented path to accuracy.
- **No training or fine-tuning.** YOLOv11l's COCO class 4 (airplane) is a coarse detector — it will fire on any aircraft silhouette. Military aircraft (fighter jets, UAVs) may be misclassified or missed at distance. A fine-tuned detector on military/aviation datasets would substantially improve precision.
- **PDF export is partially stubbed.** The TECHNICAL_DEEP_DIVE.md acknowledges "PDF export button is a stub" — `reportlab` or `jsPDF` integration is listed as future work.
- **No WebSocket authentication.** Open WebSocket endpoints on a local network are accessible to any client. Documented as a known limitation.
- **TensorRT engine is GPU-architecture-specific.** Not distributable; each user must compile locally. An ONNX fallback would enable cross-platform deployment.
- **Windows only for live camera feed.** Docker camera passthrough is Linux-native; the README correctly notes this limitation.

---

## 6. Code Quality Assessment

**Structure:** `backend/app/main.py` contains the FastAPI server, WebSocket bus, and ML engine spawn logic in a well-organized single file. `frontend/src/App.jsx` is the React command center. Clean separation between backend and frontend with independent Dockerfiles.

**Documentation:** Three dedicated technical documents (TECHNICAL_DEEP_DIVE.md, ARCHITECTURE.md, SPACE_MANAGEMENT.md) plus a comprehensive README. TECHNICAL_DEEP_DIVE is the best technical writing in the portfolio — code examples, design rationale, and known limitations are all present.

**Test Coverage:** Linting configured (`.flake8`). No unit or integration tests for the ML pipeline or FastAPI routes.

**Docker:** Multi-stage Dockerfiles for backend and frontend. NVIDIA Container Toolkit required for GPU passthrough (correctly documented). Nginx SPA config present.

---

## 7. Maturity Breakdown

| Dimension | Score | Notes |
|-----------|-------|-------|
| Functionality | 8/10 | Three-stage pipeline functional; PDF stub and serial CLIP are notable gaps |
| Code Quality | 8/10 | Clean process architecture; excellent documentation; thin test coverage |
| Documentation | 10/10 | Best-documented project in portfolio; TECHNICAL_DEEP_DIVE is exceptional |
| Scalability | 6/10 | Single camera; serial CLIP; no ONNX; Windows-only live feed |
| Security | 5/10 | No WS auth; no HTTPS in local deployment; acknowledged in docs |
| **Overall** | **7.4/10** | Technically ambitious and superbly documented; deployment constraints limit real-world use |

---

## 8. Suggested Next Steps

1. **Batch CLIP calls.** Collect all per-frame detection crops into a list and call `classifier()` once with `candidate_labels` applied to all crops simultaneously. This is the highest-impact single optimization — it eliminates the O(n) CLIP latency for scenes with multiple aircraft.
2. **Complete the PDF dossier export.** The stub is noted in the technical deep dive — `jsPDF` is already a frontend dependency (same as other projects in the portfolio). Completing this would close the most visible UX gap.
3. **Add camera calibration for altitude estimation.** Using `cv2.calibrateCamera()` with a checkerboard pattern to obtain real intrinsic parameters, plus a per-class wingspan lookup table (sourced from public aviation databases), would transform the altitude readout from decorative to defensible.

---

## 9. Verdict

WingID is the most technically ambitious full-stack project in the portfolio, combining three distinct neural systems (YOLO TensorRT, CLIP zero-shot, pinhole geometry) in a process-isolated, dual-WebSocket architecture with a genuine command-center aesthetic. The design decisions — process isolation for the ML daemon, inverted WS bus pattern, direct img.src mutation for 60fps rendering — are all well-reasoned and explicitly documented in what is arguably the best technical writing in the entire portfolio. The limitations are honest and well-identified: serial CLIP calls, approximate altitude estimation, partial PDF stub, and no WebSocket authentication. This project demonstrates a level of systems engineering thinking that sets it apart from the other entries.
