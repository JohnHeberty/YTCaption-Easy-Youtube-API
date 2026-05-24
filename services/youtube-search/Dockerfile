# YouTube Search Service - Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Metadata
LABEL maintainer="youtube-search-service" \
      version="1.0.0" \
      description="YouTube Search Microservice"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy shared as common/ (build context é raiz do projeto)
COPY shared/ ./common/

# Copy requirements
COPY services/youtube-search/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/youtube-search/app/ ./app/
COPY services/youtube-search/run.py .

# Create necessary directories
RUN mkdir -p /app/data/logs

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (configurable via PORT env var)
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/health || exit 1

# Run via run.py — garante que SIGTERM propaga corretamente (sem sh -c intermediário)
CMD ["python", "run.py"]
