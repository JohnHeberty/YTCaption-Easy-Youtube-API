# INVESTIGATION.md — Auditoria de Conformidade Arquitetural

Auditoria completa dos 10 microserviços (SE1-SE10) do monorepo YTCaption-Easy-Youtube-API.
Cada serviço foi investigado fase a fase verificando: conformidade com padrões, SOLID, clean code, Redis, Celery, jobs e padrões ausentes.

---

## Sumário Executivo

| Serviço | Padrão | SOLID | Clean Code | Redis | Celery | Jobs | Nota |
|---------|--------|-------|------------|-------|--------|------|------|
| SE1 Orchestrator | 12/14 | 2/5 | Parcial | Bom | NÃO USA | Parcial | **C** |
| SE2 Video Downloader | 14/14 | 3/5 | Parcial | Bom | Bom | Bom | **B+** |
| SE3 Audio Normalization | 12/14 | 2/5 | Parcial | Bom | Bom | Parcial | **C+** |
| SE4 Audio Transcriber | 12/14 | 4/5 | Parcial | Bom | Bom | Bom | **B** |
| SE5 Make Video Clip | 12/14 | 2/5 | Ruim | Parcial | Parcial | Bom | **C-** |
| SE6 YouTube Search | 14/14 | 2/5 | Ruim | Bom | Bom | NÃO USA | **C+** |
| SE7 Audio Generation | 12/14 | 3/5 | Parcial | FRACO | Parcial | Parcial | **C-** |
| SE8 Image Generation | 12/14 | 1/5 | Ruim | NÃO USA | Parcial | NÃO USA | **D+** |
| SE9 Make Video IMG | 8/14 | 1/5 | Ruim | CRÍTICO | NÃO USA | NÃO USA | **D** |
| SE10 Clothes Segmentation | 13/14 | 4/5 | Bom | Bom | N/A | Bom | **B+** |

**Média geral: 6.2/10** — Apenas 3 de 10 serviços seguem bem os padrões arquiteturais.

---

## Respostas às Perguntas do Usuário

### Todos os services respeitam os padrões impostos?
**NÃO.** Apenas SE2, SE4 e SE10 seguem bem todos os padrões. SE5, SE7, SE8 e SE9 violam padrões críticos.

### Todos têm boa arquitetura?
**NÃO.** SE5 (celery_tasks 1400+ linhas), SE8 (worker 687 linhas) e SE9 (reinventa tudo) são os piores.

### Todos usam Redis e Celery?
**NÃO.** SE1 tem Celery no requirements mas NUNCA usa. SE8 usa Redis apenas como broker do Celery (jobs em memória). SE9 tem Redis customizado e Celery customizado.

### Todos têm jobs?
**NÃO.** SE6, SE8 e SE9 NÃO usam `StandardJob` do shared library. SE6 e SE8 têm modelos próprios. SE9 reinventa completamente.

### Todos têm boa SOLID?
**NÃO.** Apenas SE4 e SE10 têm boa conformidade SOLID. SE5, SE8 e SE9 têm violações graves.

### Todos têm boa clean code?
**NÃO.** SE5, SE6, SE8 e SE9 têm código duplicado, dead code, magic numbers e god classes.

---

