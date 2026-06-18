# PLANO DE PADRONIZAÇÃO — MONOREPO YTCaption

## Escopo
- **9 services**: SE1-SE9
- **Padrão alvo**: `BaseServiceSettings` (shared), `create_service_app()`, .env padronizado
- **Risco**: Alto (muda config de todos os services) — requer validação por service

---

## FASE 0 — Preparação do Shared Library

**Objetivo**: Garantir que `BaseServiceSettings` suporta todos os padrões necessários.

**Arquivo**: `shared/config_utils/base_settings.py`

| Item | Status Atual | Ação |
|---|---|---|
| `app_name` | ✅ | Manter |
| `app_version` | ✅ | Manter |
| `environment` | ✅ | Manter |
| `debug` | ✅ | Manter |
| `host` | ✅ | Manter |
| `port` | ✅ | Manter |
| `workers` | ✅ | Manter |
| `redis_url` | ✅ | Manter |
| `cache_ttl_hours` | ✅ | Manter |
| `max_file_size_mb` | ✅ | Manter |
| `upload_dir` | ✅ | Manter |
| `temp_dir` | ✅ | Manter |
| `log_dir` | ✅ | Manter |
| `log_level` | ✅ | Manter |
| `log_format` | ✅ | Manter |
| `api_key` | ❌ **falta** | **Adicionar**: `api_key: Optional[str] = Field(default=None, env='API_KEY')` |
| `tz` | ❌ **falta** | **Adicionar**: `tz: str = Field(default='America/Sao_Paulo', env='TZ')` |
| `output_dir` | ❌ **falta** | **Adicionar**: `output_dir: str = Field(default='./data/outputs', env='OUTPUT_DIR')` |
| `divisor` | ❌ **falta** | **Adicionar**: `divisor: Optional[int] = Field(default=None, env='DIVISOR')` |

**Ação**: Adicionar 4 campos ao `BaseServiceSettings`. Manter `extra = 'allow'` para extensões.

---

## FASE 1 — Padrão .env Universal

### Template obrigatório (em português, seções com `# =====`):

```bash
# ===== APLICAÇÃO =====
APP_NAME=<Nome do Service>
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false
TZ=America/Sao_Paulo

# ===== SERVIDOR =====
HOST=0.0.0.0
DIVISOR=<N>
PORT=800${DIVISOR}
WORKERS=1

# ===== REDIS =====
REDIS_URL=redis://192.168.1.110:6379/${DIVISOR}

# ===== CELERY (se aplicável) =====
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# ===== CACHE =====
CACHE_TTL_HOURS=24

# ===== DIRETÓRIOS =====
TEMP_DIR=./data/temp
LOG_DIR=./logs

# ===== LOGGING =====
LOG_LEVEL=INFO
LOG_FORMAT=json

# ===== API KEY =====
API_KEY=se<N>-test-key-2026

# ===== TIMEOUTS =====
JOB_PROCESSING_TIMEOUT_SECONDS=<valor>

# ===== CONFIGURAÇÕES ESPECÍFICAS DO SERVICE =====
# (variáveis únicas de cada service aqui)
```

### Correções por Service:

| Service | Correções no .env |
|---|---|
| **SE1** | Renomear `APP_VERSION` → `VERSION`; adicionar `LOG_FORMAT=json` |
| **SE2** | ✅ Já está ok (quase perfeito) |
| **SE3** | Remover `IP_REDIS` (usar inline no REDIS_URL); remover variáveis duplicadas (`CACHE__TTL_HOURS` + `CACHE_TTL_HOURS`) |
| **SE4** | Remover `DATABASE__*` (não usa PG); simplificar seções whisper |
| **SE5** | **CRÍTICO**: Corrigir `REDIS_URL` de `...6379/0` para `...6379/${DIVISOR}`; adicionar seções que faltam; remover `TZ` do início (mover para bloco APLICAÇÃO) |
| **SE6** | Corrigir `ENVIRONMENT=production` → `development`; adicionar `WORKERS=1` |
| **SE7** | Adicionar `LOG_DIR`; remover `IP_REDIS` (usar inline) |
| **SE8** | Adicionar `API_KEY`; adicionar `LOG_DIR` |
| **SE9** | **Criar .env** a partir do .env.example com padrão completo; adicionar `ENVIRONMENT`, `HOST`, `TZ`, `WORKERS`, `DIVISOR`, `LOG_DIR`, `LOG_FORMAT` |

