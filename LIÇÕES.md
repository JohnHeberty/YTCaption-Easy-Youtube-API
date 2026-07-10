# LIÇÕES.md — Lições Aprendidas (Cross-Service)

**Última atualização:** 2026-07-10
**Nota:** Lições específicas do pipeline NSFW (SE11) foram migradas para `services/se11-clothes-removal/docs/LICOES-NSFW.md`

---

## 23. GPU memory management — SE10+SE8 (2026-07-04)

**Problema:** SE10 mantinha modelos carregados 120s (idle timer), overlap com SE8 causava CUDA corruption.

**Solução:**
- SE10: `unload_all_models()` imediatamente após cada request no route handler
- SE8: `del sd` em checkpoint.py libera ~6GB RAM; `unload_all_models()` no finally block
- SE8: `MODEL_IDLE_TIMEOUT=60` descarga modelos após 60s idle

**Lições:**
- **`torch.cuda.empty_cache()` NÃO funciona para liberar VRAM** — só limpa cache do allocator, não descarrega pesos
- **`unload_all_models()` do model_management é o correto** — descarrega pesos do VRAM
- **`del sd` + `del model` + `gc.collect()`** libera RAM do Python, mas o memory allocator pode não retornar ao OS
- **VRAM overlap entre containers é silenciosamente destrutivo** — CUDA handle corrompido, retorno HTTP 200 com lista vazia
- **SE10 idle deve ser ZERO** — não há razão para manter modelos carregados entre requests

---

## 36. GroundingDINO + SAM2 + BiRefNet são LEGADO no SE10 — substituídos por SegFormer B2

**Data:** 2026-07-05
**Serviço:** SE10 (clothes-segmentation)

### Contexto
O SE10 carregava 4 detectores na startup: GroundingDINO, SAM2, YOLO11-seg, BiRefNet, e SegFormer B2. Dos 4, apenas SegFormer e YOLO funcionavam.

### Problema
- **GroundingDINO**: Precisa de CUDA custom ops (`_C`) que estão quebradas neste container. Falha toda vez com `name '_C' is not defined`.
- **SAM2**: Só é usado quando GroundingDINO fornece bounding boxes sem masks. Como SegFormer sempre retorna masks pixel-level, SAM2 é **sempre pulado**.
- **BiRefNet**: Falha no init com CUDNN OOM (822MB buffer não cabe).

### Solução
1. **Desativar** carregamento de GroundingDINO, SAM2 e BiRefNet em `_load_gpu_models()`
2. **Remover** dead code paths no `segment()` e `ensemble_detector`
3. **Remover** volume mounts desnecessários no docker-compose
4. **Manter** YOLO11-seg (funciona, usado no ensemble person mode)
5. **Manter** SegFormer B2 (PRIMARY detector, único que funciona)

### Resultado
- RAM SE10 idle: 1.9GB → **1.0GB** (economia ~900MB)
- Startup sem erros (antes: ~50 linhas de warnings/errors)
- Detecção funciona igual (SegFormer + YOLO ensemble)

### Lição
Quando um detector é claramente superior e os outros falham/são ignorados, **remover o carregamento** reduz memória, startup time e complexidade. Manter código comentado para reativação futura se necessário.

### Detalhes técnicos
- **GroundingDINO** (661MB checkpoint): Detecção por texto ("person", "woman") → bounding boxes. Substituído por SegFormer (classificação pixel-level, 18 classes)
- **SAM2** (148MB checkpoint): Pega boxes do GroundingDINO → máscaras. Substituído por SegFormer (já retorna masks)
- **BiRefNet** (800MB ONNX): Person segmentation binária. Substituído por SegFormer (multi-classe, mais granular)
- **YOLO11-seg** (~50MB): Funciona, mantido para person detection no ensemble mode
- **SegFormer B2** (~300MB): 18 classes, pixel-level, funciona perfeitamente

### Arquivos modificados
- `services/se10-clothes-segmentation/app/services/segmentor.py`
- `services/se10-clothes-segmentation/app/services/ensemble_detector.py` (reescrito do zero)
- `services/se10-clothes-segmentation/app/services/birefnet_detector.py` (DELETADO)
- `services/se10-clothes-segmentation/app/core/constants.py`
- `services/se10-clothes-segmentation/app/main.py`
- `services/se10-clothes-segmentation/app/api/routes/segment.py`
- `services/se10-clothes-segmentation/app/api/routes/health.py`
- `services/se10-clothes-segmentation/app/services/yolo_detector.py`
- `services/se10-clothes-segmentation/docker/docker-compose.gpu.yml`
- `services/se10-clothes-segmentation/docker/docker-compose.yml`

### NÃO remover
- Checkpoints `.pth` do disco (podem ser úteis se container for reconstruído com CUDA ops corretos)

