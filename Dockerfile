FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt

# CPU PyTorch for reliable FYP demo images (avoids multi-GB CUDA wheels).
# Fail the build if core deps cannot install. MediaPipe remains optional.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu \
    && grep -v -E '^(torch|torchvision)==' /app/backend/requirements.txt \
        > /tmp/requirements.nocuda.txt \
    && pip install --no-cache-dir -r /tmp/requirements.nocuda.txt

# MediaPipe is optional and large; OpenCV posture fallback is used in-container.
# Install later with: docker compose exec api pip install mediapipe

COPY backend /app/backend
COPY ai /app/ai

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app
# Force CPU inference in containers unless overridden
ENV YOLO_DEVICE=cpu
EXPOSE 8000

ENTRYPOINT ["python", "/app/backend/docker_entrypoint.py"]
