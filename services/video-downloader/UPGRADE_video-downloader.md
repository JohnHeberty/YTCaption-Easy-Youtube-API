# UPGRADE ANALYSIS — video-downloader
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Versão atual do serviço: 3.0.0 (FastAPI) / 1.0.0 (Dockerfile LABEL — inconsistente)

---

## 1. RESUMO EXECUTIVO

O `video-downloader` é o serviço com **maior débito técnico crítico não-corrigido** da stack. Contém um **bug grave de exception handler**, `reload=True` hardcoded para produção no `run.py`, ausência de `tenacity` para retry, versão inconsistente entre Dockerfile e FastAPI, e é sem dúvida o serviço **menos testado** (apenas 2 arquivos de teste, sem unit/, integration/, ou e2e/ estruturados). Apesar disso, o Dockerfile é bem formado e o `RedisJobStore` usa `ResilientRedisStore` corretamente.

**Saúde geral: 4.5/10** — Questões críticas que podem causar falhas silenciosas em produção.

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03

| Item | Status |
|------|---------|
| `exception_handler` class bug → async function | ✅ DONE |
| `reload=True` hardcoded in `run.py` → `reload=debug` | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| `PYTHONPATH=/app` in Dockerfile | ✅ DONE |
| `requirements-test.txt` created | ✅ DONE |
| `tenacity` retry for yt-dlp downloads | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `LABEL version "3.0.0"` in Dockerfile fixed | ✅ DONE |
| `pydantic-settings` added to `requirements.txt` | ✅ DONE |
| `user-agents-original.txt` moved to `.trash/` | ✅ DONE |
| `.trash/` added to `.gitignore` | ✅ DONE |
| `logs/` runtime log rotations moved to `.trash/logs/` | ✅ DONE |
| `cache/*.mp4` cached downloads moved to `.trash/cache/` | ✅ DONE |
| `uploads/` added to `.gitignore`; `.gitkeep` placed | ✅ DONE |
| `.dockerignore` criado (cobindo `cache/`, `logs/`, `uploads/`, `.trash/`, `tests/`) | ✅ DONE |
| Dependency versions normalized (fastapi 0.120.0, uvicorn 0.38.0, pydantic 2.12.3, pydantic-settings 2.11.0) | ✅ DONE |
| `constraints.txt` version ranges updated to allow 0.120.x / 0.38.x / 2.12.x | ✅ DONE |
| Dockerfile `EXPOSE 8000` → `8002` + HEALTHCHECK port `8000` → `8002` corrected | ✅ DONE |
| `.env` PORT `800${DIVISOR}` → `8002` hardcoded (Docker env_file não expande vars) | ✅ DONE |
| `.env` REDIS_URL/CELERY_* `${DIVISOR}` hardcoded to literal `/2` | ✅ DONE |
| `root docker-compose.yml` port `8000:8001` → `8002:8002` + healthcheck URL fixed | ✅ DONE |
| `root docker-compose.yml` broken `user-agents-original.txt` volume mount removed | ✅ DONE |
| `config.py` default port `8000` → `8002` aligned with canonical .env value | ✅ DONE |
| `logs/video-downloader.json` moved to `.trash/logs/` | ✅ DONE |

---

## 2. MAPA DE GAPS POR CATEGORIA

### 2.1 🚨 BUG CRÍTICO — exception_handler como Classe ✅ DONE

**Este bug causa handlers de exceção inoperantes em produção.**

```python
# ATUAL — exceptions.py (BUG: exception_handler é uma CLASSE que herda de Exception)
class exception_handler(Exception):
    pass

# Em main.py:
from .exceptions import VideoDownloadException, ServiceException, exception_handler
app.add_exception_handler(VideoDownloadException, exception_handler)   # ← QUEBRADO
app.add_exception_handler(ServiceException, exception_handler)         # ← QUEBRADO
```

