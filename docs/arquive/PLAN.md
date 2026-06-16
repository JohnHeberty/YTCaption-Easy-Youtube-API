# PLANO: se8-image-generation (Fooocus API)

## Resumo

Criar servico `se8-image-generation` na porta **8008** que encapsula a Fooocus API
(SDXL image generation) seguindo todos os padroes dos servicos se1-se7.

**Estrategia**: Container separado para Fooocus API (GPU) + container leve para
se8 API (proxy HTTP). FOOOCUS repositorio bind-mounted em ambos para dev.
Nenhuma modificacao no repositorio FOOOCUS.

---

## 1. Diretorio alvo

```
/root/YTCaption-Easy-Youtube-API/services/se8-image-generation/
```

## 2. Estrutura de arquivos

```
services/se8-image-generation/
├── .env                          # DIVISOR=8, PORT=8008, REDIS DB=8
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── constraints.txt
├── requirements.txt
├── requirements-docker.txt
├── run.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health_routes.py
│   │   ├── images_routes.py
│   │   └── query_routes.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── celery_config.py
│   │   └── celery_tasks.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── image_service.py
│   └── middleware/
│       └── __init__.py
├── docker/
│   ├── Dockerfile                # se8 API (python:3.11-slim, sem GPU)
│   ├── Dockerfile.fooocus        # Fooocus API (nvidia/cuda, GPU)
│   ├── docker-compose.yml        # GPU
│   └── docker-compose.prod.yml   # Production
├── tests/
│   └── __init__.py
└── data/
    ├── outputs/
    ├── models/
    └── temp/
```

## 3. Estrategia de integracao FOOOCUS

### Arquitetura

```
[Cliente :8008] --> [se8 API (proxy)] --> [Fooocus API :8888 (interno, GPU)]
                                              |
                                          [Fooocus Worker]
```

### Container 1: `image-generation-api` (porta 8008)

- **Imagem**: `python:3.11-slim` — NAO precisa de GPU nem PyTorch
- **Funcao**: FastAPI proxy que aceita requests padronizados e repassa para Fooocus API
- **Celery**: Worker integrado para tarefas assincronas
- **Dependencias**: shared/ lib (bind-mounted), celery, redis, httpx, pydantic

### Container 2: `fooocus-api` (porta 8888, NAO exposta)

