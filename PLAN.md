# Plano de Refatoração SOLID — YTCaption-Easy-Youtube-API

**Data:** 2026-07-07
**Status:** Planejamento

---

## Visão Consolidada

Investigação identificou ~96 violações SOLID distribuídas assim:

| Serviço | HIGH | MEDIUM | LOW | Total |
|---|---|---|---|---|
| **SE8** (worker/pipeline) | 13 | 18 | 6 | **37** |
| **SE11** (pipeline_nsfw) | 5 | 13 | 5 | **23** |
| **SE10** (segmentor) | 7 | 11 | 5 | **23** |
| **Shared lib** | ~6 | ~7 | — | **~13** |
| **Total** | **~31** | **~49** | **~16** | **~96** |

---

## Top 5 Violations Mais Impactantes

### 1. SE11 — `pipeline_nsfw.py` — God Function (S1)

- **`run_nsfw()`** tem **~800 linhas** e 10+ responsabilidades: decode, SE10 detect, mask hole-filling (3 fallbacks), head/face separation (6 etapas), clothes detect, IP-Adapter, FaceID, debug images, SE8 inpaint com retry (5 attempts), face restore, pose validation, result clothes detection, skin HSV, composite scoring, early stop, upscale, output assembly, Redis update.
- **Duplicação**: `pipeline_nsfw_experimental.py` tem **~80%** da mesma lógica (~800 linhas) — manter 2 arquivos iguais é o maior risco de divergência.

### 2. SE8 — `worker.py` — God Module (S1+S2)

- **1505 linhas** no worker: task detection, faceid adapter (com classes `nn.Module` inline!), IP-Adapter, inpaint, vary, upscale, ControlNet, diffusion, cleanup.
- **`_apply_inpaint()`** = 250+ linhas com 7 responsabilidades.
- **`_load_faceid_adapter()`** define 2 classes `nn.Module` inline dentro da função.

### 3. SE10 — `segmentor.py` — God Class (S1)

- `ClothesSegmentor.segment()` = **290 linhas** com 8 etapas sequenciais misturadas.
- Duplicação: `gc.collect() + malloc_trim()` copiado **3 vezes**.
- Magic numbers `{4, 5, 6, 7}` duplicados **3 vezes** sem usar constante existente.

### 4. SE11 — Hardcoded Scoring/Prompts (O1+O2)

- `SCORE_W_SKIN=0.4`, `SCORE_W_HEAD=0.2`, etc. hardcoded — tuning exige alterar código.
- Prompt NSFW hardcoded — rota aceita `prompt` mas ignora.

### 5. Shared — Zero Protocols/ABCs (D1)

- Nenhuma interface formal. Cada serviço define seus próprios wrappers (duplicados 8x). `JobRedisStore` existe no shared mas cada serviço envolve com wrapper próprio.

---

## Detalhamento por Serviço

### SE11 — Clothes Removal (23 violações)

