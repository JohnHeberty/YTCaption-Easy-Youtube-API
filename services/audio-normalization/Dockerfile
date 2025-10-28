# Use NVIDIA CUDA base image para suporte GPU
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Instala Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    python3-pip \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Metadata para identificação
LABEL maintainer="audio-normalization-service" \
      version="2.0.0" \
      description="Audio Normalization Microservice with CUDA Support"

# Variáveis de ambiente para otimização e CUDA
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    CUDA_VISIBLE_DEVICES=0 \
    FORCE_CUDA=1

# Instala dependências do sistema para processamento de áudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Diretório de trabalho
WORKDIR /app

# Copia requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python
# PyTorch com CUDA 12.1 support primeiro
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    torch==2.1.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt

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
