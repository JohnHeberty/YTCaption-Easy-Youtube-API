# SE9 — Make Video IMG

## Documento de Investigação e Arquitetura (v3)

**Data:** 2026-06-19  
**Status:** Implementado e validado  
**Porta:** 8009 | **API Key:** se9-test-key-2026

---

## 1. Visão Geral

### O que é
Microserviço SE9 que gera vídeos para redes sociais (TikTok, Reels, Shorts) a partir de **payload JSON enviado pelo n8n**. O n8n coleta posts (Reddit, Twitter, RSS), gera roteiros com IA, e manda tudo para o SE9 via API REST.

### Fluxo completo

```
Reddit/Twitter → n8n (coleta + roteiro) → POST /jobs → SE9 (orquestra)
  ├── SE7 (áudio TTS)     → narração WAV
  ├── SE8 (imagens SDXL)  → cenas PNG
  └── FFmpeg (assembly)    → vídeo final MP4
```

### Por que é separo do SE5?

| SE5 (Make Video Clip) | SE9 (Make Video IMG) |
|---|---|
| Fonte: YouTube shorts | Fonte: Imagens geradas (SE8) |
| Áudio: Upload manual | Áudio: Gerado automaticamente (SE7) |
| Pipeline: Download → Transform → Validate | Pipeline: Script → Audio → Images → Compose |
| Redis DB: 5 | Redis DB: 9 |
| Celery worker | In-memory worker thread |

São fluxos completamente diferentes. SE9 é mais simples e especializado.

---

## 2. API Completa

### 2.1 Criar job

```http
POST /jobs
X-API-Key: se9-test-key-2026
Content-Type: application/json

{
  "post_id": "1q5o4zw",
  "hook": "No Réveillon, um papo que quase virou algo mais...",
  "estimated_seconds": 96,
  "language": "pt-BR",
  "narration": [
    {"t": 0, "text": "Eu vi a matéria e fiquei perplexo..."},
    {"t": 8, "text": "O documento foi encontrado no fim de 2025..."}
  ],
  "scene_suggestions": [
    {"t": 0, "visual": "B-roll de arquivos antigos, fotos em preto e branco."},
    {"t": 8, "visual": "Imagem de uma estante de livros em um apartamento."}
  ],
  "on_screen_text": [
    {"t": 0, "text": "15 anos depois..."}
  ],
  "title_options": ["O Passaporte Perdido"],
  "hashtags": ["#relatos", "#misterio"],
  "safety_notes": [],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16",
  "zoom_style": "random",
  "webhook_url": "https://n8n.seu-dominio.com/webhook/video-ready"
}
```

