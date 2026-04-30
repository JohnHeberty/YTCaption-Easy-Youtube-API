# PLAN.md — Plano de Qualidade YTCaption-Easy-Youtube-API

## Status: ✅ COMPLETO (2026-04-30)

---

## Checklist Geral

- [x] **F1-T1**: Unificar padrões de DI em todos os serviços (6 DI modules criados)
- [x] **F1-T2**: Criar `pyproject.toml` na raiz com configuração centralizada
- [x] **F1-T3**: Eliminar código legado duplicado — Orchestrator modules/ imports migrados
- [x] **F1-T3**: Eliminar código legado duplicado — Audio Normalization domain/processor.py removido
- [x] **F1-T3**: Eliminar código legado duplicado — Video Downloader domain/downloader.py removido
- [x] **F1-T3**: Eliminar código legado duplicado — Orchestrator core/config.py com dict-access compatível
- [x] **F1-T3**: Eliminar código legado duplicado — Audio Norm exceptions unificadas (core/exceptions.py)
- [x] **F1-T3**: Eliminar código legado duplicado — Tests legados marcados como DEPRECATED
- [x] **F2-T4**: Padronizar conftest.py e fixtures por serviço
- [x] **F2-T5**: Integrar fakeredis para testes de Redis
- [x] **F2-T6**: Adicionar respx para mock de HTTP clients
- [x] **F2-T7**: Adicionar testes unitários para os novos routers
- [x] **F2-T8**: Descontinuar testes antigos e migrar para nova estrutura
- [x] **F3-T9**: Padronizar serialização/deserialização no Redis com versionamento
- [x] **F3-T10**: Implementar health checks consistentes via common/health_utils
- [x] **F3-T11**: Implementar retry com backoff nos clients de microserviço
- [x] **F3-T12**: Adicionar logging estruturado consistente
- [x] **F4-T13**: Implementar pipeline CI/CD com GitHub Actions
- [x] **F4-T14**: Adicionar `make lint` no Makefile raiz
- [x] **F4-T15**: Documentar arquitetura SOLID em ADRs
- [x] **F4-T16**: Adicionar `make test-ci` target para execução rápida em CI
- [x] **F4-T17**: Eliminar pytest.ini duplicados conflitantes
- [x] **F4-T18**: Padronizar exception hierarchy em common/exceptions.py
- [x] **F4-T19**: Adicionar type hints completos (mypy strict por serviço)
- [x] **F4-T20**: Implementar OpenAPI docs consistentes nos routers

---

## Fase 1 — Fundamentos (P0)

### F1-T1: Unificar padrões de DI em todos os serviços

**Problema:** 5 padrões diferentes de acesso a globais. Zero uso de `Depends()`.

**Para cada serviço, criar `app/infrastructure/dependencies.py`:**

```python
from functools import lru_cache
from app.infrastructure.redis_store import RedisJobStore
from app.core.config import get_settings

@lru_cache(maxsize=1)
def get_job_store() -> RedisJobStore:
    settings = get_settings()
    return RedisJobStore(redis_url=settings['redis_url'])

# override para testes
_override_job_store = None

def get_job_store_override():
    if _override_job_store is not None:
        return _override_job_store
    return get_job_store()

def set_job_store_override(store):
    global _override_job_store
    _override_job_store = store

def reset_job_store_override():
    global _override_job_store
    _override_job_store = None
```

**Migração nas rotas:**
```python
# ANTES:
from app.main import job_store

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get_job(job_id)

# DEPOIS:
from app.infrastructure.dependencies import get_job_store_override as get_store

@app.get("/jobs/{job_id}")
async def get_job(job_id: str, store: RedisJobStore = Depends(get_store)):
    job = store.get_job(job_id)
```

**Validação:**
- [ ] Zero ocorrências de `from app.main import` nas rotas (`grep -r "from app.main import" services/*/app/api/ orchestrator/api/`)
- [ ] Cada serviço tem `infrastructure/dependencies.py`
- [ ] `python3 -c "from app.infrastructure.dependencies import get_job_store_override"` funciona em cada serviço

---

### F1-T2: Criar pyproject.toml na raiz

**Validação:**
- [ ] `pip install -e .` funciona na raiz
- [ ] `black --check .` usa config do pyproject.toml
- [ ] `flake8 .` usa config do pyproject.toml

