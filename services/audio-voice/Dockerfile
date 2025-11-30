# Base NVIDIA correta para seu driver 550.x
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git software-properties-common \
 && add-apt-repository ppa:deadsnakes/ppa -y \
 && apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3.11-distutils python3.11-venv \
 && curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
 && python3.11 /tmp/get-pip.py \
 && ln -sf /usr/bin/python3.11 /usr/bin/python \
 && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
 && rm -f /tmp/get-pip.py \
 && rm -rf /var/lib/apt/lists/*

LABEL maintainer="audio-voice-service" \
      version="2.0.1" \
      description="Audio Voice Service - CUDA 11.8 + PyTorch 2.4"

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    CUDA_VISIBLE_DEVICES=0 \
    FORCE_CUDA=1 \
    LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"

# Dependências
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
    git curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt constraints.txt ./

# 🔥 Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# 🔥 Instalar TODAS as dependências (vai instalar torch cu121)
RUN python -m pip install --no-cache-dir --ignore-installed blinker \
      -r requirements.txt -c constraints.txt

# 🔥 FORÇAR PyTorch cu118 POR ÚLTIMO com todas deps CUDA 11.8
RUN python -m pip install --no-cache-dir --force-reinstall \
      torch==2.4.0+cu118 torchaudio==2.4.0+cu118 \
      --index-url https://download.pytorch.org/whl/cu118

# Remove toolchain pesado
RUN apt-get purge -y --auto-remove \
    build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
 && apt-get autoremove -y && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY app/ ./app/
COPY run.py .
COPY scripts/ ./scripts/

# Criar speaker default (será recriado pelo entrypoint se volume sobrescrever)
RUN python scripts/create_default_speaker.py

# Não sobrescrever libcuda.so — usar a versão montada do host
# (Nenhum symlink conflitante será criado!)

# Usuário
RUN useradd -m -u 1000 appuser

RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
    /app/voice_profiles /app/models /app/models/f5tts /app/models/whisper \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models

USER appuser

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:8005/ || exit 1

CMD ["python", "run.py"]
