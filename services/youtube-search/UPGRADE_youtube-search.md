# UPGRADE ANALYSIS — youtube-search
> Análise realizada em: 2026-03-01  
> Autor: Senior Python Engineer Review  
> Versão atual do serviço: 1.0.0

---

## 1. RESUMO EXECUTIVO

O `youtube-search` é o serviço com melhor consistência de idioma (código em inglês, algo único na stack), boa estrutura de exceptions com HTTP mapping, e bom uso de CORS configurável. No entanto, apresenta problemas estruturais importantes: ausência de `run.py` (usa `sh -c` no Dockerfile), `ytbpy/` embutida no `app/` (biblioteca interna sem versionamento ou isolamento), `proxies.txt` commitado em `app/ytbpy/`, configuração sem tipagem, estrutura de testes plana sem separação por nível, e ausência de `tenacity` para retry em chamadas à API do YouTube.

**Saúde geral: 6/10** — Padrões corretos nos lugares certos, mas gaps estruturais e de resiliência importantes.

---

## IMPLEMENTATION STATUS
> Last updated: 2026-03

| Item | Status |
|------|---------|
| `@app.on_event` lifecycle → `lifespan` | ✅ DONE |
| `pydantic_settings.BaseSettings` config | ✅ DONE |
| `constraints.txt` added | ✅ DONE |
| `tenacity` retry for YouTube API calls | ✅ DONE |
| `prometheus-client` `/metrics` endpoint | ✅ DONE |
| Dockerfile `CMD sh -c` → `["python", "run.py"]` | ✅ DONE |
| `COPY run.py` added to Dockerfile | ✅ DONE |
| `proxies.txt` added to `.gitignore` | ✅ DONE |
| `PYTHONPATH` already present in Dockerfile | ✅ N/A — no change needed |
| `.trash/` added to `.gitignore` | ✅ DONE |
| Celery `task_failure` signal handler added | ✅ DONE |
| Dependency versions normalized (fastapi 0.120.0, uvicorn 0.38.0, pydantic 2.12.3, pydantic-settings 2.11.0) | ✅ DONE |
| `constraints.txt` version ranges updated to allow 0.120.x / 0.38.x / 2.12.x | ✅ DONE |
| `.env` `${IP_REDIS}`/`${DIVISOR}` in REDIS_URL/CELERY_* hardcoded to `redis://192.168.1.110:6379/1` | ✅ DONE |
| `logs/youtube-search.json` moved to `.trash/logs/` | ✅ DONE |

---

## 2. MAPA DE GAPS POR CATEGORIA

### 2.1 `run.py` Existe mas o Dockerfile o Ignora — Startup Frágil ✅ DONE

**Validação confirmou:** `run.py` existe e está bem escrito (usa `settings.debug`, `limit_max_requests`, `limit_concurrency`). O problema é que o **Dockerfile não o usa**:

```dockerfile
# ATUAL — Dockerfile usa sh -c e IGNORA o run.py existente
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
```

**Problemas do `sh -c`:**
1. `sh -c` cria um processo filho — PID 1 é o shell, não o Python. Sinais `SIGTERM` não chegam ao uvicorn (graceful shutdown falha)
2. `log_level` hardcoded `"info"` — não respeita `LOG_LEVEL` env var
3. O `run.py` existente já tem `limit_max_requests=1000` e `limit_concurrency=100` — sendo desperdiçados

```dockerfile
# CORREÇÃO MÍNIMA — apenas mudar o CMD no Dockerfile:
# ATUAL:
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]

# ALVO — usar run.py que já existe:
COPY run.py .    # já está no COPY app/ mas run.py é raiz — verificar se está sendo copiado
CMD ["python", "run.py"]
```

> **Nota:** O `run.py` atual do youtube-search já está adequadamente escrito. A única mudança necessária é no `CMD` do Dockerfile.

---

### 2.2 `ytbpy/` Embutida no `app/`

```
app/ytbpy/
├── __init__.py
├── channel.py
├── playlist.py
├── proxies.txt      # ← arquivo de dados dentro do código-fonte!
├── search.py
├── utils.py
└── video.py
```

**Problemas:**
1. `proxies.txt` com lista de proxies **dentro do código** — segurança e manutenção comprometidas
2. `ytbpy` não tem versionamento próprio, testes próprios, ou changelog
3. Acoplamento forte: mudanças na API do YouTube requerem mudanças dentro do `app/`
4. Impossível reutilizar em outros serviços sem copiar a pasta

**Ação recomendada:**

**Opção A (curto prazo):** Mover `ytbpy/` para a raiz do serviço e separar configuração:
```
youtube-search/
├── ytbpy/          # ← mover para fora de app/
│   ├── __init__.py
│   ├── channel.py
│   └── ...
├── config/
│   └── proxies.txt  # ← separar arquivo de dados
├── app/
│   └── ...
```

