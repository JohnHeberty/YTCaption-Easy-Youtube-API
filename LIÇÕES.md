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
