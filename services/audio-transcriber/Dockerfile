# Base NVIDIA correta para driver 550.x (mesma do GPU-OK)
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

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

# Labels
LABEL maintainer="audio-transcriber-service" \
      version="2.0.0" \
      description="Audio Transcription Microservice with Whisper + CUDA Support"

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FORCE_CUDA=1 \
    LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"

# Dependências de sistema (ffmpeg etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
    libavformat58 libavcodec58 libavdevice58 \
    libavutil56 libavfilter7 libswscale5 libswresample3 \
    curl grep \
 && ldconfig \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 🔥 COPY common FIRST (required by requirements.txt)
COPY common/ ./common/

# Copia requirements antes p/ cache de layers
COPY requirements.txt .
COPY constraints.txt .

# 🔥 Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# 🔥 Instalar setuptools primeiro (fix para openai-whisper)
RUN python -m pip install --no-cache-dir setuptools wheel

# 🔥 Instalar TODAS as dependências
RUN python -m pip install --no-cache-dir --ignore-installed blinker \
      -r requirements.txt -c constraints.txt

# 🔥 FORÇAR PyTorch cu118 POR ÚLTIMO (compatível com CUDA 11.8)
RUN python -m pip install --no-cache-dir --force-reinstall \
      torch==2.4.0+cu118 torchaudio==2.4.0+cu118 \
      --index-url https://download.pytorch.org/whl/cu118

# Não remover nada - manter todas as dependências instaladas
# (ffmpeg precisa das bibliotecas libav* que foram instaladas com os pacotes -dev)

# Copia código
COPY app/ ./app/
COPY run.py .

# Usuário não-root
RUN useradd -m -u 1000 appuser

# Diretórios e permissões
RUN mkdir -p /app/uploads /app/transcriptions /app/models /app/temp /app/logs /app/processed \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/uploads /app/transcriptions /app/models /app/temp /app/logs /app/processed

USER appuser

EXPOSE 8003

# Healthcheck (usa o curl instalado)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8003/health || exit 1

CMD ["python", "run.py"]