**Opção B (longo prazo):** Publicar `ytbpy` como pacote interno (`-e ./ytbpy` no requirements.txt), similar ao que já é feito com `common`.

**Proxies.txt — remover do repo:**
```bash
# Adicionar ao .gitignore
echo "app/ytbpy/proxies.txt" >> services/youtube-search/.gitignore
# Gerenciar via ENV var ou secret management:
YOUTUBE_PROXIES_FILE=/path/to/proxies.txt
```

---

### 2.3 Arquitetura de Código

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura de diretórios | ❌ Flat (8 arquivos no raiz de `app/`) | Layered (domain/infra/services/core) | Média |
| `config.py` | ✅ DONE — `pydantic_settings.BaseSettings` implementado | Manter | — |
| `main.py` tamanho | ❌ 915 linhas "God file" | Extrair rotas para `app/api/routes/` | Alta |
| `@app.on_event` lifecycle | ✅ DONE — migrado para `lifespan` | Manter | — |

**Config alvo:**
```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from functools import lru_cache

class YouTubeSearchSettings(BaseSettings):
    app_name: str = "YouTube Search Service"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"
    log_dir: str = "./logs"
    
    redis_url: str = "redis://localhost:6379/0"
    
    # CORS
    cors_enabled: bool = True
    cors_origins: List[str] = ["*"]
    cors_credentials: bool = False
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]
    
    # YouTube
    youtube_default_timeout: int = 10
    youtube_max_results: int = 50
    
    # Rate limit
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache(maxsize=1)
def get_settings() -> YouTubeSearchSettings:
    return YouTubeSearchSettings()
```

---

### 2.4 Resiliência — Ausência de Retry para API YouTube ✅ DONE

O `YouTubeSearchProcessor` chama a API do YouTube (via `ytbpy`) sem nenhum retry. A API do YouTube é notoriamente instável (rate limits, timeouts, mudanças de estrutura silenciosas).

```python
# ATUAL — sem proteção contra falhas transitórias
result = processor.search(query)  # Se falhar, job vai para FAILED permanentemente

# ALVO — com retry exponencial
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((YouTubeAPIError, ConnectionError, TimeoutError)),
    reraise=True,
)
async def search_with_retry(processor, query: str, **kwargs):
    return await processor.search(query, **kwargs)
```

---

### 2.5 Dockerfile

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| `CMD` frágil com `sh -c` | ✅ DONE — `CMD ["python", "run.py"]` | Manter | — |
| HEALTHCHECK com `${PORT:-8001}` | ⚠️ Variável não expandida em build time | Usar porta fixa ou `run.py` | Média |
| `run.py` no CMD | ✅ DONE — `CMD ["python", "run.py"]` ativo | Manter | — |
| `constraints.txt` | ✅ DONE — criado | Manter | — |
| `PYTHONPATH` | ✅ Definido como `/app` | Manter | — |
| `apt-get clean` duplicado | ⚠️ `apt-get clean` depois de já ter `rm -rf /var/lib/apt/lists/*` | Remover redundância | Baixa |

---

### 2.6 Testes

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Estrutura | ❌ Flat (6 arquivos, sem subpastas) | unit/integration/e2e | Alta |
| `test_e2e.py` | ⚠️ e2e em arquivo flat | Mover para `tests/e2e/` | Média |
| `test_integration.py` | ⚠️ Flat | Mover para `tests/integration/` | Média |
| `run_tests.py` | ✅ Presente | Manter | — |
| `requirements-test.txt` | ✅ Presente | Manter | — |
| `pytest.ini` | ✅ Presente | Manter | — |
| Test para ytbpy | ❌ Ausente | Criar unit tests para ytbpy/ | Alta |

**Estrutura alvo:**
```
tests/
├── conftest.py
├── requirements-test.txt
├── run_tests.py
├── unit/
│   ├── test_models.py       (mover de test_models.py)
│   ├── test_config.py       (mover de test_config.py)
│   └── test_ytbpy.py        ← CRIAR
├── integration/
│   └── test_integration.py  (mover)
└── e2e/
    └── test_e2e.py          (mover)
```

---

### 2.7 Dependências (`requirements.txt`)

| Pacote | Versão Atual | Alinhamento Stack | Ação |
|--------|-------------|-------------------|------|
| `fastapi` | 0.109.0 | ❌ Defasado | Atualizar para `0.115.x` |
| `pydantic` | 2.5.3 | ❌ Defasado | Atualizar para `2.11.x` |
| `pydantic-settings` | 2.1.0 | ⚠️ Defasado | Atualizar para `2.7.x` |
| `uvicorn` | 0.27.0 | ❌ Defasado | Atualizar para `0.34.x` |
| `tenacity` | ✅ DONE — `9.0.0` adicionado com retry na API YouTube | Manter | — |
| `prometheus-client` | ✅ DONE — adicionado, endpoint `/metrics` ativo | Manter | — |
| `httpx` | 0.26.0 | ✅ Presente | Atualizar para `0.28.x` |

