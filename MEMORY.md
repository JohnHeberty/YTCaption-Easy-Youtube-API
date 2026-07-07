# Estado Atual — Monorepo YTCaption

## Última sessão (2026-07-07)

### 🟢 SOLID Phase 4 — Config Extensível concluído (2026-07-07)

**Tarefas executadas:**
4.1 LoRA weights e NSFW prompt configuráveis via YAML:
  - `configs/nsfw_production.yaml` e `configs/nsfw_experimental.yaml` criados
  - `NSFWConfig` frozen dataclass e `get_nsfw_config()` loader em `_helpers.py`
  - Loader lê YAML com fallback hardcoded quando arquivo ausente ou malformado
  - Ambos pipelines usam `get_nsfw_config(profile)` em vez de constantes hardcoded
  - `pyyaml>=6.0` adicionado ao `requirements.txt`
  - Dockerfile copia `configs/`; docker-compose monta para dev iteration
4.2 Registry pattern SE8 worker — DEFERRED (fora do escopo).
4.3 `segformer_detector.py`: `close_kernel_size` parametrizável (default=120).

**Arquivos alterados:** `_helpers.py`, `pipeline_nsfw.py`, `pipeline_nsfw_experimental.py`, `segformer_detector.py`, `configs/nsfw_production.yaml` (novo), `configs/nsfw_experimental.yaml` (novo), `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `test_helpers.py`.
**Resultado:** +271 linhas, 9 arquivos, todos os testes passando (SE11: 58, SE10: 62).
**Commits:** `489efd84` (fase 4 inicial), `d9bc28b7` (YAML config refactor), `70aa132f` (LoRA duplication fix).

### 🟢 Hardcoded LoRA duplication fix (2026-07-07)

**Problema:** `http_client.py` tinha LoRAs hardcoded (NsfwPov=0.2) como fallback em `inpaint()`, contradizendo o YAML config. `pipeline.py` (rota /jobs) usava esses LoRAs sem saber.

**Solução:**
- `loras` agora é obrigatório em `inpaint()` — `ValueError` se `None`
- `LORAS_CLOTHES` adicionado em `_helpers.py` (NsfwPov=0.2, detail=0.8)
- `pipeline.py` importa e passa `LORAS_CLOTHES` explicitamente
- Todas as 3 rotas agora especificam LoRAs explicitamente:
  - `/jobs` → `LORAS_CLOTHES` (leve)
  - `/jobs/nsfw` → `get_nsfw_config('production').loras` (full NSFW)
  - `/jobs/nsfw-test` → `get_nsfw_config('experimental').loras` (teste)

**Arquivos:** `http_client.py`, `_helpers.py`, `pipeline.py`. Commit: `70aa132f`.

### 🟢 Hardcoded values cleanup (2026-07-07)

**Problema:** 28 hardcoded high-severity values encontrados no scan. Principais:
- `inpaint_respective_field`: 3 valores diferentes (0.85, 0.618, 0.55)
- Upload size: 20MB em routes.py vs 50MB em constants.py
- `base_model`: juggernautXL em models.py/http_client.py vs lustify nos pipelines
- `max_attempts`, `base_strength`, `faceid_weight`: hardcoded em ambos pipelines

**Solução:**
1. `inpaint_respective_field`: adicionado ao YAML config + NSFWConfig (prod=0.618, exp=0.55)
2. Upload size: routes.py agora usa `MAX_FILE_SIZE_MB` de constants.py (50MB)
3. `base_model`: unificado para `lustifySDXLNSFW_v20-inpainting.safetensors` em todos os lugares
4. `max_attempts`, `base_strength`, `faceid_weight`: movidos para YAML config

**Arquivos:** `routes.py`, `models.py`, `http_client.py`, `_helpers.py`, `pipeline_nsfw.py`, `pipeline_nsfw_experimental.py`, `nsfw_production.yaml`, `nsfw_experimental.yaml`. Commit: `6ace3f3b`.

### 🟢 SOLID Phase 3 — Interfaces e DIP concluído (2026-07-07)

**Tarefas executadas:**
3.1 `shared/protocols.py` criado com 10 Protocol classes: DetectorProtocol, SegmentorProtocol, InpaintClientProtocol, UpscaleClientProtocol, FaceRestoreClientProtocol, SE8ClientProtocol, SE10ClientProtocol, JobStoreProtocol, PoseDetectorProtocol, FaceDetectorProtocol, ServiceClientProtocol.
3.2 SE8ClientProtocol combina Inpaint/Upscale/FaceRestore — consumers podem depender só da capability necessária.
3.3 ClothesRemovalJobStore conforma a JobStoreProtocol (duck typing estrutural).
3.4 EnsembleDetector usa DetectorProtocol para type hints.

**Arquivos alterados:** `shared/protocols.py` (novo, 221 linhas), `ensemble_detector.py`, `http_client.py`, `redis_store.py`.
**Resultado:** +236 linhas, 4 arquivos, todos os testes passando (SE11: 51, SE10: 62).
**Commit:** `30c190bf`.

### 🟢 SOLID Phase 2 — Decompose God Functions concluído (2026-07-07)

**Tarefas executadas:**
2.1 `detect_person_with_fallbacks()` extraído para `_helpers.py` — 3 fallback strategies (retry→GrabCut→face-ellipse), ~170 linhas duplicadas → função async compartilhada.
2.2 `upscale_result()` + `restore_face()` extraídos para `_helpers.py` — lógica SE8 compartilhada.
2.3 `segment()` decomposto em 5 sub-métodos: `_empty_result()`, `_detect()`, `_filter_detections()`, `_annotate()`, `_build_objects()`.
2.4 SE8 inner classes (FaceIDProj/FaceIDIPAdapter) — DEFERRED (menor prioridade, maior risco).

**Arquivos alterados:** `_helpers.py` (+242), `pipeline_nsfw.py` (-173), `pipeline_nsfw_experimental.py` (-196), `segmentor.py` (refactored).
**Resultado:** -99 linhas líquidas, 4 arquivos, todos os testes passando (SE11: 11, SE10: 46).
**Commit:** `182cefa5`.

### 🟢 SOLID Testes — Cobertura para Phase 1+2 (2026-07-07)

**Novos testes criados:**
- `services/se11-clothes-removal/tests/unit/test_helpers.py` — 40 testes para `_helpers.py`
- `services/se10-clothes-segmentation/tests/unit/test_segmentor_methods.py` — 17 testes para sub-métodos de `segmentor.py`
**Total:** 113 testes passando (51 SE11 + 62 SE10). Commit `a5b2b99a`.

### SOLID Phase 1 — Quick Wins concluído (2026-07-07)

**Tarefas executadas:**
1.1 `_helpers.py` expandido: funções duplicadas (`decode_image`, `to_data_uri`, `strip_data_uri`, `fix_b64_padding`, `combine_masks`, `detect_skin_hsv`, `compute_composite_score`) + `ScoringWeights` dataclass + constantes `CLOTHES_CLASSES`, `DEFAULT_CLOTHES_NEGATIVE`.
1.2 Magic numbers `{4,5,6,7}` → `CLOTHING_IDS` (3 ocorrências em segmentor.py).
1.3 Scoring weights → `ScoringWeights` frozen dataclass em `_helpers.py`.
1.4 `gc.collect()+malloc_trim()` → `_cleanup_memory()` static method (3 blocos duplicados).
1.5 `BODY_IDS` deletado (IDs 18-19 fora de range, unused).

**Arquivos alterados:** `_helpers.py`, `pipeline_nsfw.py`, `pipeline_nsfw_experimental.py`, `pipeline.py`, `http_client.py`, `segmentor.py`, `segformer_detector.py`, + 2 test fixes.
**Resultado:** -157 linhas líquidas, 9 arquivos, todos os testes passando (SE11: 11, SE10: 46).
**Commit:** `81832da1`.
**Nota:** SE10 precisa de rebuild (não volume-mounted). SE11 já está live.

### SOLID Refactoring Plan — 96 violações documentadas (2026-07-07)

**Investigação:** Varredura SOLID completa em SE8, SE10, SE11, Shared lib.
**Resultado:** 96 violações (31 HIGH, 49 MEDIUM, 16 LOW). Top: SE8 37, SE11 23, SE10 23, Shared 13.
**Documento:** `/root/YTCaption-Easy-Youtube-API/PLAN.md` — 4 fases priorizadas: Quick Wins (2.5h), Decompor God Functions (10h), Interfaces/DIP (8h), Config Extensível (2h).
**Commit:** `d624ec5d`.

### Sessão anterior (2026-07-05)

### 🟢 SE8 Memory Leak Fix — GPU/RAM cleanup after job (2026-07-05)

**Problema:** Após job, GPU ficava com 6469 MiB e RAM 32GB. Duas sessões de model management (ComfyUI + SE8 model_manager), worker só limpava ComfyUI.

**Solução:** Worker finally block agora faz:
1. Pipeline cache cleanup (loaded_controlnets, clip_cond_cache)
2. SE8 model_manager.unload_all() (CLIP, Expansion, IP-Adapter)
3. ComfyUI unload_all_models() (UNet, VAE, ControlNet)
4. gc.collect() + malloc_trim() + torch.cuda.empty_cache()

**Resultado:** GPU idle 17507→576 MiB, RAM 964→431 MB (SE8). Commit `5d01b1aa`.

### 🟢 GroundingDINO + SAM2 + BiRefNet REMOVIDOS — substituídos por SegFormer B2 (2026-07-05)

**Problema:** SE10 carregava 4 detectores na startup, apenas 2 funcionavam:
- **GroundingDINO**: CUDA custom ops (`_C`) quebradas → falha toda request
- **SAM2**: sempre pulado (SegFormer já retorna masks pixel-level)
- **BiRefNet**: CUDNN OOM no init (822MB buffer não cabe)
- **YOLO11-seg**: funciona, mantido
- **SegFormer B2**: funciona, PRIMARY detector

**Ação:** Remoção completa de TODO o código morto:
| Arquivo | Mudança |
|---------|---------|
| `ensemble_detector.py` | **Reescrito do zero** — só SegFormer + YOLO |
| `birefnet_detector.py` | **DELETADO** (arquivo inteiro morto) |
| `segmentor.py` | Sem GD/SAM2/BiRefNet em nenhum code path |
| `constants.py` | Constantes de checkpoint removidas |
| `health.py` | Refs a checkpoints GD/SAM2 removidas |
| `yolo_detector.py` | Docstring atualizado |
| `main.py` | Startup limpo |
| `docker-compose.gpu.yml` | Mounts BiRefNet removidos |
| `docker-compose.yml` | Mounts BiRefNet removidos |

**Resultado:**
- RAM SE10 idle: **1.9GB → 1.0GB** (economia ~900MB)
- Startup sem erros (antes: ~50 linhas warnings/errors)
- Ensemble/SegFormer funcionam normalmente
- Zero referências a GD/SAM2/BiRefNet em código executável

**Commits:** `965088b0` (skip loading), `cc729234` (remove dead code)

**Lição:** Quando um detector é claramente superior e os outros falham/são ignorados, remover carregamento reduz memória, startup time e complexidade. Manter checkpoints no disco para reativação futura.

### 🟢 Previous Sessions

### 🔴 Florence-2-large REMOVIDO — resultados péssimos (2026-07-04)

**Problema:** Florence-2 (base e large) gera falsos positivos catastroficos:
- Logo "GUCCI" detectado como "spaghetti strap" 
- Cabelo/fundo detectado como "skirt"
- Máscara de inpainting ficou no logo e cabelo, NÃO nas roupas
- Resultado: imagem praticamente identica ao original

**Causa raiz:** Florence-2 usa bounding boxes imprecisos. Detecção "pequena" ≠ detecção correta.

**Decisão:** Florence-2 REMOVIDO do pipeline. Substituído por SegFormer B2.

### 🟢 Florence-2 Cleanup — referências removidas do codebase (2026-07-04)

**Ação:** Todas as referências ao Florence-2 foram removidas de SE10 e SE11:

| Arquivo | Mudança |
|---------|---------|
| SE10 `florence_detector.py` | **DELETADO** (202 linhas) |
| SE10 `segmentor.py` | Docstring e comments atualizados |
| SE10 `ensemble_detector.py` | Docstring atualizado |
| SE11 `core/models.py` | `DetectorType`: FLORENCE2→SEGFORMER+ENSEMBLE |
| SE11 `api/schemas.py` | `DetectorType` enum, descriptions, examples |
| SE11 `api/routes.py` | Detector list, descriptions (3 endpoints) |
| SE11 `infrastructure/http_client.py` | Docstring |
| SE11 `services/pipeline.py` | PROGRESSIVE_PASSES: florence2→segformer |

**Validação:** 7/7 arquivos py_compile OK, 0 referências florence restantes em SE10/SE11.

### 🟢 Morphological Closing — buracos na máscara resolvidos (2026-07-04)

**Problema:** Máscara de roupa tinha buracos entre itens (gap entre hoodie e pants na barriga exposta).

**Solução em 2 camadas:**
1. **SE10 `segformer_detector.py`:** closing kernel 120×120 no `clothing_mask` + flood-fill + connected components (maior componente)
2. **SE11 `pipeline_nsfw_experimental.py`:** closing kernel 100×100 no `inpaint_mask` + `bitwise_and` com `person_binary`

**Resultado:** Máscara 100% sólida, sem buracos, sem bleeding para fundo.

**Lição:** Closing sozinho expande máscara para fora da pessoa — SEMPRE fazer `bitwise_and` com `person_binary` depois.

### 🟢 4x-UltraSharp ESRGAN — FUNCIONANDO (2026-07-05)

**Problema anterior:** Real-ESRGAN do SE8 via `/v1/generation/image-upscale-vary` degradava cores (Blue -38%).

**Causa raiz descoberta:** O endpoint `/v1/generation/image-upscale-vary` NÃO usa ESRGAN — gera imagem do zero via SDXL (text-to-image). O `upscale_state` é variável morta, nunca consumida. A distorção era do SDXL, não do ESRGAN.

**Solução:** Criado endpoint puro ESRGAN em SE8: `POST /v1/tools/upscale-esrgan`
- Aceita upload de imagem via multipart
- Carrega modelo `4x-UltraSharp.pth` (67MB, CivitAI, treinado para realismo)
- Usa `perform_upscale()` do `upscaler.py` — ESRGAN puro, sem SDXL
- Retorna base64 PNG

**Correções em SE8 `upscaler.py`:**
1. `RRDBNet` do `ldm_patched` aceita `state_dict` como primeiro arg (não `num_in_ch`)
2. `ImageUpscaleWithModel()` sem args — modelo passado no `.upscale(model, tensor)`
3. `numpy_to_pytorch` NÃO faz permute — mantém HWC, `ImageUpscaleWithModel` converte internamente
4. Key rename: `residual_block_` → `RDB` (sem ponto)

**Resultado de cores (test01):**
| Canal | Original | Upscaled | Diff | % |
|-------|----------|----------|------|---|
| Blue | 160.6 | 160.0 | -0.6 | **-0.4%** |
| Green | 151.5 | 151.6 | +0.1 | **+0.1%** |
| Red | 131.1 | 130.7 | -0.4 | **-0.3%** |

**Arquivos alterados:**
- `SE8 app/services/upscaler.py`: Model loading + tensor conversion corrigidos
- `SE8 app/api/tools_routes.py`: Novo endpoint `/v1/tools/upscale-esrgan`
- `SE11 app/infrastructure/http_client.py`: `upscale()` agora usa novo endpoint
- `SE11 app/services/pipeline_nsfw.py`: Upscale reabilitado
- `SE11 app/services/pipeline_nsfw_experimental.py`: Upscale reabilitado
- `SE8 data/models/upscale_models/4x-UltraSharp.pth`: Modelo baixado (67MB)

**Teste E2E:** `cr_421ced7c7cbc` — 5 tentativas, todas pose_changed=False, upscale completou em ~6s.

### 🟡 Próximos Passos (2026-07-05)

**✅ CONCLUÍDOS:**
1. ~~Equilibrar steps vs velocidade~~ — 50 steps validado
2. ~~Testar com mais imagens~~ — 4 imagens testadas com sucesso
3. ~~Upscaler pós-inpainting~~ — **4x-UltraSharp ESRGAN FUNCIONANDO** (Blue -0.4%, cores preservadas)
4. ~~Investigar upscaler alternativo~~ — Criado endpoint puro ESRGAN em SE8, bypassa SDXL

> **SE11 pipeline details:** Ver `services/se11-clothes-removal/docs/LICOES-NSFW.md`
> **SE11 roadmap:** Ver `services/se11-clothes-removal/docs/ROADMAP.md`

**Arquivos em `show/`:**
- `v30_*.png` — resultado com closing + mask 100% sólida
- `v31_*.png` — resultado com closing + steps=60
- `v32_*.png` — resultado com 50 steps (4 imagens)
- `test_images/` — 8 imagens de teste para validação

### 🟢 Alternativas de Segmentação Pesquisadas (2026-07-04)

| Modelo | Likes | Classes | mIoU | Formato | Nota |
|--------|-------|---------|------|---------|------|
| **SegFormer B2 Clothes** | 502 | 18 | 0.69 | HF/ONNX/PyTorch | 🏆 ESCOLHIDO |
| SegFormer B3 Clothes | 37 | 18 | 0.70 | HF/PyTorch | B3 = 47M params |
| SegFormer B5 Human Parsing | 26 | 18 | 0.63 | HF/PyTorch | Maior, mais lento |
| SCHP (LIP) | 1.2k stars | 20 | 0.59 | PyTorch/ONNX | ResNet-101, pesado |
| SCHP (ATR) | 1.2k stars | 18 | 0.82 | PyTorch/ONNX | Melhor mIoU, dataset menor |
| U2Net Cloth Seg | 612 stars | 3 (top/bottom/combined) | - | PyTorch | Simples, 3 classes apenas |
| BiRefNet Portrait | já temos | 1 (foreground) | - | ONNX | Pessoa completa |
| YOLO11-m-seg | já temos | 1 (pessoa) | - | PyTorch | Pessoa com máscara |
| GroundingDINO+SAM2 | já temos | via texto | - | PyTorch | QUEBRADO no container |
| Florence-2 (base/large) | removido | via texto | - | PyTorch | FALSOS POSITIVOS |

**Links úteis:**
- SegFormer B2: `https://huggingface.co/mattmdjaga/segformer_b2_clothes` (502 likes)
- SegFormer B3: `https://huggingface.co/sayeed99/segformer_b3_clothes`
- SCHP: `https://github.com/GoGoDuck912/Self-Correction-Human-Parsing` (1.2k stars)
- SCHP ONNX: `https://huggingface.co/pirocheto/schp-lip-20`

