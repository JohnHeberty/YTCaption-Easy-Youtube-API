# Arquitetura do Monorepo

## Estrutura Geral

Monorepo multi-serviço Python. Cada serviço é um microserviço FastAPI independente com seu próprio `Dockerfile`, `requirements.txt` e testes.

| Diretório | Port | Descrição | Stack | Status |
|---|---|---|---|---|
| `services/se1-orchestrator/` | 8001 | Pipeline orchestrator | FastAPI + Celery | Ativo |
| `services/se2-video-downloader/` | 8002 | Video download (yt-dlp) | FastAPI + Celery | Ativo |
| `services/se3-audio-normalization/` | 8003 | Audio normalization (ffmpeg) | FastAPI + Celery | Ativo |
| `services/se4-audio-transcriber/` | 8004 | Whisper transcription | FastAPI + Celery | Ativo |
| `services/se5-make-video-clip/` | 8005 | Video clip generation (ffmpeg) | FastAPI + Celery | Ativo |
| `services/se6-youtube-search/` | 8006 | YouTube search API | FastAPI + Celery | Ativo |
| `services/se7-audio-generation/` | 8007 | TTS Chatterbox (GPU) | FastAPI + Celery | Ativo |
| `services/se8-image-generation/` | 8008 | Fooocus SDXL (GPU) | FastAPI + Thread worker | Ativo |
| `services/se9-make-video-img/` | 8009 | Ken Burns video builder | FastAPI + Thread worker | Ativo |
| `services/se10-clothes-segmentation/` | 8010 | GroundingDINO+SAM2 (CPU) | FastAPI + ThreadPoolExecutor | Ativo |
| `services/se11-clothes-removal/` | 8011 | SE10→SE8 inpaint pipeline | FastAPI + Celery | Ativo |
| `shared/` | — | Biblioteca compartilhada | models, config, utils, middleware | Ativo |

### Caminhos Importantes
- Root: `/root/YTCaption-Easy-Youtube-API`
- Services: `/root/YTCaption-Easy-Youtube-API/services/`
- Shared: `/root/YTCaption-Easy-Youtube-API/shared/`
- FOOOCUS ref: `/root/YTCaption-Easy-Youtube-API/FOOOCUS/` (imutável)

### Regras Estruturais
- Cada serviço é independente — não importar entre serviços diretamente.
- Usar `shared/` para código comum (models, config, utils, middleware).
- Redis: cada serviço usa DB diferente (SE1=DB1, SE2=DB2, ... SE11=DB11).
- Docker compose para deploy e orquestração.
- `FOOOCUS/` é referência imutável — nunca modificar.

## Arquitetura por Serviço

### SE1-SE6 (Pipeline clássico)
- FastAPI + Celery + Redis
- Worker assíncrono via Celery
- Auth: `X-API-Key` header
- Config: variáveis de ambiente (`.env`)
- Health: `GET /health`, `GET /ping`
- Jobs: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs/{id}`

### SE7 (Audio Generation)
- TTS Chatterbox (GPU obrigatório)
- Voice profiles via `voice_seeder.py`
- Container: nvidia/cuda base

### SE8 (Image Engine)
- FOOOCUS rewrite completo (ldm_patched, modules, extras)
- Container unificado (API + worker em thread)
- 8 monkey-patches FOOOCUS replicados
- Container: `image-engine`, nvidia/cuda:12.1.1

### SE9 (Video IMG)
- Ken Burns video builder
- In-memory worker (não Celery)
- Pipeline: script → áudio → imagens → vídeo

### SE10-SE11 (Clothes)
- SE10: GroundingDINO+SAM2 (CPU only)
- SE11: SE10→SE8 inpaint pipeline
- External deps: GroundingDINO, segment-anything-2

## Shared Library (`shared/`)

Biblioteca compartilhada entre todos os serviços:
- `models/` — Pydantic v2 models (BaseJob, etc.)
- `config_utils/` — Settings base, env parsing
- `middleware/` — Auth, request logging
- `health_utils/` — Health check helpers
- `redis_utils/` — Redis connection helpers
- `log_utils/` — Structured logging
- `di.py` — Dependency injection container

## Docker

Cada serviço tem seu próprio Dockerfile. Deploy via `docker-compose.yml` na raiz.
- SE7, SE8: GPU (nvidia/cuda)
- SE10: CPU only
- Demais: CPU
- Container naming: `ytcaption-se{N}-{service-name}`

## Convenções

- Python 3.10+, `from __future__ import annotations`
- Pydantic v2 (não v1)
- pathlib.Path para caminhos
- Type hints completos
- pytest para testes
- Exceções específicas, não `except Exception` genérico
