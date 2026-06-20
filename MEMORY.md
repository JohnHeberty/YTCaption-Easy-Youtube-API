# Estado Atual — Monorepo YTCaption

## Última sessão (2026-06-19)
- **SE11 Clothes Removal** — criado do zero (23 arquivos), 11 testes passando
- **SE10 Masks** — modificado para retornar masks binárias (3 arquivos alterados)
- **FIX-2 arquivado** — concat SIGKILL fix + INVESTIGACAO.md restaurado
- **Root docs limpos** — apenas AGENTS.md, INVESTIGATION.md, MEMORY.md, README.md, SE9-UP.md

## Serviços Ativos

| Service | Port | Status | Description |
|---|---|---|---|
| se1-orchestrator | 8001 | ✅ Healthy | Pipeline orchestrator |
| se2-video-downloader | 8002 | ✅ Healthy | Video download |
| se3-audio-normalization | 8003 | ✅ Healthy | Audio normalization |
| se4-audio-transcriber | 8004 | ✅ Healthy | Whisper transcription |
| se5-video-clip | 8005 | ✅ Healthy | Video clip generation |
| se6-youtube-search | 8006 | ✅ Healthy | YouTube search |
| se7-audio-generation | 8007 | ✅ Healthy | TTS Chatterbox (GPU) |
| se8-image-generation | 8008 | ✅ Healthy | Fooocus SDXL (GPU) |
| se9-make-video-img | 8009 | ✅ Healthy | Ken Burns video builder |
| se10-clothes-segmentation | 8010 | ⛔ Not deployed | GroundingDINO+SAM2 (sem external/) |
| se11-clothes-removal | 8011 | ✅ Local tested | SE10→SE8 pipeline (nova impl) |

## SE11 — Clothes Removal Service (NOVO)

### Arquitetura
Fluxo: imagem → SE10 (detecção de roupas + masks) → combina masks (union OpenCV) → SE8 (Fooocus inpaint) → resultado

### Arquivos (23)
```
services/se11-clothes-removal/
├── app/main.py, worker.py, run.py
├── app/core/config.py, constants.py, models.py
├── app/api/routes.py, health_routes.py, download_routes.py, admin_routes.py
├── app/services/pipeline.py
├── app/infrastructure/redis_store.py, http_client.py
├── docker/Dockerfile, docker-compose.yml
├── tests/conftest.py, tests/unit/test_pipeline.py
├── .env, .env.example, requirements.txt, .gitignore, Makefile
```

### Endpoints SE11
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /jobs | ✅ | Criar job (image base64) |
| GET | /jobs | ✅ | Listar jobs |
| GET | /jobs/{id} | ✅ | Status do job |
| DELETE | /jobs/{id} | ✅ | Deletar job |
| GET | /jobs/{id}/download | ✅ | Download resultado |
| GET | /health | ❌ | Health check |
| GET | /health/deep | ❌ | Deep health (SE10+SE8) |
| GET | /ping | ❌ | Pong |
| GET | /admin/stats | ✅ | Estatísticas |
| POST | /admin/cleanup | ✅ | Cleanup |

### Validação SE11
- ✅ 11/11 testes unitários passando
- ✅ Todos os módulos py_compile OK
- ✅ API server inicia, health/ping respondem
- ✅ Deep health detecta SE8=ok, SE10=unreachable
- ✅ Job creation funciona (falha esperada no SE10 por indisponibilidade)
- ✅ Admin stats e list funcionam

### Bloqueio SE11 E2E
- SE10 não deployável — diretórios `external/GroundingDINO/` e `external/segment-anything-2/` não existem no repo
- Docker build falha: `COPY external/` → not found
- **Para E2E completo:** clonar repos ML + baixar checkpoints

## SE10 — Modificações para Masks (2026-06-19)

### Arquivos alterados (3)
1. `app/domain/models.py` — `masks: Optional[List[str]]` em SegmentResult
2. `app/services/segmentor.py` — encoding binário SAM2 masks → base64 PNG
3. `app/api/routes.py` — passa masks do segmentor para response

### docker-compose.yml corrigido
- Context corrigido para `../../..` (monorepo root)
- Volumes corrigidos
- `extra_hosts` adicionado para host.docker.internal
- `version: "3.8"` removido (deprecated)

## SE9 — Make Video IMG (2026-06-19)

### FIX-2 validado e arquivado
- `concat_simple()` implementado em `ffmpeg_utils.py:303` — resolve SIGKILL com >8 segmentos
- `video_assembler.py` usa concat_simple quando >8 segmentos, xfade quando ≤8
- 27/27 testes passando
- E2E validado com script 100 (17 narrações, 12 segmentos)

## SE8 — Image Engine

### Config
- Port: 8008, API Key: se8-test-key-2026
- Container unificado GPU+API com Fooocus vendored
- Docker: `image-engine` container, nvidia/cuda:12.1.1, torch 2.1.0+cu121

### Rotas SE8 (25)
Health(4) + Engines(4) + V1 Gen(5) + V2 Gen(5) + Query(4) + Tools(2) + Files(1)

## Docs Arquivados (2026-06-19)
```
docs/archive/se9-make-video-img/
├── FIX-ERROS-2026-06-19.md
├── FIX-2-2026-06-19.md
├── INVESTIGACAO-v4.1.md
└── VALID-2026-06-17.md
```

## Próximos Passos
1. **SE10 deploy** — clonar GroundingDINO + SAM2, baixar checkpoints, buildar Docker
2. **SE11 E2E** — testar pipeline completo SE10→SE8 com imagem real
3. **SE11 Docker** — buildar e deployar com compose
4. **Integração** — conectar SE11 ao SE1 ou APIs externas
