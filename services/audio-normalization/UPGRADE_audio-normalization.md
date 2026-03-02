# UPGRADE ANALYSIS — audio-normalization
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Versão atual do serviço: 2.0.0

---

## 1. RESUMO EXECUTIVO

O `audio-normalization` apresenta uma situação paradoxal: possui o **Dockerfile mais bem estruturado** da stack (healthcheck, non-root, envs corretos), as dependências Python mais atualizadas (`fastapi==0.120.0`, `pydantic==2.12.3`) e uma estrutura de `services/` com SRP aplicado (`AudioNormalizer`, `FileValidator`, etc.). Porém, ao mesmo tempo, carrega **responsabilidades fora de escopo** (`ass_generator.py`, `sync_diagnostics.py` são sobre legendas, não áudio), arquitetura plana no nível `app/` (sem domain/infrastructure separation), exceptions anêmicas, e código de middleware embutido direto no `main.py`.

**Saúde geral: 6.5/10** — Boa infraestrutura de container, arquitetura de código precisa de refatoração.

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03

| Item | Status |
|------|---------|
| Dockerfile `EXPOSE 8002` → `8003` + HEALTHCHECK port `8002` → `8003` corrected | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `PYTHONPATH=/app` added to Dockerfile | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `.gitignore` created | ✅ DONE |
| `logs/*.log` files moved to `.trash/logs/` | ✅ DONE |
| `uploads/*.mp4` runtime files moved to `.trash/uploads/` | ✅ DONE |
| `uploads/` added to `.gitignore`; `.gitkeep` placed | ✅ DONE |
| Dockerfile double `apt-get` RUN blocks merged into one | ✅ DONE |
| `non-root USER appuser` added to Dockerfile | ✅ DONE |
| `run.py` `limit_max_requests=1000`, `limit_concurrency=30` added | ✅ DONE |
| Celery `task_failure` signal handler added | ✅ DONE |
| `requirements-test.txt` created | ✅ DONE |
| Dependency versions normalized (fastapi 0.120.0, uvicorn 0.38.0, pydantic 2.12.3, pydantic-settings 2.11.0) | ✅ DONE |
| `.env` `${DIVISOR}` in REDIS_URL/CELERY_* hardcoded to literal `/3` | ✅ DONE |
| `root docker-compose.yml` port mapping `8001:8001` → `8003:8003` + `PORT=8003` injected | ✅ DONE |
| `run.py` default PORT `8002` → `8003` aligned with canonical .env value | ✅ DONE |
| `uploads/*.webm`, `uploads/*.wav`, `processed/`, `temp/` runtime files → `.trash/` | ✅ DONE |
| `logs/audio-normalization.json` moved to `.trash/logs/` | ✅ DONE |

---

## 2. MAPA DE GAPS POR CATEGORIA

### 2.1 Arquitetura de Código

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura de diretórios | ❌ Flat (12 arquivos no raiz de `app/`) | Layered (domain/infra/services/core) | Alta |
| `config.py` | ✅ DONE — `pydantic_settings.BaseSettings` implementado | Manter | — |
| `main.py` tamanho | ❌ 1383 linhas "God file" | Extrair rotas para `app/api/routes/` | Alta |
| `@app.on_event` lifecycle | ✅ DONE — migrado para `lifespan` | Manter | — |
| `BodySizeMiddleware` inline | ❌ Middleware definido dentro de `main.py` | Mover para `app/middleware/` | Média |

**Detalhe — `BodySizeMiddleware` no lugar errado:**
```python
# ATUAL — definido DENTRO do main.py (acoplamento)
class BodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int): ...
    async def dispatch(self, request, call_next): ...

# ALVO — em app/middleware/body_size.py
# main.py apenas importa e registra:
from .middleware.body_size import BodySizeMiddleware
app.add_middleware(BodySizeMiddleware, max_size=settings.max_body_size_bytes)
```

---

### 2.2 Responsabilidade de Domínio (SRP Violado)

**Problema crítico:** O serviço de normalização de áudio contém lógica de **legendas** — algo que pertence ao `make-video` ou a um serviço dedicado.

| Arquivo | Responsabilidade Atual | Status |
|---------|----------------------|--------|
| `app/ass_generator.py` | Gera legendas `.ass` a partir de `.srt` | ❌ **Fora de escopo** |
| `app/sync_diagnostics.py` | Detecta drift temporal em legendas SRT/ASS | ❌ **Fora de escopo** |
| `app/audio_extractor.py` (services/) | Extrai áudio | ✅ Correto |
| `app/audio_normalizer.py` (services/) | Normaliza áudio | ✅ Correto |
| `app/file_validator.py` (services/) | Valida arquivos | ✅ Correto |

**Resultado da verificação (validado):**
- `tests/unit/test_ass_generator.py` e `tests/unit/test_sync_diagnostics.py` existem e importam esses módulos
- Portanto **estão sendo usados** — não podem ser simplesmente deletados
- A questão é **arquitetural**: o serviço de normalização de áudio carrega lógica de legendas que conceitualmente pertence ao `make-video`

