# BIG PLAN TÉCNICO — SE9 IMAGE ENGINE

```
┌─────────────────────────────────────────────────────────────────┐
│  PROJETO: SE9 Image Engine                                      │
│  VERSÃO: 1.0                                                    │
│  TECH LEADER: Senior                                            │
│  DATA: 2026-06-17                                               │
│  REFERÊNCIA: FOOOCUS (117K+ linhas, 447 arquivos Python)       │
│  TARGET: ~80 arquivos, ~8,000 linhas (refatoração limpa)       │
└─────────────────────────────────────────────────────────────────┘
```

## 1. ARQUITETURA ALTA

```
┌─────────────────────────────────────────────────────────────────┐
│                    SE9 IMAGE ENGINE                              │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ FastAPI   │───▶│ Celery Worker │───▶│ GPU Pipeline         │  │
│  │ Routes    │    │ (Redis queue) │    │                      │  │
│  │ (26 rotas)│    │               │    │ ┌──────────────────┐ │  │
│  └──────────┘    │ AsyncTask     │    │ │ Model Manager    │ │  │
│                  │ (80+ fields)  │    │ │ (VRAM, load/     │ │  │
│  ┌──────────┐    │               │    │ │  unload, cache)  │ │  │
│  │ Auth     │    └──────────────┘    │ └──────────────────┘ │  │
│  │ Middleware│                        │ ┌──────────────────┐ │  │
│  └──────────┘                        │ │ SD Pipeline      │ │  │
│                                      │ │ (CLIP, VAE,      │ │  │
│  ┌──────────┐                        │ │  Diffusion)      │ │  │
│  │ Config   │                        │ └──────────────────┘ │  │
│  │ (.env)   │                        │ ┌──────────────────┐ │  │
│  └──────────┘                        │ │ Extras           │ │  │
│                                      │ │ (IP-Adapter,     │ │  │
│                                      │ │  ControlNet,     │ │  │
│                                      │ │  Face, Enhance)  │ │  │
│                                      │ └──────────────────┘ │  │
│                                      └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2. ESTRUTURA DE DIRETÓRIOS

```
services/se9-image-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                          ← FastAPI app, lifespan, middleware
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    ← Settings (herda BaseServiceSettings)
│   │   └── constants.py                 ← MAX_SEED, aspect ratios, styles
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py                    ← Pydantic request/response (reutilizar SE8)
│   │   └── enums.py                     ← Performance, UpscaleMethod, etc.
│   ├── services/
│   │   ├── __init__.py
│   │   ├── model_manager.py             ← GPU/VRAM, load/unload (refs model_management.py:807)
│   │   ├── model_patcher.py             ← ModelPatcher (load/unload/patch)
│   │   ├── model_base.py               ← SDXL, SDXLRefiner dataclasses
│   │   ├── checkpoint.py               ← load_checkpoint_guess_config wrapper
│   │   ├── pipeline.py                  ← refresh_everything, encode, decode (refs default_pipeline.py:515)
│   │   ├── core_ops.py                  ← StableDiffusionModel, operators (refs core.py:341)
│   │   ├── sampler.py                   ← Diffusion sampling, scheduler patching
│   │   ├── worker.py                    ← AsyncTask, process_generate (refs worker.py:1579)
│   │   ├── task_queue.py               ← TaskQueue, QueueTask
│   │   ├── lora_manager.py              ← LoRA loading, key mapping
│   │   ├── style_engine.py              ← Styles, expansion, wildcards
│   │   ├── image_utils.py              ← HWC3, resize, erode_or_dilate
│   │   └── enhance.py                   ← Enhance pipeline, mask generation
│   ├── extras/
│   │   ├── __init__.py
│   │   ├── ip_adapter.py                ← IP-Adapter loading + patching
│   │   ├── controlnet.py                ← ControlNet (Canny, CPDS)
│   │   ├── inpaint_worker.py            ← Inpaint post-processing
│   │   ├── upscaler.py                  ← SR upscale (ESRGAN)
│   │   ├── expansion.py                 ← FooocusExpansion (GPT-2)
│   │   ├── face_restore.py              ← Face detection/restoration
│   │   ├── face_crop.py                 ← Face cropping
│   │   ├── censor.py                    ← NSFW detection
│   │   ├── preprocessors.py             ← Canny, CPDS preprocessors
│   │   └── inpaint_mask.py              ← SAM/DINO mask generation
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py                      ← API key middleware
│   │   ├── health_routes.py             ← /health, /ping, /
│   │   ├── generate_routes.py           ← V1 generation (10 rotas)
│   │   ├── generate_v2_routes.py        ← V2 generation (5 rotas)
│   │   ├── models_routes.py             ← /v1/engines/* (4 rotas)
│   │   ├── tools_routes.py              ← /v1/tools/* (2 rotas)
│   │   └── file_routes.py               ← /files/{date}/{name}
│   └── infrastructure/
│       ├── __init__.py
│       ├── operators.py                  ← VAEDecode, EmptyLatent, ControlNet, FreeU
│       ├── patches.py                    ← 8 monkey-patches (de modules/patch.py)
│       ├── latent_formats.py             ← LatentFormat classes
│       ├── celery_config.py             ← Celery app config
│       └── celery_tasks.py              ← Async generation task
├── docker/
│   ├── Dockerfile                       ← Multi-stage: api + worker
│   ├── Dockerfile.gpu                   ← GPU worker (nvidia/cuda)
│   ├── docker-compose.yml               ← Development
│   └── docker-compose.prod.yml          ← Production
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_model_manager.py
│   │   ├── test_pipeline.py
│   │   ├── test_core_ops.py
│   │   ├── test_worker.py
│   │   └── test_lora_manager.py
│   ├── api/
│   │   ├── test_auth.py
│   │   ├── test_health_routes.py
│   │   ├── test_generate_routes.py
│   │   ├── test_generate_v2_routes.py
│   │   ├── test_models_routes.py
│   │   ├── test_tools_routes.py
│   │   └── test_file_routes.py
│   └── integration/
│       └── test_gpu_pipeline.py         ← Real GPU tests
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env
├── run.py
└── README.md
```

## 3. MAPA DE PORTAÇÃO FOOOCUS → SE9 (REFATORADO)

### 3.1 ldm_patched Refatorado (~2,560 linhas de ~5,000)

| ldm_patched Original | SE9 Módulo Limpo | Linhas Est. | O que muda |
|---|---|---|---|
| `modules/model_management.py` | `services/model_manager.py` | ~600 | Remove dead code, tipagem forte, context manager |
| `modules/model_patcher.py` | `services/model_patcher.py` | ~250 | Simplifica ModelPatcher |
| `modules/sd.py` | `services/checkpoint.py` | ~400 | load_checkpoint_guess_config isolado |
| `modules/model_base.py` | `services/model_base.py` | ~100 | SDXL/SDXLRefiner como dataclasses |
| `modules/samplers.py` | `services/sampler.py` | ~300 | KSampler wrapping |
| `modules/sample.py` | `services/image_utils.py` | ~100 | prepare_mask, utilities |
| `modules/latent_formats.py` | `infrastructure/latent_formats.py` | ~80 | LatentFormat classes |
| `modules/utils.py` | `services/image_utils.py` | ~150 | load_torch_file, HWC3, resize |
| `modules/args_parser.py` | `core/config.py` (absorvido) | ~50 | Args → Settings |
| `contrib/external.py` | `infrastructure/operators.py` | ~400 | VAEDecode, EmptyLatent, ControlNet |
| `contrib/external_freelunch.py` | `infrastructure/operators.py` | ~50 | FreeU_V2 |
| `contrib/external_model_advanced.py` | `infrastructure/operators.py` | ~80 | ModelSamplingDiscrete/EDM |

### 3.2 Fooocus Core Refatorado (~1,800 linhas de ~3,000)

| FOOOCUS Original | SE9 Módulo | Linhas Est. |
|---|---|---|
| `modules/default_pipeline.py` (515) | `services/pipeline.py` | ~400 |
| `modules/core.py` (341) | `services/core_ops.py` | ~280 |
| `modules/patch.py` (~400) | `infrastructure/patches.py` | ~350 |
| `modules/config.py` (~600) | `core/config.py` + `services/checkpoint.py` | ~500 |
| `modules/sdxl_styles.py` (~200) | `services/style_engine.py` | ~180 |
| `modules/inpaint_worker.py` (~200) | `extras/inpaint_worker.py` | ~180 |
| `modules/upscaler.py` (~50) | `extras/upscaler.py` | ~40 |
| `modules/flags.py` (~100) | `domain/enums.py` | ~80 |
| `modules/util.py` (~300) | `services/image_utils.py` | ~200 |
| `modules/meta_parser.py` (~150) | `infrastructure/meta_parser.py` | ~120 |
| `modules/constants.py` | `core/constants.py` | ~20 |

### 3.3 API + Worker Refatorado (~2,500 linhas de ~3,000)

| FOOOCUS Original | SE9 Módulo | Linhas Est. |
|---|---|---|
| `fooocusapi/worker.py` (1579) | `services/worker.py` | ~1200 |
| `fooocusapi/task_queue.py` (~200) | `services/task_queue.py` | ~180 |
| `fooocusapi/api.py` (161) | `app/main.py` | ~120 |
| `fooocusapi/routes/generate_v1.py` (215) | `api/generate_routes.py` | ~180 |
| `fooocusapi/routes/generate_v2.py` (247) | `api/generate_v2_routes.py` | ~200 |
| `fooocusapi/routes/query.py` (234) | `api/` (distribuído) | ~200 |
| `fooocusapi/parameters.py` (~100) | `domain/models.py` (absorvido) | 0 |
| `fooocusapi/models/*` (~800) | `domain/models.py` (reutilizar SE8) | ~350 |

### 3.4 Extras (~1,200 linhas)

| FOOOCUS Original | SE9 Módulo | Linhas Est. |
|---|---|---|
| `extras/ip_adapter.py` (~200) | `extras/ip_adapter.py` | ~180 |
| `extras/inpaint_mask.py` (~150) | `extras/inpaint_mask.py` | ~140 |
| `extras/expansion.py` (~80) | `extras/expansion.py` | ~70 |
| `extras/face_crop.py` (~100) | `extras/face_crop.py` | ~90 |
| `extras/censor.py` (~50) | `extras/censor.py` | ~40 |
| `extras/preprocessors.py` (~200) | `extras/preprocessors.py` | ~180 |
| `Fooocus/extras/face_restore/` | `extras/face_restore.py` | ~100 |
| `fooocusapi/utils/*` (~200) | `infrastructure/file_utils.py` | ~150 |

### 3.5 Totais

| Categoria | FOOOCUS Original | SE9 Refatorado | Redução |
|---|---|---|---|
| ldm_patched | ~5,000 | ~2,560 | -49% |
| Fooocus Core | ~3,000 | ~1,800 | -40% |
| API + Worker | ~3,000 | ~2,500 | -17% |
| Extras | ~1,500 | ~1,200 | -20% |
| **TOTAL** | **~12,500** | **~8,060** | **-36%** |

## 4. FASES DETALHADAS

### FASE 1: Infraestrutura Base (Sprint 1-2)

**Objetivo:** Estrutura de diretórios, configuração, detecção de GPU, gerenciamento de VRAM.

**Arquivos:** `app/core/config.py`, `app/services/model_manager.py`, Docker

**Tarefa 1.1: Configuração** (`app/core/config.py`)
- Herdar `BaseServiceSettings` do shared/
- Settings: `gpu_mode` (lazy/eager/auto), `gpu_device_id`, `max_vram_mb`, `output_dir`, `model_dir`, `temp_dir`, `queue_size`, `se9_api_key`, `redis_url`
- Defaults: lazy mode, auto device detection
- .env.example com todas as variáveis

**Tarefa 1.2: Constants** (`app/core/constants.py`)
- MAX_SEED = 2**32 - 1
- Aspect ratios default (1152*896, 896*1152, etc.)
- Default styles, default LoRAs
- Performance steps mapping

**Tarefa 1.3: Enums** (`app/domain/enums.py`)
- PerformanceSelection (Speed/Quality/Extreme Speed/Lightning/Hyper-SD)
- UpscaleOrVaryMethod
- OutpaintExpansion
- ControlNetType
- MaskModel
- DescribeImageType
- RefinerSwapMethod

**Tarefa 1.4: Device Detection** (`app/services/model_manager.py:1-120`)
- Portar `get_torch_device()` de `model_management.py:76-91`
- Portar `VRAMState` e `CPUState` enums
- Portar detecção CUDA/MPS/DirectML/XPU
- Função `detect_gpu() -> GPUInfo(device, vram_total, vram_free)`
- Funcção `get_free_memory(device) -> int`

**Tarefa 1.5: VRAM Management** (`app/services/model_manager.py:120-500`)
- Portar `LoadedModel` class com `model_load()` / `model_unload()`
- Portar `load_models_gpu()` (LRU eviction por ordem de uso)
- Portar `free_memory()` com iteração reversa
- Portar `soft_empty_cache()` (CUDA/MPS/XPU cache clear)
- Portar `current_loaded_models` global list
- Portar `cleanup_models()` (refcount-based cleanup)
- **Novo:** `ModelManager` class com `preload()`, `unload_all()`, `get_status()`

**Tarefa 1.6: Lazy/Eager Load** (`app/services/model_manager.py:500-600`)
- Lazy (default): load on first request, unload after timeout (configurable via `MODEL_IDLE_TIMEOUT`)
- Eager: preload on startup via lifespan
- `ModelManager.start_lazy_timer()` / `ModelManager.cancel_timer()`
- Thread-safe with `threading.Lock`

**Tarefa 1.7: Docker** (`docker/`)
- `Dockerfile`: Multi-stage (api + worker targets)
- `Dockerfile.gpu`: nvidia/cuda:12.1.1 base, PyTorch 2.1+CUDA 12.1
- `docker-compose.yml`: 2 services (api + worker), NVIDIA runtime, volumes para models/outputs

**Critérios de Aceite:**
- `detect_gpu()` retorna device correto
- `load_models_gpu()` carrega/evicta modelos
- Lazy load: modelo descarrega após timeout
- Docker builda e roda com GPU

---

### FASE 2: Model Loading (Sprint 3-4)

**Objetivo:** Carregar SDXL checkpoints, LoRAs, refiner, expansion.

**Tarefa 2.1: Checkpoint Loading** (`app/services/checkpoint.py`)
- Portar `load_checkpoint_guess_config()` de `sd.py:430-493`
- Detectar SDXL vs SD1.5 vs SD2 vs SD3
- Retorna `StableDiffusionModel` com unet, vae, clip, clip_vision
- Handle VAE fp16 fix, dtype detection

**Tarefa 2.2: StableDiffusionModel** (`app/services/model_base.py`)
- Portar `StableDiffusionModel` class de `core.py:37-123`
- Fields: unet, vae, clip, clip_vision, filename, vae_filename
- unet_with_lora, clip_with_lora
- lora_key_map_unet, lora_key_map_clip
- visited_loras tracking
- **Novo:** Dataclass com validação

**Tarefa 2.3: ModelPatcher** (`app/services/model_patcher.py`)
- Portar `ModelPatcher` de `model_patcher.py`
- `patch_model()`: move to device, apply LoRA patches
- `unpatch_model()`: move to offload_device (CPU)
- `model_load()`: load into VRAM com lowvram support
- `model_unload()`: restore original weights, move to CPU

**Tarefa 2.4: LoRA Management** (`app/services/lora_manager.py`)
- Portar `refresh_loras()` de `core.py:62-123`
- Portar `model_lora_keys_unet()` / `model_lora_keys_clip()`
- Portar `match_lora()` de `modules/lora.py`
- Weight application (scale factor)
- LoRA stacking (múltiplos LoRAs simultâneos)
- visited_loras cache (skip reload se mesma config)

**Tarefa 2.5: Model Cache**
- Cache por filename em `refresh_base_model()` / `refresh_refiner_model()`
- Se `model_base.filename == filename` e `model_base.vae_filename == vae_filename`, skip
- LoRA cache: `visited_loras == str(loras)`

**Tarefa 2.6: Operators** (`app/infrastructure/operators.py`)
- Portar `EmptyLatentImage` de `contrib/external.py`
- Portar `VAEDecode` / `VAEEncode` / `VAEDecodeTiled` / `VAEEncodeTiled`
- Portar `ControlNetApplyAdvanced`
- Portar `FreeU_V2` de `contrib/external_freelunch.py`
- Portar `ModelSamplingDiscrete` / `ModelSamplingContinuousEDM`
- Wrapper classes com `patch()` / `__call__`

**Critérios de Aceite:**
- SDXL base carrega em < 30s
- LoRAs aplicam corretamente (peso 0-2)
- Cache evita reload do mesmo modelo
- Refiner load/unload condicional

---

### FASE 3: Pipeline Core (Sprint 5-6)

**Objetivo:** Text-to-image completo (CLIP → VAE → Diffusion → Decode).

**Tarefa 3.1: Pipeline Orchestration** (`app/services/pipeline.py`)
- Portar `refresh_everything()` de `default_pipeline.py:234-267`
- Portar `refresh_base_model()` / `refresh_refiner_model()`
- Portar `synthesize_refiner_model()`
- Portar `refresh_controlnets()` (cache-based)
- Portar `clip_encode()` / `clip_encode_single()` com caching
- Portar `set_clip_skip()` / `clear_all_caches()`
- Portar `prepare_text_encoder()`
- Portar `clone_cond()`
- **Novo:** PipelineState class (encapsula globals)

**Tarefa 3.2: VAE Operations** (`app/services/core_ops.py`)
- Portar `encode_vae()` de `core.py` (usa opVAEEncode)
- Portar `decode_vae()` de `core.py` (usa opVAEDecode)
- Portar `encode_vae_inpaint()` (mask + pixels → latent)
- Portar `encode_vae_tiled()` / `decode_vae_tiled()` (para upscale)
- Handle fp16 vs fp32 precision

**Tarefa 3.3: Diffusion Sampling** (`app/services/sampler.py`)
- Portar `process_diffusion()` de `default_pipeline.py` (linhas 278+)
- Sampler options: dpmpp_2m_ssd_gpu, euler, dpmpp_sde, etc.
- Scheduler options: karras, sgm_uniform, normal, etc.
- Refiner swap: joint/swap/alternative
- Callback para progress reporting
- Tile mode para imagens grandes

**Tarefa 3.4: Style Engine** (`app/services/style_engine.py`)
- Portar `apply_style()` de `modules/sdxl_styles.py`
- Portar `get_random_style()`
- Portar `fooocus_expansion` handling
- Portar `apply_arrays()` / `apply_wildcards()`
- Portar `remove_empty_str()` / `safe_str()`

**Tarefa 3.5: Patches** (`app/infrastructure/patches.py`)
- Portar TODOS os 8 monkey-patches de `modules/patch.py`
- `patch_all()` — ser chamado uma vez no startup
- Cada patch documentado com propósito

**Tarefa 3.6: Latent Formats** (`app/infrastructure/latent_formats.py`)
- Portar `LatentFormat` classes
- SDXL latent scaling factor
- SD1.5 latent format

**Critérios de Aceite:**
- Text → CLIP encode → latents → decode → image (file PNG)
- Estilos aplicam prompt/negative prompt
- Expansion gera texto adicional
- Sampler/scheduler configuráveis

---

### FASE 4: Worker + Task Queue (Sprint 7)

**Objetivo:** Async task processing, Celery integration.

**Tarefa 4.1: Task Queue** (`app/services/task_queue.py`)
- Portar `TaskQueue` / `QueueTask` de `fooocusapi/task_queue.py`
- FIFO queue com thread-safe
- `add_task()` → returns QueueTask
- `finish_task()` / `is_task_finished()`
- Webhook callback support
- Job status tracking (WAITING/RUNNING/FINISHED/FAILED)

**Tarefa 4.2: AsyncTask** (`app/services/worker.py:1-300`)
- Portar `AsyncTask` class de `worker.py:42-200`
- 80+ campos mapeados
- Performance modes com auto-config
- cn_tasks dict para ControlNet
- enhance_ctrls list para enhance pipeline

**Tarefa 4.3: process_generate — Text-to-Image** (`app/services/worker.py:300-800`)
- Portar `process_generate()` — PRIORIDADE: path text-to-image
- Sub-funções:
  - `process_prompt()` (line 755-868): refresh_everything → CLIP encode → expansion → styles
  - `apply_patch_settings()` (line 419-427)
  - `process_task()` (line 371-417): diffusion call + save
  - `yield_result()` / `return_result()`: result formatting
  - `save_and_log()`: metadata + file save

**Tarefa 4.4: Celery Integration** (`app/infrastructure/celery_config.py`, `celery_tasks.py`)
- Celery app config (redis broker)
- Task: `generate_image` — async generation
- Task: `cleanup_expired_jobs`
- Hard limit: 600s, Soft: 540s
- Concurrency: 1 (GPU single-threaded)

**Tarefa 4.5: Stop/Interrupt**
- `process_stop()` → `interrupt_current_processing()`
- Thread-safe interrupt flag
- Handle EarlyReturnException

**Critérios de Aceite:**
- Task queue aceita e processa jobs via Redis
- Text-to-image retorna imagem via Celery task
- Stop interrompe geração
- Progress callbacks funcionam

---

### FASE 5: API Routes (Sprint 8)

**Objetivo:** 26 rotas com parity com FOOOCUS.

**Tarefa 5.1: Auth** (`app/api/auth.py`)
- API key via `X-API-Key` header
- Exempt: /health, /health/deep, /ping, /
- `SE9_API_KEY` env var

**Tarefa 5.2: Health** (`app/api/health_routes.py`)
- GET / — home page (hidden from schema)
- GET /health — health check (checar worker status)
- GET /health/deep — deep health (verificar GPU, Redis, disk)
- GET /ping — simple pong

**Tarefa 5.3: V1 Generation** (`app/api/generate_routes.py`)
- POST /v1/generation/text-to-image — multipart form
- POST /v1/generation/image-upscale-vary — multipart + file upload
- POST /v1/generation/image-inpaint-outpaint — multipart + file upload
- POST /v1/generation/image-prompt — multipart + optional upload
- POST /v1/generation/image-enhance — multipart + optional upload
- POST /v1/generation/stop
- GET /v1/generation/query-job — ?job_id=&require_step_preview=
- GET /v1/generation/job-queue
- GET /v1/generation/job-history — ?job_id=&page=&page_size=&delete=
- GET /v1/generation/outputs

**Tarefa 5.4: V2 Generation** (`app/api/generate_v2_routes.py`)
- POST /v2/generation/text-to-image-with-ip — JSON body
- POST /v2/generation/image-upscale-vary — JSON body
- POST /v2/generation/image-inpaint-outpaint — JSON body
- POST /v2/generation/image-prompt — JSON body
- POST /v2/generation/image-enhance — JSON body

**Tarefa 5.5: Engines** (`app/api/models_routes.py`)
- GET /v1/engines/all-models
- GET /v1/engines/styles
- GET /v1/engines/styles-detail
- GET /v1/engines/clean_vram

**Tarefa 5.6: Tools** (`app/api/tools_routes.py`)
- POST /v1/tools/describe-image — multipart
- POST /v1/tools/generate_mask — JSON

**Tarefa 5.7: Files** (`app/api/file_routes.py`)
- GET /files/{date}/{file_name}

**Critérios de Aceite:**
- 26/26 rotas respondem
- Auth funciona (401 sem key)
- Request/response format idêntico ao FOOOCUS
- OpenAPI docs gerados automaticamente

---

### FASE 6: Features Avançadas (Sprint 9)

**Objetivo:** Upscale, Inpaint, ControlNet, Enhance, Performance Modes.

**Tarefa 6.1: Image Upscale/Vary**
- Portar `apply_vary()` do worker (vary subtle/strong)
- Portar `apply_upscale()` do worker (1.5x/2x/fast/custom)
- Portar `perform_upscale()` de `modules/upscaler.py`
- SR models: ESRGAN download + cache

**Tarefa 6.2: Image Inpaint/Outpaint**
- Portar `apply_inpaint()` do worker
- Portar `InpaintWorker` de `modules/inpaint_worker.py`
- Portar `apply_outpaint()` (pad/extend mask)
- Inpaint models: head + patch download

**Tarefa 6.3: ControlNet + IP-Adapter**
- Portar `apply_control_nets()` do worker
- Portar `load_ip_adapter()` / `patch_model()`
- Canny: `preprocessors.canny_pyramid()`
- CPDS: `preprocessors.cpds()`
- CLIP Vision loading

**Tarefa 6.4: Enhance Pipeline**
- Portar `process_enhance()` / `enhance_upscale()`
- SAM + DINO mask generation (`generate_mask_from_image`)
- Multi-pass enhancement com processing_order

**Tarefa 6.5: Performance Modes**
- Lightning: download LoRA, override sampler/scheduler/cfg
- LCM: same pattern
- Hyper-SD: same pattern
- Extreme Speed: LCM defaults

**Tarefa 6.6: process_generate — Full paths**
- Completar `process_generate()` com:
  - `apply_image_input()` (tabs: uov/inpaint/ip/enhance)
  - `apply_vary()` / `apply_upscale()` / `apply_inpaint()`
  - `apply_control_nets()` / `apply_freeu()`
  - `process_enhance()` / `enhance_upscale()`
  - Performance mode handling

**Critérios de Aceite:**
- Vary subtle/strong gera resultado correto
- Upscale 1.5x/2x funciona
- Inpaint com mask funciona
- IP-Adapter aplica estilo de imagem
- Enhance pipeline com SAM/DINO funciona

---

### FASE 7: Qualidade (Sprint 10)

**Tarefa 7.1: Testes Unitários**
- Model manager: mock GPU, test load/unload/evict
- Pipeline: mock models, test encode/decode flow
- Worker: mock pipeline, test task lifecycle
- ≥80% coverage

**Tarefa 7.2: Testes de Integração**
- Docker build
- Container health check
- Real GPU text-to-image generation
- All 26 routes via httpx

**Tarefa 7.3: Documentação**
- OpenAPI auto-generated (FastAPI)
- README com setup, configuração, API reference
- Docker compose examples

**Tarefa 7.4: Deploy**
- deploy.sh com SE9
- test_services_real.sh com SE9
- docker-compose.prod.yml

## 5. DEPENDÊNCIAS ENTRE FASES

```
FASE 1 (Infra) ──▶ FASE 2 (Models) ──▶ FASE 3 (Pipeline) ──▶ FASE 4 (Worker)
                                        │                       │
                                        ▼                       ▼
                                   FASE 5 (API Routes) ◀──────┘
                                        │
                                   FASE 6 (Advanced) ◀── FASE 4
                                        │
                                   FASE 7 (Quality) ◀── FASE 5+6
```

## 6. SEQUÊNCIA DE EXECUÇÃO (TEXT-TO-IMAGE FIRST)

```
SPRINT 1 (Dias 1-2): Infraestrutura Base
├── Criar se9-image-engine/ estrutura
├── app/core/config.py
├── app/core/constants.py
├── app/domain/enums.py
├── app/domain/models.py (reutilizar SE8)
├── run.py
├── requirements.txt
├── pyproject.toml
├── .env / .env.example
└── Makefile

SPRINT 2 (Dias 3-4): Model Manager + GPU
├── app/services/model_manager.py (device detection + VRAM)
├── app/services/model_patcher.py (load/unload/evict)
├── app/services/model_base.py (SDXL dataclass)
├── app/services/checkpoint.py (load_checkpoint_guess_config)
├── app/infrastructure/latent_formats.py
├── Testes unitários
└── Dockerfile

SPRINT 3 (Dias 5-6): Pipeline Core
├── app/services/pipeline.py (refresh_everything, clip_encode, vae)
├── app/services/core_ops.py (StableDiffusionModel, operators)
├── app/services/sampler.py (KSampler, schedulers)
├── app/infrastructure/patches.py (8 monkey-patches)
├── app/infrastructure/operators.py
└── Testes pipeline

SPRINT 4 (Dias 7-8): Worker + Task Queue
├── app/services/worker.py (text-to-image path)
├── app/services/task_queue.py
├── app/services/style_engine.py
├── app/infrastructure/celery_config.py
├── app/infrastructure/celery_tasks.py
└── Teste integração: gerar imagem via GPU

SPRINT 5 (Dias 9-10): API Routes (Core)
├── app/api/auth.py
├── app/api/health_routes.py
├── app/api/generate_routes.py (text-to-image only)
├── app/api/generate_v2_routes.py (text-to-image-with-ip only)
├── app/api/file_routes.py
├── docker-compose.yml
└── Testes API

SPRINT 6 (Dias 11-12): All Routes
├── V1 restantes (upscale-vary, inpaint, image-prompt, enhance, stop)
├── V2 restantes (4 rotas)
├── query-job, job-queue, job-history, outputs
├── app/api/models_routes.py
└── 26/26 rotas testadas

SPRINT 7 (Dias 13-14): LoRAs + Extras
├── app/services/lora_manager.py
├── app/extras/ip_adapter.py
├── app/extras/controlnet.py
├── app/extras/inpaint_worker.py
├── app/extras/upscaler.py
└── app/extras/expansion.py

SPRINT 8 (Dias 15-16): Enhance + Performance
├── app/extras/enhance.py
├── app/extras/face_restore.py
├── app/extras/face_crop.py
├── app/extras/censor.py
├── app/extras/preprocessors.py
├── app/extras/inpaint_mask.py
├── Performance modes (LCM/Lightning/Hyper-SD)
└── app/api/tools_routes.py

SPRINT 9 (Dias 17-18): Integration + Polish
├── Webhook callback
├── Metadata parser
├── File utils (save_output_file)
├── Redis/Celery integration completa
└── Testes de integração

SPRINT 10 (Dias 19-20): Quality
├── Testes unitários ≥80%
├── Testes integração GPU
├── Docker deploy completo
├── deploy.sh + test_services_real.sh
├── README + OpenAPI docs
└── Code review final
```

## 7. CRITÉRIOS DE ACEITE FINAL

| # | Critério | Como validar |
|---|---------|-------------|
| 1 | Docker build OK | `docker compose build` < 5min |
| 2 | Container roda | `docker compose up` + `/health` retorna 200 |
| 3 | GPU detectada | `/health/deep` mostra device + VRAM |
| 4 | Text-to-image funciona | POST `/v1/generation/text-to-image` retorna imagem |
| 5 | Lazy load funciona | VRAM antes ≠ VRAM depois de idle timeout |
| 6 | 26/26 rotas OK | Teste todas as rotas com curl |
| 7 | Auth funciona | 401 sem key, 200 com key |
| 8 | ≥80% coverage | `pytest --cov` |
| 9 | Testes GPU passam | `pytest -m gpu` |
| 10 | deploy.sh atualizado | SE9 no script de deploy |
