# UPGRADE COMPATIBILITY — Stack-Wide Standardization
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Escopo: Todos os 5 microserviços do projeto YTCaption-Easy-Youtube-API

> Nota editorial: os padroes estaveis extraidos desta auditoria foram promovidos para [docs/reference/stack-standardization.md](../reference/stack-standardization.md). Este arquivo permanece como registro historico da iniciativa e de sua matriz de conformidade.

---

## 1. VISÃO GERAL DA STACK

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YTCaption-Easy-Youtube-API                          │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────────────┐    │
│  │  youtube-search │    │ video-downloader │    │  audio-transcriber   │    │
│  │    port: 8001   │    │   port: 8000     │    │    port: 8003/8004   │    │
│  └────────┬────────┘    └────────┬─────────┘    └──────────┬───────────┘   │
│           │                     │                          │               │
│           └──────────┬──────────┘                          │               │
│                      ▼                                      │               │
│           ┌──────────────────┐                             │               │
│           │    make-video    │◄────────────────────────────┘               │
│           │   port: 8005     │                                             │
│           └────────┬─────────┘                                             │
│                    │                                                        │
│           ┌────────▼─────────┐                                             │
│           │audio-normalization│                                             │
│           │   port: 8002      │                                             │
│           └──────────────────┘                                             │
│                                                                             │
│  Shared: Redis (ports: 0-5 por DB)  |  Common Library                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03 — Completed across all services

### video-downloader
| Item | Status |
|------|--------|
| `exception_handler` class bug → async function | ✅ DONE |
| `reload=True` hardcoded → `reload=debug` | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| `PYTHONPATH=/app` in Dockerfile | ✅ DONE |
| `requirements-test.txt` created | ✅ DONE |
| `tenacity` retry for downloads | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `LABEL version "3.0.0"` fixed | ✅ DONE |
| `pydantic-settings` added to `requirements.txt` | ✅ DONE |
| `user-agents-original.txt` moved to `.trash/` | ✅ DONE |

### youtube-search
| Item | Status |
|------|--------|
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| `tenacity` retry for YouTube API calls | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| Dockerfile `CMD sh -c` → `["python", "run.py"]` | ✅ DONE |
| `COPY run.py` added to Dockerfile | ✅ DONE |
| `proxies.txt` added to `.gitignore` | ✅ DONE |

### audio-normalization
| Item | Status |
|------|--------|
| Dockerfile `EXPOSE 8003` → `8002` + HEALTHCHECK port | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `PYTHONPATH=/app` added to Dockerfile | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `.gitignore` created | ✅ DONE |
| `logs/*.log` moved to `.trash/logs/` | ✅ DONE |

### audio-transcriber
| Item | Status |
|------|--------|
| HEALTHCHECK `start-period` 40s → 120s, `timeout` 10s → 15s | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `PYTHONPATH=/app` added to Dockerfile | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `.gitignore` created | ✅ DONE |
| `pydantic-settings` added to `requirements.txt` | ✅ DONE |
| `logs/` committed files moved to `.trash/logs/`; `.gitkeep` added | ✅ DONE |