## SE1 — Orchestrator Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:102-112` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:12` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:125-133` |
| `GET /` | ✅ SIM | `app/main.py:151-170` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:43` |
| Job CRUD (GET/DELETE) | ⚠️ PARCIAL | `app/api/jobs_routes.py` — **falta DELETE** |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:37` |
| `get_logger(__name__)` | ✅ SIM | Todos os módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:22-25` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:29-30` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:21-22` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:9-10` |
| `data/` directory | ✅ SIM | `.env:39` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:13-14` |

### Violações SOLID

1. **SRP — God class**: `PipelineOrchestrator` (`app/services/pipeline_orchestrator.py:166-477`) — 482 linhas, 5 responsabilidades (download, normalização, transcrição, polling, persistência)
2. **ISP**: `MicroserviceClientInterface` (`app/domain/interfaces.py:11-94`) força implementação de 5 métodos
3. **DIP**: `pipeline_orchestrator.py:340-343` cria `httpx.AsyncClient` diretamente, bypassando abstração

### Clean Code

- **Dead code**: `app/api/pipeline_routes.py` (148 linhas) é duplicata de `app/main.py:173-209`
- **Dead code**: `_legacy/` directory inteiro não referenciado
- **Dead code**: `app/core/constants.py:10-54` — classes de constantes nunca usadas
- **Dead code**: `app/core/validators.py` — `YouTubeURLValidator` definido mas nunca aplicado
- **Duplicação**: Duas hierarquias de exceções (`app/core/exceptions.py` e `app/infrastructure/exceptions.py`)
- **Duplicação**: `now_brazil()` fallback copiado em 4 arquivos
- **Magic numbers**: `pipeline_orchestrator.py:412` (`max_consecutive_errors = 5`), `:465` (thresholds 10, 50)
- **Bug**: `app/infrastructure/redis_store.py:38` — TTL hardcoded `24 * 3600` ignora config do construtor

### Redis
- Usa `ResilientRedisStore` com circuit breaker ✅
- Dados: Jobs serializados via Pydantic, sorted set para listagem
- **Bug**: TTL hardcoded ignora `ttl_hours` do construtor
- **Bug**: Sorted set sem TTL (vazamento de memória)

### Celery
- **NÃO USA** — `celery==5.3.4` no requirements mas nunca importado
- Usa `BackgroundTasks` do FastAPI como fallback

### Jobs
- Dois modelos de job: `PipelineJob` (antigo, usado) e `PipelineJobV2` (novo, não usado)
- **Bug de tipo**: `save_job()` recebe `PipelineJob` mas espera `PipelineJobV2`
- Falta endpoint `DELETE /jobs/{job_id}`

### Docker
- **Bug**: `EXPOSE 8000` mas app escuta em 8001
- **Bug**: `HEALTHCHECK` aponta para 8000 mas app está em 8001
- Build single-stage (não multi-stage)

### `.env` vs `.env.example`
- 12+ variáveis inconsistente (`APP_VERSION`, `PORT`, timeouts, etc.)
- **Segurança**: API key real `se1-test-key-2026` no `.env`

### Testes
- `admin_routes.py`: 0% cobertura
- `jobs_routes.py`: 0% cobertura
- `microservice_client.py`: 0% cobertura
- `redis_store.py`: 0% cobertura
- E2E tests todos pulados

---

## SE2 — Video Downloader Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:53-67` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:7` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:58-61` |
| `GET /` | ✅ SIM | `app/main.py:70-104` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:19-46` |
| Job CRUD | ✅ SIM | `app/api/jobs_routes.py:31-207` (7 endpoints) |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:5,19,61` |
| `get_logger(__name__)` | ✅ SIM | Todos os módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:41,51` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:57-58` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:23,57` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:17` |
| `data/` directory | ✅ SIM | `app/core/config.py:28-30` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11,15` |

### Violações SOLID

1. **SRP**: `_perform_total_cleanup()` (`app/api/admin_routes.py:105-314`) — 310 linhas, 6+ responsabilidades
2. **SRP**: `UserAgentManager` — loading, rotation, quarantine, stats, quality scoring
3. **ISP**: `CeleryTaskInterface` (`app/domain/interfaces.py:129-155`) — `check_workers` não pertence à interface de tarefas
4. **OCP**: `_perform_total_cleanup` usa if/else hardcoded — adicionar target requer modificar função

### Clean Code

- **Dead code**: `app/services/domain_services.py` inteiro (164 linhas) — nunca importado
- **Dead code**: `app/shared/exceptions.py:39-43` — `AudioProcessingError` nunca usada
- **Dead code**: `app/middleware/rate_limiter.py` e `body_size.py` — definidos mas nunca registrados
- **Versão inconsistente**: `config.py:12` = 2.0.0, `main.py:57` = 3.0.0, docker-compose = 1.0.0
- **Duplicação**: `task_failure_handler` e `task_revoked_handler` duplicam padrão Redis
- **Duplicação**: `now_brazil()` fallback em 2 arquivos
- **Teste quebrado**: `tests/test_models.py:5` — importa de `app.models` (caminho errado)
- **Exceção engolida**: `app/api/jobs_routes.py:90-91` — `except Exception` expõe erro ao cliente
- **Fail-open**: `video_downloader.py:142-143` — verificação de espaço em disco falha silenciosamente

### Redis
- Usa `ResilientRedisStore` com circuit breaker ✅
- Jobs serializados via Pydantic com TTL 24h
- **Bug**: Sorted set sem TTL (vazamento de memória quando job expira via setex)
- **Bug**: `list_jobs()` busca TODOS os IDs e deserializa 1 por 1 — O(N) roundtrips

### Celery
- Bom: `download_video_task` com retry, sinais, progress tracking
- Bom: `cleanup_expired_jobs` periódico
- **Problema**: Store instanciado a cada invocation (não reutiliza singleton)
- **Dead code**: Fallback `execute_pipeline_background()` nunca chamado

### Jobs
- Usa `StandardJob` corretamente ✅
- Ciclo de vida completo: queued → processing → completed/failed
- Detecção de órfãos e limpeza periódica
- Idempotência via job ID determinístico

### Docker
- Multi-stage build ✅
- HEALTHCHECK correto ✅

### `.env` vs `.env.example`
- `.env` tem API key real `se2-test-key-2026` (commitado)
- `.env` e `.env.example` idênticos exceto API_KEY

### Testes
- `test_models.py:5` importa de `app.models` (caminho errado)
- Integration tests são stubs (`assert True`)
- Celery tasks sem testes

---

## SE3 — Audio Normalization Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py` |
| `get_settings()` → Pydantic | ⚠️ PARCIAL | Retorna Pydantic mas tem interface `dict` (compat) |
| `GET /` | ✅ SIM | — |
| `GET /health` | ✅ SIM | — |
| Job CRUD | ✅ SIM | — |
| Auth `X-API-Key` | ✅ SIM | — |
| `get_logger(__name__)` | ✅ SIM | — |
| Docker non-root | ✅ SIM | — |
| Docker HEALTHCHECK | ✅ SIM | — |
| Docker ytcaption-network | ✅ SIM | — |
| Docker `env_file` | ✅ SIM | — |
| `data/` directory | ✅ SIM | — |
| `.env` com `${DIVISOR}` | ✅ SIM | — |

