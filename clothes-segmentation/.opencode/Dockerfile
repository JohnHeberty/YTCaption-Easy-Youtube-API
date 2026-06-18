FROM python:3.12-slim

WORKDIR /app

RUN pip install fastapi uvicorn httpx

COPY patch_proxy.py /app/patch_proxy.py

CMD ["sh", "-c", "uvicorn patch_proxy:app --host 0.0.0.0 --port ${PROXY_PORT:-4001}"]