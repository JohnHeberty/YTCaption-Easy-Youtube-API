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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements-docker.txt requirements.txt
# Install CPU-only torch first from PyTorch index, then other requirements
RUN pip install --no-cache-dir torch==2.1.1 torchaudio==2.1.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directories
RUN mkdir -p /app/storage/audio_uploads \
             /app/storage/shorts_cache \
             /app/storage/temp \
             /app/storage/output_videos \
             /app/logs

# Set permissions
RUN chmod -R 755 /app/storage /app/logs

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:8004/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
