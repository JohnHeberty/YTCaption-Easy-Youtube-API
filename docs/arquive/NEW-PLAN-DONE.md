# PLANO DE REFACTORY: clothes-segmentation → services/se10-clothes-segmentation

## Contexto

O projeto `clothes-segmentation/` é um protótipo funcional de segmentação de roupas usando GroundingDINO + SAM2. Precisa ser refatorado em um microservice padronizado seguindo o padrão SE8 do monorepo.

**Porta**: 8010 | **Nome**: `se10-clothes-segmentation` | **Complexidade**: Alta

---

## DECISÕES DE ARQUITETURA (que precisam ser tomadas ANTES de começar)

### D1: Gerenciamento do `external/` (GroundingDINO + SAM2)

**Problema**: O código usa `sys.path.insert()` para importar de `external/GroundingDINO/` e `external/segment-anything-2/`. Isso é frágil, não-idempotente, e não funciona em Docker.

**Opções**:

| Opção | Prós | Contras |
|-------|------|---------|
| **A) Editable installs** (`pip install -e external/GroundingDINO && pip install -e external/segment-anything-2`) | Imports limpos, funciona em Docker, idempotente | Precisa de `setup.py`/`pyproject.toml` em cada repo externo (já existem) |
| **B) Vendorizar código** (copiar apenas os módulos necessários) | Controle total, sem dependência de git clone | Precisa manter sincronizado com upstream |
| **C) PyPI packages** (usar `groundingdino` e `sam2` do PyPI se existirem) | Padrão, fácil | Versões podem não estar atualizadas |

**Recomendação**: Opção A (editable installs). Os repos já têm `setup.py`/`pyproject.toml`. No Dockerfile, `pip install -e ./external/GroundingDINO && pip install -e ./external/segment-anything-2`. No código, imports limpos: `from groundingdino.util.inference import Model`, `from sam2.build_sam import build_sam2`.

### D2: GPU vs CPU

**Problema**: O monorepo tem um padrão claro: GPU workers via Celery + Dockerfile.gpu (como SE8). Mas clothes-segmentation originalmente roda em CPU.

**Opções**:

| Opção | Prós | Contras |
|-------|------|---------|
| **A) CPU-only** (simpler) | Sem necessidade de GPU, deploy simples | Lento (~30s por imagem em CPU) |
| **B) GPU-first, CPU fallback** (como SE8) | Rápido em GPU, funciona sem | Complexidade de Dockerfile.gpu, Celery worker |
| **C) GPU via Celery split** (SE8 pattern exato) | Arquitetura consistente no monorepo | Overkill se GPU não está disponível |

**Recomendação**: Opção B. Criar `Dockerfile` (CPU) e `Dockerfile.gpu` (GPU + Celery). O código atual já funciona em CPU — a detecção de GPU pode ser automática via `torch.cuda.is_available()`.

### D3: Modelo de Jobs

**Problema**: O endpoint atual é síncrono (bloqueia até completar). Para imagens grandes ou múltiplos objetos, isso pode levar 30+ segundos.

**Opções**:

| Opção | Prós | Contras |
|-------|------|---------|
| **A) Síncrono + async fallback** (como SE8) | Simples, funciona para uso básico | Bloqueia worker thread |
| **B) Async nativo** (job queue + polling) | Escalável, não bloqueia | Mais complexo, precisa Redis/Celery |
| **C) Híbrido** (sync para imagens pequenas, async para batch) | O melhor dos dois mundos | Mais código para manter |

**Recomendação**: Opção A (como SE8). Manter endpoint síncrono com `ThreadPoolExecutor`, mas integrar com `StandardJob` para tracking. Se o usuário quiser async depois, é incremental.

---

## ESTRUTURA FINAL