**Resposta:**
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "queued",
  "post_id": "1q5o4zw",
  "estimated_seconds": 96,
  "scenes_count": 2,
  "message": "Video generation started"
}
```

### 2.2 Consultar status

```http
GET /jobs/{job_id}
```

```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_audio",
  "progress": 25,
  "stages": {
    "generating_audio": {"status": "processing", "progress": 50},
    "generating_images": {"status": "pending", "progress": 0},
    "assembling_video": {"status": "pending", "progress": 0}
  },
  "created_at": "2026-06-19T15:00:00-03:00",
  "error": null
}
```

### 2.3 Download

```http
GET /download/{job_id}
→ video/mp4 (FileResponse)
```

### 2.4 Listar jobs

```http
GET /jobs
```

```json
{
  "jobs": [
    {"job_id": "rbg_xxx", "status": "completed", "progress": 100, "post_id": "...", "created_at": "..."}
  ],
  "total": 1
}
```

### 2.5 Deletar job

```http
DELETE /jobs/{job_id}
```

Remove diretório de output E chave Redis.

### 2.6 Health check

```http
GET /health
```

```json
{
  "status": "healthy",
  "service": "make-video-img",
  "version": "1.0.0",
  "checks": {
    "se7": {"status": "ok"},
    "se8": {"status": "ok"},
    "disk": {"status": "ok"},
    "ffmpeg": {"status": "ok"}
  }
}
```

### 2.7 Ping

```http
GET /ping
→ {"pong": true}
```

### 2.8 Admin

```http
GET /admin/stats    → job counts by status, disk usage
POST /admin/cleanup → remove failed job dirs + Redis keys
```

### 2.9 Webhook de notificação

Quando o vídeo estiver pronto, o SE9 faz POST no `webhook_url`:

```json
{
  "event": "video_ready",
  "job_id": "rbg_a1b2c3d4e5f6",
  "post_id": "1q5o4zw",
  "status": "completed",
  "download_url": "http://se9-host:8009/download/rbg_a1b2c3d4e5f6",
  "title": "O Passaporte Perdido",
  "hashtags": ["#relatos", "#misterio"],
  "duration_seconds": 96
}
```

Retry: 3 tentativas com backoff exponencial (2s, 4s, 8s).

---

## 3. Arquitetura Interna

### 3.1 Árvore de arquivos (22 arquivos)

```
services/se9-make-video-img/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + lifespan + router setup
│   ├── worker.py                  # In-memory worker thread
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # BaseServiceSettings (Pydantic)
│   │   ├── models.py              # VideoJob, CreateVideoRequest, enums
│   │   └── constants.py           # JOB_ID_PREFIX, ASPECT_RATIOS, ZOOM_STYLES, TRANSITIONS
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # POST /jobs, GET /jobs, GET/DELETE /jobs/{id}
│   │   ├── download_routes.py     # GET /download/{id}
│   │   ├── health_routes.py       # GET /health, GET /ping
│   │   ├── admin_routes.py        # GET /admin/stats, POST /admin/cleanup
│   │   └── webhook.py             # POST webhook com retry
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_generator.py     # SE7 client + chunking + WAV concat
│   │   ├── image_generator.py     # SE8 client (sync mode)
│   │   ├── video_assembler.py     # FFmpeg assembly orchestrator
│   │   └── pipeline.py            # Pipeline full orchestrator
│   └── infrastructure/
│       ├── __init__.py
│       ├── http_client.py         # SE7Client + SE8Client (httpx async)
│       ├── ffmpeg_utils.py        # FFmpeg wrappers (zoompan, xfade, concat)
│       └── redis_store.py         # VideoJobStore + _FakeRedis fallback
├── docker/
│   ├── Dockerfile                 # Python 3.11-slim + ffmpeg
│   └── docker-compose.yml         # Port 8009, healthcheck, 2G memory
├── tests/
│   ├── conftest.py                # Shared fixtures, auto-detect SE7/SE8
│   ├── fixtures_loader.py         # CSV loader (7 fixtures, 975 scripts)
│   ├── fixtures/                  # CSV files from make-video-backgraund/db/data/
│   ├── unit/
│   │   ├── test_models.py         # 10 tests: models, enums, constants
│   │   ├── test_store.py          # 5 tests: FakeRedis CRUD
│   │   ├── test_audio_chunking.py # 7 tests: text splitting, narration concat
│   │   └── test_video_assembler_srt.py # 3 tests: scene duration calculation
│   └── e2e/
│       ├── test_full_pipeline.py  # Mock mode (offline) + real mode (SE7+SE8)
│       └── test_real_pipeline.py  # Real CSV fixture test with SE7+SE8
├── Makefile                       # build, up, down, logs, test
├── requirements.txt               # fastapi, pydantic, httpx, redis
├── .env                           # Configuração completa
├── .env.example                   # Template
├── run.py                         # Entry point (uvicorn)
└── pytest.ini                     # testpaths, markers e2e
```

### 3.2 Camadas

| Camada | Arquivos | Responsabilidade |
|---|---|---|
| **Core** | config.py, models.py, constants.py | Configuração, modelos de dados, constantes |
| **API** | routes.py, download_routes.py, health_routes.py, admin_routes.py, webhook.py | HTTP endpoints, validação |
| **Services** | audio_generator.py, image_generator.py, video_assembler.py, pipeline.py | Lógica de negócio |
| **Infrastructure** | http_client.py, ffmpeg_utils.py, redis_store.py | Clients externos, FFmpeg, persistência |

---

## 4. Pipeline Detalhado

### 4.1 Fase 1 — Receber payload (routes.py)

1. Validar payload: `post_id`, `hook`, `estimated_seconds`, `narration`, `scene_suggestions`
2. Gerar `job_id`: `rbg_{uuid4().hex[:12]}`
3. Criar `VideoJob` com status `QUEUED`
4. Salvar no Redis (TTL 2 dias)
5. Iniciar worker (se não está rodando)
6. Retornar `job_id` imediatamente

### 4.2 Fase 2 — Gerar áudio (pipeline.py → audio_generator.py)

1. Concatenar `narration` em texto único (ordenado por timestamp)
2. Chunking: se texto > 5000 chars, dividir por parágrafos → frases → hard split
3. Para cada chunk: SE7 POST /jobs → poll → download WAV
4. Concat WAV files via ffmpeg concat filter
5. Obter duração real via ffprobe

**Retry:** até 3 tentativas, backoff exponencial (2s, 4s, 8s)  
**Timeout SE7:** 600s total  
**Tempo real (GPU):** ~35s | **CPU:** ~3-5min

### 4.3 Fase 3 — Gerar imagens (pipeline.py → image_generator.py)

1. Para cada `scene_suggestion`:
   - Enviar prompt + suffix cinematográfico para SE8 POST /v1/generation/text-to-image
   - SE8 retorna lista de imagens (síncrono, sem polling)
   - Download PNG via GET /files/{date}/{filename}
   - Salvar como `scene_{t}.png`
2. Progress callback: atualiza Redis a cada imagem

**Prompt suffix automático:** `, cinematic composition, depth of field, volumetric lighting, high detail, professional photography, 8k resolution`  
**Tempo real:** ~10s por imagem

### 4.4 Fase 4 — Montar vídeo (pipeline.py → video_assembler.py)

```
1. Calcular número de cenas necessárias:
   per_scene_duration = total_span / (narration_segments - 1)  [clamp 3-15s]
   num_scenes_needed = audio_duration / per_scene_duration + 1

