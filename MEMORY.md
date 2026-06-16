# Estado Atual — Monorepo PetCare / YTCaption

## Última sessão (2026-06-16)
- **SE8 IMAGE GENERATION COMPLETO** — 100% rota parity com FOOOCUS (24/24 + /health = 25 rotas)
- **PLAN.md arquivado** → `docs/arquive/PLAN.md`
- **Todos os 7 serviços rodando**: se1-se7 (ports 8001-8007), se8 (8008 + fooocus-api 8888)

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
| se8-image-generation | 8008 | ✅ Healthy | FOOOCUS proxy (GPU) |

## SE8 — Arquitetura

3 containers:
- `image-generation-api` (port 8008) — FastAPI proxy → FOOOCUS API
- `fooocus-api` (port 8888) — FOOOCUS stable diffusion API (nvidia/cuda:12.1.0)
- `image-generation-celery` — Async worker for image generation

### Rotas SE8 (25 = 24 FOOOCUS + /health)
**V1 Generation**: text-to-image, image-upscale-vary, image-inpaint-outpaint, image-prompt, image-enhance, stop, query-job, job-queue, job-history, outputs
**V2 Generation**: text-to-image-with-ip, image-upscale-vary, image-inpaint-outpaint, image-prompt, image-enhance
**Models**: all-models, styles, styles-detail, clean_vram
**Tools**: describe-image, generate_mask
**Files**: /files/{date}/{file_name}
**Health**: /health, /health/deep, /ping, / (home)

### Arquivos-chave SE8
- `app/main.py` — FastAPI app com 6 routers
- `app/domain/models.py` — Pydantic V1+V2+Tools models
- `app/services/image_service.py` — FooocusClient com raw body proxy
- `app/api/generate_routes.py` — V1 generation (multipart form)
- `app/api/generate_v2_routes.py` — V2 generation (JSON)
- `app/api/tools_routes.py` — describe-image, generate_mask
- `app/api/file_routes.py` — /files/{date}/{filename}
- `app/api/models_routes.py` — engines
- `app/api/health_routes.py` — health, ping, home
- `docker/docker-compose.yml` — 3 containers
- `docker/Dockerfile.fooocus` — FOOOCUS container

### Config SE8
- `path_outputs=/app/fooocus/outputs/files` (must match file_utils.output_dir)
- FOOOCUS model paths via env vars: path_checkpoints, path_loras, etc.
- Redis DB=8
- FooocusClient: raw body forwarding (Request → httpx → fooocus-api:8888)

## Pendências SE8
1. Commitar mudanças do se8
2. Atualizar deploy.sh e test_services_real.sh
3. Atualizar README com documentação das rotas
4. Atualizar docker-compose.prod.yml volume binds

## Decisões de Arquitetura
- FOOOCUS é read-only (se8 faz proxy via HTTP)
- Raw body forwarding para V1 multipart e V2 JSON
- GPU mandatory para se8 (PyTorch+CUDA+SDXL ~11GB)
- Portas sequenciais: 8001-8008
- shared/ renomeado de common/, bind-mount como /app/common em containers

## Riscos
- FOOOCUS fooocus-api container foi criado via `docker run` (não docker-compose) devido a erro de interpolação `${DIVISOR}` no .env
- 11GB de modelos em se8/data/models/ (commitar via Git LFS se necessário)