---

## FASE 2 — Padrão config.py (BaseServiceSettings)

### Abordagem para cada service:

1. **Substituir** a classe de settings atual por herança de `BaseServiceSettings`
2. **Adicionar** campos específicos do service como overrides
3. **Manter** `get_settings()` retornando a instância (não dict)
4. **Atualizar** todos os `settings['key']` → `settings.key` no service inteiro

### Detalhamento por Service:

#### SE1 — Orchestrator
- **Atual**: `OrchestratorSettings(BaseSettings)` — 208 linhas, campos manuais
- **Novo**: `OrchestratorSettings(BaseServiceSettings)` — herda campos comuns, só adiciona: `video_downloader_url`, `audio_normalization_url`, `audio_transcriber_url`, timeouts, polling, circuit breaker
- **Impacto**: ~15 arquivos usam `settings['key']` — migrar para `settings.key`

#### SE2 — Video Downloader
- **Atual**: `Settings(BaseSettings)` — 76 linhas
- **Novo**: `Settings(BaseServiceSettings)` — herda comuns, adiciona: `max_concurrent_downloads`, `default_quality`, `job_processing_timeout_seconds`, `downloads_dir`
- **Impacto**: Mínimo — já usa `settings.get()` em maioria

#### SE3 — Audio Normalization
- **Atual**: `_CoreSettings` + `get_settings() → Dict` — mistura Pydantic com dict manual
- **Novo**: `AudioNormSettings(BaseServiceSettings)` — eliminar dict, retornar instância Pydantic
- **Impacto**: **ALTO** — ~30+ referências `settings['key']` espalhadas em 612 linhas de main.py + services

#### SE4 — Audio Transcriber
- **Atual**: `CoreSettings(BaseSettings)` + `get_settings() → Dict` — mesmo padrão SE3
- **Novo**: `TranscriberSettings(BaseServiceSettings)` — eliminar dict, retornar instância
- **Impacto**: **ALTO** — muitas referências dict

#### SE5 — Make Video Clip
- **Atual**: `Settings(BaseSettings)` + `os.getenv()` manual — 244 linhas, o mais defasado
- **Novo**: `MakeVideoSettings(BaseServiceSettings)` — eliminar `os.getenv()`, eliminar `expand_env_vars`, eliminar `load_dotenv()`
- **Impacto**: **CRÍTICO** — 445 linhas de .env, 60+ campos, `extra="allow"`, retorna dict

#### SE6 — YouTube Search
- **Atual**: `_CoreSettings` + `get_settings() → Dict` — mesmo padrão SE3
- **Novo**: `SearchSettings(BaseServiceSettings)` — eliminar dict
- **Impacto**: Moderado

#### SE7 — Audio Generation
- **Atual**: `CoreSettings(BaseSettings)` — 55 linhas, `extra="allow"`, `class Config`
- **Novo**: `AudioGenSettings(BaseServiceSettings)` — herdar comuns, manter campos específicos
- **Impacto**: Baixo — já retorna instância

#### SE8 — Image Generation
- **Atual**: `ImageEngineSettings(BaseServiceSettings)` — **JÁ USA O PADRÃO** ✅
- **Novo**: Nenhuma mudança necessária (só verificar se `api_key` está presente)
- **Impacto**: Nenhum

#### SE9 — Make Video IMG
- **Atual**: `Settings(BaseSettings)` — 36 linhas, `model_config` dict
- **Novo**: `VideoImgSettings(BaseServiceSettings)` — herdar comuns, adicionar SE7/SE8 URLs, video defaults
- **Impacto**: **ALTO** — precisa migrar main.py para `create_service_app()`

---

## FASE 3 — Padrão main.py (create_service_app)

