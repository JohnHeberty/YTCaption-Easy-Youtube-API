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

# Cria diretórios necessários com permissões adequadas
RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
    && chmod 755 /app/uploads /app/processed /app/temp /app/logs

# Usuário não-root para segurança
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expõe porta do serviço
EXPOSE 8001

# Healthcheck para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Comando padrão
CMD ["python", "run.py"]
