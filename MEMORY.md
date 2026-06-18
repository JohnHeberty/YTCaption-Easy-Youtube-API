# Estado Atual — Monorepo YTCaption

## Última sessão (2026-06-18)
- **SE8 IMAGE ENGINE COMPLETO** — 100% E2E validado com GPU real (RTX 3090)
- **10/10 rotas de geração SUCCESS** — text-to-image, upscale, inpaint, image-prompt, enhance (V1+V2)
- **25/25 rotas respondendo** — health, engines, generation, query, tools, files, auth
- **104 testes pytest** — 103 passing, 1 deselected (pre-existing webp content-type test)
- **FOOOCUS completamente isolado** — 227 arquivos vendored (ldm_patched, modules, extras, sdxl_styles)
- **SE8 antigo (proxy) removido** — SE9 renomeado para SE8
- **Docker GPU funcional** — nvidia/cuda:12.1.1, torch 2.1.0+cu121, RTX 3090 24GB

## Serviços Ativos

| Service | Port | Status | Description |
|---|---|---|---|
| se1-audio-transcription | 8001 | ✅ Healthy | Whisper transcription |
| se2-video-processor | 8002 | ✅ Healthy | Video processing |
| se3-video-editor | 8003 | ✅ Healthy | Video editing (GPU) |
| se4-face-recognition | 8004 | ✅ Healthy | Face recognition (GPU) |
| se5-image-generation | 8005 | ✅ Healthy | Image generation (GPU) |
| se6-notification | 8006 | ✅ Healthy | Push notifications |
| se7-audio-generation | 8007 | ✅ Healthy | TTS/STT (GPU) |
| se8-image-generation | 8008 | ✅ Healthy | Image engine (GPU, FOOOCUS rewrite) |

## SE8 — Arquitetura Atual

1 container unificado (GPU+API):
- `image-engine` (port 8008) — FastAPI + in-memory worker thread + GPU pipeline
- FOOOCUS dependencies vendored em `ldm_patched/`, `modules/`, `extras/`, `sdxl_styles/`
- Zero dependência externa do repositório FOOOCUS

### Rotas SE8 (25 total)
**Health (4)**: /, /ping, /health, /health/deep
**Engines (4)**: all-models, styles, styles-detail, clean_vram
**V1 Generation (5)**: text-to-image, image-upscale-vary, image-inpaint-outpaint, image-prompt, image-enhance
**V2 Generation (5)**: text-to-image-with-ip, image-upscale-vary, image-inpaint-outpaint, image-prompt, image-enhance
**Query (4)**: query-job, job-queue, job-history, outputs
**Tools (2)**: describe-image, generate_mask
**Files (1)**: /files/{date}/{file_name}
**Missing**: POST /v1/generation/stop (FOOOCUS tem, SE8 não)

### Arquivos-chave SE8
- `app/main.py` — FastAPI app com 7 routers, worker thread no lifespan
- `app/domain/models.py` — Pydantic V1+V2+Tools models
- `app/services/pipeline.py` — Pipeline de geração (817 linhas)
- `app/services/worker.py` — Worker loop + process_generate (664 linhas)
- `app/services/model_manager.py` — GPU/VRAM management (793 linhas)
- `app/services/checkpoint.py` — Model loading (476 linhas)
- `app/api/api_utils.py` — call_worker, req_to_params (385 linhas)
- `docker/Dockerfile.gpu-api` — Container unificado GPU+API
- `docker/docker-compose.gpu.yml` — Docker compose com GPU mounts

### Config SE8
- Port: 8008, API Key: se8-test-key-2026
- Redis DB=8, GPU_MODE=lazy
- MODEL_DIR: ./data/models, OUTPUT_DIR: ./data/outputs
- Container: appuser (uid=1000), python3.11, torch 2.1.0+cu121

## Bugs Corrigidos nesta Sessão
1. `ldm_patched/modules/model_sampling.py` — torch.cumprod() numpy compat (torch.tensor wrapper)
2. `app/services/pipeline.py` — VAE name "Automatic" treated as filename
3. `app/services/pipeline.py` — patch_settings[pid] KeyError (2 locations)
4. `app/infrastructure/core_ops.py` — VAEApprox not inheriting torch.nn.Module
5. `app/api/tools_routes.py` — fooocusapi import replaced with inline helpers

## Decisões de Arquitetura
- SE8 antigo (proxy) foi removido — SE9 renomeado para SE8
- Container unificado (API+worker no mesmo container, thread-based)
- FOOOCUS 100% vendored — ldm_patched, modules, extras, sdxl_styles copiados para dentro do SE8
- modules/config.py paths adaptados de `../models/` para `../data/models/`
- GPU via manual device/lib mounts (nvidia-container-toolkit 1.18.2 tem bug com driver 590)

## Riscos
- GPU devices montados manualmente no docker-compose (não usa nvidia-ctk)
- transformsers 5.x incompatível — fixado com 4.37.2
- numpy 2.x incompatível com torch 2.1 — fixado com <2
- GPG keys expired no base image ubuntu — usa --allow-insecure-repositories