### Violações SOLID

1. **SRP**: `main.py` é god file (500+ linhas) — needs decomposition
2. **OCP**: Camada de compatibilidade `dict` em `get_settings()` — interface legada

### Clean Code
- `main.py` precisa ser decomposto (500+ linhas)
- Camada de compatibilidade dict adiciona complexidade desnecessária

### Redis / Celery / Jobs
- Usa shared utilities corretamente ✅
- Bom integração com Celery ✅

---

## SE4 — Audio Transcriber Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:51-61` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:9` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:129-132` |
| `GET /` | ✅ SIM | `app/main.py:67-108` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:28-55` |
| Job CRUD | ✅ SIM | 9 endpoints em `app/api/jobs_routes.py` |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:6,12` |
| `get_logger(__name__)` | ✅ SIM | 58 matches em 27+ módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:80,88` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:93-94` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:37-38` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:22-23` |
| `data/` directory | ✅ SIM | `data/logs/`, `data/uploads/`, `data/models/` |
| `.env` com `${DIVISOR}` | ⚠️ PARCIAL | PORT usa DIVISOR, Redis não tem REDIS_DB separado |

### Violações SOLID

1. **SRP**: `TranscriptionProcessor` (`app/services/processor.py`) — 702 linhas, god class
2. **LSP**: `RedisJobStorage` (`app/infrastructure/storage.py:308-372`) — stub que nunca implementa Redis, todos os métodos delegam para super()

### Clean Code

- **Dead code**: `RedisJobStorage` inteiro (308-372) — stub com TODO
- **Dead code**: `WhisperModelManager` (`app/services/model_manager.py`) — nunca importado
- **Duplicação**: `now_brazil()` fallback em 6+ arquivos
- **Duplicação**: `model_sizes` dict em 3+ arquivos
- **Duplicação**: Resolução de caminhos em `processor.py` e `transcription_service.py`

### Redis
- Usa `ResilientRedisStore` com circuit breaker ✅
- Jobs serializados via Pydantic com TTL 24h
- Sorted set para listagem

### Celery
- `transcribe_audio` task com retry ✅
- Beat schedule para cleanup ✅
- Signal handlers para falhas ✅
- `--pool=solo` correto para GPU

### Jobs
- Usa `StandardJob` corretamente ✅
- State machine com `JobStateUpdater`
- Detecção de órfãos ✅

---