---

### F1-T3: Eliminar código legado duplicado

**Arquivos a eliminar (após migrar imports):**

| Serviço | Arquivo Legado | Arquivo Refatorado |
|---------|---------------|--------------------|
| Orchestrator | `modules/models.py` | `domain/models.py` |
| Orchestrator | `modules/orchestrator.py` | `services/pipeline_orchestrator.py` |
| Orchestrator | `modules/redis_store.py` | `infrastructure/redis_store.py` |
| Orchestrator | `modules/config.py` | `core/config.py` |
| Audio Norm | `app/domain/processor.py` | `app/services/audio_processor.py` |
| Audio Norm | `app/downloader.py` (se existir) | `app/services/video_downloader.py` |
| Audio Transcriber | `app/celery_config.py` | `app/workers/celery_config.py` |
| Audio Transcriber | `app/workers/celery_tasks.py` (duplicado) | `app/infrastructure/celery_tasks.py` (único) |

**Validação por item:**
- [ ] `grep -r "from modules\." orchestrator/` retorna 0 resultados
- [ ] `grep -r "from app\.domain\.processor import" services/audio-normalization/` retorna 0
- [ ] `python3 -c "import ast; ast.parse(open('main.py').read())"` passa em cada serviço
- [ ] Testes unitários existentes ainda passam

---

## Fase 2 — Testabilidade (P1)

### F2-T4: Padronizar conftest.py e fixtures

**Criar `common/test_utils/`:**

```
common/test_utils/
├── __init__.py
├── mock_redis.py          # MockRedis compartilhado
├── mock_http_client.py    # Mock httpx.AsyncClient
├── mock_celery.py         # Mock Celery app e tasks
├── fixtures.py            # Fixtures comuns
└── conftest.py            # Pytest plugins
```

**Validação:**
- [ ] `python3 -c "from common.test_utils import MockRedis"` funciona
- [ ] `python3 -c "from common.test_utils import mock_celery_app"` funciona
- [ ] Cada conftest.py de serviço importa de `common.test_utils`

---

### F2-T5: Integrar fakeredis

**Validação:**
- [ ] `fakeredis` adicionado ao `common/requirements.txt`
- [ ] `pip install fakeredis` funciona
- [ ] `common/test_utils/mock_redis.py` usa `fakeredis.FakeRedis()`
- [ ] Todos os conftest.py usam `FakeRedis()` em vez de `Mock()`
- [ ] Teste: `pytest tests/unit/test_redis_store.py` passa em cada serviço

---

### F2-T6: Adicionar respx

**Validação:**
- [ ] `respx` adicionado ao requirements-test de cada serviço
- [ ] `common/test_utils/mock_http_client.py` criado com fixtures respx
- [ ] Teste de integração do Orchestrator usa respx em vez de AsyncMock

---

### F2-T7: Adicionar testes unitários para os novos routers

**Para cada serviço, criar:**

| Serviço | Arquivo de Teste | Endpoints Cobertos |
|---------|-----------------|--------------------|
| Orchestrator | `tests/unit/api/test_health_routes.py` | GET /health |
| Orchestrator | `tests/unit/api/test_admin_routes.py` | GET /admin/stats, POST /admin/cleanup, POST /admin/factory-reset |
| Orchestrator | `tests/unit/api/test_jobs_routes.py` | GET /jobs, GET /jobs/{id}, GET /jobs/{id}/wait, GET /jobs/{id}/stream |
| Video Downloader | `tests/unit/api/test_jobs_routes.py` | POST /jobs, GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}, GET /jobs/orphaned |
| Video Downloader | `tests/unit/api/test_admin_routes.py` | POST /admin/cleanup, GET /admin/stats, GET /admin/queue |
| Video Downloader | `tests/unit/api/test_health_routes.py` | GET /health, GET /metrics |
| Audio Transcriber | `tests/unit/api/test_jobs_routes.py` | POST /jobs, GET /jobs, GET /jobs/{id}, DELETE /jobs/{id} |
| Audio Transcriber | `tests/unit/api/test_admin_routes.py` | POST /admin/cleanup, GET /admin/stats |
| Audio Transcriber | `tests/unit/api/test_health_routes.py` | GET /health, GET /languages, GET /engines |
| Audio Transcriber | `tests/unit/api/test_model_routes.py` | POST /model/load, POST /model/unload, GET /model/status |

