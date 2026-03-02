# UPGRADE ANALYSIS — audio-transcriber
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Versão atual do serviço: 2.0.0

---

## 1. RESUMO EXECUTIVO

O `audio-transcriber` é o serviço **mais maduro da stack** em termos de arquitetura. Já adotou a separação em camadas (domain / infrastructure / services / core / shared / workers) e usa a biblioteca `common` corretamente. Entretanto, ainda carrega **débito técnico acumulado** em: Dockerfile incompleto, lifecycle deprecated, config sem tipagem, pasta `.trash/` com 18 artefatos obsoletos, e ausência de rate limiting / métricas Prometheus.

**Saúde geral: 7/10** — Base sólida, ajustes pontuais de alta prioridade.

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03

| Item | Status |
|------|---------|
| Dockerfile HEALTHCHECK `start-period 40s` → `120s`, `timeout 10s` → `15s` | ✅ DONE |
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `PYTHONPATH=/app` added to Dockerfile | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| `.gitignore` created | ✅ DONE |
| `pydantic-settings` added to `requirements.txt` | ✅ DONE |
| `logs/` committed files (7 files) moved to `.trash/logs/`; `.gitkeep` added | ✅ DONE |
| `uploads/*.ogg` runtime files moved to `.trash/uploads/` | ✅ DONE |
| `uploads/` added to `.gitignore`; `.gitkeep` placed | ✅ DONE |
| `run.py` uvicorn limits added (`limit_max_requests=10_000`, `limit_concurrency=20`) | ✅ DONE |
| Dependency versions normalized to stack standard (fastapi 0.120.0, uvicorn 0.38.0, pydantic 2.12.3, pydantic-settings 2.11.0) | ✅ DONE |
| `.env` PORT `800${DIVISOR}` → `8004` hardcoded (Docker env_file não expande vars) | ✅ DONE |
| `.env` REDIS_URL/CELERY_* `${DIVISOR}` hardcoded to literal `/4` | ✅ DONE |
| `root docker-compose.yml` port `${PORT}:${PORT}` → `8004:8004` fixed | ✅ DONE |
| Dockerfile `EXPOSE 8003` → `8004` + HEALTHCHECK port corrected | ✅ DONE |
| `run.py` default PORT `"8003"` → `"8004"` aligned with canonical .env value | ✅ DONE |

---

## 2. MAPA DE GAPS POR CATEGORIA

### 2.1 Arquitetura de Código

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura de diretórios | ✅ Layered (domain/infra/services/core) | Manter | — |
| `config.py` | ✅ DONE — `pydantic_settings.BaseSettings` implementado | Manter | — |
| `main.py` | ⚠️ 1642 linhas — "God file" | Extrair rotas para `app/api/routes/` | Alta |
| `@app.on_event` lifecycle | ✅ DONE — migrado para `lifespan` | Manter | — |
| Importação fallback `now_brazil` | ⚠️ Bloco `try/except` duplicado em 5+ arquivos | Centralizar em `common` (já existe) | Média |

**Detalhe — Config sem tipagem (`app/core/config.py`):**
```python
# ATUAL — sem validação, sem autocomplete, sem docs
def get_settings() -> Dict[str, Any]:
    return { 'host': os.getenv('HOST', '0.0.0.0'), ... }

# ALVO — validação automática, env docs, singleton cacheado
from pydantic_settings import BaseSettings

class TranscriberSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8003
    redis_url: str = "redis://localhost:6379/0"
    whisper_model: str = "base"
    ...
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache(maxsize=1)
def get_settings() -> TranscriberSettings:
    return TranscriberSettings()
```

**Detalhe — Lifecycle deprecated (`app/main.py`):**
```python
# ATUAL — deprecated e será removido em versão futura
@app.on_event("startup")
async def startup_event():
    ...

@app.on_event("shutdown")
async def shutdown_event():
    ...

# ALVO — modern lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await job_store.start_cleanup_task()
    logger.info("Audio Transcription Service started")
    yield
    # shutdown
    if job_store._cleanup_task:
        job_store._cleanup_task.cancel()
    logger.info("Audio Transcription Service shutdown")

app = FastAPI(title="...", lifespan=lifespan)
```

---

