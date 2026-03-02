# UPGRADE ANALYSIS — make-video
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Versão atual do serviço: 1.0.0

---

## 1. RESUMO EXECUTIVO

O `make-video` é o serviço **mais complexo e mais rico em padrões avançados**: possui `ErrorCode` hierárquico estilo enterprise, `DistributedRateLimiter`, `CircuitBreaker`, `CheckpointManager`, `HealthChecker` dedicado, `EventPublisher`, métricas Prometheus, telemetria, e estrutura modular completa. No entanto, carrega **décadas de débito técnico visível**: classe `SimpleRateLimiter` marcada como `# LEGACY... NÃO USAR em produção` ainda presente no `main.py`, pasta `.trash/` com 30+ artefatos, CORS configurado com `allow_origins=["*"]`, `Dockerfile` copia o diretório inteiro (incluindo `.trash/`, `sprints/`, dados de teste), ausência de `constraints.txt`, e processo de startup/shutdown ainda usando `@app.on_event` deprecated.

**Saúde geral: 7.5/10** — Arquitetura excelente, execução e limpeza precisam de atenção urgente.

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03

| Item | Status |
|------|---------|
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| CORS `allow_credentials=True` removed | ✅ DONE |
| `PYTHONPATH=/app` + `PYTHONUNBUFFERED` + `PYTHONDONTWRITEBYTECODE` added to Dockerfile | ✅ DONE |
| `sprints/` moved to `docs/services/make-video/sprints/` | ✅ DONE |
| `pytest-cov` duplicate removed from `requirements.txt` | ✅ DONE |
| `.dockerignore` updated to exclude `.trash/` and `sprints/` | ✅ DONE |
| Runtime data files (17 logs, 15 mp4, 15 ogg, 1 .db) moved to `.trash/` | ✅ DONE |
| `.gitignore` fixed: `trash/` → `.trash/`; `data/` runtime patterns added | ✅ DONE |
| `.dockerignore` extended with `data/` runtime exclusions (mp4, ogg, db, logs) | ✅ DONE |
| `.gitkeep` files placed in all empty `data/` subdirectories | ✅ DONE |
| `tests/requirements-test.txt` created | ✅ DONE |
| Celery `task_failure` signal handler added | ✅ DONE |
| `run.py` limits added (`limit_max_requests=1_000`, `limit_concurrency=10`, `reload` env var) | ✅ DONE |
| `${DIVISOR}` PORT variable hack removed; `run.py` cleaned up | ✅ DONE |
| `.env` PORT `800${DIVISOR}` → `8005` hardcoded (Docker env_file não expande vars) | ✅ DONE |
| `data/logs/app/make_video_general.log` + `make_video_errors.log` → `.trash/` | ✅ DONE |
| Dependency versions normalized (fastapi 0.120.0, uvicorn 0.38.0, pydantic 2.12.3, pydantic-settings 2.11.0) | ✅ DONE |
| `constraints.txt` version ranges updated; `requirements-docker.txt` in sync | ✅ DONE |
| Dockerfile `COPY . .` → seletivo (`app/`, `run.py`); exclui `.trash/`, `data/`, `logs/` | ✅ DONE |
| Dockerfile `apt-get` sem `--no-install-recommends` → adicionado | ✅ DONE |
| Dockerfile non-root user (`appuser 1000`) adicionado | ✅ DONE |
| Dockerfile HEALTHCHECK adicionado (porta 8005, start-period=90s) | ✅ DONE |

---

## 2. MAPA DE GAPS POR CATEGORIA

### 2.1 Código Legado no main.py (2312 linhas!)

`main.py` com **2312 linhas** é o maior "God file" da stack, e ainda contém:

```python
# ATUAL — LEGACY code explicitamente marcado como "NÃO USAR" ainda presente
class SimpleRateLimiter:
    """
    LEGACY: SimpleRateLimiter (in-memory, não distribuído)
    Mantido como referência, mas NÃO USAR em produção multi-instance
    """
```

**Ação:** Deletar `SimpleRateLimiter` completamente. O `DistributedRateLimiter` em `infrastructure/` já existe e deve ser o único usado.

**Estrutura alvo para main.py:**
```python
# main.py deve ter < 100 linhas — apenas bootstrap
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.routes import jobs, health, status
from .core.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()

app = FastAPI(title="Make-Video Service", lifespan=lifespan)
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(health.router)
app.include_router(status.router)
```

---