### make-video
| Item | Status |
|------|--------|
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| CORS `allow_credentials=True` removed | ✅ DONE |
| `PYTHONPATH=/app` + `PYTHONUNBUFFERED` + `PYTHONDONTWRITEBYTECODE` in Dockerfile | ✅ DONE |
| `sprints/` moved to `docs/services/se5-make-video/sprints/` | ✅ DONE |
| `pytest-cov` duplicate removed | ✅ DONE |
| `.dockerignore` updated | ✅ DONE |
| Runtime data (logs, mp4, ogg, db) moved to `.trash/` | ✅ DONE |
| `.gitignore` fixed: `trash/` → `.trash/`; `data/` patterns added | ✅ DONE |
| `.dockerignore` extended with `data/` runtime exclusions | ✅ DONE |
| `.trash/` added to `.gitignore` (video-downloader, youtube-search) | ✅ DONE |
| `logs/` + `cache/` runtime data moved to `.trash/` (video-downloader) | ✅ DONE |
| `uploads/` runtime data moved to `.trash/` (audio-normalization, audio-transcriber) | ✅ DONE |
| `uploads/` added to `.gitignore` for all 3 upload-processing services | ✅ DONE |
| Dockerfile double `apt-get` merged into one layer (audio-normalization) | ✅ DONE |
| `run.py` uvicorn limits added (audio-transcriber, make-video) | ✅ DONE |
| Celery `task_failure` signal handler added (youtube-search, make-video) | ✅ DONE |
| `tests/requirements-test.txt` created (make-video) | ✅ DONE |
| Dependency versions normalized across all 4 services to fastapi 0.120.0 / uvicorn 0.38.0 / pydantic 2.12.3 / pydantic-settings 2.11.0 | ✅ DONE |
| `constraints.txt` version ranges updated in 3 services to allow 0.120.x / 0.38.x / 2.12.x | ✅ DONE |
| `make-video/run.py` `${DIVISOR}` variable hack removed; proper env-driven config | ✅ DONE |
| make-video Dockerfile: non-root user (`appuser 1000`) adicionado | ✅ DONE |
| make-video Dockerfile: HEALTHCHECK adicionado (8005, start-period=90s) | ✅ DONE |
| make-video Dockerfile: `COPY . .` → seletivo; `--no-install-recommends` adicionado | ✅ DONE |
| video-downloader `.dockerignore` criado | ✅ DONE |

---

## 2. MATRIZ DE CONFORMIDADE ATUAL

| Padrão | audio-transcriber | audio-normalization | video-downloader | make-video | youtube-search |
|--------|:-----------------:|:-------------------:|:----------------:|:----------:|:--------------:|
| **Arquitetura em camadas** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **pydantic_settings.BaseSettings** | ✅ DONE | ✅ DONE | ✅ DONE | ✅ | ✅ DONE |
| **lifespan (não on_event)** | ✅ DONE | ✅ DONE | ✅ DONE | ✅ DONE | ✅ DONE |
| **run.py com uvicorn configurável** | ✅ | ⚠️ | ✅ DONE reload=debug | ✅ | ✅ DONE |
| **Dockerfile: non-root user** | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Dockerfile: HEALTHCHECK** | ✅ DONE start-period=120s | ✅ DONE porta 8002 corrigida | ✅ | ❌ | ✅ |
| **constraints.txt** | ✅ | ✅ | ✅ DONE | ✅ DONE | ✅ DONE |
| **Exception handler (async fn)** | ✅ | ❌ sem mapping | ✅ DONE | ✅ | ✅ |
| **tenacity (retry)** | ✅ | ✅ | ✅ DONE | ✅ | ✅ DONE |
| **prometheus-client** | ✅ DONE | ✅ DONE | ✅ DONE | ✅ | ✅ DONE |
| **ResilientRedisStore** | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| **Testes: unit/integration/e2e** | ✅ | ⚠️ | ❌ | ✅ | ❌ |
| **requirements-test.txt** | ✅ | ✅ | ✅ DONE | ❌ | ✅ |
| **.trash/ limpo** | ❌ 18 files | ✅ | ✅ | ❌ 30+ files | ✅ |
| **fastapi ≥ 0.115** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **pydantic ≥ 2.11** | ❌ | ✅ | ❌ | ❌ | ❌ |

**Legenda:** ✅ Conforme | ⚠️ Parcial | ❌ Não conforme

---

## 3. PADRÃO ALVO DEFINIDO (Golden Standard)

### 3.1 Versões de Dependências (Stack-Wide)

Baseado na versão mais recente já adotada pelo serviço de `audio-normalization`:

```txt
# === CORE WEB FRAMEWORK ===
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.3
pydantic-settings==2.7.1
python-multipart==0.0.20

# === COMMON LIBRARY ===
-e ./common

# === REDIS & ASYNC ===
redis==5.2.1
celery==5.5.0
tenacity==9.0.0

# === OBSERVABILIDADE ===
prometheus-client==0.21.1

# === HTTP CLIENT ===
httpx==0.28.1
```

> **Regra:** Cada serviço tem suas dependências específicas **além** desse core. As versões acima são o **mínimo obrigatório** de todos.

