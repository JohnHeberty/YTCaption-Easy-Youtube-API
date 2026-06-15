FROM python:3.11-slim

ENV SERVICE_NAME=orchestrator
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY common/ /app/common/

COPY services/se1-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/se1-orchestrator/app/ ./app/
COPY services/se1-orchestrator/run.py .

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "run.py"]