---

## 37. SE8 Memory Leak — Duas sessões de model management precisam de cleanup duplo

**Data:** 2026-07-05
**Serviço:** SE8 (image-generation)

### Problema
Após job completar, SE8 retinha ~6.5GB GPU e ~32GB RAM. Investigação revelou DUAS sessões independentes de model management:
1. **ComfyUI** (`ldm_patched.modules.model_management.current_loaded_models`) — gerencia UNet, VAE, ControlNet
2. **SE8 custom** (`app.services.model_manager.ModelManager._loaded_models`) — gerencia CLIP, Expansion, IP-Adapter

O worker finally block SÓ chamava `unload_all_models()` do ComfyUI. O SE8 model_manager nunca era limpo.

### Solução
Worker finally block agora faz cleanup completo:
```python
# 1. Pipeline cache cleanup
pipeline.loaded_controlnets.clear()
pipeline.clip_cond_cache.clear()

# 2. SE8 model_manager (CLIP, Expansion, IP-Adapter)
from app.services.model_manager import get_model_manager
mgr = get_model_manager()
mgr.unload_all()

# 3. ComfyUI (UNet, VAE, ControlNet)
from ldm_patched.modules.model_management import unload_all_models
unload_all_models()

# 4. System cleanup
gc.collect()
ctypes.CDLL("libc.so.6").malloc_trim(0)
torch.cuda.empty_cache()
```

### Resultado
- GPU: 6469→576 MiB (pós-job, ~2min delay para CUDA release)
- RAM SE8: 32GB→431 MB

### Lição
Quando um sistema usa frameworks diferentes para gerenciar modelos (ComfyUI + custom), SEMPRE limpar ambos no cleanup. Um sem o outro = memory leak.

### Referências
- ComfyUI: `ldm_patched/modules/model_management.py` — `current_loaded_models` list, `unload_all_models()`
- SE8: `app/services/model_manager.py` — `_loaded_models` list, `unload_all()`
- Worker: `app/services/worker.py` — finally block

---

## 38. Field mapping bugs entre API e Worker — chave de dictionary mismatch

**Data:** 2026-07-10
**Serviço:** SE8 (image-generation)

### Problema
Três campos tinham nomes diferentes entre `req_to_params` (API) e `_build_async_task` (worker):
- `save_extension` (API) → `output_format` (worker) — sempre "png"
- `save_meta` (API) → `save_metadata_to_images` (worker) — sempre False
- `meta_scheme` (API) → `metadata_scheme` (worker) — sempre "fooocus"

### Lição
- **Quando um dict passa por camadas intermediárias, o nome da chave deve ser idêntico** — qualquer renomeação silenciosa causa default value
- **Testes não detectaram porque testavam apenas o output HTTP**, não o estado interno do worker
- **Bug de 4+ anos** — nunca foi reportado porque o default era aceitável (png, fooocus, False)

### Fix
- `_build_async_task`: trocar `req.get("output_format")` → `req.get("save_extension")`
- `_build_async_task`: trocar `adv.get("save_metadata_to_images")` → `req.get("save_meta")`
- `_build_async_task`: trocar `adv.get("metadata_scheme")` → `req.get("meta_scheme")`

---

## 37. SE8 API Refactoring — Schemas, response_model, Field descriptions

**Data:** 2026-07-10
**Serviço:** SE8 (image-generation)

### Padrão estabelecido
Todos os services devem seguir o padrão SE9/SE11:
1. `app/api/schemas.py` — response schemas separados do domain
2. `ErrorResponse` unificado para todos os erros
3. `response_model=` em TODOS os endpoints (exceto streaming/variável)
4. `Field(description=...)` em TODOS os campos Pydantic
5. Handler global de exceções em `app/main.py`

### Lições
- **`response_model=` não funciona em endpoints com return type variável** — SE8 V1/V2 generation routes retornam `Response | dict | list[dict]` dependendo do modo (sync/async/streaming). Solução: deixar sem `response_model` nesses casos, adicionar apenas nos endpoints de retorno fixo.
- **Testes que patcham `module.os.path`** — se o código usa `__import__("os")` ou `import os as _os`, o patch não funciona. Usar `import os` no nível do módulo para que patches funcionem.
- **`face_routes.py` retornava `dict` via `.model_dump()`** — quando `response_model=FaceRestoreResponse` está definido, retornar o modelo diretamente (não `.model_dump()`) para validação automática.
- **DEFAULT_LORAS duplicado** — `models.py` (Lora instances) + `constants.py` (dict literals) com mesmos dados. Consolidação: manter APENAS em `models.py`.

---

## 41. Testes precisam de env vars em conftest.py (2026-07-10)