2. Loop circular de imagens: image_paths[i % len(image_paths)]

3. Criar title card (3s) se hook_text:
   - Imagem 2x rescaled → zoompan lento → darkened (black@0.6)
   - Texto branco centralizado com fade-in (0.8s)
   - Fallback sem texto se drawtext indisponível

4. Para cada cena, criar segmento Ken Burns:
   - zoom_in: 1.0 → 1.20 (linear, contínuo)
   - zoom_out: 1.20 → 1.0 (linear, contínuo)
   - Alternância: sequências A/B por segmento
   - Velocidade auto-calculada: (ZOOM_MAX - ZOOM_MIN) / n_frames
   - Filter chain: scale 2x → zoompan → format yuv420p

5. Concatenar segmentos:
   - ≤8 segmentos: xfade com transições aleatórias (32 tipos)
   - >8 segmentos: batches de 8 com xfade + concat_simple entre batches

6. Pad áudio com silêncio no início (duração do title card)

7. Adicionar áudio ao vídeo:
   - AAC-LC, 44100Hz, stereo, 192k
   - -c:v copy (sem re-encode de vídeo)

8. Trim para duração do áudio padded:
   - Re-encode com H264 Main Profile Level 4.0
```

### 4.5 Fase 5 — Entregar resultado

1. Vídeo salvo em `data/outputs/{job_id}/{job_id}_final.mp4`
2. Status → `COMPLETED`
3. Webhook enviado se configurado
4. Todos os artefatos preservados (audio, imagens, intermediários)

---

## 5. Modelos de Dados

### 5.1 VideoJobStatus (6 estados)

```
QUEUED → GENERATING_AUDIO → GENERATING_IMAGES → ASSEMBLING_VIDEO → COMPLETED
                    ↓                                ↓
                FAILED                           FAILED
```

### 5.2 VideoJob

```python
class VideoJob(BaseModel):
    job_id: str                           # "rbg_a1b2c3d4e5f6"
    post_id: str                          # ID do post original
    status: VideoJobStatus                # Estado atual
    progress: float                       # 0-100 (ponderado: audio 40%, images 30%, assembly 30%)
    stages: dict[str, StageInfo]          # 3 estágios com progress individual
    request: CreateVideoRequest           # Payload original do n8n
    audio_path: Optional[str]             # Caminho do WAV gerado
    video_path: Optional[str]             # Caminho do MP4 final
    images: list[str]                     # Caminhos das imagens geradas
    created_at: datetime
    updated_at: datetime
    error: Optional[str]                  # Mensagem de erro se FAILED
