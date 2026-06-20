FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ ./common/
RUN pip install --no-cache-dir ./common

COPY services/se11-clothes-removal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/se11-clothes-removal/app/ ./app/
COPY services/se11-clothes-removal/run.py .

RUN mkdir -p /app/data/{outputs,logs,temp} && useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8011/health || exit 1

CMD ["python", "run.py"]