**Ação recomendada (sem quebrar):**
1. **Manter os arquivos** na posição atual a curto prazo
2. Planejar migração para `make-video/app/subtitle_processing/` (já existe este módulo lá)
3. Criar abstração via endpoint dedicado ou mover para `common/subtitle_utils/`
4. Somente depois de migrado e testado, remover do audio-normalization

---

### 2.3 Exceptions sem HTTP Mapping

**Problema:** `exceptions.py` contém apenas classes vazias sem HTTP status code, mensagem padrão, ou handler correto.

```python
# ATUAL — anêmico, sem valor
class AudioProcessingError(Exception):
    pass

class ResourceError(Exception):
    pass
```

```python
# ALVO — exceções com contexto rico
from fastapi import status

class AudioNormalizationException(Exception):
    """Base exception com status HTTP e contexto"""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "AUDIO_NORMALIZATION_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class FileValidationError(AudioNormalizationException):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, "FILE_VALIDATION_ERROR")


class ProcessingTimeoutError(AudioNormalizationException):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_408_REQUEST_TIMEOUT, "PROCESSING_TIMEOUT")


class ResourceNotFoundError(AudioNormalizationException):
    def __init__(self, resource_id: str):
        super().__init__(f"Resource not found: {resource_id}", status.HTTP_404_NOT_FOUND, "NOT_FOUND")
```

---

### 2.4 Dockerfile

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| HEALTHCHECK | ✅ DONE — porta corrigida para `8002` | Manter | — |
| Non-root user | ✅ `USER appuser` presente | Manter | — |
| `constraints.txt` | ✅ Presente | Manter | — |
| TZ=Etc/UTC em ARG | ⚠️ `TZ` deveria ser ENV | Já é ENV | — |
| Porta exposta vs .env | ✅ DONE — HEALTHCHECK e EXPOSE corrigidos para `8002` | Manter | — |

```dockerfile
# BUG ATUAL — porta errada no HEALTHCHECK
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8003/health || exit 1

# CORRETO — conforme PORT=8002 no docker-compose
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8002/health || exit 1
```

---

### 2.5 run.py

Verificar se existe — se não existir, criar:

```python
#!/usr/bin/env python3
"""Audio Normalization Service startup"""
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        reload=s.debug,
        log_level=s.log_level.lower(),
        workers=1,
        limit_max_requests=5_000,
        limit_concurrency=20,
    )
```

---

### 2.6 Testes

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura | ⚠️ Mix: arquivos flat + `unit/` folder | Estrutura completa: unit/integration/e2e | Alta |
| `conftest.py` | ⚠️ Apenas na raiz de `tests/` | Separar por nível | Média |
| `test_chaos.py` | ✅ Presente | Manter e expandir | — |
| `test_performance.py` | ✅ Presente | Manter | — |
| `test_gpu.py` | ⚠️ Sem GPU no Docker CPU-only | Marcar com `@pytest.mark.skipif(not gpu, ...)` | Média |
| requirements-test.txt | ✅ Presente | Manter | — |

**Estrutura alvo de testes:**
```
tests/
├── conftest.py              # fixtures globais
├── requirements-test.txt
├── run_tests.py
├── unit/
│   ├── test_models.py
│   ├── test_config.py
│   └── test_exceptions.py
├── integration/
│   ├── test_normalization.py
│   ├── test_job_polling.py
│   └── test_redis_store.py
├── e2e/
│   └── test_all_features.py
├── chaos/
│   └── test_chaos.py
└── performance/
    └── test_performance.py
```

---

### 2.7 Dependências (`requirements.txt`)

| Pacote | Versão Atual | Alinhamento Stack | Ação |
|--------|-------------|-------------------|------|
| `fastapi` | 0.120.0 | ✅ Mais novo | Usar como versão-alvo para toda a stack |
| `pydantic` | 2.12.3 | ✅ Mais novo | Usar como versão-alvo |
| `uvicorn` | 0.38.0 | ✅ Mais novo | Usar como versão-alvo |
| `pydantic-settings` | 2.11.0 | ✅ Mais novo | Usar como versão-alvo |
| `tenacity` | 9.0.0 | ✅ Correto | Manter |
| `prometheus-client` | ✅ DONE — adicionado, endpoint `/metrics` ativo | Manter | — |
| `httpx` | ❌ Ausente | Adicionar para testes | Baixa |

---

### 2.8 Resiliência e Observabilidade

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Circuit Breaker Redis | ✅ Via `common.redis_utils` | Manter | — |
| Retry com tenacity | ✅ Presente | Manter | — |
| Rate limiting | ❌ Ausente | Middleware de rate limit | Média |
| Prometheus metrics | ✅ DONE — `/metrics` endpoint ativo | Manter | — |
| `/health` endpoint | ✅ Deep check (Redis + disk + ffmpeg) | Manter e expandir | — |
| Logging estruturado | ✅ Via `common.log_utils` | Manter | — |