**SegFormer B2 classes:** Background, Hat, Hair, Sunglasses, Upper-clothes, Skirt, Pants, Dress, Belt, Left-shoe, Right-shoe, Face, Left-leg, Right-leg, Left-arm, Right-arm, Bag, Scarf

### 🟢 SegFormer B2 — implementado e E2E validado (2026-07-04)

**Objetivo:** Substituir Florence-2 (falsos positivos catastroficos) por SegFormer B2 (pixel-level clothing segmentation, 18 classes).

**Implementação completa:**
1. **`segformer_detector.py`**: Detector completo com `segment_clothes()` e `segment_to_sv_detections()`
   - Retorna detecções SEPARADAS por classe (Upper-clothes, Skirt, Pants, Dress)
   - Cada classe tem sua própria bbox e mask — previne filtro de area errado
2. **`ensemble_detector.py`**: SegFormer B2 como PRIMARY para clothes mode
   - `_consensus_vote()`: clothes → SegFormer primary; person → BiRefNet primary
   - Usa `segment_to_sv_detections()` para detecções per-class
3. **`segmentor.py`**: 
   - `max_area_pct=0.80` para SegFormer/ensemble (cada classe é independente)
   - Nesting filter pulado para SegFormer (classes independentes, sem overlap real)
   - Labels de classe via `LABELS` do SegFormer (não array `classes`)
   - `unload_gpu_models()` mantém SegFormer CPU-only ativo
