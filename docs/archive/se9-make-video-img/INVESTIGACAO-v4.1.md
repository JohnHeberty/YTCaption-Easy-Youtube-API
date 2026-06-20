# SE9 — Make Video IMG

## Documento de Investigação e Arquitetura

**Versão:** 4.1  
**Data:** 2026-06-19  
**Status:** Implementado, testado, rodando em Docker — todas as pendências resolvidas  
**Porta:** 800${DIVISOR}  
**API Key:** `se9-test-key-2026`

---

## 1. Visão Geral

### O que é

Serviço de geração automática de vídeos para redes sociais (TikTok, Reels, Shorts) a partir de **scripts de texto enviados por HTTP**. O SE9 orquestra:

- **SE7** (port 8007) → narração TTS (Chatterbox PT-BR)
- **SE8** (port 8008) → geração de imagens (Stable Diffusion SDXL)
- **FFmpeg** → montagem do vídeo final (Ken Burns + crossfade)

### Fluxo completo

```
Cliente/n8n → POST /jobs → SE9 (orquestra)
  ├── SE7 (TTS)      → narração WAV (chunked)
  ├── SE8 (SDXL)     → imagens PNG por cena
  └── FFmpeg          → vídeo MP4 final
        1. Title card (3s hook + fade-in animado + overlay escuro)
        2. Ken Burns segments (8 estilos de zoom/pan)
        3. Concat com xfade transitions (32 tipos aleatórios)
        4. Áudio mixado (AAC 192k stereo)
        5. Trim para duração exata
```

### Por que é independente do SE5

| SE5 (Make Video Clip) | SE9 (Make Video IMG) |
|---|---|
| Fonte: YouTube shorts | Fonte: Imagens geradas |
| Áudio: Upload manual | Áudio: Gerado automaticamente (SE7) |
| Pipeline: Download → Transform → Validate | Pipeline: Script → Audio → Images → Compose |
| Celery + Redis | Worker in-memory + Redis |

São fluxos completamente diferentes. SE9 é mais simples e especializado.

---

## 2. API

### 2.1 Criar job

```http
POST /jobs
X-API-Key: se9-test-key-2026
Content-Type: application/json

{
  "post_id": "1q5o4zw",
  "hook": "No Réveillon, um papo que quase virou algo mais...",
  "estimated_seconds": 96,
  "narration": [
    {"t": 0, "text": "Eu vi a matéria e fiquei perplexo..."},
    {"t": 8, "text": "O documento foi encontrado..."}
  ],
  "scene_suggestions": [
    {"t": 0, "visual": "B-roll de arquivos antigos..."},
    {"t": 8, "visual": "Imagem de uma estante de livros..."}
  ],
  "on_screen_text": [{"t": 0, "text": "15 anos depois..."}],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16",
  "zoom_style": "random"
}
```

**Resposta (201):**
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "queued",
  "post_id": "1q5o4zw",
  "estimated_seconds": 96,
  "scenes_count": 8,
  "message": "Video generation started"
}
```

### 2.2 Consultar status

```http
GET /jobs/{job_id}
```

**Resposta:**
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_images",
  "progress": 55,
  "stages": {
    "generating_audio": {"status": "completed", "progress": 100},
    "generating_images": {"status": "processing", "progress": 50},
    "assembling_video": {"status": "pending", "progress": 0}
  },
  "created_at": "2026-06-19T10:25:00-03:00"
}
```

### 2.3 Download

```http
GET /download/{job_id}
```

Retorna: `video/mp4` binário

### 2.4 Outras rotas

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Info do serviço + lista de endpoints |
| GET | `/health` | Health check (SE7, SE8, disco, ffmpeg) |
| GET | `/ping` | `{"pong": true}` |
| GET | `/jobs` | Lista todos os jobs |
| DELETE | `/jobs/{job_id}` | Deleta job e arquivos |
| GET | `/admin/stats` | Estatísticas do sistema |
| POST | `/admin/cleanup` | Limpa jobs failed (dirs + Redis) |

### 2.5 Webhook

Se `webhook_url` for informado no payload, o SE9 faz POST quando o vídeo estiver pronto:

```json
{
  "event": "video_ready",
  "job_id": "rbg_a1b2c3d4e5f6",
  "post_id": "1q5o4zw",
  "status": "completed",
  "download_url": "http://localhost:8009/download/rbg_a1b2c3d4e5f6",
  "title": "O Passaporte Perdido",
  "hashtags": ["#relatos", "#misterio"],
  "duration_seconds": 96,
  "file_size_mb": 2.5
}
```

> **Nota:** `download_url` usa `EXTERNAL_URL` (configurável via env var, fallback para localhost).

---

## 3. Arquitetura Interna

### 3.1 Estrutura de arquivos

```
services/se9-make-video-img/
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app + lifespan + setup_routers
│   ├── worker.py                       # VideoWorker (thread in-memory)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                   # MakeVideoImgSettings(BaseServiceSettings)
│   │   ├── models.py                   # VideoJob, CreateVideoRequest, enums
│   │   └── constants.py                # JOB_PREFIX, ASPECT_RATIOS, ZOOM_STYLES
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                   # POST /jobs, GET/DELETE /jobs/{id}, GET /
│   │   ├── download_routes.py          # GET /download/{id}
│   │   ├── health_routes.py            # GET /health, /ping
│   │   ├── admin_routes.py             # GET /admin/stats, POST /admin/cleanup
│   │   └── webhook.py                  # send_webhook() via POST
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_generator.py          # SE7 client + chunking + WAV concat
│   │   ├── image_generator.py          # SE8 client (sync mode)
│   │   ├── video_assembler.py          # FFmpeg pipeline (Ken Burns + xfade)
│   │   └── pipeline.py                 # Orquestrador: audio → images → video
│   └── infrastructure/
│       ├── __init__.py
│       ├── http_client.py              # SE7Client + SE8Client (httpx async)
│       ├── ffmpeg_utils.py             # Wrappers FFmpeg (287 linhas)
│       └── redis_store.py              # VideoJobStore + _FakeRedis fallback
├── docker/
│   ├── Dockerfile                      # Python 3.11-slim + ffmpeg + non-root
│   └── docker-compose.yml              # Port 8009, ytcaption-network, 2GB RAM
├── tests/
│   ├── conftest.py                     # Fixtures compartilhadas
│   ├── fixtures_loader.py              # Leitura CSV → CreateVideoRequest
│   ├── fixtures/                       # 7 CSVs com ~200 scripts
│   ├── unit/
│   │   ├── test_models.py              # 10 testes — modelos Pydantic
│   │   ├── test_store.py               # 5 testes — FakeRedis CRUD
│   │   ├── test_video_assembler_srt.py # 3 testes — duração de cenas
│   │   └── test_audio_chunking.py      # 7 testes — chunking de texto
│   └── e2e/
│       └── test_full_pipeline.py       # Teste E2E com mock ou real
├── requirements.txt
├── .env
├── .env.example
├── run.py
├── pytest.ini
└── INVESTIGACAO.md                     # Este documento
```

**Total: 22 arquivos fonte, 4 arquivos de teste**

### 3.2 Camada Core

#### config.py — MakeVideoImgSettings

Extends `BaseServiceSettings` do shared library. Configuração centralizada.

```python
class MakeVideoImgSettings(BaseServiceSettings):
    # Serviços downstream
    se7_url: str = "http://localhost:8007"
    se7_api_key: str = "se7-test-key-2026"
    se8_url: str = "http://localhost:8008"
    se8_api_key: str = "se8-test-key-2026"

    # Defaults de vídeo
    default_voice_id: str = "builtin_feminino"
    default_aspect_ratio: str = "9:16"
    default_width: int = 1080
    default_height: int = 1920
    default_fps: int = 30
    default_zoom_speed: float = 0.004
    default_crossfade_duration: float = 0.8
    default_image_steps: int = 30
    default_image_performance: str = "Quality"

    # TTS params (para SE7)
    tts_exaggeration: float = 0.5
    tts_cfg_weight: float = 0.7
    tts_temperature: float = 0.5

    # External URL (para webhooks)
    external_url: str = ""

    # Title card
    title_card_duration: float = 3.0
    title_card_wrap_width: int = 30

    # Timeouts
    se7_poll_interval: int = 5      # segundos entre polls
    se7_timeout: int = 600          # timeout total SE7
    se8_poll_interval: int = 3
    se8_timeout: int = 300
    ffmpeg_segment_timeout: int = 60
    ffmpeg_total_timeout: int = 300
```

