# Estado Atual — Monorepo YTCaption

## Última sessão (2026-06-19/20)
- **SE11 Clothes Removal** — criado do zero (23 arquivos), 11 testes passando, **E2E validado** via Docker compose
- **SE10 Masks** — modificado para retornar masks binárias (3 arquivos alterados)
- **SE10 Deploy** — Docker compose rebuild com todos fixes: SAM2 config, bertwarper transformers 5.x, segmentor area
- **SE11 PNG transparency fix** — `require_base64=False` + download via URL, resultado RGB válido
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
| se10-clothes-segmentation | 8010 | ✅ Healthy | GroundingDINO+SAM2 (CPU) |
| se11-clothes-removal | 8011 | ✅ E2E validated | SE10→SE8 inpaint pipeline |

## SE11 — Clothes Removal Service

### Arquitetura
Fluxo: imagem → SE10 (detecção de roupas + masks) → combina masks (union OpenCV) → SE8 (Fooocus inpaint) → resultado

### Endpoints
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
- ✅ Deep health detecta SE8=ok, SE10=ok
- ✅ **E2E passou (compose-persisted)**: SE11 → SE10 → SE8 → resultado RGB 931KB, 24s
- ✅ **PNG transparency fix**: resultado é RGB (não RGBA)

### SE11 Config
- Port: 8011, API_KEY: se11-test-key-2026
- DIVISOR=11, Redis DB=11
- SE10_URL=http://host.docker.internal:8010 (Docker) / http://localhost:8010 (local)
- SE8_URL=http://host.docker.internal:8008 (Docker) / http://localhost:8008 (local)
- DEFAULT_PROMPT="nude, naked body, smooth skin"

### Fixes aplicados
1. **base64 padding** — `_fix_b64_padding()` antes de `b64.b64decode()`
2. **PNG transparency** — `require_base64=False` em SE8 client + download via file URL, evita base64 truncado do SE8

## SE10 — Clothes Segmentation

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
- `groundingdino_swint_ogc.pth` (662MB) em `checkpoints/`
- `sam2_hiera_tiny.pt` (149MB) em `checkpoints/`

### External deps
- `external/GroundingDINO/` ← IDEA-Research/GroundingDINO (depth 1)
- `external/segment-anything-2/` ← facebookresearch/sam2 (depth 1)
- Bertwarper patchado para transformers>=5.0

## SE9 — Make Video IMG
### FIX-2 validado e arquivado
- `concat_simple()` em `ffmpeg_utils.py:303` — resolve SIGKILL com >8 segmentos
- 27/27 testes passando

## SE8 — Image Engine
- Port: 8008, Container: `image-engine`, nvidia/cuda:12.1.1
- Rotas: Health(4) + Engines(4) + V1 Gen(5) + V2 Gen(5) + Query(4) + Tools(2) + Files(1)

## Docs Arquivados
```
docs/archive/se9-make-video-img/
├── FIX-ERROS-2026-06-19.md
├── FIX-2-2026-06-19.md
├── INVESTIGACAO-v4.1.md
└── VALID-2026-06-17.md
```

## Próximos Passos
1. ✅ SE10 deploy com todos fixes — Docker compose rebuild persistido
2. ✅ SE11 E2E testado via compose — pipeline completo funciona, RGB válido
3. Integração SE11 ao SE1 ou APIs externas