4. **Dockerfile**: `pip install "transformers==4.48.3"` (compatibilidade)

**Bugs corrigidos:**
- `segment_to_sv_detections` retornava 1 detecção combinada → filtrada por max_area_pct
- `segment()` criava nova instância a cada call → agora usa `self._segformer_detector`
- Nesting filter removia bboxes internos (Pants dentro de Upper-clothes)
- Labels errados ("sweater", "blazer") → agora usa LABELS do SegFormer

**Resultados TESTE1.jpg (segformer direto):**
- Upper-clothes: 42.09%, Skirt: 0.56%, Pants: 7.97% = 50.62% total
- 3 detecções separadas, 3 masks, 795ms

**Resultados TESTE1.jpg (ensemble):**
- 3 classes detectadas, 3 masks, 2957ms

**E2E Test (job `cr_af7adaf30fc1`):**
- 5 attempts executados (sem early stop — composite > 5.0)
- Melhor: attempt 3 — composite=10.303, skin_ratio=2.04, clothes=62.1%, head=0.112%
- Pose changed=false (DWPose verificou consistência)
- Garment masks: `20_garment_0_Upper-clothes.png`, `21_garment_1_Skirt.png`, `22_garment_2_Pants.png`

**Arquivos alterados:**
- `services/se10-clothes-segmentation/app/services/segformer_detector.py`: Detecções per-class
- `services/se10-clothes-segmentation/app/services/ensemble_detector.py`: SegFormer como primary
- `services/se10-clothes-segmentation/app/services/segmentor.py`: max_area, nesting, labels
- `services/se10-clothes-segmentation/app/api/routes/segment.py`: detector=segformer