---

### 3.2 Estrutura de Diretórios Padrão

Todos os serviços devem adotar a estrutura em camadas:

```
services/<nome-do-servico>/
├── .dockerignore            # Exclui .trash/, sprints/, data/, logs/, tests/
├── .env                     # Não commitado
├── .env.example             # Template documentado
├── .gitignore               # logs/, temp/, uploads/, __pycache__, .env
├── constraints.txt          # Lock de versões para reproducibilidade
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pytest.ini
├── README.md
├── requirements.txt
├── requirements-docker.txt  # Subset para container (sem dev deps)
├── run.py
├── app/
│   ├── __init__.py
│   ├── main.py              # < 150 linhas — apenas bootstrap + include_router
│   ├── api/
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── jobs.py      # Rotas de jobs
│   │       └── health.py    # /health e /metrics
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # pydantic_settings.BaseSettings + @lru_cache
│   │   └── constants.py     # Constantes do domínio
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py        # Pydantic models (Job, JobStatus, etc.)
│   │   └── exceptions.py    # Hierarquia de exceções com HTTP status
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── redis_store.py   # RedisJobStore via ResilientRedisStore
│   │   ├── celery_config.py
│   │   └── celery_tasks.py  # + @signals.task_failure.connect
│   └── services/
│       └── __init__.py      # Lógica de negócio
├── common/ -> symlink ou cópia
└── tests/
    ├── conftest.py
    ├── requirements-test.txt
    ├── run_tests.py
    ├── unit/
    ├── integration/
    └── e2e/
```

---

### 3.3 Template `config.py` Padrão

```python
"""
Service configuration — seguindo Twelve-Factor App (III. Config)
Todas as configurações vêm de variáveis de ambiente. Zero magic strings.
"""
from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    # === Identidade ===
    service_name: str = "<nome-do-servico>"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # === Servidor ===
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_format: str = "json"

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"

    # === Cache ===
    cache_ttl_hours: int = 24
    cache_cleanup_interval_minutes: int = 30

    # === CORS ===
    cors_enabled: bool = False
    cors_origins: List[str] = ["*"]
    cors_credentials: bool = False

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",           # Ignora variáveis não declaradas (não falha)
    )


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Singleton thread-safe de configurações."""
    return ServiceSettings()
```

---

### 3.4 Template `main.py` Padrão (< 100 linhas)

```python
"""<Nome do Serviço> — FastAPI application bootstrap"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.routing import Mount

from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers

from .core.config import get_settings
from .domain.exceptions import ServiceBaseException, exception_handler
from .infrastructure.redis_store import RedisJobStore
from .api.routes import jobs, health

settings = get_settings()

setup_structured_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    json_format=(settings.log_format == "json"),
)
logger = get_logger(__name__)

job_store = RedisJobStore(redis_url=settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: startup → yield → shutdown"""
    logger.info(f"Starting {settings.service_name} v{settings.version}")
    await job_store.start_cleanup_task()
    yield
    logger.info(f"Shutting down {settings.service_name}")
    if job_store._cleanup_task:
        job_store._cleanup_task.cancel()


app = FastAPI(
    title=settings.service_name,
    version=settings.version,
    lifespan=lifespan,
)

setup_exception_handlers(app, debug=settings.debug)
app.add_exception_handler(ServiceBaseException, exception_handler)

if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Prometheus metrics (via ASGI sub-application)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(jobs.router)
app.include_router(health.router)
```

---

### 3.5 Template `exceptions.py` Padrão

```python
"""Domain exceptions with HTTP status mapping."""
from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class ServiceBaseException(Exception):
    """Base exception — todos os erros do serviço herdam desta."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class ResourceNotFoundError(ServiceBaseException):
    def __init__(self, resource_id: str):
        super().__init__(
            f"Resource '{resource_id}' not found",
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND",
        )


class ValidationError(ServiceBaseException):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR")


class ProcessingTimeoutError(ServiceBaseException):
    def __init__(self, job_id: str, timeout_seconds: int):
        super().__init__(
            f"Job '{job_id}' timed out after {timeout_seconds}s",
            status.HTTP_408_REQUEST_TIMEOUT,
            "PROCESSING_TIMEOUT",
        )


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unified exception handler — JSON consistente para todos os erros."""
    logger.error(f"Exception in {request.method} {request.url.path}: {exc}", exc_info=True)

    if isinstance(exc, ServiceBaseException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "error_code": exc.error_code,
                "type": exc.__class__.__name__,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc), "type": "UnknownError"},
    )
```