| ID | Princípio | Severidade | Arquivo:Linhas | Descrição |
|---|---|---|---|---|
| S1 | SRP | HIGH | `pipeline_nsfw.py:381-1183` | `run_nsfw()` = ~800 linhas, 10+ responsabilidades |
| S2 | SRP | HIGH | `pipeline_nsfw_experimental.py:277-1075` | Duplicação ~80% de `run_nsfw()` |
| S3 | SRP | MEDIUM | `pipeline.py:409-699` | `run_clothes_removal()` dispatcher + implementação inline |
| S4 | SRP | MEDIUM | `routes.py:202-316,343-438,465-605` | Boilerplate duplicado 3x em handlers |
| S5 | SRP | MEDIUM | `http_client.py:131-491` | `SE8Client` com 4 capabilities numa classe |
| S6 | SRP | MEDIUM | `head_detector.py:1-369` | 3 estratégias + rendering num módulo |
| S7 | SRP | MEDIUM | `pose_detector.py:1-888` | Detecção, comparação, visualização, CLI num arquivo |
| S8 | SRP | LOW | `pipeline_nsfw.py:171-227` | `_build_clothes_neutral_ref()` = 5 operações misturadas |
| O1 | OCP | HIGH | `pipeline_nsfw.py:50-55` | Scoring weights hardcoded |
| O2 | OCP | HIGH | `pipeline_nsfw.py:712-747` | Prompt NSFW hardcoded (ignora input do usuário) |
| O3 | OCP | MEDIUM | 3 arquivos | LoRA configs hardcoded em 3 arquivos diferentes |
| O4 | OCP | MEDIUM | `pipeline_nsfw.py:913` | Nome do modelo inpainting hardcoded |
| O5 | OCP | MEDIUM | `pipeline_nsfw.py:450-552` | Fallback strategies como if/elif rígido |
| O6 | OCP | LOW | 3 arquivos | `CLOTHES_CLASSES` duplicado em 3 arquivos |
| L1 | LSP | MEDIUM | `http_client.py:68-123,131-301` | `SE10Client`/`SE8Client` herdam `ServiceClient` sem interface comum |
| L2 | LSP | LOW | `pose_detector.py:168-200` | `detect_pose()` aceita path ou array, exceções diferentes |
| I1 | ISP | MEDIUM | `http_client.py:131-491` | `SE8Client` força dependência em 4 capabilities |
| I2 | ISP | MEDIUM | `models.py:119-163` | `ClothesRemovalJob` expõe estado mutável |
| I3 | ISP | LOW | `routes.py:202-316` | Form params desnecessários para modos não-usados |
| D1 | DIP | HIGH | `pipeline_nsfw.py:391-392` | `SE10Client()`/`SE8Client()` instanciados diretamente |
| D2 | DIP | HIGH | `pipeline_nsfw.py:392` | Dependência concreta em `ClothesRemovalJobStore` |
| D3 | DIP | MEDIUM | `head_detector.py:20-35,213-226` | Haarcascade/MediaPipe como singletons globais |
| D4 | DIP | MEDIUM | `pose_detector.py:46-52` | DWPose hardcoded como único detector |
| D5 | DIP | LOW | 3 arquivos | `httpx.get()` direto para download de imagens |

### SE8 — Image Generation (37 violações)