```

### 5.3 CreateVideoRequest (16 campos)

| Campo | Tipo | Obrigatório | Default |
|---|---|---|---|
| post_id | str | Sim | — |
| hook | str | Sim | — |
| estimated_seconds | int | Sim | — |
| language | str | Não | "pt-BR" |
| content_rating | str | Não | "Geral" |
| narration | list[NarrationSegment] | Sim | — |
| scene_suggestions | list[SceneSuggestion] | Sim | — |
| on_screen_text | list[OnScreenText] | Não | [] |
| title_options | list[str] | Não | [] |
| hashtags | list[str] | Não | [] |
| safety_notes | list[str] | Não | [] |
| voice_id | str | Não | "builtin_feminino" |
| aspect_ratio | str | Não | "9:16" |
| zoom_style | str | Não | "random" |
| webhook_url | Optional[str] | Não | None |

### 5.4 StageInfo

```python
class StageInfo(BaseModel):
    status: StageStatus      # pending | processing | completed | failed
    progress: float          # 0.0 - 100.0
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

---

## 6. Configuração (.env)

```bash
# APP
APP_NAME=Make Video IMG
APP_VERSION=1.0.0
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8009
WORKERS=1
API_KEY=se9-test-key-2026
TZ=America/Sao_Paulo
DIVISOR=9

# REDIS
REDIS_URL=redis://192.168.1.110:6379/9

# SE7
SE7_URL=http://localhost:8007
SE7_API_KEY=se7-test-key-2026

# SE8
SE8_URL=http://localhost:8008
SE8_API_KEY=se8-test-key-2026

# VIDEO DEFAULTS
DEFAULT_VOICE_ID=builtin_feminino
DEFAULT_ASPECT_RATIO=9:16
DEFAULT_WIDTH=1080
DEFAULT_HEIGHT=1920
DEFAULT_FPS=30
DEFAULT_ZOOM_SPEED=0.004
DEFAULT_CROSSFADE_DURATION=0.3
DEFAULT_IMAGE_STEPS=30
DEFAULT_IMAGE_PERFORMANCE=Quality

# TTS PARAMS (passed to SE7)
TTS_EXAGGERATION=0.5
TTS_CFG_WEIGHT=0.7
TTS_TEMPERATURE=0.5

# TIMEOUTS
SE7_POLL_INTERVAL=5
SE7_TIMEOUT=600
SE8_POLL_INTERVAL=3
SE8_TIMEOUT=300
FFMPEG_SEGMENT_TIMEOUT=60
FFMPEG_TOTAL_TIMEOUT=300

# TITLE CARD
TITLE_CARD_DURATION=3.0
TITLE_CARD_WRAP_WIDTH=30

# EXTERNAL URL (for webhooks)
EXTERNAL_URL=

# PATHS
TEMP_DIR=/tmp/se9
OUTPUT_DIR=/app/data/outputs
LOG_DIR=/app/data/logs
LOG_LEVEL=INFO
```

---

## 7. Docker

### 7.1 Dockerfile

- Base: `python:3.11-slim`
- Instala: ffmpeg, curl
- Non-root user: `appuser`
- Copia shared lib → `pip install`
- Copia código do serviço → `pip install -r requirements.txt`
- HEALTHCHECK: `curl -f http://localhost:8009/ping`
- CMD: `uvicorn app.main:app`

### 7.2 docker-compose.yml

- Container: `se9-make-video-img`
- Port: 8009:8009
- Memory limit: 2G
- Bind mounts: `data/outputs/` e `data/logs/`
- Network: `ytcaption-network` (external)
- SE7/SE8 via `host.docker.internal:host-gateway`
- Healthcheck: curl /ping

---

## 8. Testes

### 8.1 Unit tests (25+)