#### models.py — Modelos de Dados

**Enums:**
- `VideoJobStatus`: QUEUED → GENERATING_AUDIO → GENERATING_IMAGES → ASSEMBLING_VIDEO → COMPLETED | FAILED
- `StageStatus`: PENDING, PROCESSING, COMPLETED, FAILED

**Modelos principais:**
- `CreateVideoRequest` — payload de entrada (16 campos, 8 obrigatórios)
- `VideoJob` — estado do job com stages, paths, progresso
- `StageInfo` — estado de cada estágio (start/complete/fail)
- `NarrationSegment`, `SceneSuggestion`, `OnScreenText` — tipos de timestamp

**Progresso ponderado:**
```
Audio:    0%  → 40%  (baseado em chunks processados)
Images:   40% → 70%  (baseado em cenas geradas)
Assembly: 70% → 100% (baseado em steps do FFmpeg)
```

#### constants.py

```python
JOB_ID_PREFIX = "rbg_"         # Prefixo legado (Reddit Background Generator)
JOB_PREFIX = "rbg_job:"        # Chave Redis
JOB_TTL = 86400 * 2            # 2 dias

ASPECT_RATIOS = {
    "9:16":  (1080, 1920),     # TikTok/Reels/Shorts
    "16:9":  (1920, 1080),     # YouTube landscape
    "1:1":   (1080, 1080),     # Instagram square
}

ZOOM_STYLES = [
    "zoom_in", "zoom_out", "pan_left", "pan_right",
    "zoom_in_left", "zoom_in_right", "zoom_out_left", "zoom_out_right",
    "random",
]

TRANSITIONS = [
    "circleopen", "circleclose",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "dissolve", "pixelize",
    "diagtl", "diagtr", "diagbl", "diagbr",
    "radial", "zoomin",
    "fadefast", "fadeslow",
    "coverleft", "coverright", "coverup", "coverdown",
    "revealleft", "revealright",
    "squeezeh", "squeezev",
]

CHATTERBOX_MAX_CHARS = 5000    # Limite do Chatterbox TTS
```

### 3.3 Camada API

#### Autenticação

Todas as rotas usam `Depends(verify_api_key)` via header `X-API-Key`. Exceções: `/health`, `/ping`, `/`.

#### POST /jobs

1. Valida payload com `CreateVideoRequest`
2. Gera `job_id = rbg_{uuid4().hex[:12]}`
3. Cria `VideoJob` com status QUEUED
4. Salva no Redis (TTL 2 dias)
5. Inicia worker se não estiver rodando
6. Retorna `CreateVideoResponse`

#### DELETE /jobs/{job_id}

Deleta o diretório `output/{job_id}/` e a entrada Redis.

### 3.4 Worker (worker.py)

```python
class VideoWorker:
    # Thread in-memory, 1 job por vez
    # Polling: verifica jobs QUEUED a cada 2s
    # Processa via run_video_pipeline()
    # Singleton via get_worker()
```

**Fluxo do loop:**
1. `_get_next_job()` → itera todos os jobs, retorna primeiro QUEUED
2. `_process_job(job)` → chama pipeline
3. Sucesso: break
4. Erro: sleep 5s, tenta novamente
5. finally: fecha cliente HTTP

### 3.5 Camada Services

#### audio_generator.py — Geração de Áudio

```
1. Concatena narration segments por timestamp
2. Chunk text se > 5000 chars (CHATTERBOX_MAX_CHARS)
   - Estratégia: parágrafos → frases → hard split
3. Para cada chunk:
   a. POST /jobs no SE7 (form-data: text, voice_id, params)
   b. Poll GET /jobs/{id} a cada 5s até completed/failed
   c. GET /jobs/{id}/download → bytes WAV
4. Concatena WAVs via ffmpeg: concat=n=N:v=0:a=1
5. Retorna (caminho, duração)
```

#### image_generator.py — Geração de Imagens

