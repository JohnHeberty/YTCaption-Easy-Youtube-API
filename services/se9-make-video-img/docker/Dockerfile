FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Sao_Paulo

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy shared library and install it first
COPY shared/ /app/shared/
RUN pip install --no-cache-dir /app/shared

# Copy service code
COPY services/se9-make-video-img/app/ app/
COPY services/se9-make-video-img/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data/outputs /app/logs /tmp && \
    chown -R appuser:appuser /app /tmp

USER appuser

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8009/ping || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
