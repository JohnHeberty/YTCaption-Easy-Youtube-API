# Use Python 3.11 slim (mais leve e moderno)
FROM python:3.11-slim

# Metadata para identificação
LABEL maintainer="video-downloader-service" \
      version="1.0.0" \
      description="Video Download Microservice with yt-dlp"

# Variáveis de ambiente para otimização
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências do sistema (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Diretório de trabalho
WORKDIR /app

# Copia requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python sem cache
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação e arquivos necessários
COPY app/ ./app/
COPY run.py .
COPY user-agents*.txt ./

# Cria diretórios necessários com permissões adequadas
RUN mkdir -p /app/cache /app/logs \
    && chmod 777 /app/cache \ 
    && chmod 777 /app/logs

# Usuário não-root para segurança
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expõe porta do serviço
EXPOSE 8000

# Healthcheck para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["python", "run.py"]