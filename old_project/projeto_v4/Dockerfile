# Lightweight image for local API
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_NAME="YTCaption v3" \
    APP_VERSION="0.1.0" \
    LOG_LEVEL=INFO \
    TIMEOUT_SECONDS=10 \
    MAX_RETRIES=2 \
    CONCURRENCY_LIMIT=4 \
    CACHE_TTL_SECONDS=86400 \
    CACHED_ONLY=true \
    DATA_DIR=/app/data

WORKDIR /app

# System deps minimal + ffmpeg for audio processing
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy projeto_v3 contents to /app 
COPY . /app

# Install deps
RUN pip install --no-cache-dir -e /app

# Make data dir
RUN mkdir -p ${DATA_DIR}
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--loop", "uvloop", "--http", "httptools", "--no-access-log"]