---

### 3.6 Template `Dockerfile` Padrão

```dockerfile
FROM python:3.11-slim

# --- Metadata ---
ARG SERVICE_NAME=<service-name>
ARG SERVICE_VERSION=1.0.0
LABEL maintainer="${SERVICE_NAME}" \
      version="${SERVICE_VERSION}" \
      description="${SERVICE_NAME} Microservice"

# --- Environment ---
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    TZ=Etc/UTC

# --- System dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python dependencies (cache layer) ---
COPY common/ ./common/
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -c constraints.txt

# --- Application code ---
COPY app/ ./app/
COPY run.py .

# --- Non-root user ---
RUN useradd -m -u 1000 appuser \
 && mkdir -p /app/logs /app/temp /app/uploads \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /app \
 && chmod -R 777 /app/logs /app/temp /app/uploads

USER appuser

EXPOSE ${PORT:-8000}

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["python", "run.py"]
```

---

### 3.7 Template `run.py` Padrão

```python
#!/usr/bin/env python3
"""Service startup — reads ALL config from environment via pydantic_settings."""
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        reload=s.debug,              # True em dev, False em prod
        workers=1,                   # 1 worker + async = suficiente para a maioria
        log_level=s.log_level.lower(),
        limit_max_requests=10_000,   # Recicla worker após N requests (memory leak prevention)
        limit_concurrency=100,
    )
```

---

### 3.8 `/health` Endpoint Padrão

Todos os serviços devem retornar a mesma estrutura:

```json
{
  "service": "audio-transcriber",
  "version": "2.0.0",
  "status": "healthy",
  "timestamp": "2026-03-01T14:00:00.000Z",
  "checks": {
    "redis": {"status": "ok", "latency_ms": 2.1},
    "disk_space": {"status": "ok", "free_gb": 45.2, "total_gb": 100.0},
    "celery_workers": {"status": "ok", "active_workers": 1},
    "<service-specific>": {"status": "ok"}
  }
}
```

**Regra:** status 200 = healthy/degraded; status 503 = unhealthy.

---

## 4. DIAGNÓSTICO CRUZADO — BUGS E RISCOS

### 🔴 Crítico (corrigir esta semana)

| Serviço | Bug | Impacto |
|---------|-----|---------|
| `video-downloader` | `class exception_handler(Exception): pass` | ✅ DONE — async function implementada |
| `video-downloader` | `reload=True` hardcoded em run.py | ✅ DONE — usa `settings.debug` |
| `audio-normalization` | HEALTHCHECK/EXPOSE na porta `8003` mas serviço é `8002` | ✅ DONE — porta corrigida para 8002 |
| `audio-transcriber` | HEALTHCHECK `start-period=40s` insuficiente para Whisper | ✅ DONE — `start-period=120s`, `timeout=15s` |
| `make-video` | `allow_origins=["*"]` + `allow_credentials=True` | ✅ DONE — `allow_credentials` removido |
| `youtube-search` | Dockerfile usa `sh -c uvicorn` ignorando `run.py` | ✅ DONE — `CMD ["python", "run.py"]` |

### 🟡 Alta (corrigir na próxima sprint)

| Padrão Ausente | Serviços Afetados | Risco |
|----------------|-------------------|-------|
| `lifespan` (deprecated `on_event`) | ✅ DONE — todos os 5 serviços migrados | Quebrará em FastAPI 1.0 |
| `pydantic_settings.BaseSettings` | ✅ DONE — 4 serviços migrados + make-video já tinha | Sem validação, sem docs, sem type safety |
| `tenacity` retry | ✅ DONE — video-downloader e youtube-search | Downloads/buscas falham permanentemente por erro transitório |
| `constraints.txt` ausente | ✅ DONE — video-downloader, make-video, youtube-search | Build não reproduzível |