| Arquivo | Testes | Cobertura |
|---|---|---|
| test_models.py | 10 | VideoJob lifecycle, enums, constants, CreateVideoRequest |
| test_store.py | 5 | _FakeRedis: save, get, update, delete, list |
| test_audio_chunking.py | 7 | Text splitting, paragraph/sentence merge, narration concat |
| test_video_assembler_srt.py | 3 | Scene duration calculation, clamping, edge cases |

### 8.2 E2E tests

| Arquivo | Modo | Descrição |
|---|---|---|
| test_full_pipeline.py | Mock/Real | Pipeline completo com auto-detect de SE7/SE8 |
| test_real_pipeline.py | Real | CSV fixtures reais (script 1068: 5 cenas, script 981: 11 cenas) |

### 8.3 Fixtures

7 CSVs em `tests/fixtures/` (copiados de `make-video-backgraund/db/data/`):
- video_scripts.csv — 975 scripts
- video_script_narration.csv — 24.991 linhas
- video_script_scene_suggestions.csv — 8.043 linhas
- video_script_on_screen_text.csv — 7.059 linhas
- video_script_hashtags.csv — 7.767 linhas
- video_script_title_options.csv — 2.942 linhas
- video_script_safety_notes.csv — 977 linhas

Delimiter: `;`, quotechar: `"`.

---

## 9. Decisões de Arquitetura

| # | Decisão | Alternativa | Motivação |
|---|---|---|---|
| 1 | API-first (sem PostgreSQL) | PostgreSQL | n8n já tem dados; zero deploy extra |
| 2 | Worker in-memory thread | Celery | 1 job por vez, sem fila complexa |
| 3 | Ken Burns via FFmpeg zoompan | OpenCV | 1 linha de filtro vs 200 linhas; memória streaming |
| 4 | Loop circular de imagens | Imagens estáticas | Cobre duração total do áudio sem frame frozen |
| 5 | Batches de 8 para concat | xfade único | Evita SIGKILL do FFmpeg com 13+ inputs |
| 6 | BaseServiceSettings | Config manual | Padrão do monorepo, herda campos comuns |
| 7 | _FakeRedis fallback | Sem fallback | Degradção graciosa quando Redis indisponível |
| 8 | Cinematic prompt suffix | Prompt cru | Melhora qualidade visual das imagens SE8 |
| 9 | TTS params via config | Hardcoded | Permite tunar por environment sem deploy |
| 10 | Audio retry com backoff | Sem retry | SE7 pode falhar intermitentemente |

---

## 10. Dependências Externas

| Serviço | Porta | Uso | Auth |
|---|---|---|---|
| SE7 | 8007 | Audio TTS (Chatterbox) | X-API-Key: se7-test-key-2026 |
| SE8 | 8008 | Image generation (SDXL) | X-API-Key: se8-test-key-2026 |
| Redis | 6379/9 | Job store (com fallback in-memory) | — |
| FFmpeg/ffprobe | local | Video assembly, audio processing | — |

---

## 11. Issues Corrigidos

| # | Severidade | Descrição | Status |
|---|---|---|---|
| 1 | **Alta** | `worker.py:63` — `_get_next_job()` fazia scan O(n) de todos os jobs | ✅ Corrigido: `get_next_queued_job()` para no primeiro QUEUED |
| 2 | **Média** | `routes.py:25` — root endpoint hardcodes `version: "1.0.0"` | ✅ Corrigido: usa `settings.app_version` |
| 3 | **Média** | `routes.py:100` — delete_job removia video_path separadamente (redundante) | ✅ Corrigido: `shutil.rmtree(output_dir)` cobre tudo |
| 4 | **Média** | `redis_store.py` — stale_ids cleanup falhava silenciosamente | ✅ Corrigido: try/except duplo com warning |
| 5 | **Baixa** | `conftest.py` — OUTPUT_DIR relativo podia quebrar com CWD diferente | ✅ Corrigido: `os.path.abspath()` |
| 6 | **Baixa** | `constants.py:3` — `JOB_ID_PREFIX = "rbg_"` herança do nome antigo | ⏸️ Adiado (quebra jobs existentes no Redis) |
| 7 | **Baixa** | `ffmpeg_utils.py` — `trim_to_duration` re-encode ambos os streams | ⏸️ Mantido (consistente com parâmetros dos steps anteriores) |

