# Base NVIDIA CUDA 12.1 para compatibilidade com ctranslate2 4.x
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ENV=development
ENV TZ=Etc/UTC
ENV BUILD_ENV=${BUILD_ENV}

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
      description="Audio Transcription Microservice with Faster-Whisper + CPU/CUDA Support" \
      build_env="${BUILD_ENV}"

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
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

# 🔥 COPY shared as common/ (build context é raiz do projeto)
COPY shared/ ./common/

# Copia requirements antes p/ cache de layers
COPY services/se4-audio-transcriber/requirements.txt .
COPY services/se4-audio-transcriber/constraints.txt .

# 🔥 Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# 🔥 Instalar setuptools primeiro (fix para openai-whisper)
RUN python -m pip install --no-cache-dir setuptools wheel

# 🔥 Instalar TODAS as dependências
RUN python -m pip install --no-cache-dir --ignore-installed blinker \
      -r requirements.txt -c constraints.txt
# Volta a usar constraints.txt com numpy 2.x
RUN python -m pip install --no-cache-dir --force-reinstall \
      torch==2.4.0+cu121 torchaudio==2.4.0+cu121 \
      --index-url https://download.pytorch.org/whl/cu121

# Não remover nada - manter todas as dependências instaladas
# (ffmpeg precisa das bibliotecas libav* que foram instaladas com os pacotes -dev)

# Copia código
COPY services/se4-audio-transcriber/app/ ./app/
COPY services/se4-audio-transcriber/run.py .

# Usuário não-root
RUN useradd -m -u 1000 appuser

# Diretórios e permissões
RUN mkdir -p /app/data/uploads /app/data/transcriptions /app/data/models /app/data/temp /app/data/logs \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/data/uploads /app/data/transcriptions /app/data/models /app/data/temp /app/data/logs

USER appuser

EXPOSE 8004

# Healthcheck — start-period=120s para aguardar warmup do modelo Whisper na GPU
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

CMD ["python", "run.py"]