### 🟢 Médio (backlog organizado)

| Padrão Ausente | Serviços Afetados |
|----------------|-------------------|
| Prometheus `/metrics` | audio-transcriber, audio-normalization, video-downloader, youtube-search |
| Arquitetura em camadas | audio-normalization, video-downloader, youtube-search |
| Testes estruturados (unit/integration/e2e) | audio-normalization, video-downloader, youtube-search |
| `main.py` < 150 linhas | Todos 5 |

---

## 5. PLANO DE MIGRAÇÃO GLOBAL

### Fase 0 — Limpeza Imediata (sem risco de regressão)
```bash
# 1. Deletar .trash/ dos 2 serviços
rm -rf services/se4-audio-transcriber/.trash/
rm -rf services/se5-make-video/.trash/

# 2. Deletar arquivos .bak (backups no repositório)
rm services/se4-audio-transcriber/tests/conftest.py.bak
rm services/se3-audio-normalization/conftest.py.bak
rm services/se5-make-video/app/video_processing/frame_preprocessor_OLD_SPRINTS.py.bak
rm services/se5-make-video/app/video_processing/subtitle_detector_v2_OLD_SPRINTS.py.bak

# 3. Deletar relatório ad-hoc commitado
rm services/se5-make-video/tests/RELATORIO_EXECUCAO.md

# 4. Remover proxies.txt do controle de versão
git rm --cached services/se6-youtube-search/app/ytbpy/proxies.txt
echo "app/ytbpy/proxies.txt" >> services/se6-youtube-search/.gitignore

# 5. Adicionar .gitignore nos 2 serviços sem: audio-transcriber e audio-normalization
# Incluir: logs/, temp/, uploads/, processed/, __pycache__, .env
```

### Fase 1 — Bugs Críticos (sprint de 1-2 dias) ✅ DONE
1. ✅ DONE Corrigir `exceptions.py` no `video-downloader` (class → async function)
2. ✅ DONE Corrigir `run.py` no `video-downloader` (reload=True → s.debug)
3. ✅ DONE Corrigir porta no HEALTHCHECK/EXPOSE do `audio-normalization/Dockerfile` (8003→8002)
4. ✅ DONE Aumentar `start-period` no HEALTHCHECK do `audio-transcriber/Dockerfile` (40s→120s)
5. ✅ DONE Corrigir `make-video` CORS (remover `allow_credentials=True` com `origins=["*"]`)
6. ✅ DONE Corrigir `youtube-search/Dockerfile` CMD: mudar `sh -c uvicorn` → `["python", "run.py"]`

### Fase 2 — Modernização Core (sprint de 3-5 dias) ✅ DONE
7. ✅ DONE Implementar `pydantic_settings.BaseSettings` em todos os 4 serviços restantes
8. ✅ DONE Migrar todos de `@app.on_event` para `lifespan`
9. ✅ DONE Criar `constraints.txt` para video-downloader, make-video, youtube-search
10. Atualizar dependências para versões alinhadas (fastapi, pydantic, uvicorn)

### Fase 3 — Resiliência (sprint de 3-5 dias)
10. ✅ DONE Adicionar `tenacity` + retry em `video-downloader` (yt-dlp) e `youtube-search` (API calls)
11. ✅ DONE Adicionar `prometheus-client` + `/metrics` em audio-transcriber, audio-normalization, video-downloader, youtube-search
12. Padronizar resposta do `/health` em todos os serviços

### Fase 4 — Estrutura e Testes (sprint de 5-8 dias)
13. Reorganizar `app/` de flat para camadas em audio-normalization, video-downloader, youtube-search
14. Criar estrutura unit/integration/e2e em video-downloader e youtube-search
15. Extrair rotas de `main.py` em todos os serviços

---

## 6. TABELA DE PORTAS (REFERÊNCIA)

