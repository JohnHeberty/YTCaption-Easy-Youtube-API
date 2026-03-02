FROM python:3.11-slim

# Install system dependencies (including build tools for webrtcvad + tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    gcc \
    g++ \
    make \
    python3-dev \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements
COPY requirements-docker.txt requirements.txt
# Install PyTorch CPU + EasyOCR and other requirements
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (selective — avoid sending .trash/, data/, logs/)
COPY app/ ./app/
COPY run.py .

# Create data directories (bind mount irá sobrescrever, mas cria estrutura base)
RUN mkdir -p /app/data/raw/audio \
             /app/data/raw/shorts \
             /app/data/raw/cache \
             /app/data/transform/videos \
             /app/data/transform/temp \
             /app/data/validate/in_progress \
             /app/data/validate/test_datasets \
             /app/data/approved/videos \
             /app/data/approved/output \
             /app/data/logs/app \
             /app/data/logs/debug \
             /app/logs

# Usuário não-root (segurança)
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

# Set permissions
RUN chmod -R 755 /app/data /app/logs

USER appuser

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8005}/health || exit 1

# Default command
CMD ["python", "run.py"]