### 2.2 Dockerfile

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| HEALTHCHECK | ✅ DONE — `start-period=120s`, `timeout=15s` | Manter | — |
| EXPOSE 8003 | ✅ Presente | Manter | — |
| Usuário não-root | ✅ `USER appuser` presente (linha 87) | Manter | — |
| ARG BUILD_ENV | ⚠️ Aceita valores arbitrários | Validar valores possíveis | Baixa |
| `start-period` insuficiente | ✅ DONE — aumentado para `120s` | Manter | — |

```dockerfile
# CORRIGIR — start-period insuficiente para warmup do modelo Whisper na GPU
# ATUAL:
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8003/health || exit 1

# ALVO:
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:8003/health || exit 1
```

> **Nota:** `start-period=120s` porque o modelo Whisper large-v3 pode demorar 60-120s para carregar na GPU antes do serviço responder no `/health`.

---

### 2.3 run.py

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| workers vem de env | ✅ Sim | Manter | — |
| reload respeita env | ✅ Sim | Manter | — |
| Port hardcoded fallback | ⚠️ `PORT=8003` (`8003` ≠ valor do `.env`) | Usar `settings.port` | Média |
| Limites uvicorn ausentes | ⚠️ Sem `limit_max_requests` | Adicionar | Baixa |

```python
# ALVO
from app.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        reload=s.debug,
        workers=1 if s.debug else s.workers,
        log_level=s.log_level.lower(),
        limit_max_requests=10_000,
        limit_concurrency=50,
    )
```

---

### 2.4 Testes

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura | ✅ unit/integration/e2e/resilience/performance/security | Manter | — |
| `conftest.py.bak` | ❌ Arquivo `.bak` no repositório | **Deletar** | Alta |
| `TEST-.ogg` | ⚠️ Sem extensão definida no gitignore | Mover para `tests/assets/` (já existe) | Média |
| requirements-test.txt | ✅ Presente | Manter | — |
| pytest.ini em tests/ | ⚠️ pytest.ini duplicado (raiz e tests/) | Manter apenas na raiz | Média |

---

### 2.5 Dependências (`requirements.txt`)

| Pacote | Versão Atual | Versão Alvo (stack-wide) | Prioridade |
|--------|-------------|--------------------------|------------|
| `fastapi` | 0.104.1 | **0.115.x** | Alta |
| `uvicorn[standard]` | 0.24.0 | **0.34.x** | Alta |
| `pydantic` | 2.5.0 | **2.11.x** | Alta |
| `pydantic-settings` | ✅ DONE — adicionado ao requirements.txt | Manter | — |
| `tenacity` | 8.2.3 | **9.0.0** | Média |
| `prometheus-client` | ✅ DONE — adicionado, endpoint `/metrics` ativo | Manter | — |

---

### 2.6 Resiliência e Observabilidade

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Circuit Breaker Redis | ✅ Via `ResilientRedisStore` | Manter | — |
| Retry com tenacity | ✅ Presente | Manter | — |
| Rate Limiting | ❌ Ausente | Adicionar middleware | Média |
| Prometheus metrics | ✅ DONE — `/metrics` endpoint ativo | Manter | — |
| Structured logging | ✅ Via `common.log_utils` | Manter | — |
| `/health` endpoint | ✅ Deep check (Redis + disk + ffmpeg) | Adicionar check do modelo Whisper | Média |

**Health check — adicionar verificação do modelo:**
```python
# Adicionar em /health
try:
    model_loaded = processor.is_model_loaded()
    health_status["checks"]["whisper_model"] = {
        "status": "ok" if model_loaded else "warning",
        "model": settings['whisper_model'],
        "device": settings['whisper_device'],
        "loaded": model_loaded
    }
except Exception as e:
    health_status["checks"]["whisper_model"] = {"status": "error", "message": str(e)}
```

---

### 2.7 Segurança

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Usuário não-root no container | ✅ `USER appuser` presente (linha 87) | Manter | — |
| CORS | ⚠️ Ausente (serviço interno) | Manter ausente ou restrito | Baixa |
| Validação de tipo de arquivo | ⚠️ Verificar extensão e MIME type | Enforçar lista allowlist | Alta |
| Tamanho máximo do body | ✅ Configurável via `MAX_FILE_SIZE_MB` | Manter | — |

---

## 3. ARQUIVOS A DELETAR (LIMPEZA)