**Outputs em `show/`:**
- `v26_segformer_result.png`, `v26_segformer_original.png`
- `v26_segformer_garment_upper_clothes.png`, `v26_segformer_garment_skirt.png`, `v26_segformer_garment_pants.png`
- `v26_segformer_mask_overlay.png`, `v26_segformer_debug_overlay.png`

### 🟢 Previous Sessions

### 🟢 SE10 GPU Migration — 51x faster detection (2026-07-03)

**Objetivo:** Reverter SE10 de CPU para GPU para detecção muito mais rápida.

**Problemas encontrados e resolvidos:**
1. **PyTorch CPU-only**: `requirements.txt` instalava `torch==2.12.0` (CPU default). Fix: `--extra-index-url https://download.pytorch.org/whl/cu130` no Dockerfile
2. **DEVICE=gpu → RuntimeError**: `_resolve_device()` passava `"gpu"` diretamente para `torch.device()` que espera `"cuda"`. Fix: device_map `{"gpu": "cuda", "cuda": "cuda", "cpu": "cpu"}`
3. **VRAM overlap SE10+SE8**: SE10 mantinha modelos carregados 120s (idle timer), overlap com SE8. Fix: `unload_all()` imediatamente após cada request no route handler
4. **Docker compose cache**: compose re-usava imagem CPU antiga. Fix: `--force-recreate` + `--build`

**Resultado E2E (TESTE1.jpg, job `cr_ddaa29841838`):**
- Ensemble detection: **583ms** (vs ~30s CPU = **51x mais rápido**)
- VRAM pico job: 10267 MiB (SE10+SE8 sequential, sem overlap)
- VRAM pós-request: **12 MiB** (unload imediato)
- RAM idle: 8.4GB
- Job: completed, 3 attempts, composite=4.408, try_3 best (pose_changed=false)

**Commits:** `48afe531` (feat), `16b1c80` (unload_all_models), `494a64d` (gitignore large files)

### 🟢 RAM Optimization — unload_all_models + app volume mount (2026-07-03)