**O que acontece:** `add_exception_handler` espera um `Callable[[Request, Exception], Response]`. Ao passar uma *classe que herda de Exception*, o FastAPI aceitará silenciosamente (não valida na inicialização), mas quando uma `VideoDownloadException` for levantada, o handler tentará *instanciar* a classe com `(request, exc)` como argumentos, resultando em erro interno — **a exceção original nunca é tratada corretamente**.

```python
# CORRETO — exceptions.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class VideoDownloadException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ServiceException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ResourceError(Exception):
    pass


class ProcessingTimeoutError(Exception):
    pass


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unified exception handler — retorna JSON consistente"""
    logger.error(f"Exception in {request.url.path}: {exc}", exc_info=True)

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, VideoDownloadException):
        status_code = getattr(exc, "status_code", 500)
    elif isinstance(exc, ResourceError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ProcessingTimeoutError):
        status_code = status.HTTP_408_REQUEST_TIMEOUT

    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "type": exc.__class__.__name__},
    )
```

---

### 2.2 🚨 BUG CRÍTICO — `reload=True` Hardcoded em run.py ✅ DONE

```python
# ATUAL — run.py (CAUSA PROBLEMAS EM PRODUÇÃO)
uvicorn.run(
    "app.main:app",
    host=host,
    port=port,
    reload=True,          # ← HARDCODED, NÃO respeita DEBUG env var
    log_level="info"
)

# CORRETO
from app.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s['host'],
        port=s['port'],
        reload=s['debug'],           # Respeita DEBUG=false em produção
        log_level=s['log_level'].lower(),
        workers=1,
        limit_max_requests=10_000,
        limit_concurrency=30,
    )
```

**Impacto:** Em produção com `reload=True`, o Uvicorn usa file watchers, aumenta uso de memória/CPU, impede múltiplos workers, e pode causar instabilidade em containers.

---

### 2.3 Versão Inconsistente ✅ DONE

| Onde | Versão |
|------|--------|
| `app/main.py` → `version="3.0.0"` | 3.0.0 |
| `Dockerfile` → `LABEL version="1.0.0"` | ~~1.0.0~~ → **3.0.0** ✅ DONE |
| `app/config.py` → `'version': os.getenv('VERSION', '2.0.0')` | ~~2.0.0~~ → **3.0.0** ✅ DONE |

**Ação:** Definir uma única fonte de verdade — `.env` com `VERSION=3.0.0` e ler de lá.

---

### 2.4 Arquitetura de Código

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura de diretórios | ❌ Flat (8 arquivos no raiz de `app/`) | Layered (domain/infra/services/core) | Média |
| `config.py` | ✅ DONE — `pydantic_settings.BaseSettings` implementado | Manter | — |
| `main.py` tamanho | ❌ 1130 linhas "God file" | Extrair rotas para `app/api/routes/` | Alta |
| `@app.on_event` lifecycle | ✅ DONE — migrado para `lifespan` | Manter | — |
| Startup sem inicialização explícita | ⚠️ `startup_event` sem `await job_store.start_cleanup_task()` explícito | Verificar | Média |

**Config atual — problemas:**
```python
# ATUAL — config.py sem tipagem, sem validação, sem docstring
import os

def get_settings():
    return {
        'port': int(os.getenv('PORT', '8001')),   # ← porta inconsistente com docker-compose
        ...
    }

# ALVO
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class VideoDownloaderSettings(BaseSettings):
    app_name: str = "Video Downloader Service"
    version: str = "3.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_hours: int = 24
    max_file_size_mb: int = 10240
    cache_dir: str = "./cache"
    downloads_dir: str = "./downloads"
    temp_dir: str = "./temp"
    log_dir: str = "./logs"
    log_level: str = "INFO"
    max_concurrent_downloads: int = 2
    default_quality: str = "best"
    job_processing_timeout_seconds: int = 1800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache(maxsize=1)
def get_settings() -> VideoDownloaderSettings:
    return VideoDownloaderSettings()
```

