# =============================================================================
# Stage: base
# =============================================================================
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

COPY services/se9-image-engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage: api
# =============================================================================
FROM base AS api

WORKDIR /app

COPY services/se9-image-engine/app/ ./app/
COPY services/se9-image-engine/run.py ./run.py

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/{outputs,models,temp} && \
    chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8009/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
