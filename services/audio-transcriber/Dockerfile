
# Use Python 3.11 slim (mais leve e moderno)
FROM python:3.11-slim

# Metadata para identificação
LABEL maintainer="audio-transcriber-service" \
      version="1.0.0" \
      description="Audio Transcription Microservice with Whisper"

# Variáveis de ambiente para otimização
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências do sistema para Whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Diretório de trabalho
WORKDIR /app

# Copia requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Remove dependências de build após instalação
RUN apt-get purge -y --auto-remove \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia código da aplicação
COPY app/ ./app/
COPY run.py .

# Cria diretórios necessários com permissões adequadas
RUN mkdir -p /app/uploads /app/transcriptions /app/models /app/temp /app/logs \
    && chmod 755 /app/uploads /app/transcriptions /app/models /app/temp /app/logs

# Usuário não-root para segurança
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expõe porta do serviço de transcrição
EXPOSE 8002

# Healthcheck para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Comando padrão
CMD ["python", "run.py"]