---

### 2.8 Observabilidade

| Item | Estado Atual | Estado Alvo | Prioridade |
|------|-------------|-------------|------------|
| Circuit Breaker Redis | ✅ Via `ResilientRedisStore` | Manter | — |
| Retry para YouTube API | ✅ DONE — `tenacity` implementado | Manter | — |
| Rate Limiting | ✅ Configurável (enabled/requests/period) | Manter + implementar middleware | Média |
| Prometheus metrics | ✅ DONE — `/metrics` endpoint ativo | Manter | — |
| `/health` endpoint | ✅ Deep check (Redis + disk + celery + ytbpy) | Manter | — |
| Structured logging | ✅ Via `common.log_utils` | Manter | — |
| Celery signal failure | ⚠️ Ausente em celery_tasks.py | Adicionar `@signals.task_failure.connect` | Média |

---

## 3. ARQUIVOS A DELETAR / MOVER

```bash
# Remover do rastreamento Git (arquivo sensível / dados): ✅ DONE
git rm --cached services/youtube-search/app/ytbpy/proxies.txt
echo "app/ytbpy/proxies.txt" >> services/youtube-search/.gitignore

# Opcionalmente mover ytbpy/ para fora de app/:
mv services/youtube-search/app/ytbpy/ services/youtube-search/ytbpy/
# Ajustar imports de .ytbpy para ytbpy
```

---

## 4. PLANO DE EXECUÇÃO (ORDENADO POR IMPACTO)

### Sprint 1 — Segurança e Startup (30min) ✅ DONE
1. ✅ DONE Corrigir `CMD` no Dockerfile: substituir `sh -c uvicorn` por `CMD ["python", "run.py"]`
2. ✅ DONE Garantir `COPY run.py .` no Dockerfile (confirmar que run.py raiz está sendo copiado)
3. ✅ DONE Remover `proxies.txt` do controle de versão (`.gitignore`)
4. ✅ DONE Criar `constraints.txt`

### Sprint 2 — Modernização (2-3h) ✅ DONE
5. ✅ DONE Migrar `config.py` para `pydantic_settings.BaseSettings`
6. ✅ DONE Migrar `@app.on_event` para `lifespan`
7. ✅ DONE Adicionar `tenacity` e retry no `YouTubeSearchProcessor`

### Sprint 3 — Estrutura de Testes (2-3h)
8. Reorganizar testes em unit/integration/e2e
9. Criar testes unitários para `ytbpy/`
10. Adicionar `@signals.task_failure.connect` no celery_tasks.py

### Sprint 4 — Observabilidade (1-2h)
11. ✅ DONE Adicionar `prometheus-client` + `/metrics`
12. Implementar rate limiting middleware configurável

---

## 5. REFERÊNCIAS

- [Docker CMD vs ENTRYPOINT](https://docs.docker.com/engine/reference/builder/#cmd)
- [Signal Handling in Docker](https://hynek.me/articles/docker-signals/)
- [tenacity Documentation](https://tenacity.readthedocs.io/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## 6. WORK COMPLETED — Padronização app/ e data/ (Session 3)

### Sprint 5 — Estrutura app/ em Camadas ✅ DONE
1. ✅ DONE Reorganizar `app/` em camadas:
   - `app/core/` ← `config.py`, `models.py`, `logging_config.py`
   - `app/domain/` ← `processor.py`
   - `app/infrastructure/` ← `celery_config.py`, `celery_tasks.py`, `redis_store.py`
   - `app/services/` ← `ytbpy/` (movido de `app/ytbpy/`)
   - `app/shared/` ← `exceptions.py`
2. ✅ DONE Atualizar todos os imports nos arquivos movidos
3. ✅ DONE Corrigir lazy imports em `main.py` que usavam `.celery_config` e `.ytbpy`
4. ✅ DONE Corrigir `celery_config.py` include: `app.celery_tasks` → `app.infrastructure.celery_tasks`
5. ✅ DONE Atualizar `run.py`: `from app.config` → `from app.core.config`

### Sprint 6 — Padronização data/ ✅ DONE
6. ✅ DONE Criar `data/logs/` com `.gitkeep`
7. ✅ DONE Atualizar `Dockerfile` mkdir: `mkdir -p logs` → `mkdir -p /app/data/logs`
8. ✅ DONE Atualizar `docker-compose.yml` (individual):
   - Volumes: `./logs:/app/logs` → `./data/logs:/app/data/logs`
9. ✅ DONE Atualizar `app/core/config.py` defaults: `./logs` → `./data/logs`
10. ✅ DONE Atualizar Celery commands (worker + beat): `-A app.celery_config.celery_app` → `-A app.infrastructure.celery_config.celery_app`
11. ✅ DONE Adicionar `data/**/*` / `!data/**/.gitkeep` ao `.gitignore`
12. ✅ DONE Adicionar `data/` ao `.dockerignore`