---

### 2.5 Dockerfile

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| HEALTHCHECK | ✅ Presente | Manter | — |
| Non-root user | ✅ `USER appuser` presente | Manter | — |
| `constraints.txt` | ✅ DONE — adicionado | Manter | — |
| `PYTHONPATH` | ✅ DONE — `ENV PYTHONPATH=/app` adicionado | Manter | — |
| `run.py` na imagem | ✅ Copiado | Manter | — |

```dockerfile
# ADICIONAR ao Dockerfile:
ENV PYTHONPATH=/app

# ANTES de pip install, copiar constraints:
COPY constraints.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt
```

---

### 2.6 Testes — ESTADO CRÍTICO

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Cobertura | ❌ Apenas 2 arquivos de teste | Mínimo 70% de cobertura | **Crítica** |
| Estrutura | ❌ Sem unit/, integration/, e2e/ | Estrutura completa | Alta |
| `conftest.py` | ✅ Presente | Expandir fixtures | Média |
| requirements-test.txt | ✅ DONE — criado | Manter | — |
| pytest.ini | ✅ Presente | Manter | — |

**Estrutura alvo mínima:**
```
tests/
├── conftest.py
├── requirements-test.txt       # ← CRIAR
├── unit/
│   ├── test_models.py          # ← CRIAR
│   ├── test_config.py          # ← CRIAR
│   └── test_exceptions.py      # ← CRIAR (validar o bug corrigido)
├── integration/
│   ├── test_downloader.py      # ← CRIAR
│   └── test_redis_store.py     # ← CRIAR
└── e2e/
    └── test_download_job.py    # ← CRIAR
```

---

### 2.7 Dependências (`requirements.txt`)

| Pacote | Versão Atual | Alinhamento Stack | Ação |
|--------|-------------|-------------------|------|
| `fastapi` | 0.104.1 | ❌ Desatualizado | Atualizar para `0.115.x` |
| `pydantic` | 2.5.0 | ❌ Defasado | Atualizar para `2.11.x` |
| `uvicorn` | 0.24.0 | ❌ Defasado | Atualizar para `0.34.x` |
| `pydantic-settings` | ✅ DONE — adicionado ao requirements.txt | Manter | — |
| `tenacity` | ✅ DONE — `9.0.0` adicionado com retry em yt-dlp | Manter | — |
| `prometheus-client` | ✅ DONE — adicionado, endpoint `/metrics` ativo | Manter | — |
| `httpx` | ❌ Ausente | Adicionar para testes de integração | Média |

**Por que tenacity é crítico aqui:**
```python
# ALVO — retry em downloads com yt-dlp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import yt_dlp

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(yt_dlp.utils.DownloadError),
)
async def _download_with_retry(url: str, opts: dict) -> dict:
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)
```

---

### 2.8 Resiliência e Observabilidade

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Circuit Breaker Redis | ✅ Via `ResilientRedisStore` | Manter | — |
| Retry em downloads | ✅ DONE — `tenacity` com 3 retries implementado | Manter | — |
| Rate Limiting | ❌ Ausente (comentário no requirements: "removido slowapi") | Re-adicionar | Média |
| Prometheus metrics | ✅ DONE — `/metrics` endpoint ativo | Manter | — |
| `/health` endpoint | ⚠️ Presente mas pouco estruturado (sem sub-checks organizados) | Padronizar com outros serviços | Média |
| Celery Signal failure | ✅ `task_failure_handler` presente | Manter | — |

---

## 3. ARQUIVOS A DELETAR (LIMPEZA)

```
# Nenhum arquivo .trash encontrado, mas verificar:
services/video-downloader/user-agents-original.txt   # ✅ DONE — movido para .trash/
services/video-downloader/user-agents.txt            # versão intermediária — manter apenas -clean.txt
```

