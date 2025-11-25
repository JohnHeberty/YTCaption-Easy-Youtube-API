# Base Python 3.10
FROM python:3.10-slim

# Metadata
LABEL maintainer="audio-voice-service" \
      version="1.0.0" \
      description="Audio Voice Microservice - Dubbing and Voice Cloning with OpenVoice"

# Evita prompts
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Env vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
      git \
      curl \
      wget \
   && rm -rf /var/lib/apt/lists/* \
   && apt-get clean

WORKDIR /app

# Requirements
COPY requirements.txt constraints.txt ./

# PyTorch CPU (ou CUDA se GPU disponível)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu -c constraints.txt && \
    pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Código
COPY app/ ./app/
COPY run.py .

# User não-root
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models

USER appuser

EXPOSE 8004

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

CMD ["python", "run.py"]