```
1. Para cada scene_suggestion:
   a. Mapeia aspect_ratio → dimensões SE8 (1024-base)
      9:16 → 1024x1792, 16:9 → 1792x1024, 1:1 → 1024x1024
   b. POST /v1/generation/text-to-image (síncrono)
      - prompt, width, height, steps=30, performance=Quality
   c. Download: GET {url_da_resposta}
   d. Salva como scene_{t}.png
2. Retorna lista de caminhos
```

> **Nota:** SE8 retorna imagens diretamente na resposta (síncrono), sem necessidade de polling.

#### video_assembler.py — Montagem do Vídeo

**Pipeline de 6 passos:**

```
1. Title Card (se hook_text fornecido)
   - Escala imagem 2x → zoompan suave → overlay escuro (black@0.6) → drawtext branco
   - Fade-in animado do texto (alpha lerp 0→1 em 0.8s)
   - Duração: 3s

2. Ken Burns Segments (8 estilos)
   - zoom_in, zoom_out, pan_left, pan_right
   - zoom_in_left, zoom_out_left, zoom_in_right, zoom_out_right
   - zoom_speed: 0.004 (4x mais dramático que antes)
   - Escala 2x → zoompan → format yuv420p
   - Encoding: libx264 -profile:v main -level 4.0 -g 30 -bf 2

3. Concat com Crossfade (32 tipos de transição)
   - xfade filter encadeado entre segmentos
   - Transições aleatórias por par de segmentos
   - Pool: circleopen, circleclose, wipeleft, wiperight, slideleft, slideright,
     smoothleft, smoothright, dissolve, pixelize, diagtl, diagtr, radial,
     zoomin, fadefast, fadeslow, coverleft, coverright, squeezeh, squeezev, etc.
   - Duração crossfade: min(0.8s, 40% da duração do segmento)

4. Padding de Áudio
   - Adiciona silêncio no início (duração do title card = 3s)
   - anullsrc=r=44100:cl=stereo + concat

5. Adicionar Áudio ao Vídeo
   - -c:v copy (sem re-encode de vídeo)
   - -c:a aac -profile:a aac_low -b:a 192k -ar 44100 -ac 2
   - Sem -shortest (vídeo segura último frame até áudio acabar)

6. Trim
   - Corta para duração do áudio padded
   - Re-encode com params explícitos
```

#### pipeline.py — Orquestrador

```python
async def run_video_pipeline(job: VideoJob):
    # 1. Cria diretório output/{job_id}/
    # 2. AudioGenerator.generate() → (path, duration)
    # Retry: 3 tentativas, backoff exponencial 2s/4s/8s
    # 3. ImageGenerator.generate_all() → [paths]
    # 4. VideoAssembler.assemble() → final_video_path
    # 5. Marca COMPLETED
    # 6. Envia webhook (se configurado)
    # Erro: Marca FAILED e re-raise
```

**Duração das cenas calculada:**
```python
timestamps = sorted(set(n.t for n in narration))
timestamps = [min(t, audio_duration) for t in timestamps]
# dur[i] = timestamps[i+1] - timestamps[i]
# Último segmento: audio_duration - timestamps[-1]
# Segmentos com dur <= 0 são removidos
```

### 3.6 Camada Infrastructure

#### http_client.py

- `ServiceClient` — base com retry exponencial (2^attempt segundos)
- `SE7Client` — POST /jobs, poll GET /jobs/{id}, download GET /jobs/{id}/download
- `SE8Client` — POST /v1/generation/text-to-image (síncrono), download GET {path}

#### ffmpeg_utils.py (287 linhas)

| Função | Descrição |
|--------|-----------|
| `run_ffmpeg(args, timeout)` | Executa ffmpeg subprocess com timeout |
| `get_audio_duration(path)` | ffprobe → float segundos |
| `create_title_card(...)` | Hook text + overlay escuro + drawtext |
| `create_segment(...)` | Ken Burns zoompan por estilo |
| `concat_segments(...)` | xfade encadeado com clamping dinâmico |
| `add_audio(...)` | Mix vídeo + áudio AAC |
| `trim_to_duration(...)` | Corta vídeo para duração exata |

**Params de encoding (consistentes em todas as etapas):**
```
-v profile:v main -level 4.0 -g 30 -bf 2
-a profile:a aac_low -b:a 192k
-pix_fmt yuv420p -movflags +faststart
```

#### redis_store.py

