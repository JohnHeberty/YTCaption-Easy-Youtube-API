# Base Ubuntu 22.04 (CPU-only, mais leve)
FROM ubuntu:22.04

# Evita prompts (tzdata) e define fuso
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Python 3.10 (padrão Ubuntu 22.04) + pip
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget git \
      python3 python3-dev python3-pip python3-venv \
      python3-distutils \
   && ln -sf /usr/bin/python3 /usr/bin/python \
   && rm -rf /var/lib/apt/lists/*

# Metadata
LABEL maintainer="audio-normalization-service" \
      version="2.0.0-cpu" \
      description="Audio Normalization Microservice - CPU Only"

# Ambiente (CPU-only)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CUDA_VISIBLE_DEVICES="" \
    FORCE_CUDA=0

# Dependências de sistema para áudio
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libsndfile1 \
   && rm -rf /var/lib/apt/lists/* \
   && apt-get clean

WORKDIR /app

# Copia biblioteca common PRIMEIRO (necessária para -e ./common)
COPY common/ ./common/

# Copia requirements antes p/ cache de layers
COPY requirements.txt .
COPY constraints.txt .

# PyTorch CPU-only + deps Python (mais leve e rápido)
RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir \
      torch==2.1.2 torchaudio==2.1.2 \
      --index-url https://download.pytorch.org/whl/cpu \
      -c constraints.txt 
RUN python -m pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copia código
COPY app/ ./app/
COPY run.py .

# Usuário não-root
RUN useradd -m -u 1000 appuser

# Diretórios e permissões
RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/uploads /app/processed /app/temp /app/logs

USER appuser

EXPOSE 8002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8002/health || exit 1

CMD ["python", "run.py"]