```
services/se10-clothes-segmentation/
├── .env                          # Configuração padrão monorepo
├── .env.example                  # Template
├── Makefile                      # Build/run/test shortcuts
├── pyproject.toml                # pytest + coverage config
├── requirements.txt              # Dependências Python
├── run.py                        # Uvicorn entrypoint
├── docker/
│   ├── Dockerfile                # CPU (multi-stage: base → api)
│   ├── Dockerfile.gpu            # GPU worker (Celery)
│   └── docker-compose.yml        # Compose config
├── app/
│   ├── __init__.py
│   ├── main.py                   # App factory + lifespan
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # ClothesSegSettings(BaseServiceSettings)
│   │   └── constants.py          # 15 classes, thresholds, defaults
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py         # GET /, /health, /health/deep, /ping
│   │   │   ├── segment.py        # POST /v1/segment
│   │   │   └── jobs.py           # GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}
│   │   └── deps.py               # Dependencies (verify_api_key, get_segmentor)
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py             # Pydantic request/response models
│   │   └── enums.py              # ClothingClass enum, thresholds
│   ├── services/
│   │   ├── __init__.py
│   │   ├── segmentor.py          # ClothesSegmentor (refatorado)
│   │   └── checkpoint.py         # Checkpoint loader com cache
│   └── infrastructure/
│       ├── __init__.py
│       └── model_loader.py       # Lazy loading, GPU detection, memory mgmt
├── external/                     # Git clones (GroundingDINO, SAM2)
│   ├── GroundingDINO/
│   └── segment-anything-2/
├── checkpoints/                  # Model weights (symlink para shared-storage)
│   └── .gitkeep
├── tests/
│   ├── conftest.py
│   ├── api/
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   └── test_segment.py
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_segmentor.py
│   │   └── test_models.py
│   └── integration/
│       └── test_segment_pipeline.py
└── data/
    ├── inputs/
    ├── outputs/
    └── temp/
```

---

## FASES DE EXECUÇÃO

### FASE 0 — Setup do Projeto (30min)

**Objetivo**: Criar a estrutura base seguindo o padrão SE8.

1. Criar diretório `services/se10-clothes-segmentation/`
2. Criar `app/core/config.py` com `ClothesSegSettings(BaseServiceSettings)`:
   - Campos herdados: `app_name`, `version`, `host`, `port`, `redis_url`, `api_key`, `log_level`, etc.
   - Campos específicos: `model_dir`, `checkpoint_dir`, `device` (auto/cpu/cuda), `max_batch_size`, `box_threshold`, `text_threshold`, `max_detection_area_pct`, `worker_threads`
   - Singleton `get_settings()` com `@lru_cache()`
3. Criar `app/core/constants.py` com as 15 classes de roupa, thresholds padrão
4. Criar `.env` e `.env.example` seguindo o template do PLAN.md
5. Criar `run.py` padrão
6. Criar `requirements.txt` (adaptar do original, adicionar `hydra-core`, `omegaconf`, `transformers` que estavam faltando)
7. Criar `Makefile` padrão

**Validação**: `python -c "from app.core.config import get_settings; s = get_settings(); print(s.app_name)"` funciona.

### FASE 1 — Configuração e Infraestrutura (30min)

**Objetivo**: Setup de logging, error handling, middleware.

1. Criar `app/main.py` usando `create_service_app()` do shared:
   - Lifespan: carregar modelo na startup, liberar na shutdown
   - Routers: health, segment, jobs
   - API key auth via `Depends(verify_api_key)`
2. Criar `app/api/deps.py` com `get_segmentor()` (dependency injection para o modelo)
3. Configurar logging estruturado via shared
4. Configurar exception handlers via shared
5. Configurar rate limiter e body size middleware

**Validação**: App importa sem erro, `/health` retorna 200.

### FASE 2 — Refatoração do Segmentor (1h)

**Objetivo**: Transformar o `ClothesSegmentor` em um serviço limpo.

**Mudanças no `services/segmentor.py`**:

1. **Remover sys.path hacks**: Usar editable installs para GroundingDINO e SAM2
2. **Lazy loading**: Modelo só carrega quando primeiro chamado (via `lifespan` ou first request)
3. **SAM2 otimização**: `set_image()` uma vez por request, predict todas as boxes de uma vez
4. **GPU auto-detect**: `torch.cuda.is_available()` para device
5. **Structured logging**: Substituir `print()` por `get_logger(__name__)`
6. **Error handling**: Try/except em load失败, decode失败, inference失败
7. **Type hints completos**: Annotations em todos os métodos