## SE5 — Make Video Clip Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:100-110` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:10` |
| `get_settings()` → Pydantic | ⚠️ PARCIAL | Retorna Pydantic mas `main.py:28,46` usa acesso dict |
| `GET /` | ✅ SIM | `app/main.py:195-222` E `app/api/routes.py:513-538` (DUPLICADO) |
| `GET /health` | ✅ SIM | `app/main.py:122-157` E `app/api/routes.py:480-511` (DUPLICADO) |
| Job CRUD | ✅ SIM | `app/api/routes.py:320-458` |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:29` |
| `get_logger(__name__)` | ✅ SIM | Todos os módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:56-62` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:68-69` |
| Docker ytcaption-network | ❌ NÃO | `docker-compose.yml:9` usa `network_mode: "host"` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:17,39,64` |
| `data/` directory | ✅ SIM | `data/approved/`, `data/raw/`, etc. |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11` |

### Violações SOLID — GRAVES

1. **SRP — CRÍTICO**: `celery_tasks.py` (~1400 linhas) — god file. `_process_make_video_async` sozinho tem ~700 linhas com 8 estágios
2. **OCP**: `celery_tasks.py:396-398` — switch domain/legacy via `if` baseado em env var
3. **LSP**: `MakeVideoJob.create_new` tem assinatura diferente do que `JobManager.create_job` espera
4. **ISP**: `MakeVideoJobStore` expõe CRUD + operacional num só (`find_orphaned_jobs`, `cleanup_expired`, `get_stats`)
5. **DIP**: Celery worker usa `global` state em vez de DI

### Clean Code — GRAVES

- **Endpoints duplicados**: `/` e `/health` definidos tanto no app quanto no router
- **Bare `except:`**: `routes.py:168`, `celery_tasks.py:344` — engolem erros silenciosamente
- **Dead code**: `CreateVideoRequest` definido mas nunca usado
- **Dead code**: `job_manager.py:41-89` — `create_job` definido mas nunca chamado
- **Magic numbers**: `celery_tasks.py:537` (`5.0`, `3600.0`), `:731` (`concat_tolerance = 2.0`)

### Redis
- Usa `ResilientRedisStore` ✅
- **Problema**: API e Celery não compartilham pool de conexão
- Lock manager com `redis.asyncio`

### Celery
- Configuração resiliente (`acks_late`, `reject_on_worker_lost`) ✅
- Beat schedule para cleanup e recuperação de órfãos ✅
- Hard timeout 3600s, soft 3300s

### Jobs
- Usa `StandardJob` corretamente ✅
- 7 stages com `StageInfo`
- Auto-recovery de órfãos a cada 2 min

---

## SE6 — YouTube Search Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:55-64` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:9` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:69-72` |
| `GET /` | ✅ SIM | `app/main.py:168-196` |
| `GET /health` | ✅ SIM | `app/main.py:72-160` |
| Job CRUD | ✅ SIM | `app/api/jobs.py:51-104` |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:25` |
| `get_logger(__name__)` | ✅ SIM | Todos os módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:42-46` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:52-53` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:30,58,86` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:15,43,71` |
| `data/` directory | ✅ SIM | `data/logs/` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11,18` |

### Violações SOLID

1. **SRP**: `YouTubeSearchProcessor` (`app/domain/processor.py:55-298`) — god class com 6 tipos de busca
2. **OCP**: `process_search_job` usa `if/elif` em `SearchType` — novo tipo requer modificar método
3. **LSP — CRÍTICO**: DOIS enums `JobStatus` concorrentes — `app/domain/models.py` vs `app/core/constants.py`
4. **DIP**: `processor.py:30-33` importa diretamente `ytbpy` concreto

### Clean Code — CRÍTICO

- **BUG CRÍTICO**: `app/api/search.py:19` importa `Job` de `app.core.models`, mas `app/api/jobs.py:22` importa `Job` de `app.domain.models` — classes DIFERENTES, causam erros em runtime
- **Dead code**: `app/core/models.py` inteiro — duplica `app/domain/models.py`
- **Dead code**: `StageStatus` e `StageInfo` definidos mas nunca usados
- **Dead code**: `JobStoreInterface` definido mas nunca implementado
- **Duplicação**: 6 endpoints de busca seguem padrão idêntico (~240 linhas duplicadas)
- **Emoji em logs**: `jobs.py:96,101` — pode causar problemas de encoding

### Redis
- Usa `ResilientRedisStore` ✅
- TTL via `os.getenv()` direto (bypass settings) ⚠️
- Admin usa conexão Redis separada para FLUSHDB

### Celery
- Bom design de tasks ✅
- Missing graceful shutdown