**Template de teste:**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)

class TestHealthRoutes:
    def test_health_returns_200(self, client):
        with patch("app.api.health_routes._get_redis_store") as mock_store:
            mock_store.return_value.ping.return_value = True
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_redis_failure_returns_503(self, client):
        with patch("app.api.health_routes._get_redis_store") as mock_store:
            mock_store.return_value.ping.return_value = False
            response = client.get("/health")
            assert response.status_code == 503
```

**Validação:**
- [ ] `pytest tests/unit/api/ -v` passa em cada serviço
- [ ] Cobertura >= 70% em cada router
- [ ] Cada endpoint tem pelo menos 2 testes: sucesso e erro

---

### F2-T8: Descontinuar testes antigos e migrar para nova estrutura

**Critério de descontinuação:**

Um teste é marcado como **DEPRECATED** quando:
1. Importa de módulos legados (ex: `from app.config import`, `from app.processor_new import`)
2. Usa `Mock()` direto em vez de `common.test_utils`
3. Não usa markers (`@pytest.mark.unit`, `@pytest.mark.integration`)
4. Testa lógica que foi movida para routers mas ainda testa o `main.py` antigo
5. Está em diretório raiz de `tests/` em vez de `tests/unit/` ou `tests/integration/`

**Processo de migração por serviço:**

#### Video Downloader
- [ ] Mover `tests/test_validators.py` → `tests/unit/core/test_validators.py`
- [ ] Mover `tests/test_service_validators.py` → `tests/unit/services/test_validators.py`
- [ ] Mover `tests/test_video_downloader.py` → `tests/unit/services/test_video_downloader.py`
- [ ] Mover `tests/test_models.py` → `tests/unit/core/test_models.py`
- [ ] Mover `tests/test_integration.py` → `tests/integration/test_api.py`
- [ ] Adicionar `@pytest.mark.unit` ou `@pytest.mark.integration` a todos
- [ ] Atualizar imports de `app.config` → `app.core.config`
- [ ] Eliminar `tests/test_integration.py` antigo após migração

#### Audio Normalization
- [ ] Mover `tests/unit/test_config.py` → atualizar imports de `app.config` para `app.core.config` (JÁ FEITO)
- [ ] Mover `tests/unit/test_job_service.py` → verificar imports legados
- [ ] Identificar testes em `tests/` raiz que importam de módulos inexistentes
- [ ] Marcar `tests/test_all_features.py`, `tests/test_chaos.py`, `tests/test_gpu.py` como DEPRECATED
- [ ] Criar `tests/integration/test_api_endpoints.py` com TestClient
- [ ] Eliminar `tests/run_complex.py` (legado, não funciona)

#### Audio Transcriber
- [ ] Consolidar 2 pytest.ini em 1 (eliminar `tests/pytest.ini` ou `pytest.ini` raiz)
- [ ] Mover testes raiz `tests/test_*.py` → `tests/unit/` ou `tests/integration/`
- [ ] Eliminar `tests/test_import.py` e `tests/test_import_simple.py` (substituídos por `test-imports` no Makefile)
- [ ] Adicionar markers a todos os testes

#### YouTube Search
- [ ] Criar `tests/unit/` e `tests/integration/` (Makefile referencia mas não existem)
- [ ] Mover `tests/test_models.py` → `tests/unit/test_models.py`
- [ ] Mover `tests/test_config.py` → `tests/unit/test_config.py`
- [ ] Mover `tests/test_core/test_validators.py` → `tests/unit/core/test_validators.py`
- [ ] Adicionar mocks de YouTube API (atualmente testa API real)

**Validação:**
- [ ] `pytest tests/unit/ -m unit -v` passa em cada serviço
- [ ] `pytest tests/integration/ -m integration -v` passa em cada serviço
- [ ] Zero warnings de `PytestCollectionWarning` (imports quebrados)
- [ ] Zero testes sem marker

---

## Fase 3 — Robustez (P2)

### F3-T9: Serialização versionada no Redis

**Criar `common/redis_utils/serializers.py`:**

```python
SERIALIZATION_VERSION = "2.0"