### 2.2 CORS Inseguro ✅ DONE

```python
# ANTERIOR — violava spec CORS (allow_credentials=True + origins=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,    # ❌ REMOVIDO
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Bug adicional:** `allow_origins=["*"]` combinado com `allow_credentials=True` **viola a especificação CORS** e alguns browsers rejeitam a resposta. O próprio FastAPI lança warning sobre isso.

```python
# ALVO — configurável via settings
from app.core.config import get_settings

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,        # Lista específica ou ["*"] sem credentials
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)
```

---

### 2.3 Dockerfile — `COPY . .` problemático ✅ DONE

```dockerfile
# ANTERIOR — copiava TUDO, incluindo .trash/, sprints/, data/, tests/, logs/
COPY . .
```

**Problemas:**
1. Imagem inclui `.trash/` com 30+ arquivos desnecessários (+20MB)
2. Inclui dados de desenvolvimento (`data/`, `tests/`, arquivos de teste)
3. Sem `constraints.txt` para reproducibilidade
4. Healthcheck comentado ("sem hardcoding") mas variável `PORT` não é definida em build time

```dockerfile
# ALVO — copiar apenas o necessário
COPY common/ ./common/
COPY requirements-docker.txt requirements.txt
COPY constraints.txt .    # ← CRIAR constraints.txt

RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY app/ ./app/
COPY run.py .

# Non-root user
RUN useradd -m -u 1000 appuser \
 && mkdir -p /app/data/raw /app/data/transform /app/data/approved /app/logs \
 && chown -R appuser:appuser /app