### Jobs — NÃO USA shared StandardJob
- **Dois modelos locais concorrentes**: `app/core/models.py:Job` e `app/domain/models.py:Job`
- IDs diferentes: core usa SHA256 16 chars, domain usa SHA256 12 chars com prefixo `ys_`
- Lifecycle local, não shared

### Testes
- Route tests quase inexistentes
- `tests/test_models.py:6` e `tests/test_e2e.py:9` importam de `app.models` (caminho errado)

---

## SE7 — Audio Generation Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:38-47` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:9` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:41-43` |
| `GET /` | ✅ SIM | `app/api/health_routes.py:13-16` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:27-56` |
| Job CRUD | ✅ SIM | `app/api/jobs_routes.py` (5 endpoints) |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:14,46` |
| `get_logger(__name__)` | ✅ SIM | Todos os módulos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:48-53` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:57-58` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:31-32` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:22-23` |
| `data/` directory | ✅ SIM | `data/models/`, `data/voices/`, `data/outputs/`, `data/temp/` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11,18` |

### Violações SOLID

1. **SRP**: `TTSGenerator.generate()` (`app/services/generator.py:22-145`) — validação, chunking, geração, assembly, I/O, progresso, erros
2. **SRP**: `ChatterboxModelManager` — download, device, load/unload, generate, status

### Clean Code

- **Dead code**: `app/core/constants.py:38-43` — 4 constantes DRAMATIC/NEUTRAL nunca usadas
- **Dead code**: `app/api/schemas.py:10-17` — `VoiceProfileResponse` nunca usado
- **Duplicação**: Redis URL resolvida em 4 lugares diferentes
- **Magic numbers**: `audio_utils.py:125` (`32767`), `model_manager.py:28` (`24000`), `generator.py:30` (`500ms`)
- **Fallback enganoso**: `app/domain/models.py:9-50` — `StandardJob` fallback com menos features
- **Private member**: `voice_seeder.py:81` acessa `voice_manager._store.save_profile()`

### Redis — FRACO ⚠️

- **NÃO usa `ResilientRedisStore`** — cliente Redis custom frágil
- Sem circuit breaker, sem connection pooling, sem retry
- `_FakeRedis` ignora TTL (testes passam mas prod pode falhar)
- Cada Celery task cria sua própria instância `JobRedisStore`

### Celery — PARCIAL

- Tasks: `generate_audio`, `cleanup_expired_jobs`
- **Fallback quebrado**: Loga warning quando Celery indisponível mas job NUNCA é processado
- Não usa `CallbackTask` do shared
- Não usa `submit_task()` do shared

### Jobs — PARCIAL

- `AudioGenerationJob` extends `StandardJob` ✅
- **Fallback perigoso**: Se import do shared falha, usa versão local com menos features
- Não usa `JobManager` nem `create_job_router()`

### Segurança — CRÍTICA

- **`.env` contém token HuggingFace commitado no repo** (precisa mover para variável de ambiente segura)

---

## SE8 — Image Generation Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:65-73` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:9` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:65-67` |
| `GET /` | ✅ SIM | `app/api/health_routes.py:18-33` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:36-54` |
| Job CRUD | ⚠️ PARCIAL | Query endpoints existem, **sem DELETE method** |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:13` |
| `get_logger(__name__)` | ⚠️ PARCIAL | Apenas `main.py` usa `get_logger`, resto usa `logging.getLogger` |
| Docker non-root | ✅ SIM | `docker/Dockerfile:33-37` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:41-42` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:29,66` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:17` |
| `data/` directory | ✅ SIM | `data/outputs/`, `data/models/`, `data/temp/` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11,22-26` |

### Violações SOLID — GRAVES

1. **SRP — CRÍTICO**: `worker.py` (687 linhas) — 8+ responsabilidades
2. **SRP**: `AsyncTask` dataclass (`task_models.py:90-199`) — 70+ campos
3. **OCP**: `get_task_type()` usa isinstance chains
4. **ISP**: `AsyncTask` força todos a depender de 70+ campos
5. **DIP**: `worker.py:508-509` importa pipeline concreto diretamente

### Clean Code