**Verificar qual arquivo é usado em `user_agent_manager.py` e deletar os desnecessários.**

---

## 4. PLANO DE EXECUÇÃO (ORDENADO POR IMPACTO)

### Sprint 1 — Bugs Críticos (1-2h) ✅ DONE
1. ✅ DONE **Corrigir `exceptions.py`**: transformar `class exception_handler(Exception)` em `async def exception_handler(request, exc) -> JSONResponse`
2. ✅ DONE **Corrigir `run.py`**: remover `reload=True` hardcoded, usar `settings.debug`
3. ✅ DONE **Corrigir versão**: unificar para `3.0.0` no `.env`, Dockerfile e `main.py`

### Sprint 2 — Modernização (2-3h) ✅ DONE
4. ✅ DONE Migrar `config.py` para `pydantic_settings.BaseSettings`
5. ✅ DONE Migrar `@app.on_event` para `lifespan`
6. ✅ DONE Adicionar `constraints.txt` e `pydantic-settings` ao requirements

### Sprint 3 — Resiliência (2-3h) ✅ DONE
7. ✅ DONE Adicionar `tenacity` e retry logic no downloader
8. ✅ DONE Adicionar `prometheus-client` + `/metrics` endpoint

### Sprint 4 — Testes (3-5h)
9. ✅ DONE Criar `tests/requirements-test.txt`
10. Criar estrutura unit/integration/e2e
11. Escrever testes para o bug do exception_handler (regression test)
12. Atingir mínimo 60% de cobertura

---

## 5. REFERÊNCIAS

- [FastAPI Exception Handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Uvicorn Production Settings](https://www.uvicorn.org/deployment/)
- [tenacity Documentation](https://tenacity.readthedocs.io/)

---

## 6. WORK COMPLETED — Padronização app/ e data/ (Session 3)

### Sprint 5 — Estrutura app/ em Camadas ✅ DONE
1. ✅ DONE Reorganizar `app/` em camadas:
   - `app/core/` ← `config.py`, `models.py`, `logging_config.py`
   - `app/domain/` ← `downloader.py`
   - `app/infrastructure/` ← `celery_config.py`, `celery_tasks.py`, `redis_store.py`
   - `app/services/` ← `user_agent_manager.py`
   - `app/shared/` ← `exceptions.py`
2. ✅ DONE Atualizar todos os imports nos arquivos movidos
3. ✅ DONE Corrigir lazy imports em `main.py` que usavam `.celery_config` (stale após reestruturação)
4. ✅ DONE Atualizar `run.py`: `from app.config` → `from app.core.config`

### Sprint 6 — Padronização data/ ✅ DONE
5. ✅ DONE Criar `data/{cache,downloads,logs}/` com `.gitkeep`
6. ✅ DONE Atualizar `Dockerfile` mkdir: `/app/{cache,logs,downloads,temp}` → `/app/data/{cache,logs,downloads,temp}`
7. ✅ DONE Atualizar `docker-compose.yml` (root + individual):
   - Volumes: `./cache:/app/cache` → `./data/cache:/app/data/cache`
   - Volumes: `./logs:/app/logs` → `./data/logs:/app/data/logs`
   - Env: `CACHE_DIR=/app/cache` → `CACHE_DIR=/app/data/cache`
8. ✅ DONE Atualizar `app/core/config.py` defaults: `./cache` → `./data/cache`, etc.
9. ✅ DONE Atualizar Celery command: `-A app.celery_config` → `-A app.infrastructure.celery_config`
10. ✅ DONE Adicionar `data/**/*` / `!data/**/.gitkeep` ao `.gitignore`
11. ✅ DONE Adicionar `data/` ao `.dockerignore`
12. ✅ DONE Build + deploy: containers `video-downloader` e `video-downloader-celery` saudáveis ✅

**Status final:** `curl http://localhost:8002/health` → `{"status": "healthy", "active_workers": 2}` ✅
