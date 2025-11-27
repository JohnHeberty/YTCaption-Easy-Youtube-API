# Base com CUDA 12.1 + cuDNN p/ Ubuntu 22.04
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Evita prompts (tzdata) e define fuso
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# --- Python 3.11 (via deadsnakes) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git \
    software-properties-common \
 && add-apt-repository ppa:deadsnakes/ppa -y \
 && apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3.11-distutils python3.11-venv \
 # pip para o Python 3.11 (evita confusão com pip do 3.10)
 && curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
 && python3.11 /tmp/get-pip.py \
 # symlinks (muitos scripts esperam "python")
 && ln -sf /usr/bin/python3.11 /usr/bin/python \
 && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
 && rm -f /tmp/get-pip.py \
 && rm -rf /var/lib/apt/lists/*

# Metadata
LABEL maintainer="audio-voice-service" \
      version="2.0.0" \
      description="Audio Voice Microservice - Dubbing and Voice Cloning with XTTS (Coqui TTS) + CUDA Support"

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    CUDA_VISIBLE_DEVICES=0 \
    FORCE_CUDA=1

# Dependências de sistema (ffmpeg etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
    git \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements
COPY requirements.txt constraints.txt ./

# PyTorch cu121 + deps Python (respeitando constraints)
RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir \
      torch==2.4.0 torchaudio==2.4.0 \
      --index-url https://download.pytorch.org/whl/cu121 \
      -c constraints.txt

# Instala demais dependências (apenas XTTS - Coqui TTS)
# --ignore-installed blinker para evitar conflito com sistema
RUN python -m pip install --no-cache-dir --ignore-installed blinker \
      -r requirements.txt -c constraints.txt

# Limpa toolchain pesado (mantém ffmpeg etc.)
RUN apt-get purge -y --auto-remove \
    build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
 && apt-get autoremove -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copia código
COPY app/ ./app/
COPY run.py .
COPY scripts/ ./scripts/

# Cria speaker default para dubbing genérico
RUN python scripts/create_default_speaker.py

# Usuário não-root
RUN useradd -m -u 1000 appuser

# Diretórios e permissões
RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
    /app/voice_profiles /app/models /app/models/f5tts /app/models/whisper && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models

USER appuser

EXPOSE 8005

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:8005/ || exit 1

CMD ["python", "run.py"]