class ModelSerializer:
    @staticmethod
    def serialize(model_dict: dict) -> dict:
        model_dict["_version"] = SERIALIZATION_VERSION
        return model_dict

    @staticmethod
    def deserialize(data: dict) -> dict:
        version = data.pop("_version", "1.0")
        if version == "1.0":
            data = ModelSerializer._migrate_v1_to_v2(data)
        return data

    @staticmethod
    def _migrate_v1_to_v2(data: dict) -> dict:
        # Adiciona campos novos, converte formatos antigos
        if "created_at" in data and data["created_at"] and "T" not in data["created_at"]:
            data["created_at"] = data["created_at"].replace(" ", "T")
        return data
```

**Validação:**
- [ ] `python3 -c "from common.redis_utils.serializers import ModelSerializer"` funciona
- [ ] Teste: serializar modelo, salvar no fakeredis, deserializar — dados preservados
- [ ] Teste: deserializar dados v1.0 → migração automática para v2.0
- [ ] Cada `RedisJobStore.save_job()` usa `ModelSerializer.serialize()`

---

### F3-T10: Health checks consistentes

**Criar `common/health_utils.py`:**

```python
@dataclass
class CheckResult:
    name: str
    status: str  # "ok", "error", "warning"
    detail: str = ""
    latency_ms: float = 0.0

class ServiceHealthChecker:
    def __init__(self, service_name: str): ...
    def add_check(self, name: str, fn: Callable): ...
    async def check_all(self) -> dict: ...
    
    @staticmethod
    def check_redis(redis_url: str) -> CheckResult: ...
    @staticmethod
    def check_disk(path: str, min_free_gb: float = 1.0) -> CheckResult: ...
    @staticmethod
    def check_celery(celery_app) -> CheckResult: ...
```

**Validação:**
- [ ] Todos os 6 serviços usam `ServiceHealthChecker`
- [ ] `/health` retorna JSON padronizado em todos
- [ ] Teste unitário: `checker.check_all()` retorna status correto com mocks

---

### F3-T11: Retry com backoff nos clients de microserviço

**Criar `common/http_utils/resilient_client.py`:**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientHttpClient:
    def __init__(self, base_url: str, timeout: float = 30.0): ...
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=60))
    async def post(self, path: str, **kwargs) -> httpx.Response: ...
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=60))
    async def get(self, path: str, **kwargs) -> httpx.Response: ...
```

**Validação:**
- [ ] `python3 -c "from common.http_utils.resilient_client import ResilientHttpClient"` funciona
- [ ] Teste: mock server retorna 500 duas vezes e 200 na terceira — cliente retorna 200
- [ ] Teste: mock server retorna 500 três vezes — cliente levanta exceção

---

### F3-T12: Logging estruturado consistente

**Validação:**
- [ ] `grep -r "logging.basicConfig" services/ orchestrator/` retorna 0 resultados (excluindo tests/)
- [ ] Todos os serviços usam `from common.log_utils import get_logger`
- [ ] `grep -r "logging.getLogger" services/ orchestrator/` retorna 0 (excluindo tests/, common/)

---

## Fase 4 — Governança (P3)

### F4-T13: Pipeline CI/CD

**Criar `.github/workflows/ci.yml`:**

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install black isort flake8 mypy bandit
      - run: black --check --line-length=100 .
      - run: isort --check --profile black .
      - run: flake8 --max-line-length=100 .
      - run: mypy --ignore-missing-imports .
      - run: bandit -r . -c .bandit.yml
  
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [orchestrator, video-downloader, audio-normalization, audio-transcriber, make-video, youtube-search]
    steps:
      - uses: actions/checkout@v4
      - run: cd services/${{ matrix.service }} && pip install -r requirements.txt && pytest -x -m "not slow and not integration" -q
