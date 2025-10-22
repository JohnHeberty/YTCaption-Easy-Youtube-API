# Multi-stage build para otimizar tamanho da imagem
FROM python:3.11-slim as builder

# Instalar dependências de sistema necessárias + ferramentas de debug de rede
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    iputils-ping \
    curl \
    dnsutils \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage final
FROM python:3.11-slim

# Instalar apenas runtime necessário + ferramentas de rede
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    iputils-ping \
    curl \
    dnsutils \
    net-tools \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root para segurança
RUN useradd -m -u 1000 appuser

# Criar diretórios necessários
WORKDIR /app

# Copiar dependências do builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código da aplicação
COPY --chown=appuser:appuser ./src /app/src
COPY --chown=appuser:appuser .env.example /app/.env

# Criar diretórios necessários com permissões corretas para appuser
RUN mkdir -p /app/temp /app/logs && chown -R appuser:appuser /app/temp /app/logs

# Criar diretório de cache do Whisper para o appuser
RUN mkdir -p /home/appuser/.cache/whisper && chown -R appuser:appuser /home/appuser/.cache

# Mudar para usuário não-root
USER appuser

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TEMP_DIR=/app/temp

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Comando de inicialização com workers dinâmicos
CMD ["sh", "-c", "uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-1}"]
