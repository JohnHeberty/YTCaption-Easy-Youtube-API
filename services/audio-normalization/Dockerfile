# Base Python 3.11 slim (alinhado com outros serviços)
FROM python:3.11-slim

# Evita prompts e define fuso
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget git \
      libsndfile1 ffmpeg \
   && rm -rf /var/lib/apt/lists/*

# Metadata
LABEL maintainer="audio-normalization-service" \
      version="2.0.0-cpu" \
      description="Audio Normalization Microservice - CPU Only - Python 3.11"

# Ambiente (CPU-only)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CUDA_VISIBLE_DEVICES="" \
    FORCE_CUDA=0

WORKDIR /app

# Copia biblioteca common PRIMEIRO (necessária para -e ./common)
COPY common/ ./common/

# Copia requirements antes p/ cache de layers
COPY requirements.txt .
COPY constraints.txt .

# Instala dependências Python (sem PyTorch - CPU only sem ML)
RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copia código
COPY app/ ./app/
COPY run.py .

# Usuário não-root
RUN useradd -m -u 1000 appuser

# Diretórios e permissões
RUN mkdir -p /app/data/uploads /app/data/processed /app/data/temp /app/data/logs \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/data/uploads /app/data/processed /app/data/temp /app/data/logs

USER appuser

EXPOSE 8003

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8003/health || exit 1

CMD ["python", "run.py"]