---

## 12. Fluxo Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO COMPLETO SE9                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ n8n  │───▶│   SE9    │───▶│   SE7    │───▶│  Áudio   │     │
│  │(Reddit)   │(API POST)│    │  (TTS)   │    │  .wav    │     │
│  └──────┘    │          │    └──────────┘    └──────────┘     │
│              │  /jobs   │                                      │
│              │          │    ┌──────────┐    ┌──────────┐     │
│              │          │───▶│   SE8    │───▶│ Imagens  │     │
│              │          │    │ (SDXL)   │    │  .png    │     │
│              └──────────┘    └──────────┘    └──────────┘     │
│                   │                                             │
│                   ▼                                             │
│              ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│              │ FFmpeg   │───▶│ Ken Burns│───▶│  Vídeo   │     │
│              │ (monta)  │    │ + Audio  │    │  .mp4    │     │
│              └──────────┘    └──────────┘    └──────────┘     │
│                                                                 │
│  Input:  JSON do n8n (post_id, narration, scenes, hook)       │
│  Output: MP4 1080x1920 (9:16), H264 Main, 30fps, AAC-LC     │
│  Tempo:  ~1min45s (GPU) | ~7-8min (CPU)                       │
│                                                                 │
│  API:   POST /jobs → GET /jobs/{id} → GET /download/{id}     │
│  Auth:  X-API-Key: se9-test-key-2026                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Status de Implementação

| Componente | Status | Notas |
|---|---|---|
| FastAPI app + lifespan | ✅ | create_service_app, structured logging |
| API routes (CRUD) | ✅ | POST/GET/DELETE /jobs, GET /download |
| Health check | ✅ | SE7, SE8, disk, ffmpeg checks |
| Admin routes | ✅ | /admin/stats, /admin/cleanup |
| API key auth | ✅ | create_api_key_dependency, health exempt |
| Worker in-memory | ✅ | Thread com event loop + efficient queued job lookup |
| Audio generator | ✅ | SE7 client, chunking, WAV concat, retry |
| Image generator | ✅ | SE8 sync mode, cinematic suffix |
| Video assembler | ✅ | Ken Burns linear, title card 3s, crossfade, batched concat |
| Pipeline orchestrator | ✅ | 3 stages, progress tracking, webhook |
| Redis store | ✅ | ZSET + pipeline + get_next_queued_job, _FakeRedis fallback |
| Docker | ✅ | Non-root, healthcheck, 2G memory |
| Unit tests (27) | ✅ | models, store, chunking, duration |
| E2E tests | ✅ | Mock + real (CSV fixtures) |
| INVESTIGACAO.md | ✅ | Documentação reflete código real |

---

## 14. Performance Real Medida

| Métrica | Valor |
|---|---|
| Script 1068 (5 cenas, 78s audio) | 182s total (GPU) |
| Script 100 (17 narrações, 12 segmentos) | ~270s total (GPU) |
| SE7 audio (GPU) | ~35s |
| SE8 images (1 cena) | ~10s |
| FFmpeg assembly (12 segmentos) | ~60s |
| Tamanho final (5 cenas) | ~5-15MB |
| Tamanho final (12 segmentos) | ~30MB |
| Artefatos preservados por job | ~17-25 arquivos |

---

## 15. Próximos Passos (Priorizado)

| # | Prioridade | Melhoria | Esforço |
|---|---|---|---|
| 1 | Alta | Re-integrar legendas (on_screen_text → SRT → burn) como opcional | 2h |
| 2 | Alta | Retry para imagens SE8 (hoje sem retry) | 1h |
| 3 | Média | Paralelizar imagens SE8 (asyncio.gather) quando SE8 suportar | 3h |
| 4 | Média | Adicionar métricas Prometheus (requests, latency, jobs_by_status) | 2h |
| 5 | Média | Rate limiting no /jobs (evitar abuse) | 1h |
| 6 | Baixa | Limpar `rbg_` prefix → `se9_` (consistência) | 30min |
| 7 | Baixa | Testes de integração com SE7/SE8 reais no CI | 2h |
| 8 | Baixa | Dashboard web para monitorar jobs em tempo real | 4h |
