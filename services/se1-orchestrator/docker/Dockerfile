FROM python:3.11-slim

ENV SERVICE_NAME=orchestrator
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/common/

COPY services/se1-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/se1-orchestrator/app/ ./app/
COPY services/se1-orchestrator/run.py .

RUN mkdir -p /app/logs \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "run.py"]