**Problema:** RAM idle ficava em 39.73GB (99.8%) após jobs. SE8 mantinha 17.47GB RAM + 7.6GB VRAM após completar job (models unloaded do model_management mas Python RSS retention + SE8 usando `soft_empty_cache()` que NÃO descarrega modelos).

**Fixes:**
1. **SE8 `worker.py` finally block**: Trocado `soft_empty_cache()` por `unload_all_models()` + `soft_empty_cache()` — `unload_all_models()` realmente descarrega pesos do VRAM, `soft_empty_cache()` só limpa cache do allocator
2. **SE8 `.env` MODEL_IDLE_TIMEOUT**: 300→60s (descarrega modelos após 60s idle)
3. **SE8 app volume mount**: Adicionado `/root/.../se8-image-generation/app:/app/app:ro` no `docker-compose.gpu.yml` — código Python agora é live-mounted, elimina necessidade de `docker cp` + rebuild
4. **Todos os arquivos SE8 re-deployed**: `task_models.py`, `worker.py`, `checkpoint.py`, `config.py` — container foi recriado via `--force-recreate` e destruiu docker cp anteriores

**Resultado E2E (TESTE1.jpg, cr_f515cca4758d):**

| Métrica | Baseline (antes) | Pico Job | Pós-Job (180s) | Ganho |
|---------|-------------------|----------|----------------|-------|
| RAM idle | 39.73GB (99.8%) | — | 10GB (25%) | **-75%** |
| GPU idle | 7616MiB | 8158MiB | 12MiB | **-99.8%** |
| SE10 idle | 20.11GB | ~3GB | 688MB | **-97%** |
| SE8 idle | 17.47GB | ~13.6GB | 13.64GB* | -22% |
| RAM pico job | — | 33.8GB | — | -15% vs 39.73GB |

*SE8 13.64GB é Python RSS retention — modelos descarregados de VRAM mas memory pages não retornadas ao OS pelo allocator. Para liberar precisaria de `madvise(MADV_DONTNEED)` ou restart do processo.

**Job scoring:**
- try_1: composite=6.491, pose_changed=true, landmark=23.21% → continuar (early stop não ativa)
- try_2: composite=2.489, pose_changed=false, landmark=10.47% → early stop correto (ambos critérios)

**Commits:** `e9101cf` (PLAN.md update), `3d21953` (RAM optimization)

### 🟢 Pose-Aware Early Stop + SE10 CPU (2026-07-03)

**Problema 1:** Early stop ativava com `composite < 5.0` mesmo quando `pose_changed=true`. Resultado: apenas 1 tentativa, pose alterada aceita sem retry.

**Problema 2:** SE10 (6GB GPU) + SE8 (17GB GPU) = 23GB/24GB causava corrupção de CUDA handle (`handle_0 INTERNAL ASSERT FAILED`). SE8 retornava HTTP 200 com lista vazia `[]`.

**Fixes:**
- `pipeline_nsfw.py` early stop: agora requer `composite < 5.0` E `pose_changed=false`. Se pose_changed=true, continua retrying.
- SE10: `DEVICE=cpu`, `runtime: nvidia` removido. Evita conflito de GPU com SE8.

**Resultado E2E (TESTE1.jpg, cr_cea3e110b398):**
- `pose_changed: false` ✅ (era true antes)
- `max_landmark_pct: 10.873%` (era 18.095%)
- `composite_score: 2.773` (era 4.875)
- `head_pct: 0.874%` — face preservada
- 1 tentativa (early stop correto — ambos critérios atendidos)

**Trade-off:** SE10 em CPU = ~30s detecção vs ~1s GPU. Aceitável porque pipeline já leva ~2min.

### 🟢 YOLO11-seg + Ensemble Voting — Multi-Detector Person Detection (2026-07-03)

**Problema:** SE10 GroundingDINO falha em imagens com fundo complexo/roupa escura (TESTE1.jpg: 1.6% coverage).

**Solução:** Adicionado YOLO11-seg como detector paralelo + ensemble voting:

| Detector | TESTE1.jpg Coverage | Velocidade | Precisão |
|----------|-------------------|------------|----------|
| GroundingDINO (antes) | 1.6% | ~9.4s | FALHOU |
| **YOLO11-seg (novo)** | **53.3%** | ~1.4s | **94.3% conf** |
| Ensemble (GD + YOLO11) | 53.3% | ~10s | Melhor de ambos |

#### Arquitetura Multi-Detector
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ GroundingDINO │  │  YOLO11-seg  │  │ BiRefNet-port│
│  (text-prompt)│  │ (COCO person)│  │ (SOTA person) │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                  │                  │
       └────────┬─────────┴──────────────────┘
                ▼
       ┌────────────────┐
       │Consensus Voting│
       │(coverage+SOTA) │
       └───────┬────────┘
               ▼
       ┌────────────────┐
       │ Quality Gate   │
       │(coverage > 10%)│
       └───────┬────────┘
               ▼
       Mask final → SAM2 (se bbox) ou direto (se mask)