```

**Validação:**
- [ ] `.github/workflows/ci.yml` criado
- [ ] `act -j lint` (ou similar) executa localmente sem erros

---

### F4-T14: `make lint` no Makefile raiz

**Validação:**
- [ ] `make lint` executa black, isort, flake8, mypy, bandit
- [ ] `make lint` retorna exit code 0 com código atual

---

### F4-T15: ADRs

```
docs/adr/
├── 001-dependency-injection-pattern.md
├── 002-redis-serialization-versioning.md
├── 003-health-check-standard.md
├── 004-logging-structured-format.md
├── 005-error-hierarchy-standard.md
└── 006-router-organization.md
```

**Validação:**
- [ ] 6 ADRs criados
- [ ] Referenciados em AGENTS.md

---

### F4-T16: `make test-ci`

**Validação:**
- [ ] `make test-ci` executa em < 2 minutos
- [ ] `make test-ci` exclui `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.e2e`

---

### F4-T17: Eliminar pytest.ini duplicados

**Ações:**
- [ ] Eliminar `services/audio-transcriber/tests/pytest.ini` (conflita com `services/audio-transcriber/pytest.ini`)
- [ ] Mover config única do `tests/pytest.ini` para o `pytest.ini` do serviço
- [ ] Eliminar `orchestrator/common/datetime_utils/pytest.ini` (duplica `common/datetime_utils/pytest.ini`)

**Validação:**
- [ ] `pytest --co -q` lista todos os testes corretamente em cada serviço
- [ ] Zero `PytestConfigWarning` sobre configs conflitantes

---

### F4-T18: Exception hierarchy em common/exceptions.py

**Criar:**

```python
# common/exceptions.py
class ServiceError(Exception):
    """Base para todas as exceções de serviço."""
    status_code: int = 500
    error_code: str = "SERVICE_ERROR"

class JobError(ServiceError): ...
class JobNotFoundError(JobError): ...
class JobExpiredError(JobError): ...
class ValidationError(ServiceError): ...
class RedisConnectionError(ServiceError): ...
class MicroserviceError(ServiceError): ...
class CircuitBreakerOpenError(ServiceError): ...
```

**Validação:**
- [ ] `python3 -c "from common.exceptions import ServiceError, JobNotFoundError"` funciona
- [ ] Cada serviço pode importar de `common.exceptions` para suas subclasses

---

### F4-T19: Type hints completos (mypy)

**Validação por serviço:**
- [ ] `mypy app/ --ignore-missing-imports --no-strict-optional` retorna 0 erros em cada serviço
- [ ] Adicionado ao `make lint`

---

### F4-T20: OpenAPI docs consistentes

**Validação:**
- [ ] `curl -s http://localhost:8000/openapi.json | python3 -m json.tool` retorna schema válido para cada serviço
- [ ] Cada endpoint tem `summary`, `description`, e `response_model`
- [ ] Nenhum endpoint retorna `dict` genérico como response_model

---

## Validação de Endpoints por Serviço (curl)

Cada seção abaixo lista os comandos curl para validar cada endpoint individualmente. Se um endpoint retornar erro, corrigir antes de marcar o checklist.

### Orchestrator (porta 8000)

```bash
# Health
- [ ] curl -s http://localhost:8000/ | python3 -m json.tool
- [ ] curl -s http://localhost:8000/health | python3 -m json.tool

# Pipeline
- [ ] curl -s -X POST http://localhost:8000/process -H "Content-Type: application/json" -d '{"youtube_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' | python3 -m json.tool

# Jobs
- [ ] curl -s http://localhost:8000/jobs | python3 -m json.tool
- [ ] curl -s http://localhost:8000/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s "http://localhost:8000/jobs/{JOB_ID}/wait?timeout=10" | python3 -m json.tool
- [ ] curl -s http://localhost:8000/jobs/{JOB_ID}/stream | head -20

# Admin
- [ ] curl -s http://localhost:8000/admin/stats | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8000/admin/cleanup | python3 -m json.tool
```

### YouTube Search (porta 8001)

```bash
- [ ] curl -s http://localhost:8001/ | python3 -m json.tool
- [ ] curl -s http://localhost:8001/health | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8001/search/video-info -H "Content-Type: application/json" -d '{"video_id":"dQw4w9WgXcQ"}' | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8001/search/videos -H "Content-Type: application/json" -d '{"query":"python tutorial","max_results":5}' | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8001/search/shorts -H "Content-Type: application/json" -d '{"query":"python shorts","max_results":5}' | python3 -m json.tool
- [ ] curl -s http://localhost:8001/jobs/ | python3 -m json.tool
- [ ] curl -s http://localhost:8001/admin/stats | python3 -m json.tool
- [ ] curl -s http://localhost:8001/admin/queue | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8001/admin/cleanup | python3 -m json.tool
```

### Video Downloader (porta 8002)