- **Dead code**: 6 enums duplicados entre `models.py` e `enums.py`
- **Dead code**: `_get_style_loras()` sempre retorna lista vazia
- **Bug**: `.env.example` diz "SE9" em vez de "SE8"
- **Bug**: `tests/conftest.py:10` — `OUTPUT_DIR="/tmp/se9-test-outputs"` (errado)
- **Bug**: `tests/api/conftest.py:17` — referencia `se9_api_key` em vez de `se8_api_key`
- **Magic numbers**: `worker.py:558` (20, 70), `pipeline.py:512` (0.834), `pipeline.py:711` (1.4)

### Redis — NÃO USA

- Jobs armazenados em memória (`TaskQueue` com listas Python)
- Redis apenas como broker do Celery
- Sem persistência de jobs, sem TTL, sem cleanup além do Celery

### Celery — PARCIAL

- Tasks definidas mas API routes usam `TaskQueue` em memória
- Worker primário é thread in-process, não Celery worker

### Jobs — NÃO USA shared StandardJob

- Modelos próprios: `QueueTask`, `AsyncTask`
- In-memory apenas, sem Redis
- História limitada a 64 itens

### `.env` vs `.env.example`
- `.env.example` diz "SE9" em vez de "SE8"
- API key `se8-test-key-2026` no `.env`

---

## SE9 — Make Video IMG Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:43` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:10` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:57` |
| `GET /` | ✅ SIM | `app/api/routes.py:21` |
| `GET /health` | ✅ SIM | `app/api/health_routes.py:12` |
| Job CRUD | ⚠️ PARCIAL | Hand-written, não shared router |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:22` |
| `get_logger(__name__)` | ❌ NÃO | Usa `logging.getLogger(__name__)` em todos |
| Docker non-root | ✅ SIM | `docker/Dockerfile:10` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:30` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:19` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:10` |
| `data/` directory | ✅ SIM | `data/outputs/`, `data/logs/` |
| `.env` com `${DIVISOR}` | ❌ NÃO | `PORT=8009` hardcoded |

### Violações SOLID — GRAVES

1. **SRP — CRÍTICO**: `VideoPipeline` (`services/pipeline.py:28`) — audio, image, video, stages, Redis, webhooks
2. **DIP — CRÍTICO**: 4 arquivos instanciam `VideoJobStore()` no module level — sem DI
3. **OCP**: Enums duplicados `VideoJobStatus` e `StageStatus` não extensíveis pelo shared

### Clean Code — CRÍTICOS

- **KEYS command**: `redis_store.py` usa `KEYS rbg_job:*` — O(N) bloqueia Redis em produção
- **Zero deps pinned**: `requirements.txt` — todas as dependências sem versão
- **`.env.example` contém API keys reais** — problema de segurança
- **Sem Makefile**
- **Magic numbers**: `video_assembler.py:64` (`title_duration = 3.0`), `ffmpeg_utils.py:67,79` (font size 52, boxborderw 20)

### Redis — CRÍTICO ⚠️⚠️

- **NÃO usa `ResilientRedisStore`** — cliente Redis customizado
- **`KEYS` command** em produção — bloqueia Redis
- Sem connection pooling, sem circuit breaker
- `_FakeRedis` não implementa `setex`
- TTL hardcoded 2 dias

### Celery — NÃO USA

- Bypass total — usa `VideoWorker` threaded customizado
- Sem task queue management
- Sem graceful fallback

### Jobs — NÃO USA shared infrastructure

- Modelo próprio `VideoJob` em vez de `StandardJob`
- Store próprio `VideoJobStore` em vez de `JobRedisStore`
- Routes hand-written em vez de `create_job_router()`

### Testes
- Sem Makefile, sem estrutura de testes padronizada

---

## SE10 — Clothes Segmentation Service

### Conformidade com Padrões

| Critério | Status | Evidência |
|----------|--------|-----------|
| `create_service_app()` | ✅ SIM | `app/main.py:43` |
| `BaseServiceSettings` | ✅ SIM | `app/core/config.py:13` |
| `get_settings()` → Pydantic | ✅ SIM | `app/core/config.py:81` |
| `GET /` | ✅ SIM | `app/api/health.py:17` |
| `GET /health` | ✅ SIM | `app/api/health.py:26` |
| Job CRUD | ✅ SIM | `app/api/jobs.py` (4 endpoints) |
| Auth `X-API-Key` | ✅ SIM | `app/main.py:21` |
| `get_logger(__name__)` | ⚠️ PARCIAL | `main.py` e `segmentor.py` usam `get_logger`; `jobs.py:11` usa `logging.getLogger` |
| Docker non-root | ✅ SIM | `docker/Dockerfile:49` |
| Docker HEALTHCHECK | ✅ SIM | `docker/Dockerfile:53` |
| Docker ytcaption-network | ✅ SIM | `docker/docker-compose.yml:37` |
| Docker `env_file` | ✅ SIM | `docker/docker-compose.yml:19` |
| `data/` directory | ✅ SIM | `data/inputs/`, `data/outputs/`, `data/temp/` |
| `.env` com `${DIVISOR}` | ✅ SIM | `.env:10-11` |