**Mudanças no `services/checkpoint.py`** (novo):

1. Verificar existência dos checkpoints no startup
2. Log de tamanho e hash dos arquivos
3. Cache de checkpoints carregados

**Mudanças em `infrastructure/model_loader.py`** (novo):

1. `load_grounding_dino()` com cache de instância
2. `load_sam2()` com cache de instância
3. Gerenciamento de memória GPU (cleanup quando idle)

**Validação**: Teste manual com imagem real, verificar que retorna resultados corretos.

### FASE 3 — API Contracts (30min)

**Objetivo**: Definir request/response models corretos.

**`app/domain/models.py`**:

```python
# Request
class SegmentRequest(BaseModel):
    """Request body for image segmentation."""
    text_prompt: str = "clothing"
    classes: Optional[List[str]] = None  # override default 15 classes
    box_threshold: Optional[float] = None  # override default
    text_threshold: Optional[float] = None
    max_objects: Optional[int] = 50

# Response
class DetectedObject(BaseModel):
    class_name: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]
    area_pct: float

class SegmentResult(BaseModel):
    detected: bool
    object_count: int
    objects: List[DetectedObject]
    mask_image: str  # base64
    processing_time_ms: float

class SegmentResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    result: Optional[SegmentResult] = None
    error: Optional[str] = None
```

**`app/domain/enums.py`**:

```python
class ClothingClass(str, Enum):
    HAT = "hat"
    SUNGLASSES = "sunglasses"
    SHIRT = "shirt"
    # ... 15 classes
```

**Validação**: Pydantic models validam corretamente, OpenAPI docs aparecem em `/docs`.

### FASE 4 — Rotas (30min)

**Objetivo**: Implementar os endpoints padronizados.

1. **`routes/health.py`**: `GET /`, `GET /health`, `GET /health/deep`, `GET /ping`
   - Health check verifica: modelo carregado, GPU disponível, disco com espaço
2. **`routes/segment.py`**: `POST /v1/segment`
   - Aceita: multipart/form-data (imagem + parâmetros opcionais)
   - Retorna: `SegmentResponse` com objeto detectado, máscara base64, tempo de processamento
   - Valida: extensão do arquivo, tamanho, formato
3. **`routes/jobs.py`**: `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs/{id}`
   - Integração com `StandardJob` do shared (para tracking futuro)

**Validação**: Todos os endpoints aparecem no OpenAPI, respondem corretamente.

### FASE 5 — Docker (30min)

**Objetivo**: Containerização completa.

**`docker/Dockerfile`** (CPU, multi-stage):

```dockerfile
FROM python:3.11-slim AS base
# Instalar dependências do sistema (libgl1, libglib2.0-0 para OpenCV)
# Copiar shared/, external/, requirements.txt
# pip install -e /app/common -e ./external/GroundingDINO -e ./external/segment-anything-2
# pip install -r requirements.txt

FROM base AS api
# Copiar app/, run.py
# Non-root user (appuser)
# Healthcheck
# CMD ["python", "run.py"]
```

**`docker/Dockerfile.gpu`** (GPU, Celery worker):

```dockerfile
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 AS base
# Instalar Python 3.11, PyTorch+CUDA
# Mesmo install do CPU mas com torch[cuda]
# CMD ["celery", "-A", "app.infrastructure.celery_app", "worker", ...]
```

**`docker/docker-compose.yml`**:

```yaml
services:
  se10-clothes-segmentation:
    build:
      context: ../..
      dockerfile: services/se10-clothes-segmentation/docker/Dockerfile
    container_name: ytcaption-se10-clothes-segmentation
    ports:
      - "8010:8010"
    env_file:
      - .env
    volumes:
      - ../../shared:/app/common:ro
      - ./app:/app/app
      - se10-checkpoints:/app/checkpoints:ro
      - se10-data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8010/health').raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  se10-checkpoints:
    external: true
  se10-data:

networks:
  ytcaption-net:
    external: true
```