### Padrão alvo:
```python
from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import setup_structured_logging, get_logger
from app.core.config import get_settings

settings = get_settings()
setup_structured_logging(service_name="seN-<name>", log_level=settings.log_level, log_dir=settings.log_dir)
logger = get_logger(__name__)
verify_api_key = create_api_key_dependency(api_key=settings.api_key)

def setup_routers(app):
    app.include_router(health_router)
    app.include_router(jobs_router)
    # ...

app = create_service_app(
    service_name="seN-<name>",
    title=settings.app_name,
    version=settings.app_version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    dependencies=[Depends(verify_api_key)],
)
```

### Correções por Service:

| Service | `create_service_app` | API Key | Logging | Ação |
|---|---|---|---|---|
| SE1 | ✅ | ✅ | ✅ | Nenhuma |
| SE2 | ✅ | ✅ | ✅ | Nenhuma |
| SE3 | ✅ | ✅ | ✅ | Nenhuma |
| SE4 | ✅ | ✅ | ✅ | Nenhuma |
| SE5 | ✅ | ✅ | ✅ | Nenhuma |
| SE6 | ✅ | ✅ | ✅ | Nenhuma |
| SE7 | ✅ | ✅ | ✅ | Nenhuma |
| SE8 | ✅ | ✅ | ✅ | Nenhuma |
| **SE9** | ❌ **manual** | ❌ **sem auth** | ❌ **basico** | **MIGRAR** para `create_service_app()`, adicionar API key, trocar logging |

---

## FASE 4 — Padrão run.py

### Padrão alvo:
```python
#!/usr/bin/env python3
"""Runner script for SE<N> <Nome>."""
import uvicorn
from app.core.config import get_settings
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_structured_logging(service_name="seN-<name>", log_level=settings.log_level)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
```

### Correções:

| Service | Ação |
|---|---|
| SE1 | ✅ OK |
| SE2 | Adicionar `setup_structured_logging` |
| SE3 | Simplificar (remover `limit_max_requests` etc — deixar no uvicorn defaults) |
| SE4 | Simplificar |
| SE5 | Simplificar |
| SE6 | Simplificar |
| SE7 | ✅ OK |
| SE8 | ✅ OK |
| SE9 | Adicionar `setup_structured_logging` |

---

## FASE 5 — Padrão Docker

### Dockerfile padrão:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY shared/ /app/common/
RUN pip install --no-cache-dir -e /app/common
COPY services/se<N>-<name>/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/se<N>-<name>/app/ /app/app/
COPY services/se<N>-<name>/run.py .
EXPOSE 800<N>
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import httpx; httpx.get('http://localhost:800<N>/health').raise_for_status()"
CMD ["python", "run.py"]
```

### docker-compose.yml padrão:
```yaml
services:
  se<N>-<name>:
    build:
      context: ../..
      dockerfile: services/se<N>-<name>/docker/Dockerfile
    container_name: ytcaption-se<N>-<name>
    ports:
      - "800<N>:800<N>"
    env_file:
      - .env
    volumes:
      - ../../shared:/app/common
      - ./app:/app/app
    networks:
      - ytcaption-net
    restart: unless-stopped

networks:
  ytcaption-net:
    external: true