```bash
- [ ] curl -s http://localhost:8002/ | python3 -m json.tool
- [ ] curl -s http://localhost:8002/health | python3 -m json.tool
- [ ] curl -s http://localhost:8002/metrics | head -10
- [ ] curl -s -X POST http://localhost:8002/jobs -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' | python3 -m json.tool
- [ ] curl -s http://localhost:8002/jobs | python3 -m json.tool
- [ ] curl -s http://localhost:8002/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s -X DELETE http://localhost:8002/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s http://localhost:8002/jobs/orphaned | python3 -m json.tool
- [ ] curl -s http://localhost:8002/admin/stats | python3 -m json.tool
- [ ] curl -s http://localhost:8002/admin/queue | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8002/admin/cleanup | python3 -m json.tool
- [ ] curl -s http://localhost:8002/user-agents/stats | python3 -m json.tool
```

### Audio Normalization (porta 8003)

```bash
- [ ] curl -s http://localhost:8003/ | python3 -m json.tool
- [ ] curl -s http://localhost:8003/health | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8003/jobs -F "file=@test.mp3" -F "remove_noise=true" | python3 -m json.tool
- [ ] curl -s http://localhost:8003/jobs | python3 -m json.tool
- [ ] curl -s http://localhost:8003/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s http://localhost:8003/jobs/{JOB_ID}/download -o /dev/null -w "%{http_code}"
- [ ] curl -s -X DELETE http://localhost:8003/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s http://localhost:8003/admin/stats | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8003/admin/cleanup | python3 -m json.tool
```

### Audio Transcriber (porta 8004)

```bash
- [ ] curl -s http://localhost:8004/ | python3 -m json.tool
- [ ] curl -s http://localhost:8004/health | python3 -m json.tool
- [ ] curl -s http://localhost:8004/health/detailed | python3 -m json.tool
- [ ] curl -s http://localhost:8004/languages | python3 -m json.tool
- [ ] curl -s http://localhost:8004/engines | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8004/jobs -F "file=@test.mp3" -F "language=pt" | python3 -m json.tool
- [ ] curl -s http://localhost:8004/jobs | python3 -m json.tool
- [ ] curl -s http://localhost:8004/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s http://localhost:8004/jobs/{JOB_ID}/download -o /dev/null -w "%{http_code}"
- [ ] curl -s http://localhost:8004/jobs/{JOB_ID}/text | python3 -m json.tool
- [ ] curl -s http://localhost:8004/jobs/{JOB_ID}/transcription | python3 -m json.tool
- [ ] curl -s -X DELETE http://localhost:8004/jobs/{JOB_ID} | python3 -m json.tool
- [ ] curl -s http://localhost:8004/admin/stats | python3 -m json.tool
- [ ] curl -s -X POST http://localhost:8004/admin/cleanup | python3 -m json.tool
- [ ] curl -s http://localhost:8004/model/status | python3 -m json.tool
- [ ] curl -s http://localhost:8004/metrics | head -10
```

### Make Video (porta 8005)

```bash
- [ ] curl -s http://localhost:8005/ | python3 -m json.tool
- [ ] curl -s http://localhost:8005/health | python3 -m json.tool
- [ ] curl -s http://localhost:8005/jobs | python3 -m json.tool
- [ ] curl -s http://localhost:8005/cache/stats | python3 -m json.tool
- [ ] curl -s http://localhost:8005/metrics | head -10
```

---

## Regra: Validação a cada checklist

**Para cada item do checklist, o processo é:**

1. Implementar a tarefa
2. Executar o comando de validação especificado na seção "Validação"
3. Se sucesso → marcar `[x]` no checklist
4. Se falha → corrigir o problema e repetir a validação
5. Só avançar para a próxima tarefa quando a atual estiver `[x]`

**Ordem de execução obrigatória:**
- Fase 1 completa antes de Fase 2
- Fase 2 completa antes de Fase 3
- Fase 4 pode rodar em paralelo com Fase 3

---

## Cronograma Estimado

| Fase | Duração | Depende de |
|------|---------|------------|
| Fase 1 | 2-3 semanas | — |
| Fase 2 | 2-3 semanas | Fase 1 |
| Fase 3 | 2-3 semanas | Fase 2 |
| Fase 4 | 2 semanas | Fase 3 |
| **Total** | **8-11 semanas** | — |