```

#### Resultados comparativos (TESTE1.jpg)
| Detector | Coverage | Confiança | Velocidade | Nota |
|----------|----------|-----------|------------|------|
| GroundingDINO | 1.6% | — | ~9.4s | FALHOU |
| YOLO11-seg (CPU) | 53.3% | 94.3% | ~1.4s | Rápido |
| **BiRefNet-portrait (GPU)** | **49.4%** | **98.9%** | **~0.8s** | **SOTA + GPU** |
| Ensemble (GD+YOLO+BRef) | 48.8% | 99.7% | ~1.2s | Melhor |

#### Arquivos criados/modificados
- `services/se10-clothes-segmentation/app/services/yolo_detector.py` — YOLO11-seg wrapper
- `services/se10-clothes-segmentation/app/services/birefnet_detector.py` — BiRefNet-portrait ONNX wrapper
- `services/se10-clothes-segmentation/app/services/ensemble_detector.py` — Multi-detector voting (GD+YOLO+BiRefNet)
- `services/se10-clothes-segmentation/app/services/segmentor.py` — Suporte `detector="yolo11"|"birefnet"|"ensemble"`
- `services/se10-clothes-segmentation/app/api/routes/segment.py` — Param `detector` no form
- `services/se10-clothes-segmentation/requirements.txt` — Adicionado `ultralytics>=8.4.0`
- `services/se11-clothes-removal/app/services/pipeline_nsfw.py` — `detector="ensemble"` em person detection
- `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental.py` — `detector="ensemble"` em person detection

#### Deploy
- SE10: Dockerfile com CUDA lib symlinks, `requirements.txt` com `onnxruntime-gpu`, `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, `nvidia-cufft-cu12`
- SE10: `docker-compose.yml` com `runtime: nvidia`, volume mounts para modelos
- SE10: Modelos via volume: `yolo11m-seg.pt` (43MB) e `birefnet-portrait.onnx` (928MB)
- SE11: `docker cp` de pipeline_nsfw.py, pipeline_nsfw_experimental.py + `docker restart`
- ⚠️ `protobuf==3.20.3` obrigatório (quebra com protobuf 7.x)

#### Resultados em show/
- `show/yolo11_final_mask.png` — máscara YOLO11-seg (53.3%)
- `show/yolo11_final_overlay.png` — overlay verde na pessoa
- `show/birefnet_mask.png` — máscara BiRefNet-portrait (49.4%)
- `show/birefnet_overlay.png` — overlay verde BiRefNet

---

## Sessão anterior (2026-07-02)

