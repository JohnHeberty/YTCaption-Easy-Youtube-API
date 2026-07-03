# =============================================================================
# Stage: base
# =============================================================================
FROM python:3.11-slim AS base

ARG DEVICE=cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libxcb1 libxcb-shm0 libxcb-xfixes0 libxcb-shape0 \
    git && \
    rm -rf /var/lib/apt/lists/*

COPY shared/ ./common/
RUN pip install --no-cache-dir ./common

# Install CPU or GPU requirements based on DEVICE arg
COPY services/se10-clothes-segmentation/requirements.txt ./requirements.txt
COPY services/se10-clothes-segmentation/requirements-cpu.txt ./requirements-cpu.txt
RUN if [ "$DEVICE" = "cpu" ]; then \
      pip install --no-cache-dir -r requirements-cpu.txt; \
    else \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu130 -r requirements.txt; \
    fi && \
    chmod -R a+r /usr/local/lib/python3.11/site-packages

# =============================================================================
# Stage: api
# =============================================================================
FROM base AS api

ARG DEVICE=cpu

WORKDIR /app

COPY services/se10-clothes-segmentation/app/ ./app/
COPY services/se10-clothes-segmentation/run.py ./run.py

# External ML repos (GroundingDINO + SAM2) — install as editable
COPY services/se10-clothes-segmentation/external/GroundingDINO/ ./external/GroundingDINO/
COPY services/se10-clothes-segmentation/external/segment-anything-2/ ./external/segment-anything-2/
RUN pip install --no-cache-dir -e ./external/GroundingDINO && \
    pip install --no-cache-dir -e ./external/segment-anything-2

# Checkpoints (read-only, expected to be mounted as volume in prod)
COPY services/se10-clothes-segmentation/checkpoints/ ./checkpoints/

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/{inputs,outputs,temp} && \
    chown -R appuser:appuser /app/data

# Create symlinks for CUDA libs ONLY when GPU mode
RUN if [ "$DEVICE" != "cpu" ]; then \
      ln -sf /usr/local/lib/python3.11/site-packages/nvidia/cu13/lib/libcudart.so.13 /usr/lib/x86_64-linux-gnu/libcudart.so.13 && \
      ln -sf /usr/local/lib/python3.11/site-packages/nvidia/cublas/lib/libcublas.so.12 /usr/lib/x86_64-linux-gnu/libcublas.so.12 && \
      ln -sf /usr/local/lib/python3.11/site-packages/nvidia/cublas/lib/libcublasLt.so.12 /usr/lib/x86_64-linux-gnu/libcublasLt.so.12 && \
      ln -sf /usr/local/lib/python3.11/site-packages/nvidia/cufft/lib/libcufft.so.11 /usr/lib/x86_64-linux-gnu/libcufft.so.11 && \
      ln -sf /usr/local/lib/python3.11/site-packages/nvidia/cufft/lib/libcufftw.so.11 /usr/lib/x86_64-linux-gnu/libcufftw.so.11 && \
      for lib in /usr/local/lib/python3.11/site-packages/nvidia/cu13/lib/*.so* /usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib/*.so* /usr/local/lib/python3.11/site-packages/nvidia/cublas/lib/*.so* /usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib/*.so* /usr/local/lib/python3.11/site-packages/nvidia/cufft/lib/*.so*; do \
        name=$(basename $lib); \
        [ ! -e /usr/lib/x86_64-linux-gnu/$name ] && ln -sf $lib /usr/lib/x86_64-linux-gnu/$name 2>/dev/null || true; \
      done && ldconfig; \
    fi

USER appuser

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