### `.trash/` — 18 arquivos obsoletos — **DELETAR TUDO**
```
services/audio-transcriber/.trash/
├── CHECKLIST.md                   # documentação obsoleta
├── COMMIT_SUMMARY.txt             # histórico de commits (pertence ao git)
├── CORRECOES_RESILIENCIA.md       # sprint doc obsoleto
├── DIAGNOSTICO_RESILIENCIA.md     # sprint doc obsoleto
├── IMPLEMENTACAO_COMPLETA.md      # sprint doc obsoleto
├── IMPLEMENTACAO_COMPLETA_FINAL.md 
├── INDICE_DOCUMENTACAO.md
├── README_DOCUMENTATION.md
├── REORGANIZATION_STATUS.md
├── SUMARIO_EXECUTIVO.md
├── VALIDACAO_RAPIDA.sh            # script de validação ad-hoc
├── build.log                      # log de build (não deve estar no repo)
├── test_e2e_complete.sh
├── test_final_validation.sh
├── test_gpu.py                    # teste ad-hoc
├── test_transcription.sh
├── test_word_timestamps.sh
├── validate-deployment.sh
└── validate-gpu.sh
```
**Comando:** `rm -rf services/audio-transcriber/.trash/`

### Outros arquivos a deletar:
```
services/audio-transcriber/tests/conftest.py.bak   # backup desnecessário no repo
```

---

## 4. PLANO DE EXECUÇÃO (ORDENADO POR RISCO)

### Sprint 1 — Segurança e Corretude (1-2h)
1. ✅ DONE Aumentar `HEALTHCHECK start-period` de `40s` para `120s` no Dockerfile
2. Deletar `.trash/` e `tests/conftest.py.bak`
3. Corrigir `run.py` para usar `settings.port` e `settings.debug`

### Sprint 2 — Modernização (2-4h)
4. ✅ DONE Migrar `config.py` para `pydantic_settings.BaseSettings`
5. ✅ DONE Migrar `@app.on_event` para `lifespan`
6. ✅ DONE Atualizar dependências para versões alinhadas com a stack

### Sprint 3 — Observabilidade (2-3h)
7. ✅ DONE Adicionar `prometheus-client` e endpoint `/metrics`
8. Adicionar check do modelo Whisper no `/health`
9. Adicionar rate limiting middleware

### Sprint 4 — Refatoração estrutural (4-8h)
10. Extrair rotas de `main.py` (1642 linhas!) para `app/api/routes/`
11. Unificar pytest.ini na raiz do serviço

---

## 5. REFERÊNCIAS

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Docker Best Practices for Python](https://docs.docker.com/language/python/develop/)
- [Twelve-Factor App](https://12factor.net/)

---

## 6. WORK COMPLETED — Padronização data/ (Session 3)

### Sprint 4 — Padronização data/ ✅ DONE
1. ✅ DONE Criar `data/{uploads,transcriptions,models,temp,logs}/` com `.gitkeep`
2. ✅ DONE Atualizar `Dockerfile` mkdir: `/app/{uploads,transcriptions,models,temp,logs,processed}` → `/app/data/{uploads,transcriptions,models,temp,logs}`
3. ✅ DONE Atualizar `docker-compose.yml` (root + individual):
   - Volumes: `./uploads:/app/uploads` → `./data/uploads:/app/data/uploads`
   - Volumes: `./transcriptions:/app/transcriptions` → `./data/transcriptions:/app/data/transcriptions`
   - Volumes: `./models:/app/models` → `./data/models:/app/data/models`
   - Volumes: `./temp:/app/temp` → `./data/temp:/app/data/temp`
   - Volumes: `./logs:/app/logs` → `./data/logs:/app/data/logs`
4. ✅ DONE Atualizar `app/core/config.py` defaults:
   - `./uploads` → `./data/uploads`
   - `./transcriptions` → `./data/transcriptions`
   - `./models` → `./data/models`
   - `./temp` → `./data/temp`
   - `./logs` → `./data/logs`
   - `./models` (whisper_download_root) → `./data/models`
5. ✅ DONE Adicionar `data/**/*` / `!data/**/.gitkeep` ao `.gitignore`
6. ✅ DONE Adicionar `data/` ao `.dockerignore`

**Nota:** `app/celery_config.py` mantido como módulo proxy (backward compatibility) — `-A app.celery_config` continua válido.