| ID | Princípio | Severidade | Arquivo:Linhas | Descrição |
|---|---|---|---|---|
| S1 | SRP | HIGH | `worker.py:1245-1449` | `process_generate()` = 200+ linhas |
| S2 | SRP | HIGH | `worker.py` (1505 linhas) | God module com 15+ responsabilidades |
| S3 | SRP | HIGH | `worker.py:775-1029` | `_apply_inpaint()` = 250+ linhas, 7 responsabilidades |
| S4 | SRP | HIGH | `worker.py:369-544` | 2 classes `nn.Module` definidas inline |
| S5 | SRP | HIGH | `pipeline.py:532-774` | `process_diffusion()` = 240+ linhas, 3 estratégias inline |
| S6 | SRP | MEDIUM | `pipeline.py:39-836` | `Pipeline` class com muitas responsabilidades |
| S7 | SRP | MEDIUM | `model_manager.py:211-783` | `ModelManager` = 5+ concerns |
| S8 | SRP | MEDIUM | `worker.py:196-231` | `_save_and_log()` com dead code |
| S9 | SRP | MEDIUM | `worker.py:547-712` | `_apply_ip_adapter()` = 165 linhas |
| O1 | OCP | HIGH | `worker.py:286-315` | `_PERFORMANCE_DEFAULTS` hardcoded |
| O2 | OCP | HIGH | `worker.py:48-59` | `_detect_task_type()` if/elif rígido |
| O3 | OCP | MEDIUM | `worker.py:763-772` | `denoising_map` hardcoded |
| O4 | OCP | MEDIUM | `worker.py:948-954` | `inpaint_patch_map` hardcoded |
| O5 | OCP | MEDIUM | `worker.py:1037` | `scale_map` hardcoded |
| O6 | OCP | LOW | `worker.py:357-364` | `type_map` hardcoded |
| O7 | OCP | MEDIUM | `upscaler.py:52-57` | Model candidates hardcoded |
| O8 | OCP | MEDIUM | `pipeline.py:469-488` | Sampler-specific logic hardcoded |
| O9 | OCP | MEDIUM | `api_utils.py:63-73` | `get_task_type()` com isinstance chain |
| O10 | OCP | LOW | `model_manager.py:677-680` | Broken GPU list hardcoded |
| L1 | LSP | HIGH | `api_utils.py:232-281` | `call_worker()` com return types inconsistentes |
| L2 | LSP | MEDIUM | `generate_v2_routes.py:45-46` | V2 routes mutam request objects |
| L3 | LSP | MEDIUM | `pipeline.py:780-787` | `_clip_separate()` degrada silenciosamente |
| L4 | LSP | LOW | `worker.py:148-193` | `_save_output_file()` duck-typing |
| L5 | LSP | LOW | `worker.py:62-145` | `_build_async_task()` polymorfismo frágil |
| I1 | ISP | HIGH | `task_models.py:90-203` | `AsyncTask` = 80+ fields monolíticos |
| I2 | ISP | HIGH | `model_manager.py:211-783` | `ModelManager` = 30+ métodos públicos |
| I3 | ISP | MEDIUM | `pipeline.py:39-836` | `Pipeline` = model loading + encoding + diffusion |
| I4 | ISP | MEDIUM | `worker.py:775-1029` | `_apply_inpaint()` depende de `AsyncTask` inteiro |
| D1 | DIP | HIGH | `worker.py:834,910-911` | `miw.current_task` = estado global mutável |
| D2 | DIP | HIGH | `worker.py:818-830` | Singletons `get_pipeline()`, `get_model_manager()` |
| D3 | DIP | HIGH | `pipeline.py:380-394` | Pipeline depende de `ModelManager` concreto |
| D4 | DIP | MEDIUM | `worker.py:42-43` | Import lazy de singleton concreto |
| D5 | DIP | MEDIUM | `worker.py:580-598` | Acoplamento a `modules.config` legado |
| D6 | DIP | MEDIUM | `pipeline.py:158-192` | Import concreto de `checkpoint` |
| D7 | DIP | MEDIUM | `upscaler.py:15-39` | `RRDBNet`/`ImageUpscaleWithModel` concretos |
| D8 | DIP | MEDIUM | `tools_routes.py:34-39,90-104` | Routes importam implementações concretas |
| D9 | DIP | MEDIUM | `model_manager.py:276-279` | `_get_torch()` muta `CUDA_VISIBLE_DEVICES` |
| D10 | DIP | LOW | `worker.py:1471-1472` | uvicorn restart command hardcoded |

### SE10 — Clothes Segmentation (23 violações)