- `VideoJobStore` — CRUD no Redis com TTL 2 dias via `ResilientRedisStore`
- **Connection pool** (max 50 conexões) + **circuit breaker** + **retry automático**
- **Pipeline batching** — `save_job`/`delete_job` usam pipeline atômico; `list_jobs` usa MGET
- Sorted set `rbg_jobs:list` para listagem (ZADD/ZREVRANGE/ZREM) — sem `KEYS`
- `_FakeRedis` — fallback in-memory quando Redis indisponível
- Chaves: `rbg_job:{job_id}` → JSON serializado

---

## 4. Pipeline Detalhado

### 4.1 Timeline de um job

```
t+0s     POST /jobs → QUEUED
t+1s     Worker detecta → GENERATING_AUDIO
t+2s     SE7 job criado, polling iniciado
t+5min   SE7 completo → audio.wav salvo
t+5min   GENERATING_IMAGES → SE8 para cada cena
t+6min   8 imagens geradas → ASSEMBLING_VIDEO
t+6min20s FFmpeg completo → COMPLETED
t+6min20s Webhook enviado (se configurado)
```

### 4.2 Performance real (medido)

| Fase | Tempo | Recurso |
|------|-------|---------|
| Áudio (10s narrados) | ~35s (GPU) / ~5min (CPU) | SE7 |
| Imagens (3 cenas) | ~50s | SE8 GPU |
| FFmpeg assembly | ~20s | CPU local |
| **Total (GPU)** | **~1min45s** | |

### 4.3 Capacidade estimada

- SE7 GPU: ~35s por job → ~100 vídeos/hora
- SE8: ~50s por 3 cenas → ~70 vídeos/hora (sequencial)
- SE9: 1 job por vez (worker single-thread)
- **Gargalo:** SE9 worker (1 job por vez)

---

## 5. Modelos de Dados

### CreateVideoRequest

| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
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
| webhook_url | str? | Não | None |

### VideoJob

| Campo | Tipo | Descrição |
|-------|------|-----------|
| job_id | str | ID único (rbg_{hex}) |
| post_id | str | ID do post original |
| status | VideoJobStatus | Estado atual |
| progress | float | 0-100% |
| stages | dict[str, StageInfo] | 3 estágios com progresso |
| request | CreateVideoRequest | Payload original |
| audio_path | str? | Caminho do WAV |
| video_path | str? | Caminho do MP4 final |
| images | list[str]? | Lista de caminhos PNG |
| created_at | datetime | Criação (BRT) |
| updated_at | datetime | Última atualização |
| error | str? | Mensagem de erro |

### Estados do Job

```
QUEUED → GENERATING_AUDIO → GENERATING_IMAGES → ASSEMBLING_VIDEO → COMPLETED
                ↓                    ↓                   ↓
              FAILED              FAILED              FAILED
```

---

## 6. Configuração

### .env

```bash
# App
APP_NAME=Make Video IMG
APP_VERSION=1.0.0
ENVIRONMENT=development
HOST=0.0.0.0
PORT=800${DIVISOR}
WORKERS=1
API_KEY=se9-test-key-2026
TZ=America/Sao_Paulo
DIVISOR=9

# Redis
REDIS_URL=redis://192.168.1.110:6379/${DIVISOR}

# SE7
SE7_URL=http://localhost:8007
SE7_API_KEY=se7-test-key-2026

# SE8
SE8_URL=http://localhost:8008
SE8_API_KEY=se8-test-key-2026

# Video Defaults
DEFAULT_VOICE_ID=builtin_feminino
DEFAULT_ASPECT_RATIO=9:16
DEFAULT_WIDTH=1080
DEFAULT_HEIGHT=1920
DEFAULT_FPS=30
DEFAULT_ZOOM_SPEED=0.004
DEFAULT_CROSSFADE_DURATION=0.3
DEFAULT_IMAGE_STEPS=30
DEFAULT_IMAGE_PERFORMANCE=Quality

# TTS Params
TTS_EXAGGERATION=0.5
TTS_CFG_WEIGHT=0.7
TTS_TEMPERATURE=0.5

# External URL (para webhooks)
EXTERNAL_URL=

# Title Card
TITLE_CARD_DURATION=3.0
TITLE_CARD_WRAP_WIDTH=30

# Timeouts
SE7_POLL_INTERVAL=5
SE7_TIMEOUT=600
SE8_POLL_INTERVAL=3
SE8_TIMEOUT=300
FFMPEG_SEGMENT_TIMEOUT=60
FFMPEG_TOTAL_TIMEOUT=300

# Paths
TEMP_DIR=/tmp
OUTPUT_DIR=./data/outputs
LOG_DIR=/app/data/logs
LOG_LEVEL=INFO
```

