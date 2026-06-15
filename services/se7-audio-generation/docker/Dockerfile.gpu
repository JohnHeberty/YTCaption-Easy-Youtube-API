FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS base

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git ffmpeg build-essential \
    python3.11 python3.11-dev python3.11-distutils python3.11-venv \
   && curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
   && python3.11 /tmp/get-pip.py \
   && ln -sf /usr/bin/python3.11 /usr/bin/python \
   && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
   && rm -f /tmp/get-pip.py \
   && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/chatterbox-space:/app \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

RUN git clone https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br \
    /app/chatterbox-space

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu121

RUN sed -i '/^torch/d; /^torchaudio/d; /^gradio/d; /cu128/d' /app/chatterbox-space/requirements.txt && \
    pip install --no-cache-dir -r /app/chatterbox-space/requirements.txt

COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

COPY services/se7-audio-generation/constraints.txt /app/constraints.txt
COPY services/se7-audio-generation/requirements.txt /app/requirements-service.txt
RUN grep -v '^-e ' /app/requirements-service.txt > /tmp/req-clean.txt && \
    pip install --no-cache-dir -r /tmp/req-clean.txt -c /app/constraints.txt

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