```

### Correções:

| Service | Healthcheck | Non-root | Network | Ação |
|---|---|---|---|---|
| SE1 | ✅ | ❌ | ytcaption-net | Adicionar non-root |
| SE2 | ✅ | ✅ | default | Migrar para ytcaption-net |
| SE3 | ✅ | ✅ | default | Migrar para ytcaption-net |
| SE4 | ✅ | ✅ | default | Migrar para ytcaption-net |
| SE5 | ❌ | ❌ | host | Adicionar healthcheck, migrar de host para ytcaption-net |
| SE6 | ✅ | ✅ | default | Migrar para ytcaption-net |
| SE7 | ✅ | ✅ | default | Migrar para ytcaption-net |
| SE8 | ✅ | ✅ | default | Migrar para ytcaption-net |
| **SE9** | ❌ | ❌ | ytcaption-net | Adicionar healthcheck, adicionar non-root |

---

## FASE 6 — Rotas Padronizadas

### Rotas que TODOS os services devem ter:

| Rota | Obrigatório | Descrição |
|---|---|---|
| `GET /` | Sim | Info do service (nome, versão, status) |
| `GET /health` | Sim | Health check (Redis, disk, deps) |
| `GET /jobs` | Sim | Listar jobs |
| `GET /jobs/{id}` | Sim | Status do job |
| `DELETE /jobs/{id}` | Sim | Deletar job + arquivos |
| `GET /download/{id}` | Se gera arquivo | Download do resultado |
| `GET /admin/stats` | Sim | Estatísticas do sistema |
| `POST /admin/cleanup` | Sim | Limpeza manual |

### Correções:

| Service | Rotas Faltando | Ação |
|---|---|---|
| SE1 | `DELETE /jobs/{id}` | Adicionar |
| SE5 | `GET /download/{id}` | Já tem `/make-video` como output — verificar |
| SE7 | `GET /`, `DELETE /jobs/{id}`, `/admin/*` | Adicionar |
| SE8 | `GET /`, `DELETE /jobs/{id}`, `/admin/*` | Adicionar |
| **SE9** | `GET /`, `DELETE /jobs/{id}`, `/admin/*` | Adicionar |

---

## FASE 7 — Validação

### Para CADA service, rodar:

```bash
# 1. Verificar imports
python -c "from app.core.config import get_settings; s = get_settings(); print(s.app_name)"

# 2. Verificar que settings é instância Pydantic (não dict)
python -c "from app.core.config import get_settings; s = get_settings(); assert hasattr(s, 'app_name'), 'NOT PYDANTIC'"

# 3. Verificar que .env é carregado
python -c "from app.core.config import get_settings; s = get_settings(); assert s.port == 800<N>, f'WRONG PORT: {s.port}'"

# 4. Verificar que create_service_app funciona
python -c "from app.main import app; print(app.title)"

# 5. Verificar que run.py funciona
python run.py &; sleep 2; curl localhost:800<N>/health; kill %1
```

---

## ORDEM DE EXECUÇÃO RECOMENDADA

| Ordem | Service | Complexidade | Justificativa |
|---|---|---|---|
| 1 | **Shared Library** | Baixa | Base para tudo |
| 2 | **SE8** | Nenhuma | Já está no padrão — servir de referência |
| 3 | **SE7** | Baixa | 55 linhas config, simples |
| 4 | **SE9** | Média | Precisa migrar para create_service_app, mas é pequeno |
| 5 | **SE2** | Baixa | .env já está ok, config simples |
| 6 | **SE6** | Baixa | Config simples, mas retorna dict |
| 7 | **SE1** | Média | Config grande mas organizado |
| 8 | **SE3** | Alta | 612 linhas main.py, muitas refs dict |
| 9 | **SE4** | Alta | Muitas configs whisper, refs dict |
| 10 | **SE5** | Crítica | O mais defasado — 445 linhas .env, 244 config, dict manual |

---

## RISCOS E MITIGAÇÕES

| Risco | Impacto | Mitigação |
|---|---|---|
| Breaking change em `settings['key']` | Crítico | Buscar TODAS as refs `settings['key']` e `settings.get('key')` antes de migrar; usar `sed` para substituir |
| Services que usam dict em Celery tasks | Alto | Celery tasks importam settings separadamente — testar cada uma |
| Docker compose com paths errados | Médio | Validar com `docker compose config` |
| .env com variáveis não reconhecidas | Baixo | `extra="allow"` no BaseServiceSettings ignora extras |
| SE5 com 60+ campos | Alto | Migrar incrementalmente — campos um por um |

---

## ENTREGÁVEIS

1. `shared/config_utils/base_settings.py` — 4 campos novos
2. 9x `app/core/config.py` — migrados para BaseServiceSettings
3. 9x `.env` — padronizados
4. 9x `.env.example` — atualizados
5. 9x `app/main.py` — padronizados (SE9 migra para create_service_app)
6. 9x `run.py` — padronizados
7. 9x `docker/Dockerfile` — com healthcheck e non-root
8. 9x `docker/docker-compose.yml` — na network ytcaption-net
9. `tests/` — validação por service

---

**Tempo estimado**: 3-4 horas (migrar 9 services com validação)

**Próximo passo**: Confirmar este plano e eu inicio pela Fase 0 (Shared Library).