| ID | Princípio | Severidade | Arquivo:Linhas | Descrição |
|---|---|---|---|---|
| S-1 | SRP | HIGH | `segmentor.py:40-489` | God class com 6+ responsabilidades |
| S-2 | SRP | HIGH | `segmentor.py:201-489` | `segment()` = 290 linhas, 8 etapas |
| S-3 | SRP | MEDIUM | `routes/segment.py:22-147` | Route handler = validation + orchestration + GPU mgmt |
| O-1 | OCP | HIGH | `segmentor.py:266-318` | Detector dispatch por string (if/elif) |
| O-2 | OCP | HIGH | `segmentor.py:331,382,420` | Magic numbers `{4,5,6,7}` duplicados 3x |
| O-3 | OCP | MEDIUM | `segmentor.py:92-99,122-133` | Model loading inline, sem registry |
| O-4 | OCP | MEDIUM | `segformer_detector.py:140` | Kernel size `(120,120)` hardcoded |
| O-5 | OCP | MEDIUM | `ensemble_detector.py:94` | YOLO confidence `0.25` hardcoded |
| O-6 | OCP | MEDIUM | `ensemble_detector.py:157-206` | Consensus voting priority hardcoded |
| O-7 | OCP | LOW | `segmentor.py:400-401` | Font/color/thickness hardcoded |
| I-1 | ISP | HIGH | `segmentor.py:481-489` | Return dict monolítico (7 keys) |
| I-2 | ISP | MEDIUM | `ensemble_detector.py:40-42` | Params `box_threshold`/`text_threshold` unused |
| I-3 | ISP | MEDIUM | `segmentor.py:201-212` | `segment()` com 8 parâmetros |
| D-1 | DIP | HIGH | `segmentor.py:93,123,238` | Imports concretos de detectores |
| D-2 | DIP | HIGH | `ensemble_detector.py:25-34` | `Any` type para detector deps |
| D-3 | DIP | MEDIUM | `segmentor.py:147-153,165-175,473-479` | `ctypes.CDLL("libc.so.6")` em business logic |
| D-4 | DIP | MEDIUM | `routes/segment.py:112` | Route chama `unload_gpu_models()` |
| D-5 | DIP | MEDIUM | `state.py:50` | Acesso externo a `_check_idle_unload()` |
| D-6 | DIP | LOW | `segmentor.py:383-384,421-422` | Import de LABELS específicos de detector |
| A-1 | — | MEDIUM | `segmentor.py:282-287,305-310,365-370` | Return "not detected" duplicado 3x |
| A-2 | — | MEDIUM | `segmentor.py:147-153,165-175,473-479` | gc+malloc_trim duplicado 3x |
| A-3 | — | LOW | `segmentor.py:383-385,421-422` | LABELS import duplicado |
| A-4 | — | LOW | `segformer_detector.py:34` | `BODY_IDS` com IDs 18-19 fora de range |

### Shared Library (~13 violações)

| ID | Princípio | Severidade | Arquivo:Linhas | Descrição |
|---|---|---|---|---|
| S-1 | SRP | HIGH | `resilient_store.py:146-391` | `ResilientRedisStore` = 4 responsabilidades |
| S-2 | SRP | HIGH | `base_settings.py:85-235` | `BaseServiceSettings` = god config |
| S-3 | SRP | HIGH | `health_utils.py:63-224` | `ServiceHealthChecker` = registry + execution + static checks |
| S-4 | SRP | MEDIUM | `resilient_store.py:20-139` | `RedisCircuitBreaker` = state machine + execution |
| S-5 | SRP | MEDIUM | `structured.py:114-203` | `setup_structured_logging()` = 90 linhas |
| S-6 | SRP | LOW | `fastapi_utils.py:226-265` | `create_api_key_dependency()` |
| O-1 | OCP | HIGH | `resilient_store.py:20-144` | Circuit breaker hardcoded como única estratégia |
| O-2 | OCP | HIGH | `health_utils.py:130-224` | 4 static checks hardcoded |
| O-3 | OCP | MEDIUM | `serializers.py:25-137` | Field lists hardcoded |
| O-4 | OCP | MEDIUM | `base_settings.py:12-51` | `RedisSettings`/`CelerySettings` duplicam pattern |
| O-5 | OCP | MEDIUM | `resilient_client.py:34-35` | Retryable status codes constantes |
| O-6 | OCP | LOW | `base_settings.py:213-220` | `create_directories()` hardcoded |
| D-1 | DIP | HIGH | Shared (toda lib) | Zero Protocols/ABCs — serviços definem interfaces próprias |
| D-2 | DIP | HIGH | `resilient_store.py:12-13` | Import direto de `redis.Redis` concreto |
| D-3 | DIP | HIGH | Múltiplos serviços | JobStore wrappers duplicados em 8+ serviços |
| D-4 | DIP | HIGH | SE2/SE3 celery_tasks.py | `CallbackTask` duplicado, ignora shared |
| D-5 | DIP | MEDIUM | `fastapi_utils.py:137-143` | Duck-typing para settings |
| D-6 | DIP | MEDIUM | `store.py:18-119` | `JobRedisStore` depende de `ResilientRedisStore` concreto |

