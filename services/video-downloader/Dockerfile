# Use Python 3.11 slim 
FROM python:3.11-slim

# Metadata para identificação
LABEL maintainer="video-downloader-service" \
      version="3.0.0" \
      description="Video Download Microservice with yt-dlp"

# Variáveis de ambiente para otimização
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala ffmpeg para merge de áudio/vídeo + curl para healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copia biblioteca common PRIMEIRO (necessária para -e ./common)
COPY common/ ./common/

# Copia requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python sem cache
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação e arquivos necessários
COPY app/ ./app/
COPY run.py .
COPY user-agents*.txt ./

# Cria usuário não-root ANTES de criar diretórios
RUN useradd -m -u 1000 appuser

# Cria diretórios necessários e define permissões corretas
# ORDEM CRÍTICA: mkdir -> chown -> chmod
RUN mkdir -p /app/data/cache /app/data/logs /app/data/downloads /app/data/temp \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app \
    && chmod -R 777 /app/data/cache /app/data/logs /app/data/downloads /app/data/temp

# Muda para usuário não-root
USER appuser

# Expõe porta do serviço
EXPOSE 8002

# Healthcheck para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Comando padrão
CMD ["python", "run.py"]