
FROM python:3.11-slim

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
    libswresample-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 4. Remover TODAS as dependências de BUILD
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
    # 5. Limpar cache
    && rm -rf /var/lib/apt/lists/* && \
    apt-get clean

COPY app/ ./app/
COPY run.py .

# Cria diretórios necessários para transcrição e modelos
RUN mkdir -p /app/uploads /app/transcriptions /app/models /app/temp && chmod 755 /app/uploads /app/transcriptions /app/models /app/temp

# Usuário não-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expõe porta do serviço de transcrição
EXPOSE 8002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Comando padrão
CMD ["python", "run.py"]