### Container SE8
- Nome: `image-engine` (NÃO `se8-image-engine`)
- Porta: 8008
- **Agora usa bind mounts** para código (`app`, `modules`, `ldm_patched`, `extras`, `sdxl_styles`, `args_manager.py`) e `data`
- **GPU mounts obrigatórios** para driver 590 (workaround nvidia-container-toolkit):
  - `/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1`
  - `/usr/lib/x86_64-linux-gnu/libcuda.so.1`
  - `/usr/lib/x86_64-linux-gnu/libnvidia-ml.so`
  - `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, `/dev/nvidia-uvm-tools`, `/dev/nvidia-modeset`
- **app volume mount**: `/root/.../se8-image-generation/app:/app/app:ro` — código Python live-mounted, sem necessidade de `docker cp`
- Criado `/app/data/wildcards` com ownership `1000:1000` para evitar `PermissionError` no startup
- **Memory management**: `unload_all_models()` no finally block libera VRAM; `MODEL_IDLE_TIMEOUT=60` descarrega após idle; `del sd` em checkpoint.py libera RAM
- Para atualizar: restart container (código via bind mount); recriar se precisar adicionar mounts GPU

## Serviços Ativos

| Service | Port | Container | Status | Description |
|---|---|---|---|---|
| se1-orchestrator | 8001 | — | ✅ Healthy | Pipeline orchestrator |
| se2-video-downloader | 8002 | — | ✅ Healthy | Video download |
| se3-audio-normalization | 8003 | — | ✅ Healthy | Audio normalization |
| se4-audio-transcriber | 8004 | — | ✅ Healthy | Whisper transcription |
| se5-video-clip | 8005 | — | ✅ Healthy | Video clip generation |
| se6-youtube-search | 8006 | — | ✅ Healthy | YouTube search |
| se7-audio-generation | 8007 | — | ✅ Healthy | TTS Chatterbox (GPU) |
| se8-image-generation | 8008 | image-engine | ✅ Healthy | Fooocus SDXL (GPU), **inpainting functional** |
| se9-make-video-img | 8009 | se9-make-video-img | ✅ Healthy | Ken Burns video builder |
| se10-clothes-segmentation | 8010 | ytcaption-se10-clothes-segmentation | ✅ Healthy | SegFormer B2 + YOLO11-seg (GPU mode, 51x faster), immediate unload_all() post-request. GroundingDINO/SAM2/BiRefNet REMOVED. |
| se11-clothes-removal | 8011 | se11-clothes-removal | ✅ E2E validated | SE10→SE8 inpaint pipeline, OpenPose ControlNet integrated |

## SE10 — Clothes Segmentation

### Detectores (2026-07-05)
- **SegFormer B2** (PRIMARY): 18 classes, pixel-level masks, ~1.7s GPU
- **YOLO11-seg** (secondary): person detection, ~30ms GPU
- ~~GroundingDINO~~ REMOVIDO — CUDA ops quebradas
- ~~SAM2~~ REMOVIDO — sempre pulado por SegFormer masks
- ~~BiRefNet~~ REMOVIDO — CUDNN OOM

### Person Mode (2026-06-20)
- `POST /v1/segment` aceita `mode="person"` (default: `"clothes"`)
- `PERSON_CLASSES = ["person", "woman", "man"]` — joinhado como `"person. woman. man."`
- `DEFAULT_MAX_AREA_PCT_PERSON = 0.80` (era 0.29 para roupas — pessoa pode cobrir 40%+ da imagem)
- Backward compatible: `mode` é opcional, default `"clothes"` mantém comportamento existente

### Docker Deploy
- Container: `ytcaption-se10-clothes-segmentation`, port 8010
- Image: `docker-se10-clothes-segmentation:latest` (9.85GB, compose-persisted)
- CPU only (DEVICE=cpu)
- HEALTHCHECK start_period: 120s (model loading)

### Bugs corrigidos (3)
1. **SAM2 Hydra config** — `constants.py:39`: path relativo ao pacote sam2, não filesystem path
2. **transformers 5.x compat** — `bertwarper.py:128-133`: `get_extended_attention_mask()` 3rd arg mudou de `device` para `dtype`
3. **Detections.area** — `segmentor.py:246-260`: pre-compute `areas` ao invés de iterar Detections (yield tuples)

### Checkpoints
- `yolo11m-seg.pt` (~50MB) em volume mount
- ~~`groundingdino_swint_ogc.pth`~~ — removido do pipeline (mantido no disco)
- ~~`sam2_hiera_tiny.pt`~~ — removido do pipeline (mantido no disco)

### External deps
- `external/GroundingDINO/` — mantido no disco, não mais carregado
- `external/segment-anything-2/` — mantido no disco, não mais carregado
- Bertwarper patchado para transformers>=5.0

## SE8 — Image Engine
- Port: 8008, Container: `image-engine`, nvidia/cuda:12.1.1
- Docker: `docker-compose.gpu.yml`, Dockerfile: `Dockerfile.gpu-api`
- Rotas: Health(4) + Engines(4) + V1 Gen(5) + V2 Gen(5) + Query(4) + Files(1)
- **Inpainting FULLY FUNCTIONAL**: VAE encode + InpaintHead CNN + patched KSampler + post_process
- **OpenPose ControlNet**: `data/models/controlnet/controlnet-openpose-sdxl.safetensors` (739MB, `control-lora-openposeXL2-rank256`)
- **ControlNet tensor format**: pass `[B, H, W, C]` to `ControlNetApplyAdvanced`; it does `image.movedim(-1,1)` internally

### SE8 Inpainting Architecture (full pipeline)
- `_apply_inpaint()`: decode image+mask → InpaintWorker(img, mask, use_fill=True, k=inpaint_respective_field) → VAE encode (torch.inference_mode) → load_latent → set modules.inpaint_worker.current_task → patch UNet with InpaintHead
- `_process_diffusion()`: uses inpaint latent (not empty latent) as initial state
- `patched_KSamplerX0Inpaint_forward`: mixes inpaint latent + energy noise into unmasked regions during denoising
- `worker.post_process()`: resizes generated content → color_correction (alpha blend) → pastes into original image
- `finally`: clears `modules.inpaint_worker.current_task = None`

### SE8 Key Fixes (2026-06-20)
1. **VAE encode** — encode_vae_inpaint wrapped in `torch.inference_mode()` (model weights are inference tensors)
2. **operators.py torch import** — `NameError: name 'torch' not defined` in `_decode_standard()` fallback
3. **InpaintHead patch** — loads 52KB CNN, feeds [latent_mask, process_latent_in(latent)] → patches UNet input block 0
4. **current_task activation** — `miw.current_task = worker` activates `patched_KSamplerX0Inpaint_forward`
5. **Inpaint latent as initial** — `_process_diffusion()` uses inpaint latent dict instead of empty latent
6. **Docker rebuild** — all fixes persisted in `docker-image-engine` image (rebuilt 2026-06-20)

## SE9 — Make Video IMG
- **27/27 testes passando, 0 warnings** (era 65)
- Critical bug fix: `chosen_seq` NameError em `video_assembler.py`
- Redis store refactor: `_use_raw` property
- Lazy import fix: `audio_generator.py`
- Dead code removal: `hook_text` param de `create_title_card()`
- ARCHITECTURE.md sincronizado com código real
- Pydantic v2 migration completa (shared library)

## Shared Library
- Pydantic v2 migration completa — 0 warnings
- `config_utils/base_settings.py`: SettingsConfigDict, field_validator, model_validator
- `models/base.py`: ConfigDict, json_encoders removido
- `di.py`: dependency injection container

## Pydantic v2 Migration — ALL SERVICES COMPLETE (2026-06-20)
348/348 arquivos py_compile OK, zero deprecation warnings.

| Service | Changes | Status |
|---|---|---|
| shared/ | Already migrated (earlier session) | ✅ |
| se1-orchestrator | `class Config` → `ConfigDict(json_schema_extra=...)`, removed `json_encoders` | ✅ |
| se2-video-downloader | 2x `class Config` → `ConfigDict(json_schema_extra=...)`, removed `json_encoders` | ✅ |
| se3-audio-normalization | Removed `json_encoders` | ✅ |
| se4-audio-transcriber | Already clean | ✅ |
| se5-make-video-clip | `@validator` → `@field_validator`+`@classmethod`, `class Config` → `ConfigDict(extra='forbid', json_schema_extra=...)`, `schema_extra` → `json_schema_extra`, `.dict()` → `.model_dump()`, removed `json_encoders` | ✅ |
| se6-youtube-search | Already clean | ✅ |
| se7-audio-generation | `class Config`+`json_encoders` removed | ✅ |
| se8-image-generation | Already clean (uses `model_config = {...}`) | ✅ |
| se9-make-video-img | Already clean | ✅ |
| se10-clothes-segmentation | Already clean (uses `model_config = {...}`) | ✅ |
| se11-clothes-removal | Already clean | ✅ |

## Docs Arquivados
```
docs/archive/se9-make-video-img/
├── FIX-ERROS-2026-06-19.md
├── FIX-2-2026-06-19.md
├── INVESTIGACAO-v4.1.md
└── VALID-2026-06-17.md
```

## Strong Typing — Batch 2 (2026-06-20)
11 shared/ files typed: `from __future__ import annotations`, return types on all functions/methods, `dict[str, Any]`/`list[str]` parameterized, `Optional` → `X | None`, bare `list` → `list[str]`.

Files: `health_utils.py`, `datetime_utils/__init__.py`, `datetime_utils/helpers.py`, `datetime_utils/conftest.py`, `log_utils/__init__.py`, `log_utils/structured.py`, `redis_utils/__init__.py`, `redis_utils/resilient_store.py`, `redis_utils/serializers.py`, `http_utils/__init__.py`, `http_utils/resilient_client.py`

All 11 py_compile OK, no logic changes.

## Strong Typing — Batch 3 (2026-06-20)
28 se2-video-downloader files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files: `app/__init__.py`, `app/main.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/logging_config.py`, `app/core/models.py`, `app/core/validators.py`, `app/core/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/api/__init__.py`, `app/domain/interfaces.py`, `app/domain/__init__.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/__init__.py`, `app/services/video_downloader.py`, `app/services/user_agent_manager.py`, `app/services/validators.py`, `app/services/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/middleware/__init__.py`, `app/shared/exceptions.py`, `app/shared/__init__.py`

All 28 py_compile OK, no logic changes.

## Strong Typing — Batch 3 SE1 (2026-06-20)
26 SE1 orchestrator files typed: `from __future__ import annotations`, return types on all functions/methods, `dict[str, Any]`/`list[str]` parameterized, `Optional` → `X | None`, bare `list` → `list[str]`, bare `dict` → `dict[str, Any]`.

Files (26): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/exceptions.py`, `app/core/ssl_config.py`, `app/api/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/domain/__init__.py`, `app/domain/models.py`, `app/domain/interfaces.py`, `app/domain/builders.py`, `app/domain/pipeline_job_v2.py`, `app/infrastructure/__init__.py`, `app/infrastructure/microservice_client.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/circuit_breaker.py`, `app/infrastructure/dependency_injection.py`, `app/services/__init__.py`, `app/services/pipeline_orchestrator.py`, `app/services/pipeline_background.py`, `app/services/health_checker.py`, `app/middleware/__init__.py`, `app/shared/__init__.py`

