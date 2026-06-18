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
    mkdir -p /app/data/{outputs,models,temp} && \
    chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
