# =============================================================================
# Stage: base
# =============================================================================
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

COPY services/se8-image-generation/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# OpenCV + Pillow for API (face_routes.py imports cv2, image_utils.py imports PIL)
RUN pip install --no-cache-dir numpy==1.24.0 opencv-python-headless==4.8.0.76 Pillow==10.0.0

# PyTorch (CPU-only for API, GPU version in Dockerfile.gpu for worker)
RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cpu

# Additional dependencies for API generation
RUN pip install --no-cache-dir psutil safetensors pyyaml

# =============================================================================
# Stage: api
# =============================================================================
FROM base AS api

WORKDIR /app

COPY services/se8-image-generation/app/ ./app/
COPY services/se8-image-generation/run.py ./run.py

# Vendored FOOOCUS dependencies (isolated inside SE8)
COPY services/se8-image-generation/ldm_patched/ ./ldm_patched/
COPY services/se8-image-generation/modules/ ./modules/
COPY services/se8-image-generation/sdxl_styles/ ./sdxl_styles/
COPY services/se8-image-generation/extras/ ./extras/
COPY services/se8-image-generation/args_manager.py ./args_manager.py

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/{outputs,models,temp} /app/data/models/{checkpoints,loras,vae,embeddings} && \
    touch /app/config.txt /app/config_modification_tutorial.txt && \
    chown -R appuser:appuser /app/data /app/config.txt /app/config_modification_tutorial.txt

USER appuser

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