**Problema:** Quando pytest roda da raiz do repo (`python3 -m pytest services/seX/tests/`), o `cwd` é a raiz e o `.env` do serviço não é encontrado pelo pydantic-settings. Settings com `Field(...)` (required) falham com `ValidationError: missing`.

**Serviços afetados:** SE4, SE6, SE7, SE11

**Solução:** Adicionar `os.environ.setdefault()` no topo de `tests/conftest.py` de cada serviço, ANTES de qualquer import que dispare settings loading:
```python
os.environ.setdefault("APP_NAME", "Service Name")
os.environ.setdefault("REDIS_URL", "redis://192.168.1.110:6379/X")
```

**Lições:**
- **Sempre setar `APP_NAME` e `REDIS_URL`** em conftest.py — são os campos required do `BaseServiceSettings`.
- **Rodar pytest do diretório do serviço** é a forma mais robusta — `.env` é encontrado naturalmente.
- **Se rodar da raiz**, conftest env vars são essenciais — sem elas, TODOS os testes do serviço falham na collection phase.
- **Testes de e2e/integration** que dependem de Redis real ou serviços live continuam falhando independente do env var.

---

## 42. Pydantic datetime vs str em API responses (2026-07-10)

**Problema:** `model_dump()` retorna `datetime` objects, mas `response_model` schemas definem `created_at: str`. Pydantic v2 lança `ValidationError: Input should be a valid string`.

**Serviço:** SE7 (audio-generation), jobs_routes.py

**Solução:** Converter explicitamente antes de instanciar o schema:
```python
data = job.model_dump()
for key in ("created_at", "started_at", "completed_at"):
    val = data.get(key)
    if hasattr(val, "isoformat"):
        data[key] = val.isoformat()
return JobDetailResponse(**data)
```

**Lições:**
- **Usar `datetime` nos schemas** quando possível (evita conversão manual).
- **Se str for necessário** (compatibilidade), converter via `.isoformat()` antes de `model_dump()`.
- **Testes de response schema** devem validar tipos, não só status code.

---

## 43. Lazy auth dependency for testable closures (2026-07-10)

**Problema:** `create_api_key_dependency(api_key=settings.se8_api_key)` captura o valor no import time. Patchar `settings.se8_api_key` depois não tem efeito — o closure já tem o valor.

**Solução:** Aceitar `Callable[[], str|None]` além de `str|None`:
```python
async def _verify(request: Request) -> None:
    resolved_key = api_key() if callable(api_key) else api_key
    if not resolved_key: return
    ...
```
Uso: `create_api_key_dependency(api_key=lambda: settings.se8_api_key)`

**Lição:** Sempre que uma dependency captura um valor estático no factory time, oferecerCallable para lazy resolution. Isso torna testável sem dependency_overrides.

---

## 44. Module-level Redis connection blocks test collection (2026-07-10)

**Problema:** SE6 `celery_tasks.py` criava `RedisJobStore(redis_url=...)` no nível do módulo. Qualquer import de `app.infrastructure` (incluindo testes) tentava conectar ao Redis.

**Solução:** Lazy initialization com `_get_job_store()` / `_get_processor()` globals:
```python
_job_store: RedisJobStore | None = None
def _get_job_store() -> RedisJobStore:
    global _job_store
    if _job_store is None:
        _job_store = RedisJobStore(redis_url=...)
    return _job_store
```

**Lição:** Nunca criar conexões de rede no nível do módulo. Sempre usar lazy init para infraestrutura (Redis, DB, Celery). O import de um módulo Python deve ser efeito colateral zero.

---

## 45. MockRedis.create_job_store still creates real connection (2026-07-10)

**Problema:** `MockRedis.create_job_store(YouTubeSearchJobStore)` chama o construtor real que conecta ao Redis, depois substitui `store.redis` por fakeredis. O construtor já falhou.

**Solução:** Usar MagicMock puro no conftest em vez de `MockRedis.create_job_store`:
```python
mock = MagicMock()
mock.redis = MagicMock()
mock.redis.ping.return_value = True
```

**Lição:** Se o construtor de uma classe tem efeitos colaterais (conexão, ping), um mock puro é mais seguro que instanciar a classe real + patch posterior.

---

## 46. sys.exit(1) em testes mata o pytest runner (2026-07-10)

**Problema:** Testes SE5 usavam `sys.exit(1)` em vez de `pytest.fail()`. O `sys.exit` mata o processo inteiro, impedindo pytest de coletar/reportar resultados.

**Solução:** Substituir todas as ocorrências por `pytest.fail("reason")`.

**Lição:** Nunca usar `sys.exit()` dentro de testes. Sempre usar `pytest.fail()`, `pytest.skip()`, ou `assert`. O `sys.exit` é para CLI entry points, não para testes.
