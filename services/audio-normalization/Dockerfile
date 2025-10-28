# Use Python 3.11 slim (mais leve e moderno)
FROM python:3.11-slim

# Metadata para identificação
LABEL maintainer="audio-normalization-service" \
      version="1.0.0" \
      description="Audio Normalization Microservice"

# Variáveis de ambiente para otimização
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências do sistema para processamento de áudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Diretório de trabalho
WORKDIR /app

# Copia requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python sem cache
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY app/ ./app/
COPY run.py .

# Cria usuário não-root ANTES de criar diretórios
RUN useradd -m -u 1000 appuser

# Cria diretórios necessários e define permissões corretas
# ORDEM CRÍTICA: mkdir -> chown -> chmod
RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app \
    && chmod -R 777 /app/uploads /app/processed /app/temp /app/logs

# Muda para usuário não-root
USER appuser

# Expõe porta do serviço
EXPOSE 8001

# Healthcheck para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Comando padrão
CMD ["python", "run.py"]