USER appuser

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8005}/health || exit 1
```

---

### 2.4 `.dockerignore` — Verificar/Criar ✅ DONE

Confirmar que `.dockerignore` existe e exclui:
```dockerignore
.trash/
sprints/
.git/
**/__pycache__/
**/*.pyc
data/
logs/
tests/
*.md
.env
.env.*
```

---

### 2.5 run.py — Workaround de Variável de Ambiente

```python
# ATUAL — workaround manual para ${DIVISOR} em PORT
port = os.getenv("PORT", "8005")
divisor = os.getenv("DIVISOR", "5")
if "${DIVISOR}" in port:
    port = port.replace("${DIVISOR}", divisor)
```

**Isso é um sinal de que o `.env` não está sendo processado antes do Python.** Docker Compose substitui variáveis no arquivo `.env` antes de passar para o container. Este workaround indica que o `.env` está sendo lido diretamente pelo Python em vez do Docker Compose. 

**Ação:** O `make-video` já usa `pydantic_settings` com `load_dotenv()`. Isso deve funcionar automaticamente. Verificar se o `run.py` pode ser simplificado:

```python
if __name__ == "__main__":
    from app.core.config import get_settings
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=s.port,
        reload=s.debug,
        log_level=s.log_level.lower(),
        workers=1,
        limit_max_requests=5_000,
    )
```

---

### 2.6 @app.on_event Deprecated ✅ DONE

```python
# ATUAL — deprecated
@app.on_event("startup")
async def startup_event():
    ...

@app.on_event("shutdown")
async def shutdown_event():
    ...
```

```python
# ALVO
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await _startup()
    yield
    # shutdown
    await _shutdown()

app = FastAPI(title="Make-Video Service", lifespan=lifespan)
```

---

### 2.7 sprints/ — Documentação dentro do código-fonte ✅ DONE

A pasta `sprints/` foi movida para `docs/services/make-video/sprints/`.

---

### 2.8 Testes

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura | ✅ unit/, integration/, e2e/ | Manter | — |
| `conftest.py` | ✅ Presente | Manter | — |
| `test_setup_validation.py` | ⚠️ Validação de setup — pode ser CI job | Manter + adicionar ao CI | Baixa |
| RELATORIO_EXECUCAO.md em tests/ | ❌ Relatório de execução não pertence ao repo | **Deletar** | Média |
| requirements-test.txt | ❌ **Ausente** | Criar | Alta |

---

### 2.9 Dependências (`requirements.txt`)

| Pacote | Versão Atual | Alinhamento Stack | Ação |
|--------|-------------|-------------------|------|
| `fastapi` | 0.104.1 | ❌ Defasado | Atualizar para `0.115.x` |
| `pydantic` | 2.5.2 | ❌ Defasado | Atualizar para `2.11.x` |
| `uvicorn` | 0.24.0 | ❌ Defasado | Atualizar para `0.34.x` |
| `pydantic-settings` | 2.1.0 | ⚠️ Defasado vs normalization | Atualizar para `2.7.x` |
| `tenacity` | 9.0.0 | ✅ Correto | Manter |
| `prometheus-client` | 0.19.0 | ⚠️ Desatualizado | Atualizar para `0.21.x` |
| `pytest-cov` | ✅ DONE — duplicata removida | Manter | — |

**Bug no requirements.txt:**
```
# ATUAL — pytest-cov listado duas vezes!
pytest-cov==4.1.0
...
pytest-cov==4.1.0   # ← DUPLICADO

# AÇÃO: remover uma das ocorrências
```

---

### 2.10 Resiliência e Observabilidade

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Circuit Breaker | ✅ `infrastructure/circuit_breaker.py` | Manter | — |
| Rate Limiting | ✅ `DistributedRateLimiter` | Remover `SimpleRateLimiter` legado | Alta |
| Prometheus | ✅ `infrastructure/metrics.py` | Manter + padronizar endpoint `/metrics` | — |
| Health Checker | ✅ `infrastructure/health_checker.py` | Manter — melhor da stack | — |
| Checkpoints | ✅ `infrastructure/checkpoint_manager.py` | Manter | — |
| Telemetria | ✅ `infrastructure/telemetry.py` | Manter | — |
| Structured logging | ✅ `infrastructure/logging_config.py` | Alinhar com `common.log_utils` | Média |

---

## 3. ARQUIVOS A DELETAR (LIMPEZA)

### `.trash/` — 30+ arquivos — **DELETAR TUDO**
```bash
rm -rf services/make-video/.trash/
```

### Arquivos `.bak` inteiros em `app/video_processing/` — **DELETAR**
Encontrados durante validação (não documentados inicialmente):
```bash
rm services/make-video/app/video_processing/frame_preprocessor_OLD_SPRINTS.py.bak
rm services/make-video/app/video_processing/subtitle_detector_v2_OLD_SPRINTS.py.bak
```

### `tests/RELATORIO_EXECUCAO.md` — relatório de execução ad-hoc
```bash
rm services/make-video/tests/RELATORIO_EXECUCAO.md
```

### Remover `sprints/` da pasta do serviço (mover para docs):
```bash
mv services/make-video/sprints/ docs/services/make-video/sprints/
```

---

## 4. PLANO DE EXECUÇÃO (ORDENADO POR IMPACTO)

### Sprint 1 — Limpeza Imediata (30min-1h)
1. `rm -rf services/make-video/.trash/`
2. Remover `SimpleRateLimiter` de `main.py`
3. ✅ DONE Corrigir bug CORS: remover `allow_credentials=True` quando `allow_origins=["*"]`
4. ✅ DONE Remover duplicata `pytest-cov` em `requirements.txt`
5. Deletar `tests/RELATORIO_EXECUCAO.md`

### Sprint 2 — Dockerfile e Container (1-2h)
6. ✅ DONE Criar `.dockerignore` abrangente
7. ✅ DONE Mudar `COPY . .` para cópia seletiva
8. ✅ DONE Criar `constraints.txt`
9. ✅ DONE Adicionar `PYTHONPATH=/app`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1` ao Dockerfile

### Sprint 3 — Modernização (2-4h)
10. ✅ DONE Migrar `@app.on_event` para `lifespan`
11. Simplificar `run.py`
12. Atualizar dependências para versões alinhadas com a stack

### Sprint 4 — Organização (1-2h)
13. ✅ DONE Mover `sprints/` para `docs/services/make-video/sprints/`
14. Criar `tests/requirements-test.txt`

---

## 5. PONTOS POSITIVOS (manter e replicar para outros serviços)

- `infrastructure/health_checker.py` — **melhor health checker da stack**, replicar nos outros
- `infrastructure/circuit_breaker.py` — implementação própria sólida
- `infrastructure/distributed_rate_limiter.py` — rate limiting com Redis
- `infrastructure/checkpoint_manager.py` — recuperação de falha em pipeline longo
- `app/shared/exceptions.py` — hierarquia de exceções com `ErrorCode` enum
- `pydantic_settings.BaseSettings` em `core/config.py` — padrão para todos

---

## 6. REFERÊNCIAS

- [CORS + Credentials Bug](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS/Errors/CORSNotSupportingCredentials)
- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [FastAPI Lifespan](https://fastapi.tiangolo.com/advanced/events/)