### Violações SOLID

1. **SRP**: `segment.py:30-58` — validação inline no handler
2. **DIP**: `_get_job_manager()` usa imports diretos de classes concretas

### Clean Code

- **`jobs.py:11`**: Usa `logging.getLogger` em vez de `get_logger`
- **Duplicate model**: `domain/models.py:57-63` — `ErrorResponse` duplica shared
- **Module-level executor**: `segment.py:12` — avaliado no import time

### Redis
- Usa `ResilientRedisStore` com circuit breaker ✅
- TTL configurável via `cache_ttl_hours`
- Conexão pooled ✅

### Celery
- Síncrono via `ThreadPoolExecutor` — apropriado para ML CPU-bound

### Jobs
- Usa shared `JobManager` e `JobRedisStore` ✅
- Usa `StandardJob` via `JobManager` ✅
- **Poderia usar `create_job_router()`** em vez de routes hand-written

---

## Tabela Comparativa Cross-Service

| Serviço | `create_service_app` | `BaseServiceSettings` | `get_settings()` Pydantic | `GET /` | `GET /health` | Job CRUD | Auth | `get_logger` | Docker non-root | HEALTHCHECK | ytcaption-network | `env_file` | `data/` | `${DIVISOR}` |
|---------|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|
| SE1 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE2 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE3 | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE4 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| SE5 | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| SE6 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE7 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE8 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE9 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| SE10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Uso de Redis por Serviço

| Serviço | ResilientRedisStore | Circuit Breaker | Connection Pool | Store Customizado | `KEYS` command |
|---------|:----:|:----:|:----:|:----:|:----:|
| SE1 | ✅ | ✅ | ✅ | ⚠️ TTL bug | ❌ |
| SE2 | ✅ | ✅ | ✅ | ❌ | ❌ |
| SE3 | ✅ | ✅ | ✅ | ❌ | ❌ |
| SE4 | ✅ | ✅ | ✅ | ❌ | ❌ |
| SE5 | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| SE6 | ✅ | ✅ | ✅ | ❌ | ❌ |
| SE7 | ❌ | ❌ | ❌ | ✅ Custom | ❌ |
| SE8 | ❌ | ❌ | ❌ | N/A (in-memory) | N/A |
| SE9 | ❌ | ❌ | ❌ | ✅ Custom | ❌ |
| SE10 | ✅ | ✅ | ✅ | ❌ | ❌ |

---

## Uso de Celery por Serviço

| Serviço | Usa Celery | Tasks Definidas | CallbackTask | submit_task() | Graceful Fallback |
|---------|:----:|:----:|:----:|:----:|:----:|
| SE1 | ❌ | 0 | ❌ | ❌ | BackgroundTasks |
| SE2 | ✅ | 2 | ❌ | ❌ | ⚠️ Dead code |
| SE3 | ✅ | 2+ | ❌ | ❌ | ✅ |
| SE4 | ✅ | 3 | ❌ | ❌ | ✅ |
| SE5 | ✅ | 1+3 beat | ❌ | ❌ | ✅ acks_late |
| SE6 | ✅ | 2 | ❌ | ❌ | ⚠️ |
| SE7 | ✅ | 2 | ❌ | ❌ | ⚠️ Quebrado |
| SE8 | ⚠️ | 3 | ❌ | ❌ | In-memory thread |
| SE9 | ❌ | 0 | ❌ | ❌ | VideoWorker custom |
| SE10 | N/A | 0 | ❌ | N/A | ThreadPoolExecutor |

---

## Uso de Jobs (StandardJob) por Serviço