---

## 3. ARQUIVOS A DELETAR (LIMPEZA)

```
# Verificar se são usados. Se não usados, DELETAR:
services/audio-normalization/app/ass_generator.py          # subtitle domain — fora de escopo
services/audio-normalization/app/sync_diagnostics.py       # subtitle domain — fora de escopo

# Logs commitados no repositório (devem estar no .gitignore): ✅ DONE — movidos para .trash/logs/
services/audio-normalization/logs/audio-normalization.json
services/audio-normalization/logs/debug.log.1
services/audio-normalization/logs/debug.log.2
services/audio-normalization/logs/debug.log.3
services/audio-normalization/logs/info.log.1 ... info.log.5
```

**Adicionar ao `.gitignore`:**
```gitignore
logs/
*.log
*.log.*
temp/
processed/
uploads/
```

---

## 4. PLANO DE EXECUÇÃO (ORDENADO POR RISCO)

### Sprint 1 — Bugs e Limpeza (30min-1h) ✅ DONE
1. ✅ DONE **Corrigir porta no HEALTHCHECK e EXPOSE**: `8003 → 8002`
2. Verificar e deletar `ass_generator.py` e `sync_diagnostics.py` se não usados
3. ✅ DONE Adicionar `logs/`, `temp/`, `processed/`, `uploads/` ao `.gitignore`
4. ✅ DONE Deletar arquivos de log commitados

### Sprint 2 — Modernização (2-3h)
5. ✅ DONE Migrar `config.py` para `pydantic_settings.BaseSettings`
6. ✅ DONE Migrar `@app.on_event` para `lifespan`
7. Mover `BodySizeMiddleware` para `app/middleware/body_size.py`
8. Enriquecer `exceptions.py` com HTTP status codes

### Sprint 3 — Estrutura (3-5h)
9. Reorganizar `app/` em camadas: core/, domain/, infrastructure/, services/
10. Extrair rotas de `main.py` para `app/api/routes/`
11. Reorganizar `tests/` para estrutura unit/integration/e2e/chaos/performance

### Sprint 4 — Observabilidade (2h)
12. ✅ DONE Adicionar `prometheus-client` e endpoint `/metrics`
13. Adicionar rate limiting

---

## 5. REFERÊNCIAS

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)

---

## 6. WORK COMPLETED — Padronização app/ e data/ (Session 3)

### Sprint 5 — Estrutura app/ em Camadas ✅ DONE
1. ✅ DONE Mover `app/ass_generator.py` + `app/sync_diagnostics.py` para `.trash/app/` (fora de escopo)
2. ✅ DONE Reorganizar `app/` em camadas:
   - `app/core/` ← `config.py`, `models.py`, `logging_config.py`
   - `app/domain/` ← `processor.py`
   - `app/infrastructure/` ← `celery_config.py`, `celery_tasks.py`, `redis_store.py`
   - `app/services/` ← `audio_extractor.py`, `audio_normalizer.py`, `file_validator.py`, `job_manager.py` (no change)
   - `app/shared/` ← `exceptions.py`
3. ✅ DONE Atualizar todos os imports nos arquivos movidos (imports relativos e absolutos)
4. ✅ DONE Corrigir lazy imports em `main.py` e `domain/processor.py` que usavam `.celery_config`/`.config` (paths stale após reestruturação)
5. ✅ DONE Corrigir `celery_config.py` include: `app.celery_tasks` → `app.infrastructure.celery_tasks`
6. ✅ DONE Atualizar `run.py`: `from app.config` → `from app.core.config`

### Sprint 6 — Padronização data/ ✅ DONE
7. ✅ DONE Criar `data/{uploads,processed,temp,logs}/` com `.gitkeep`
8. ✅ DONE Atualizar `Dockerfile` mkdir: `/app/{uploads,processed,temp,logs}` → `/app/data/{uploads,processed,temp,logs}`
9. ✅ DONE Atualizar `docker-compose.yml` (root + individual):
   - Volumes: `./uploads:/app/uploads` → `./data/uploads:/app/data/uploads`
   - Env: `UPLOAD_DIR=/app/uploads` → `UPLOAD_DIR=/app/data/uploads`
   - Env: `OUTPUT_DIR=/app/processed` → `OUTPUT_DIR=/app/data/processed`
   - Env: `TEMP_DIR=/app/temp` → `TEMP_DIR=/app/data/temp`
10. ✅ DONE Atualizar `app/core/config.py` defaults: `./uploads` → `./data/uploads`, etc.
11. ✅ DONE Atualizar Celery command: `-A app.celery_config` → `-A app.infrastructure.celery_config`
12. ✅ DONE Adicionar `data/**/*` / `!data/**/.gitkeep` ao `.gitignore`
13. ✅ DONE Adicionar `data/` ao `.dockerignore`
14. ✅ DONE Build + deploy: containers `audio-normalization` e `audio-normalization-celery` saudáveis ✅

**Status final:** `curl http://localhost:8003/health` → `{"status": "healthy"}` ✅
