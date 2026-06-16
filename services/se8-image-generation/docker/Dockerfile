FROM python:3.11-slim AS base

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
   && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

COPY services/se8-image-generation/constraints.txt /app/constraints.txt
COPY services/se8-image-generation/requirements.txt /app/requirements-service.txt
RUN grep -v '^-e ' /app/requirements-service.txt > /tmp/req-clean.txt && \
    pip install --no-cache-dir -r /tmp/req-clean.txt -c /app/constraints.txt

COPY services/se8-image-generation/app/ ./app/
COPY services/se8-image-generation/run.py .

RUN mkdir -p /app/data/outputs /app/data/models /app/data/temp

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/data

USER appuser

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]

FROM base AS worker
CMD ["celery", "-A", "app.infrastructure.celery_config.celery_app", "worker", \
     "--loglevel=info", "--concurrency=1", "--queues=image_generation_queue", "--pool=solo"]
