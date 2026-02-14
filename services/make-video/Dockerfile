FROM python:3.11-slim

# Install system dependencies (including build tools for webrtcvad + tesseract for OCR)
RUN apt-get update && apt-get install -y \
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

# Copy requirements
COPY requirements-docker.txt requirements.txt
# Install PyTorch CPU + EasyOCR and other requirements
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

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

# Set permissions
RUN chmod -R 755 /app/data /app/logs

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:8004/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