---

## Plano de Execução — Priorizado

### Fase 1: Quick Wins (alto impacto, baixo risco) — ~2.5h

| # | O quê | Onde | Esforço |
|---|---|---|---|
| 1.1 | Extrair funções helper duplicadas para `_helpers.py` (já existe) | SE11 pipeline_nsfw/experimental | 1h |
| 1.2 | Mover magic numbers `{4,5,6,7}` para constante `CLOTHING_IDS` | SE10 segmentor.py | 15min |
| 1.3 | Mover scoring weights para `settings` ou dataclass | SE11 pipeline_nsfw.py:50-55 | 30min |
| 1.4 | Extrair `gc.collect() + malloc_trim()` para `_cleanup_memory()` | SE10 segmentor.py (3x) | 15min |
| 1.5 | Deletar `BODY_IDS` com IDs fora de range | SE10 segformer_detector.py:34 | 5min |

### Fase 2: Decompor God Functions (alto impacto, médio risco) — ~10h

| # | O quê | Onde | Esforço |
|---|---|---|---|
| 2.1 | Dividir `run_nsfw()` em: `_detect_person()`, `_build_head_mask()`, `_build_reference()`, `_run_inpaint_loop()`, `_score_and_validate()`, `_upscale_and_finalize()` | SE11 pipeline_nsfw.py | 3-4h |
| 2.2 | Mesclar `pipeline_nsfw.py` e `pipeline_nsfw_experimental.py` com Strategy pattern (diferenças são mínimas: mask construction, LoRA weights) | SE11 | 2-3h |
| 2.3 | Dividir `segment()` em: `_decode()`, `_detect()`, `_filter()`, `_annotate()`, `_build_response()` | SE10 segmentor.py | 2h |
| 2.4 | Extrair inner classes `FaceIDProj` e `FaceIDIPAdapter` para módulo próprio | SE8 worker.py:403-489 | 30min |

### Fase 3: Interfaces e DIP (médio impacto, médio risco) — ~8h

| # | O quê | Onde | Esforço |
|---|---|---|---|
| 3.1 | Criar `DetectorProtocol` no shared para SE10 | shared + SE10 | 1h |
| 3.2 | Dividir `SE8Client` em `InpaintClient`, `UpscaleClient`, `FaceRestoreClient` | SE11 http_client.py | 1-2h |
| 3.3 | Criar `JobStoreProtocol` no shared, eliminar wrappers duplicados em 8 serviços | shared + SE1-SE11 | 3-4h |
| 3.4 | Usar `typing.Protocol` para `PoseDetector` e `FaceDetector` | SE11 | 1h |

### Fase 4: Config Extensível (baixo impacto, baixo risco) — ~2h

| # | O quê | Onde | Esforço |
|---|---|---|---|
| 4.1 | Config-driven LoRA weights (em vez de hardcoded em 3 arquivos) | SE11 | 30min |
| 4.2 | Registry pattern para task types no SE8 worker | SE8 worker.py | 1h |
| 4.3 | Configurable morphological kernel sizes | SE10 segformer_detector.py | 15min |

---

## Recomendação

**Começar pela Fase 1** (quick wins) — mudanças pontuais que reduzem duplicação imediatamente sem risco de regressão. Depois a **Fase 2.1 + 2.2** (decompor SE11 pipeline) que é onde o maior risco de divergência vive (80% lógica duplicada entre experimental e production).

**Fase 2.2 é a mais crítica**: mesclar `pipeline_nsfw.py` e `pipeline_nsfw_experimental.py` elimina o maior risco de manutenção do projeto.
