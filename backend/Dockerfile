# ─────────────────────────────────────────────────────────────────────────────
# WingID — Backend Dockerfile
#
# Build context: project root (set in docker-compose.yml)
# GPU: Requires NVIDIA Container Toolkit for inference.
#      See docker-compose.yml → deploy.resources.reservations.devices
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="Devansh Tyagi"
LABEL description="WingID FastAPI backend — ML inference server"

# System dependencies required by OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/app ./app

# ─── NOTE ON MODEL WEIGHTS ────────────────────────────────────────────────
# yolo11l.pt / yolo11l.engine are gitignored (>50 MB each).
# Mount them at runtime via a Docker volume, e.g.:
#   docker run -v ./backend/yolo11l.pt:/app/yolo11l.pt ...
# Or they will be auto-downloaded by ultralytics on first run.
# ─────────────────────────────────────────────────────────────────────────

EXPOSE 8000

# Disable uvicorn reload in production container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