All 26 py_compile OK, no logic changes.

## Strong Typing — Batch 5 SE7 (2026-06-20)
29 se7-audio-generation files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (29): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/api/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/api/schemas.py`, `app/api/voices_routes.py`, `app/domain/__init__.py`, `app/domain/exceptions.py`, `app/domain/interfaces.py`, `app/domain/models.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/services/__init__.py`, `app/services/audio_utils.py`, `app/services/generator.py`, `app/services/model_manager.py`, `app/services/pt_br_normalizer.py`, `app/services/voice_manager.py`, `app/services/voice_seeder.py`, `app/middleware/__init__.py`, `app/shared/__init__.py`

All 29 py_compile OK, no logic changes.

## Strong Typing — Batch 4 SE3 (2026-06-20)
29 se3-audio-normalization files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (29): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/exceptions.py`, `app/core/logging_config.py`, `app/core/models.py`, `app/core/validators.py`, `app/domain/__init__.py`, `app/domain/interfaces.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/middleware/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/services/__init__.py`, `app/services/audio_extractor.py`, `app/services/audio_normalizer.py`, `app/services/audio_processor.py`, `app/services/cleanup_service.py`, `app/services/file_validator.py`, `app/services/job_manager.py`, `app/services/job_service.py`, `app/shared/__init__.py`, `app/shared/exceptions.py`

All 29 py_compile OK, no logic changes.

## Strong Typing — Batch 5 SE6 (2026-06-20)
33 se6-youtube-search files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (33): `app/__init__.py`, `app/main.py`, `app/api/__init__.py`, `app/api/admin.py`, `app/api/jobs.py`, `app/api/routes.py`, `app/api/search.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/logging_config.py`, `app/core/validators.py`, `app/domain/__init__.py`, `app/domain/interfaces.py`, `app/domain/models.py`, `app/domain/processor.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/middleware/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/services/__init__.py`, `app/services/ytbpy/__init__.py`, `app/services/ytbpy/channel.py`, `app/services/ytbpy/playlist.py`, `app/services/ytbpy/search.py`, `app/services/ytbpy/utils.py`, `app/services/ytbpy/video.py`, `app/shared/__init__.py`, `app/shared/exceptions.py`

All 33 py_compile OK, no logic changes.

## Strong Typing — Batch 6 SE5 (2026-06-20)
33 se5-make-video-clip files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (33): `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/checkpoint_manager.py`, `app/infrastructure/circuit_breaker.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/file_logger.py`, `app/infrastructure/health_checker.py`, `app/infrastructure/lock_manager.py`, `app/infrastructure/metrics.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/subprocess_utils.py`, `app/infrastructure/telemetry.py`, `app/api/__init__.py`, `app/api/api_client.py`, `app/api/routes.py`, `app/services/__init__.py`, `app/services/blacklist_factory.py`, `app/services/blacklist_manager.py`, `app/services/cache_manager.py`, `app/services/cleanup_service.py`, `app/services/file_operations.py`, `app/services/job_manager.py`, `app/services/shorts_manager.py`, `app/services/sqlite_blacklist.py`, `app/services/subtitle_generator.py`, `app/services/subtitle_postprocessor.py`, `app/services/sync_validator.py`, `app/services/video_builder.py`, `app/services/video_compatibility_fixer.py`, `app/services/video_compatibility_validator.py`, `app/services/video_status_factory.py`, `app/services/video_status_store.py`

All 33 py_compile OK, no logic changes.

## Strong Typing — Batch 7 SE8 (2026-06-20)
44 se8-image-generation files typed: `from __future__ import annotations` added to all files, return types on all functions/methods/properties/`__init__`, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed, `Callable` moved to `collections.abc`.

Files (44): `app/__init__.py`, `app/main.py`, `args_manager.py`, `app/api/__init__.py`, `app/api/admin_routes.py`, `app/api/api_utils.py`, `app/api/file_routes.py`, `app/api/generate_routes.py`, `app/api/generate_v2_routes.py`, `app/api/health_routes.py`, `app/api/image_utils.py`, `app/api/models_routes.py`, `app/api/query_routes.py`, `app/api/tools_routes.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/domain/__init__.py`, `app/domain/models.py`, `app/domain/task_models.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/core_ops.py`, `app/infrastructure/operators.py`, `app/services/__init__.py`, `app/services/checkpoint.py`, `app/services/controlnet.py`, `app/services/expansion.py`, `app/services/face_crop.py`, `app/services/face_restoration.py`, `app/services/inpaint_worker.py`, `app/services/ip_adapter.py`, `app/services/lora_manager.py`, `app/services/model_base.py`, `app/services/model_manager.py`, `app/services/model_patcher.py`, `app/services/pipeline.py`, `app/services/preprocessors.py`, `app/services/task_queue.py`, `app/services/upscaler.py`, `app/services/vae_interpose.py`, `app/services/worker.py`, `app/shared/__init__.py`, `app/extras/__init__.py`

All 44 py_compile OK, no logic changes.

> **SE11 details:** Ver `services/se11-clothes-removal/docs/LICOES-NSFW.md` e `services/se11-clothes-removal/docs/ROADMAP.md`