| Serviço | Porta Principal | Redis DB | Celery Worker |
|---------|----------------|----------|---------------|
| youtube-search | 8001 | DB 1 | Sim |
| audio-normalization | 8002 | DB 2 | Sim |
| audio-transcriber | 8003/8004 | DB 3/4 | Sim |
| audio-transcriber (worker) | — | DB 4 | Sim |
| make-video | 8005 | DB 5 | Sim |
| video-downloader | 8000 | DB 0 | Sim |
| orchestrator | 8006+ | — | — |

> **Atenção:** Verificar que `REDIS_URL` de cada serviço usa o DB correto. Múltiplos serviços no mesmo DB causam colisão de keys.

---

## 7. REGRAS DE OURO (NON-NEGOTIABLE)

1. **Zero código em main.py que não seja bootstrap** — rotas ficam em `api/routes/`
2. **Zero `os.getenv()` fora de `config.py`** — toda config passa pelo `BaseSettings`
3. **Zero `reload=True` hardcoded** — sempre `reload=settings.debug`
4. **Zero `allow_origins=["*"]` + `allow_credentials=True`** — viola CORS spec
5. **Zero arquivos `.bak`, `.log`, `build.log` no repositório** — `.gitignore` é obrigatório
6. **Zero pasta `.trash/` no repositório** — use `git rm` + branch/tag para histórico
7. **Todo container roda como non-root** — `USER appuser` obrigatório
8. **Todo container tem HEALTHCHECK** — porta deve bater com `PORT` env var
9. **Todo serviço tem `constraints.txt`** — reproducibilidade de builds
10. **Todo handler de exceção é `async def`** — nunca uma `class` registrada como handler

---

## 8. SCRIPTS DE VALIDAÇÃO AUTOMATIZADA

```bash
#!/bin/bash
# validate_standards.sh — verificar conformidade dos padrões
set -e

SERVICES=("audio-transcriber" "audio-normalization" "video-downloader" "make-video" "youtube-search")
PASS=0; FAIL=0

check() {
    local service=$1 desc=$2 cmd=$3
    if eval "$cmd" &>/dev/null; then
        echo "  ✅ $service: $desc"
        PASS=$((PASS+1))
    else
        echo "  ❌ $service: $desc"
        FAIL=$((FAIL+1))
    fi
}

for svc in "${SERVICES[@]}"; do
    dir="services/$svc"
    echo "\n=== $svc ==="
    check "$svc" "run.py exists"           "[ -f $dir/run.py ]"
    check "$svc" "constraints.txt exists"  "[ -f $dir/constraints.txt ]"
    check "$svc" "HEALTHCHECK in Dockerfile" "grep -q HEALTHCHECK $dir/Dockerfile"
    check "$svc" "USER appuser in Dockerfile" "grep -q 'USER appuser' $dir/Dockerfile"
    check "$svc" ".gitignore exists"       "[ -f $dir/.gitignore ]"
    check "$svc" "No .trash/ directory"    "[ ! -d $dir/.trash ]"
    check "$svc" "No reload=True hardcoded" "! grep -q 'reload=True' $dir/run.py 2>/dev/null"
    check "$svc" "pydantic_settings imported" "grep -rq 'pydantic_settings' $dir/app/"
    check "$svc" "lifespan context manager" "grep -rq 'lifespan' $dir/app/main.py"
    check "$svc" "No on_event" "! grep -q 'on_event' $dir/app/main.py"
done

echo "\n=== RESULTADO: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
```

---

## 9. REFERÊNCIAS E BOAS PRÁTICAS

| Referência | Aplicação |
|------------|-----------|
| [Twelve-Factor App](https://12factor.net/) | Config (III), Processes (VI), Disposability (IX) |
| [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/) | lifespan, exception handlers, routers |
| [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Config type-safe |
| [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/) | Non-root, HEALTHCHECK, cache layers |
| [OWASP API Security](https://owasp.org/www-project-api-security/) | CORS, input validation |
| [Python Tenacity](https://tenacity.readthedocs.io/) | Retry + circuit breaker |
| [Prometheus Python Client](https://github.com/prometheus/client_python) | Metrics |
| [Google Engineering Practices](https://google.github.io/eng-practices/) | Code review standards |