- **Imagem**: `nvidia/cuda:12.1.1-devel-ubuntu22.04` + PyTorch CUDA
- **Funcao**: Fooocus API original rodando internamente
- **FOOOCUS**: Bind-mounted via `../../../FOOOCUS:/app/fooocus` (read-only)
- **GPU**: `runtime: nvidia`
- **Dependencias**: PyTorch 2.1.0+cu121, todas do FOOOCUS/requirements.txt
- **shared/**: NAO bind-mount (Fooocus API original nao usa shared/ lib)
- **Startup**: `python main.py --host 0.0.0.0 --port 8888 --preload-pipeline --skip-pip`

### Container 3: `celery-worker`

- **Mesma imagem** do container 1 (se8 API)
- **Funcao**: Processa tarefas de geracao de imagem via Celery
- **Conexao**: Faz HTTP para `http://fooocus-api:8888` (mesma rede Docker)

### Por que containers separados?

1. **Isolamento de dependencias**: PyTorch+CUDA (11GB) nao conflita com shared/ lib
2. **Flexibilidade**: Fooocus API pode ser reiniciado independentemente
3. **Seguranca**: FOOOCUS repositorio fica read-only, sem risco de escrita acidental
4. **Dev vs Prod**: Dev usa bind-mount; Prod pode usar COPY no Dockerfile

## 4. Arquivos-chave

### 4.1 `app/core/config.py`

```python
from functools import lru_cache
from typing import Optional
from pydantic import Field
from common.config_utils.base_settings import BaseServiceSettings

class ImageGenerationSettings(BaseServiceSettings):
    app_name: str = "Image Generation Service"
    port: int = 8008
    
    # Fooocus API connection
    fooocus_api_url: str = "http://fooocus-api:8888"
    fooocus_api_key: Optional[str] = None
    
    # Generation defaults
    default_performance: str = "Speed"
    default_prompt_negative: str = ""
    default_cfg_scale: float = 4.0
    default_sharpness: float = 2.0
    default_width: int = 1024
    default_height: int = 1024
    max_image_number: int = 4
    max_queue_size: int = 100
    
    # Storage
    output_dir: str = "./data/outputs"
    model_dir: str = "./data/models"
    
    # Redis DB=8
    redis_url: str = "redis://192.168.1.110:6379/8"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

@lru_cache()
def get_settings() -> ImageGenerationSettings:
    return ImageGenerationSettings()
```

### 4.2 `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from common.fastapi_utils import create_service_app
from common.log_utils import get_logger
from app.core.config import get_settings
from app.api import health_routes, images_routes, query_routes

logger = get_logger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    yield
    logger.info("Shutting down Image Generation Service")

def setup_routers(app: FastAPI):
    app.include_router(health_routes.router)
    app.include_router(images_routes.router)
    app.include_router(query_routes.router)

app = create_service_app(
    service_name="image-generation",
    title=settings.app_name,
    description="SDXL image generation service powered by Fooocus",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
)
```

### 4.3 `app/services/image_service.py`

Cliente HTTP para Fooocus API:

```python
import httpx
from typing import List, Optional
from app.core.config import get_settings
from common.log_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()

class FooocusClient:
    def __init__(self):
        self.base_url = settings.fooocus_api_url
        self.headers = {}
        if settings.fooocus_api_key:
            self.headers["X-API-Key"] = settings.fooocus_api_key
    
    async def text_to_image(
        self, prompt: str, negative_prompt: str = "",
        style_selections: List[str] = None,
        performance: str = None,
        width: int = None, height: int = None,
        image_number: int = 1,
        async_process: bool = False,
    ) -> dict:
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt or settings.default_prompt_negative,
            "style_selections": style_selections or [],
            "performance_selection": performance or settings.default_performance,
            "aspect_ratios_selection": f"{width or settings.default_width}×{height or settings.default_height}",
            "image_number": min(image_number, settings.max_image_number),
            "async_process": async_process,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url}/v2/generation/text-to-image-with-ip",
                json=payload, headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()
    
    async def query_job(self, job_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v2/query/{job_id}",
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()
    
    async def stop_job(self, job_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{self.base_url}/v2/query/{job_id}",
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()

fooocus_client = FooocusClient()
```

### 4.4 `app/infrastructure/celery_config.py`

```python
from common.celery_utils import create_celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)

celery_app = create_celery_app(
    "image_generation",
    task_default_queue="image_generation_queue",
    task_routes={
        "generate_image": {"queue": "image_generation_queue"},
        "cleanup_expired_jobs": {"queue": "image_generation_queue"},
    },
    task_time_limit=600,
    task_soft_time_limit=540,
    timezone="America/Sao_Paulo",
    enable_utc=False,
)

from . import celery_tasks
```

### 4.5 `app/api/images_routes.py`

```python
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from app.services.image_service import fooocus_client
from app.domain.models import TextToImageRequest, ImageResponse, JobStatus

router = APIRouter(prefix="/v1/generation", tags=["Generation"])

@router.post("/text-to-image", response_model=ImageResponse)
async def text_to_image(req: TextToImageRequest):
    try:
        result = await fooocus_client.text_to_image(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            style_selections=req.style_selections,
            performance=req.performance,
            width=req.width,
            height=req.height,
            image_number=req.image_number,
            async_process=req.async_process,
        )
        return ImageResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{job_id}", response_model=JobStatus)
async def query_job(job_id: str):
    try:
        return await fooocus_client.query_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{job_id}")
async def stop_job(job_id: str):
    try:
        return await fooocus_client.stop_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4.6 `app/domain/models.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TextToImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style_selections: List[str] = []
    performance: str = "Speed"
    width: int = 1024
    height: int = 1024
    image_number: int = 1
    async_process: bool = False

class ImageResult(BaseModel):
    seed: str
    image: str
    finish_reason: str

class ImageResponse(BaseModel):
    images: List[ImageResult]

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    results: Optional[List[ImageResult]] = None
```

### 4.7 `app/api/health_routes.py`

```python
from fastapi import APIRouter
import httpx
from app.core.config import get_settings
from common.log_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["Health"])

@router.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.fooocus_api_url}/docs")
            fooocus_ok = resp.status_code == 200
    except Exception:
        fooocus_ok = False
    
    return {
        "status": "healthy" if fooocus_ok else "degraded",
        "service": "image-generation",
        "fooocus_api": "connected" if fooocus_ok else "disconnected",
    }

@router.get("/health/deep")
async def health_deep():
    health = await health()
    health["checks"] = {
        "fooocus_api": health["fooocus_api"],
    }
    return health
```

### 4.8 `.env`

```env
APP_NAME=Image Generation Service
VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false
TZ=America/Sao_Paulo

DIVISOR=8
PORT=800${DIVISOR}
HOST=0.0.0.0

IP_REDIS=192.168.1.110
REDIS_URL=redis://${IP_REDIS}:6379/${DIVISOR}

CELERY_BROKER_URL=redis://${IP_REDIS}:6379/${DIVISOR}
CELERY_RESULT_BACKEND=redis://${IP_REDIS}:6379/${DIVISOR}
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=false
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_SOFT_TIME_LIMIT=540
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=20

FOOOCUS_API_URL=http://fooocus-api:8888
FOOOCUS_API_KEY=

DEFAULT_PERFORMANCE=Speed
DEFAULT_CFG_SCALE=4.0
DEFAULT_SHARPNESS=2.0
DEFAULT_WIDTH=1024
DEFAULT_HEIGHT=1024
MAX_IMAGE_NUMBER=4

OUTPUT_DIR=./data/outputs
MODEL_DIR=./data/models
TEMP_DIR=./data/temp
LOG_LEVEL=INFO
```

## 5. Docker

### 5.1 `docker/Dockerfile` (se8 API — sem GPU)

```dockerfile
FROM python:3.11-slim AS base

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    python3.11 python3.11-dev python3.11-distutils python3.11-venv \
   && curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
   && python3.11 /tmp/get-pip.py \
   && ln -sf /usr/bin/python3.11 /usr/bin/python \
   && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
   && rm -f /tmp/get-pip.py \
   && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY shared/ ./common/
RUN pip install --no-cache-dir -e ./common

COPY services/se8-image-generation/constraints.txt /app/constraints.txt
COPY services/se8-image-generation/requirements.txt /app/requirements-service.txt
RUN grep -v '^-e ' /app/requirements-service.txt > /tmp/req-clean.txt && \
    pip install --no-cache-dir -r /tmp/req-clean.txt -c /app/constraints.txt

COPY services/se8-image-generation/app/ ./app/
COPY services/se8-image-generation/run.py .

RUN mkdir -p /app/data/outputs /app/data/models /app/data/temp

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/data

USER appuser

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]

FROM base AS worker
CMD ["celery", "-A", "app.infrastructure.celery_config.celery_app", "worker", \
     "--loglevel=info", "--concurrency=1", "--queues=image_generation_queue", "--pool=solo"]
```

### 5.2 `docker/Dockerfile.fooocus` (Fooocus API — GPU)

```dockerfile
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 AS base

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git ffmpeg build-essential \
    python3.11 python3.11-dev python3.11-distutils python3.11-venv \
   && curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
   && python3.11 /tmp/get-pip.py \
   && ln -sf /usr/bin/python3.11 /usr/bin/python \
   && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
   && rm -f /tmp/get-pip.py \
   && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/fooocus:/app \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    PYTORCH_ENABLE_MPS_FALLBACK=1

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 \
    --extra-index-url https://download.pytorch.org/whl/cu121

COPY FOOOCUS/requirements.txt /tmp/requirements-fooocus.txt
RUN pip install --no-cache-dir -r /tmp/requirements-fooocus.txt && \
    rm /tmp/requirements-fooocus.txt

COPY FOOOCUS/Fooocus/requirements_versions.txt /tmp/requirements-versions.txt
RUN pip install --no-cache-dir -r /tmp/requirements-versions.txt && \
    rm /tmp/requirements-versions.txt

RUN mkdir -p /app/fooocus /app/data/outputs /app/data/models /app/data/temp

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/data

USER appuser

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8888/docs || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8888", \
     "--preload-pipeline", "--skip-pip", "--disable-image-log"]
```

### 5.3 `docker/docker-compose.yml`

```yaml
name: se8-image-generation-gpu
services:
  image-generation-api:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile
      target: api
    container_name: image-generation-api
    ports:
      - "${PORT}:${PORT}"
    volumes:
      - ../../../shared:/app/common
      - ../app:/app/app
      - ../data:/app/data
    env_file:
      - ../.env
    environment:
      - TZ=${TZ}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8008/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  fooocus-api:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile.fooocus
    container_name: fooocus-api
    volumes:
      - ../../../FOOOCUS:/app/fooocus
      - ../data/models:/app/data/models
      - ../data/outputs:/app/data/outputs
    env_file:
      - ../.env
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
    runtime: nvidia
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/docs"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  celery-worker:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile
      target: worker
    container_name: image-generation-celery
    command: >
      python -m celery -A app.infrastructure.celery_config.celery_app worker
      --loglevel=info --concurrency=1 --queues=image_generation_queue --pool=solo
    volumes:
      - ../../../shared:/app/common
      - ../app:/app/app
      - ../data:/app/data
    env_file:
      - ../.env
    environment:
      - C_FORCE_ROOT=true
      - TZ=${TZ}
    restart: unless-stopped
    depends_on:
      image-generation-api:
        condition: service_healthy
```

### 5.4 `docker/docker-compose.prod.yml`

```yaml
name: se8-image-generation-gpu
services:
  image-generation-api:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile
      target: api
    container_name: image-generation-api
    ports:
      - "${PORT}:${PORT}"
    volumes:
      - ../../../shared:/app/common:ro
      - ../data:/app/data
    env_file:
      - ../.env
    environment:
      - TZ=${TZ}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8008/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - se8-internal

  fooocus-api:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile.fooocus
    container_name: fooocus-api
    volumes:
      - fooocus-models:/app/data/models
      - fooocus-outputs:/app/data/outputs
    env_file:
      - ../.env
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
    runtime: nvidia
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/docs"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    networks:
      - se8-internal

  celery-worker:
    build:
      context: ../../..
      dockerfile: services/se8-image-generation/docker/Dockerfile
      target: worker
    container_name: image-generation-celery
    command: >
      python -m celery -A app.infrastructure.celery_config.celery_app worker
      --loglevel=info --concurrency=1 --queues=image_generation_queue --pool=solo
    volumes:
      - ../../../shared:/app/common:ro
      - ../app:/app/app:ro
      - ../data:/app/data
    env_file:
      - ../.env
    environment:
      - C_FORCE_ROOT=true
      - TZ=${TZ}
    restart: unless-stopped
    depends_on:
      image-generation-api:
        condition: service_healthy
    networks:
      - se8-internal

volumes:
  fooocus-models:
    driver: local
  fooocus-outputs:
    driver: local

networks:
  se8-internal:
    driver: bridge
```

## 6. Makefile

```makefile
SERVICE_NAME := se8-image-generation
IMAGE_NAME := image-generation
IMAGE_NAME_FOOOCUS := fooocus-api
PORT := 8008
DC := docker compose
DC_FILE := docker/docker-compose.yml
DC_PROD := docker/docker-compose.prod.yml
DC_ARGS := --env-file .env

.PHONY: help build up down restart logs status health dev stop clean rebuild

help:
	@echo "Targets:"
	@echo "  build      - Build images (GPU)"
	@echo "  up         - Start containers (GPU)"
	@echo "  down       - Stop containers"
	@echo "  restart    - down + up"
	@echo "  logs       - View logs"
	@echo "  status     - Container status"
	@echo "  health     - Health check"
	@echo "  rebuild    - Build (no-cache) + up"
	@echo "  clean      - Remove containers, images, volumes"
	@echo "  dev        - Local dev (uvicorn, no Docker)"

build:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) build

up:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) up -d

down:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) down

restart: down up

logs:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) logs -f --tail=100

status:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) ps

health:
	@curl -sf http://localhost:$(PORT)/health && echo "" || echo "FAIL"

dev:
	uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --reload

stop:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) stop

clean:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) down -v --rmi local

rebuild:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) build --no-cache && \
	$(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) up -d
```

## 7. Integracao com shared/

- `from common.fastapi_utils import create_service_app`
- `from common.log_utils import get_logger`
- `from common.config_utils.base_settings import BaseServiceSettings`
- `from common.celery_utils import create_celery_app`
- `from common.exception_handlers import setup_exception_handlers`
- `from common.middleware import BodySizeMiddleware, RateLimiterMiddleware`

## 8. Validacao

1. `docker compose build` — ambos containers constroem sem erro
2. `docker compose up` — se8 API inicia em <30s, Fooocus API em <120s
3. `curl http://localhost:8008/health` — retorna 200 com `fooocus_api: connected`
4. `curl http://localhost:8008/v1/generation/text-to-image -d '{"prompt":"a cat"}'` — gera imagem
5. Celery worker conecta via Redis DB=8
6. Shared/ lib funciona (logging estruturado, health check)
7. `make rebuild` funciona limpo

## 9. Riscos

| Risco | Mitigacao |
|-------|-----------|
| **Fooocus models (~11GB) precisam ser baixados** | Volume persistente; primeiro build demora ~30min |
| **Fooocus API cold start 120s+** | `start_period: 120s`; `--preload-pipeline` |
| **GPU compartilhada com se3/se5/se7** | NVIDIA_VISIBLE_DEVICES; 1 GPU = 1 container GPU por vez |
| **Espaco em disco (PyTorch+CUDA ~11GB)** | Monitorar; considerar CUDA slimmer em prod |
| **Conflito Pydantic v2** | Fooocus usa 2.4.2; shared/ usa pydantic-settings — compativel |
| **FOOOCUS bind-mount read-only** | Nenhuma escrita; outputs em `../data/` |
| **Fooocus API key (opcional)** | Se definido, se8 proxy envia `X-API-Key` header |

## 10. Ordem de execucao

1. Criar diretorio `services/se8-image-generation/` com toda estrutura
2. Criar `.env`, `.env.example`, `.gitignore`
3. Criar `app/core/config.py`
4. Criar `app/domain/models.py`
5. Criar `app/services/image_service.py`
6. Criar `app/api/` (health_routes, images_routes, query_routes)
7. Criar `app/infrastructure/` (celery_config, celery_tasks)
8. Criar `app/main.py`
9. Criar `run.py`, `constraints.txt`, `requirements.txt`
10. Criar `docker/Dockerfile` (se8 API)
11. Criar `docker/Dockerfile.fooocus` (Fooocus API)
12. Criar `docker/docker-compose.yml`
13. Criar `docker/docker-compose.prod.yml`
14. Criar `Makefile`
15. Criar `README.md`
16. `make build` e `make up`
17. Testar health check e geracao de imagem
18. Integrar com `deploy.sh` e `test_services_real.sh`
19. Commit
