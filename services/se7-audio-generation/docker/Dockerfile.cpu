FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/chatterbox-space:/app

# Clone Chatterbox Space (publico, sem token)
RUN git clone https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br \
    /app/chatterbox-space

# PyTorch CPU
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Dependencias do Chatterbox (pula torch/torchaudio/gradio/CUDA index)
RUN sed -i '/^torch/d; /^torchaudio/d; /^gradio/d; /cu128/d' /app/chatterbox-space/requirements.txt && \
    pip install --no-cache-dir -r /app/chatterbox-space/requirements.txt

# Shared library
COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

# Service deps
COPY services/se7-audio-generation/constraints.txt /app/constraints.txt
COPY services/se7-audio-generation/requirements.txt /app/requirements-service.txt
RUN grep -v '^-e ' /app/requirements-service.txt > /tmp/req-clean.txt && \
    pip install --no-cache-dir -r /tmp/req-clean.txt -c /app/constraints.txt

# Service code
COPY services/se7-audio-generation/app/ ./app/
COPY services/se7-audio-generation/run.py .

RUN mkdir -p /app/data/models /app/data/voices /app/data/outputs /app/data/temp

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/data

USER appuser

EXPOSE 8007

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]

FROM base AS worker
CMD ["celery", "-A", "app.infrastructure.celery_config.celery_app", "worker", \
     "--loglevel=info", "--concurrency=1", "--queues=audio_generation_queue"]