### requirements.txt

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
httpx
redis
```

+ `common` library (via `pip install -e /app/shared` no Docker)

---

## 7. Docker

### Dockerfile

- **Base:** python:3.11-slim
- **Instala:** ffmpeg, curl, shared lib, requirements
- **User:** appuser (non-root)
- **Healthcheck:** `curl -f localhost:8009/ping`
- **CMD:** uvicorn app.main:app

### docker-compose.yml

- Porta: `${HOST_PORT:-8009}:${CONTAINER_PORT:-8009}`
- Network: ytcaption-network (external)
- Memory: 2GB limit
- Volume: `../output:/app/data/outputs` (bind mount)
- Extra hosts: `host.docker.internal:host-gateway`
- Env overrides: SE7_URL/SE8_URL apontam para host

---

## 8. Testes

### Unitários (25 testes)

| Arquivo | Testes | O que cobre |
|---------|--------|-------------|
| test_models.py | 10 | CreateVideoRequest, VideoJob, enums, constants |
| test_store.py | 5 | FakeRedis: save, get, update, delete, list |
| test_video_assembler_srt.py | 3 | Cálculo de duração de cenas |
| test_audio_chunking.py | 7 | Chunking de texto (parágrafos, frases, hard split) |

### E2E (1 teste)

- `test_full_pipeline_from_csv` — Script CSV → áudio → imagens → vídeo → validação
- Auto-detecta SE7/SE8 online
- Se offline: mock (sine wave WAV + solid color PNG)
- Se online: geração real

### Fixtures

7 arquivos CSV com ~200 scripts completos:
- `video_scripts.csv` — scripts principais
- `video_script_narration.csv` — narração por timestamp
- `video_script_scene_suggestions.csv` — cenas visuais
- `video_script_on_screen_text.csv` — textos na tela
- `video_script_hashtags.csv`, `title_options.csv`, `safety_notes.csv`

---

## 9. Decisões de Arquitetura

| Decisão | Motivação |
|---------|-----------|
| API-first (sem PG) | n8n manda payload completo, SE9 só executa |
| Worker in-memory (não Celery) | 1 job por vez, mesma pattern do SE7, menor complexidade |
| Redis com fallback _FakeRedis | Development funciona sem Redis |
| Ken Burns via FFmpeg zoompan | 1 linha de filtro vs ~200 com OpenCV |
| SE8 síncrono | Retorna imagem direto, sem polling |
| Audio chunking | Chatterbox limita em 5000 chars |
| Title card 3s + fade-in | Hook visual com tempo para leitura, animação suave |
| 8 estilos Ken Burns | Variedade visual: zoom+pan combinados, não só básico |
| 32 transições xfade | Evita monotonia visual, seleção aleatória por segmento |
| Sem legendas no conteúdo | Só title card, conteúdo é áudio + imagem |
| Bind mount output | Arquivos visíveis no host para debug |

---

## 10. Dependências Externas

| Serviço | Porta | Modelo | Autenticação |
|---------|-------|--------|--------------|
| SE7 (TTS) | 8007 | Chatterbox Multilingual PT-BR | X-API-Key: se7-test-key-2026 |
| SE8 (Images) | 8008 | Stable Diffusion SDXL | X-API-Key: se8-test-key-2026 |
| Redis | 6379/9 | — | URL connection |
| FFmpeg | local | H.264 + AAC | — |

---

## 11. Issues Conhecidos

| # | Severidade | Arquivo | Descrição | Status |
|---|-----------|---------|-----------|--------|
| 1 | ~~ALTA~~ | pipeline.py:47-68 | Retry de áudio usava backoff linear (10s, 20s) | ✅ **CORRIGIDO** — backoff exponencial (2s, 4s, 8s), 3 retries |
| 2 | ~~MÉDIA~~ | webhook.py:22 | download_url usava localhost | ✅ **CORRIGIDO** — usa EXTERNAL_URL env var |
| 3 | ~~MÉDIA~~ | admin_routes.py:50 | Cleanup deletava completed | ✅ **CORRIGIDO** — só remove failed |
| 4 | ~~ALTA~~ | redis_store.py | Redis usava `KEYS` command (O(N), bloqueia Redis) | ✅ **CORRIGIDO** — migrado para sorted set (ZADD/ZREVRANGE/ZREM) |
| 5 | ~~ALTA~~ | redis_store.py | Redis sem connection pool, circuit breaker, retry | ✅ **CORRIGIDO** — migrado para `ResilientRedisStore` do shared lib |
| 6 | ~~ALTA~~ | .env.example | API keys reais expostas (se9, se7, se8) | ✅ **CORRIGIDO** — substituídas por placeholders |
| 7 | ~~MÉDIA~~ | .env | PORT e REDIS_URL não usavam `${DIVISOR}` | ✅ **CORRIGIDO** — padrão `${DIVISOR}` aplicado |
| 8 | ~~BAIXA~~ | (inexistente) | Serviço não tinha Makefile | ✅ **CORRIGIDO** — Makefile adicionado (169 linhas) |
| 9 | ~~MÉDIA~~ | 8 arquivos | `logging.getLogger` em vez de `get_logger` | ✅ **CORRIGIDO** — migrado para `get_logger(__name__)` |
| 10 | ~~BAIXA~~ | worker.py:62-67 | `_get_next_job()` itera TODOS os jobs — O(n) | Aberto |
| 11 | ~~BAIXA~~ | ffmpeg_utils.py:56 | textwrap width=20 era estreito para textos longos | ✅ **CORRIGIDO** — aumentado para 30 via settings |
| 12 | ~~MÉDIA~~ | webhook.py | Webhook sem retry — falha silenciosa | ✅ **CORRIGIDO** — 3 tentativas com backoff exponencial |
| 13 | ~~MÉDIA~~ | webhook.py:18 | `EXTERNAL_URL` via `os.getenv()` raw, sem validação | ✅ **CORRIGIDO** — via Pydantic settings |
| 14 | ~~MÉDIA~~ | admin_routes.py | Cleanup não removia Redis keys após rmtree | ✅ **CORRIGIDO** — `delete_job()` após cleanup |
| 15 | ~~BAIXA~~ | video_assembler.py:83 | Title card duration hardcoded (3.0s) | ✅ **CORRIGIDO** — via `title_card_duration` settings |
| 16 | ~~BAIXA~~ | redis_store.py | `save_job`/`delete_job` sem pipeline atômico | ✅ **CORRIGIDO** — pipeline batching + MGET |

---

## 12. Fluxo Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO COMPLETO SE9                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │n8n/  │───▶│   SE9    │───▶│   SE7    │───▶│  Áudio   │     │
│  │Cliente   │(API POST) │    │  (TTS)   │    │  .wav    │     │
│  └──────┘    │          │    └──────────┘    └──────────┘     │
│              │  /jobs   │                                      │
│              │          │    ┌──────────┐    ┌──────────┐     │
│              │          │───▶│   SE8    │───▶│ Imagens  │     │
│              │          │    │ (SDXL)   │    │  .png    │     │
│              └──────────┘    └──────────┘    └──────────┘     │
│                   │                                             │
│                   ▼                                             │
│              ┌──────────┐                                      │
│              │  FFmpeg  │                                      │
│              │ 1.Title  │  3s hook + fade-in + overlay         │
│              │ 2.KenBnz │  8 estilos zoom/pan                  │
│              │ 3.Concat │  32 xfade transitions                │
│              │ 4.Audio  │  AAC 192k stereo                     │
│              │ 5.Trim   │  duração exata                       │
│              └──────────┘                                      │
│                   │                                             │
│                   ▼                                             │
│              ┌──────────┐                                      │
│              │ output/  │  {job_id}/{job_id}_final.mp4         │
│              └──────────┘                                      │
│                                                                 │
│  Input:  JSON (post_id, narration, scenes, hook)               │
│  Output: MP4 1080x1920 (9:16), H264 Main, AAC, 30fps         │
│  Tempo:  ~1min45s (GPU) / ~7min (CPU)                         │
│                                                                 │
│  API:   POST /jobs → GET /jobs/{id} → GET /download/{id}     │
│  Auth:  X-API-Key: se9-test-key-2026                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Status de Implementação

| Componente | Status | Notas |
|------------|--------|-------|
| Config (BaseServiceSettings) | ✅ | Padronizado com shared lib |
| API routes (CRUD completo) | ✅ | POST, GET, DELETE, LIST |
| Health check | ✅ | SE7, SE8, disco, ffmpeg |
| Admin routes | ✅ | stats + cleanup |
| Audio generator | ✅ | SE7 chunking + WAV concat |
| Image generator | ✅ | SE8 síncrono |
| Video assembler | ✅ | Ken Burns 8 estilos + xfade 32 tipos + title card 3s fade-in |
| Pipeline orchestration | ✅ | Retry audio, progress callback |
| Worker in-memory | ✅ | Single-thread, polling 2s |
| Webhook | ✅ | POST notify com retry 3x + EXTERNAL_URL via settings |
| Redis store | ✅ | **ResilientRedisStore** + sorted set (ZADD/ZREVRANGE/ZREM) |
| Docker | ✅ | Non-root, healthcheck, 2GB, ytcaption-network |
| Makefile | ✅ | 28 targets, padrão do monorepo |
| Logging | ✅ | `get_logger(__name__)` em todos os módulos |
| Unit tests (25) | ✅ | All passing |
| E2E tests (1) | ✅ | Mock/real auto-detect |
| Real validation | ✅ | Job completo, download OK |
| Windows compat (0x80004005) | ✅ | aac_low, profile, level, g, bf |

---

## 14. Próximos Passos (Melhorias)

### Implementado (v4.0 — Correções de Arquitetura)
- ✅ **Redis → ResilientRedisStore** — connection pool, circuit breaker, retry, graceful degradation
- ✅ **KEYS → Sorted Set** — `ZADD`/`ZREVRANGE`/`ZREM` substitui `KEYS rbg_job:*`
- ✅ **Makefile** — 28 targets (help, venv, install, dev, test, build, up, down, logs, etc.)
- ✅ **`${DIVISOR}` pattern** — PORT e REDIS_URL usam variável `${DIVISOR}`
- ✅ **Logging migration** — 8 arquivos migrados de `logging.getLogger` → `get_logger`
- ✅ **`.env.example` limpo** — API keys substituídas por placeholders

### Implementado (v4.1 — Correções de Código)

#### Prioridade Alta
1. ✅ **Webhook retry** — 3 tentativas com backoff exponencial (2s, 4s, 8s) — `webhook.py`
2. ✅ **Admin cleanup** — remove dirs + Redis keys para jobs failed — `admin_routes.py`
3. ✅ **Webhook URL** — `EXTERNAL_URL` via Pydantic settings com fallback localhost — `config.py` + `webhook.py`

#### Prioridade Média
4. ✅ **Redis pipeline batching** — `save_job`/`delete_job` usam pipeline atômico; `list_jobs` usa MGET — `redis_store.py`
5. ✅ **Title card customizável** — `title_card_duration` e `title_card_wrap_width` via settings — `config.py` + `video_assembler.py` + `ffmpeg_utils.py`
6. ✅ **Retry backoff exponencial** — 3 retries com 2s, 4s, 8s (era linear 10s, 20s) — `pipeline.py`
7. ✅ **textwrap width** — Aumentado para 30 (safe max para canvas 1080px com fontsize=52)

> Decisões sobre itens fora do escopo (Prometheus, JOB_ID_PREFIX, E2E test) documentadas em `docs/issues/decisions/SE9-decisions-2026-06-19.md`.

### Implementado (v3.1)
- ✅ Title card: 3s com fade-in animado (alpha lerp 0→1 em 0.8s)
- ✅ Ken Burns: 8 estilos (zoom_in/out, pan_left/right, zoom+pan combinados)
- ✅ Transições: 32 tipos xfade com seleção aleatória por segmento
- ✅ Zoom speed: 0.004 (4x mais dramático que 0.001)
- ✅ Crossfade: 0.8s (mais suave que 0.5s)