**Validação**: `docker compose config` válido, `docker compose up` funciona, `/health` retorna 200.

### FASE 6 — Testes (45min)

**Objetivo**: Cobertura mínima de 80%.

1. **Unit tests** (`tests/unit/`):
   - `test_config.py`: Settings carrega corretamente, defaults são válidos
   - `test_models.py`: Pydantic models validam/rejeitam corretamente
   - `test_segmentor.py`: Mock de torch/groundingdino/sam2, testar lógica de filtering

2. **API tests** (`tests/api/`):
   - `test_health.py`: Todos os endpoints de health retornam 200
   - `test_segment.py`: Upload de imagem válida retorna resultado, upload inválido retorna 400/422
   - `test_auth.py`: Requests sem API key retornam 401

3. **Integration tests** (`tests/integration/`):
   - `test_segment_pipeline.py`: Teste completo com imagem real (se GPU disponível) ou mock

**Validação**: `pytest tests/ -v --tb=short` passa, coverage ≥ 80%.

### FASE 7 — Limpeza e Migração (15min)

**Objetivo**: Migrar dados do projeto antigo, limpar.

1. Mover `checkpoints/` do projeto original para shared storage (symlink)
2. Mover `tests/test_images/` para o novo projeto
3. Atualizar `.gitignore` do monorepo para incluir `services/se10-clothes-segmentation/data/`
4. Criar `tests/e2e/.gitkeep`
5. Deletar `clothes-segmentation/` (ou mover para `archive/` se preferir preservar)

---

## RISCOS E MITIGAÇÕES

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| GroundingDINO não instala como editable | Alto | Média | Testar `pip install -e` antes de começar; fallback: vendorizar código |
| SAM2 requer versão específica de PyTorch | Alto | Média | Verificar compatibilidade `torch>=2.5.1` (SAM2) vs `torch==2.12.0` (atual) |
| Checkpoints muito grandes para Docker image | Médio | Alta | Usar volumes separados, nunca copiar para image |
| GPU não disponível em produção | Médio | Alta | Garantir que CPU fallback funciona perfeitamente |
| `hydra-core` conflita com outras deps | Baixo | Baixa | Testar install completo antes de começar |
| Memory leak com models carregados | Alto | Baixa | Monitorar com `/health/deep`, implementar idle timeout |

---

## ORDEN DE EXECUÇÃO E TIMELINE

| Fase | Tempo | Dependências | Entregável |
|------|-------|--------------|------------|
| Fase 0 | 30min | Nenhuma | Estrutura + config + .env |
| Fase 1 | 30min | Fase 0 | App factory + logging + auth |
| Fase 2 | 1h | Fase 1 | Segmentor refatorado |
| Fase 3 | 30min | Fase 1 | API contracts (models) |
| Fase 4 | 30min | Fase 2, 3 | Rotas funcionais |
| Fase 5 | 30min | Fase 4 | Docker funcionando |
| Fase 6 | 45min | Fase 4 | Testes com 80% coverage |
| Fase 7 | 15min | Tudo | Limpeza + migração |
| **Total** | **~4h** | | |

---

## CHECKLIST DE VALIDAÇÃO FINAL

```bash
# 1. App importa
python -c "from app.main import app; print(app.title)"

# 2. Settings são Pydantic
python -c "from app.core.config import get_settings; s = get_settings(); assert hasattr(s, 'port')"

# 3. .env é carregado
python -c "from app.core.config import get_settings; s = get_settings(); assert s.port == 8010"

# 4. Health check funciona
curl http://localhost:8010/health

# 5. Segment funciona (com imagem real)
curl -X POST http://localhost:8010/v1/segment -F "file=@test.jpg"

# 6. Auth funciona
curl http://localhost:8010/jobs  # deve retornar 401 sem header

# 7. Docker build funciona
docker compose -f docker/docker-compose.yml build

# 8. Docker compose up funciona
docker compose -f docker/docker-compose.yml up -d

# 9. Testes passam
pytest tests/ -v --tb=short

# 10. Coverage ≥ 80%
pytest tests/ --cov=app --cov-report=term-missing
```