| Serviço | Usa StandardJob | JobManager | create_job_router | JobRedisStore | Lifecycle Completo |
|---------|:----:|:----:|:----:|:----:|:----:|
| SE1 | ⚠️ Dual model | ⚠️ | ❌ | ✅ | ⚠️ |
| SE2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE3 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE4 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SE5 | ✅ | ⚠️ Unused | ❌ | ⚠️ | ✅ |
| SE6 | ❌ Local | ❌ | ❌ | ❌ | ⚠️ |
| SE7 | ⚠️ Fallback | ❌ | ❌ | ❌ | ⚠️ |
| SE8 | ❌ Local | ❌ | ❌ | ❌ | ⚠️ |
| SE9 | ❌ Local | ❌ | ❌ | ❌ | ⚠️ |
| SE10 | ✅ | ✅ | ❌ | ✅ | ✅ |

---

## Violações SOLID por Serviço

| Serviço | SRP | OCP | LSP | ISP | DIP |
|---------|:----:|:----:|:----:|:----:|:----:|
| SE1 | ❌ God class | ⚠️ | ✅ | ❌ | ⚠️ |
| SE2 | ❌ 310-line method | ❌ | ✅ | ⚠️ | ✅ |
| SE3 | ❌ God file | ❌ | ✅ | ✅ | ✅ |
| SE4 | ❌ God class | ✅ | ❌ Stub | ✅ | ✅ |
| SE5 | ❌ 700-line func | ❌ | ❌ | ❌ | ❌ |
| SE6 | ❌ God class | ❌ | ❌ Dual enums | ⚠️ | ❌ |
| SE7 | ❌ God method | ✅ | ⚠️ FakeRedis | ✅ | ✅ |
| SE8 | ❌ 687-line module | ❌ | ⚠️ | ❌ | ❌ |
| SE9 | ❌ God class | ❌ | ✅ | ✅ | ❌ |
| SE10 | ⚠️ Inline | ✅ | ✅ | ✅ | ⚠️ |

---

## Problemas de Segurança

| Serviço | Problema | Severidade |
|---------|----------|-----------|
| SE1 | API key real no `.env` | 🟡 Médio |
| SE2 | API key real no `.env` | 🟡 Médio |
| SE5 | `network_mode: "host"` | 🟡 Médio |
| SE7 | **Token HuggingFace real no `.env`** | 🔴 Crítico |
| SE7 | `.env` commitado com secrets | 🔴 Crítico |
| SE8 | `.env.example` com wrong service name | 🟡 Médio |
| SE9 | `.env.example` contém API keys reais | 🔴 Crítico |

---

## Prioridades de Correção

### 🔴 Crítico (Imediato)

1. **SE9**: Substituir `VideoJobStore`/`VideoJob` por shared `JobRedisStore`/`StandardJob`
2. **SE9**: Eliminar `KEYS` command — usar sorted set como shared store
3. **SE9**: Pin dependências em `requirements.txt`
4. **SE9**: Fix `.env.example` — remover keys reais
5. **SE7**: Remover token HuggingFace de `.env`, adicionar ao `.gitignore`
6. **SE6**: Corrigir bug de import dual `Job` (`core/models` vs `domain/models`)

### 🟠 Alto

7. **SE5**: Decompor `celery_tasks.py` (1400+ linhas) em módulos menores
8. **SE5**: Remover endpoints `/` e `/health` duplicados
9. **SE5**: Substituir `network_mode: "host"` por bridge networking
10. **SE8**: Substituir `QueueTask` em memória por `StandardJob` + `JobRedisStore`
11. **SE7**: Migrar para `ResilientRedisStore` com circuit breaker
12. **SE7**: Implementar `JobManager` e `create_job_router()`

### 🟡 Médio

13. **SE1**: Remover `pipeline_routes.py` dead code e `_legacy/` directory
14. **SE1**: Fix bug TTL hardcoded em `redis_store.py`
15. **SE1**: Implementar DELETE endpoint
16. **SE3**: Decompor `main.py` (500+ linhas)
17. **SE4**: Decompor `TranscriptionProcessor` (702 linhas)
18. **SE6**: Decompor `YouTubeSearchProcessor`
19. **SE8**: Corrigir `.env.example` (diz SE9 em vez de SE8)
20. **SE10**: Usar `create_job_router()` em vez de hand-written routes

### 🟢 Baixo

21. Consolidar `now_brazil()` fallback em local único
22. Remover dead code em todos os serviços
23. Padronizar versionamento (evitar drift entre config/main/docker)
24. Adicionar testes unitários nos serviços sem cobertura

---

*Data da Auditoria: Junho 2026*
*Escopo: 10 microserviços (SE1-SE10)*
*Método: Investigação fase a fase com análise de código fonte*