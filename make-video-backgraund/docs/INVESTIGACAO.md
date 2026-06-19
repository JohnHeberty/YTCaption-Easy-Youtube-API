# SE9 — Make Video IMG

## Documento de Investigação e Arquitetura

**Data:** 2026-06-18 (v3 — Implementado e validado)
**Status:** Implementado, 28/28 testes passando

---

## 1. Visão Geral do Projeto

### O que é
Um microservice (SE9) que automatiza a criação de vídeos para redes sociais (TikTok, Reels, Shorts) a partir de **dados enviados via API REST**. Um orchestrator externo (n8n, automação própria, etc.) coleta conteúdo, gera roteiros com IA, e envia tudo para o SE9 via API.

### Fluxo completo

```
Fonte (Reddit/Twitter/RSS/etc) → Orchestrator (roteiro IA) → POST /jobs → SE9 (orquestra)
  ├── SE7 (áudio)  → narração WAV
  ├── SE8 (imagens) → cenas PNG
  └── FFmpeg        → vídeo final MP4
```

### Por que API-first (sem PostgreSQL)?

| Com PostgreSQL | API-first (atual) |
|---|---|
| Precisa de credenciais PG | Zero dependência de banco |
| Deploy mais complexo | Deploy simples |
| Sync de schema entre caller e SE9 | Contrato via JSON |
| Query para buscar roteiros | Caller já filtrou o que interessa |

O caller **já tem todos os dados**. Não precisamos acessar o banco — recebemos o payload pronto via HTTP.

### Dados que o caller envia

O payload JSON é o mesmo formato que o n8n usa para `reddit.save_video_script(p_payload jsonb)`:

```json
{
  "post_id": "1q5o4zw",
  "hook": "No Réveillon, um papo que quase virou algo mais...",
  "estimated_seconds": 96,
  "language": "pt-BR",
  "content_rating": "Geral",
  "narration": [
    {"t": 0, "text": "Eu vi a matéria e fiquei perplexo..."},
    {"t": 8, "text": "O documento foi encontrado no fim de 2025..."}
  ],
  "scene_suggestions": [
    {"t": 0, "visual": "B-roll de arquivos antigos, fotos em preto e branco."},
    {"t": 8, "visual": "Imagem de uma estante de livros em um apartamento."}
  ],
  "on_screen_text": [
    {"t": 0, "text": "15 anos depois..."},
    {"t": 8, "text": "O passaporte foi encontrado"}
  ],
  "title_options": ["O Passaporte Perdido", "O Mistério Reacende", "15 Anos Depois"],
  "hashtags": ["#relatos", "#historiareal", "#misterio"],
  "safety_notes": []
}
```

**Exemplo real (script_id=14):** 16 segmentos de narração, 8 cenas, 3 títulos, 8 hashtags — tudo alinhado temporalmente com timestamps `t` (segundos).

---

## 2. API do SE9

**Porta:** 8009
**Auth:** `X-API-Key: se9-test-key-2026` (health/ping isentos)

### 2.1 Root

```http
GET /
```

```json
{
  "service": "make-video-img",
  "version": "1.0.0",
  "endpoints": {
    "POST /jobs": "Create video generation job",
    "GET /jobs": "List all jobs",
    "GET /jobs/{job_id}": "Get job status",
    "DELETE /jobs/{job_id}": "Delete job",
    "GET /download/{job_id}": "Download completed video",
    "GET /health": "Health check"
  }
}
```

### 2.2 Criar job de vídeo

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
    {"t": 8, "text": "O documento foi encontrado..."}
  ],
  "scene_suggestions": [
    {"t": 0, "visual": "B-roll de arquivos antigos..."},
    {"t": 8, "visual": "Imagem de uma estante de livros..."}
  ],
  "on_screen_text": [
    {"t": 0, "text": "15 anos depois..."}
  ],
  "title_options": ["O Passaporte Perdido", "O Mistério Reacende"],
  "hashtags": ["#relatos", "#misterio"],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16",
  "zoom_style": "random"
}
```

### Resposta

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

### 2.3 Consultar status

```http
GET /jobs/{job_id}
X-API-Key: se9-test-key-2026
```

```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_audio",
  "progress": 25.0,
  "stages": {
    "generating_audio": {"status": "processing", "progress": 25.0},
    "generating_images": {"status": "pending", "progress": 0.0},
    "assembling_video": {"status": "pending", "progress": 0.0}
  },
  "created_at": "2026-06-18T15:00:00-03:00",
  "error": null
}
```

### 2.4 Listar jobs

```http
GET /jobs
X-API-Key: se9-test-key-2026
```

```json
{
  "jobs": [
    {"job_id": "rbg_abc123", "status": "completed", "progress": 100.0, "post_id": "1q5o4zw", "created_at": "..."}
  ],
  "total": 1
}
```

### 2.5 Deletar job

```http
DELETE /jobs/{job_id}
X-API-Key: se9-test-key-2026
```

Remove o job do Redis, arquivos temporários e vídeo final.

### 2.6 Download do vídeo

```http
GET /download/{job_id}
X-API-Key: se9-test-key-2026
```

Retorna: `video/mp4` binário via `FileResponse`

### 2.7 Webhook de notificação (opcional)

```http
POST /jobs
{
  ...payload...,
  "webhook_url": "https://n8n.seu-dominio.com/webhook/video-ready"
}
```

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

### 2.8 Health check

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

### 2.9 Ping

```http
GET /ping
```

```json
{"pong": true}
```

---

## 3. Pipeline Detalhado

### 3.1 Fase 1 — Receber e validar payload

```
Entrada: POST /jobs com payload completo
```

1. Validar payload obrigatório via Pydantic: `post_id`, `hook`, `estimated_seconds`, `narration`, `scene_suggestions`
2. Gerar `job_id` único (`rbg_{uuid12}`)
3. Salvar job no Redis (status: `queued`)
4. Worker in-memory (thread) pega o job da fila
5. Retornar `job_id` imediatamente

### 3.2 Fase 2 — Gerar áudio (SE7)

```
Entrada: narration [{t, text}]
Saída: arquivo WAV com áudio completo
```

1. Concatena todos os `text` dos segmentos de narração em uma string
2. **Chunking:** Se texto > 5000 chars (limite Chatterbox), split por parágrafos, merge parágrafos pequenos, fallback por frases para parágrafos longos
3. Para cada chunk, envia para SE7: `POST http://se7:8007/jobs`
   - `text`: chunk de narração
   - `voice_id`: o que o caller enviou (padrão: `builtin_feminino`)
   - `exaggeration`, `cfg_weight`, `temperature`: defaults
4. Polling: `GET http://se7:8007/jobs/{ag_job_id}` a cada 5s
5. Download: `GET http://se7:8007/jobs/{ag_job_id}/download`
6. Se múltiplos chunks: concat WAVs via ffmpeg
7. Obter duração real via ffprobe

**Autenticação:** `X-API-Key: se7-test-key-2026`

**Tempo estimado:** ~5min (CPU) ou ~30s (GPU)

### 3.3 Fase 3 — Gerar imagens (SE8)

```
Entrada: scene_suggestions [{t, visual}]
Saída: imagens PNG para cada cena
```

1. Para cada cena em `scene_suggestions` (sequencial):
   - Enviar para SE8: `POST http://se8:8008/v1/generation/text-to-image`
     - `prompt`: valor de `visual`
     - `width/height`: conforme aspect_ratio (9:16 → 1024x1792)
     - `steps`: 30 (configurável)
     - `performance`: "Quality"
   - Polling: `GET http://se8:8008/v1/generation/query-job?job_id={se8_job_id}`
   - Download: `GET http://se8:8008/files/{date}/{filename}`
   - Salvar em `/tmp/rbg_{job_id}/scene_{t}.png`

2. Progresso: atualizar a cada imagem concluída

**Autenticação:** `X-API-Key: se8-test-key-2026`

**Tempo estimado:** ~10s por imagem × 8 cenas = ~80s

### 3.4 Fase 4 — Montar vídeo (FFmpeg)

```
Entrada: áudio WAV + imagens PNG + timestamps
Saída: vídeo MP4 final
```

**Algoritmo (5 etapas):**

```
1. Calcular duração de cada cena:
   - Para cada cena i: dur_i = t[i+1] - t[i]
   - Última cena: dur = audio_duration - t[last]

2. Para cada cena, criar segmento de vídeo com Ken Burns:
   ffmpeg -loop 1 -i scene_{t}.png -t {dur_i} \
     -vf "scale=2160x3840,zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s=1080x1920:fps=30,format=yuv420p" \
     -c:v libx264 -pix_fmt yuv420p segment_{i}.mp4

3. Concatenar segmentos com crossfade (xfade filter):
   ffmpeg -i seg0.mp4 -i seg1.mp4 ... -i segN.mp4 \
     -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.5:offset={off0}[v01];..." \
     -map "[vout]" -c:v libx264 -preset fast -crf 23 video_concat.mp4

4. Adicionar áudio:
   ffmpeg -i video_concat.mp4 -i audio.wav \
     -c:v copy -c:a aac -b:a 192k video_audio.mp4

5. Se houver on_screen_text: gerar SRT → burn no vídeo
   ffmpeg -i video_audio.mp4 \
     -vf "subtitles=subtitles.srt:force_style='FontSize=22,Alignment=2,MarginV=60'" \
     -c:a copy video_subtitled.mp4

6. Trim para duração do áudio:
   ffmpeg -i video_subtitled.mp4 -t {audio_duration} \
     -c:v libx264 -c:a aac final.mp4
```

**Efeito Ken Burns (zoompan filter):**

| Estilo | Expressão zoom | Efeito |
|---|---|---|
| Zoom in | `z='1+0.001*on'` | Aproxima suavemente |
| Zoom out | `z='1.05-0.001*on'` | Afasta suavemente |
| Pan left | `x='iw*0.1-on*0.005'` | Desliza para esquerda |
| Pan right | `x='on*0.005'` | Desliza para direita |
| Random | Escolhe uma das acima por cena | Variação visual |

**Parâmetros configuráveis:**
- `zoom_speed`: 0.001 (0.1% por frame)
- `crossfade_duration`: 0.5s
- `output_resolution`: 1080x1920 (9:16) — configurável
- `fps`: 30
- `crf`: 23 (qualidade)

### 3.5 Fase 5 — Entregar resultado

1. Job status → `completed`, progress → 100%
2. Salvar metadata no Redis
3. Se `webhook_url` foi informado, fazer POST com dados do vídeo
4. Limpar temporários (segmentos, chunks de áudio, SRT intermediários)

---

## 4. Jobs e Estados

### 4.1 Modelo de Job

```python
class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 4.2 Progresso

| Estágio | Faixa | Dependência |
|---|---|---|
| QUEUED | 0% | — |
| GENERATING_AUDIO | 0-40% | SE7 |
| GENERATING_IMAGES | 40-70% | SE8 |
| ASSEMBLING_VIDEO | 70-100% | FFmpeg local |
| COMPLETED | 100% | — |

### 4.3 TTL

Jobs expiram automaticamente após **2 dias** (86400 * 2 segundos) via TTL no Redis.

---

## 5. Estimativas de Performance

### 5.1 Por Vídeo

| Fase | Tempo Estimado | Recurso |
|---|---|---|
| Validação payload | <1s | CPU |
| Geração áudio (60s narrados) | ~5min | SE7 (CPU) |
| Geração imagens (8 cenas) | ~80s | SE8 (GPU) |
| Montagem FFmpeg | ~30s | CPU |
| **Total** | **~7-8min** | |

### 5.2 Capacidade

- SE7 (CPU): 1 job por vez → ~7 vídeos/hora
- SE8 (GPU): 1 job por vez, sequencial → ~7 vídeos/hora
- SE9 worker: processa 1 job por vez (thread única)
- **Gargalo:** SE7 (CPU) — se mover para GPU, cai para ~1min

### 5.3 Pipeline atual: sequencial

```
Fase 1:  [====SE7====]                    (5min)
Fase 2:                [==SE8==]...[==SE8==]  (80s sequencial)
Fase 3:                                          [FFMPEG] (30s)
```

Futuro: SE8 imagens em paralelo com SE7 áudio (reduz para ~5min total)

---

## 6. Estrutura do Microservice

```
services/se9-make-video-img/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app via create_service_app + lifespan
│   ├── worker.py                  # Worker in-memory (thread), 1 job por vez
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # MakeVideoImgSettings(BaseServiceSettings) com ConfigDict
│   │   ├── models.py              # Pydantic models (CreateVideoRequest, VideoJob, etc.)
│   │   └── constants.py           # JOB_PREFIX, ASPECT_RATIOS, ZOOM_STYLES, etc.
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # GET /, POST /jobs, GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}
│   │   ├── download_routes.py     # GET /download/{job_id}
│   │   ├── health_routes.py       # GET /health (ServiceHealthChecker), GET /ping
│   │   ├── admin_routes.py        # GET /admin/stats, POST /admin/cleanup
│   │   └── webhook.py             # send_webhook() POST callback
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_generator.py     # SE7 client + chunking + concat WAV
│   │   ├── image_generator.py     # SE8 client + progress callback
│   │   ├── video_assembler.py     # FFmpeg Ken Burns + crossfade + subtitles
│   │   └── pipeline.py            # Orquestra tudo: audio → images → assembly
│   └── infrastructure/
│       ├── __init__.py
│       ├── redis_store.py         # VideoJobStore + _FakeRedis fallback
│       ├── http_client.py         # ServiceClient, SE7Client, SE8Client
│       └── ffmpeg_utils.py        # run_ffmpeg, create_segment, concat_segments, etc.
├── docker/
│   ├── Dockerfile                 # Python 3.11-slim + ffmpeg, non-root user, healthcheck
│   └── docker-compose.yml         # Port 8009, ytcaption-net, memory limit 2G
├── tests/
│   ├── conftest.py                # Fixtures: csv_data_dir, temp_dir, services_online
│   ├── fixtures_loader.py         # Lê CSVs, agrupa por script_id, monta CreateVideoRequest
│   ├── fixtures/                  # 7 CSVs de dados reais
│   ├── unit/
│   │   ├── test_models.py         # 10 testes: lifecycle, stages, validation
│   │   ├── test_audio_chunking.py # 8 testes: text splitting, sentence fallback
│   │   ├── test_video_assembler_srt.py # 4 testes: SRT generation, timestamps
│   │   └── test_store.py          # 5 testes: FakeRedis CRUD
│   └── e2e/
│       └── test_full_pipeline.py  # Pipeline completo: mock audio/video + real FFmpeg
├── requirements.txt               # fastapi, httpx, redis, -e ../shared (SEM celery)
├── run.py                         # uvicorn runner via settings
├── .env                           # Variáveis de ambiente
├── .env.example                   # Template
└── pytest.ini                     # markers: e2e
```

### Dependências (requirements.txt)

```
# Core
fastapi
uvicorn[standard]
pydantic
pydantic-settings

# Redis (job store)
redis

# HTTP (comunicar com SE7/SE8)
httpx

# Common library
-e ../shared
```

**Sem dependência de PostgreSQL, Celery, psycopg2, sqlalchemy.**

---

## 7. Configuração (.env)

```bash
# === APP ===
APP_NAME=Make Video IMG
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false
HOST=0.0.0.0
PORT=8009
WORKERS=1
API_KEY=se9-test-key-2026
TZ=America/Sao_Paulo
DIVISOR=9

# === REDIS ===
REDIS_URL=redis://192.168.1.110:6379/9

# === SE7 (Audio Generation) ===
SE7_URL=http://localhost:8007
SE7_API_KEY=se7-test-key-2026

# === SE8 (Image Generation) ===
SE8_URL=http://localhost:8008
SE8_API_KEY=se8-test-key-2026

# === VIDEO SETTINGS ===
DEFAULT_VOICE_ID=builtin_feminino
DEFAULT_ASPECT_RATIO=9:16
DEFAULT_WIDTH=1080
DEFAULT_HEIGHT=1920
DEFAULT_FPS=30
DEFAULT_ZOOM_SPEED=0.001
DEFAULT_CROSSFADE_DURATION=0.5
DEFAULT_IMAGE_STEPS=30
DEFAULT_IMAGE_PERFORMANCE=Quality

# === TIMEOUTS (seconds) ===
SE7_POLL_INTERVAL=5
SE7_TIMEOUT=600
SE8_POLL_INTERVAL=3
SE8_TIMEOUT=300
FFMPEG_SEGMENT_TIMEOUT=60
FFMPEG_TOTAL_TIMEOUT=300

# === PATHS ===
TEMP_DIR=/tmp
OUTPUT_DIR=./data/outputs
LOG_DIR=./logs
LOG_LEVEL=INFO
```

**Sem variáveis CELERY_*.**

---

## 8. Integração com n8n / Orchestrators

### 8.1 Como o n8n chama o SE9

No n8n, adicionar um node **HTTP Request** após a geração do roteiro:

```
Method: POST
URL: http://se9-host:8009/jobs
Headers:
  X-API-Key: se9-test-key-2026
  Content-Type: application/json
Body: (JSON)
  Usar os mesmos campos que o n8n já gera para o save_video_script()
```

### 8.2 Mapeamento: payload n8n → payload SE9

| Campo n8n (save_video_script) | Campo SE9 API | Obrigatório? |
|---|---|---|
| `p_payload->>'post_id'` | `post_id` | Sim |
| `p_payload->>'hook'` | `hook` | Sim |
| `p_payload->>'estimated_seconds'` | `estimated_seconds` | Sim |
| `p_payload->>'language'` | `language` | Não (default: pt-BR) |
| `p_payload->>'content_rating'` | `content_rating` | Não (default: Geral) |
| `p_payload->'narration'` | `narration` | Sim |
| `p_payload->'scene_suggestions'` | `scene_suggestions` | Sim |
| `p_payload->'on_screen_text'` | `on_screen_text` | Não |
| `p_payload->'title_options'` | `title_options` | Não |
| `p_payload->'hashtags'` | `hashtags` | Não |
| `p_payload->'safety_notes'` | `safety_notes` | Não |
| — | `voice_id` | Não (default: builtin_feminino) |
| — | `aspect_ratio` | Não (default: 9:16) |
| — | `zoom_style` | Não (default: random) |
| — | `webhook_url` | Não |

### 8.3 Webhook de retorno

Quando o vídeo estiver pronto, o SE9 faz POST no `webhook_url` (se informado):

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

O caller pode usar esse webhook para:
- Atualizar status de publicação
- Enviar notificação
- Iniciar publicação automática

---

## 9. Decisões de Arquitetura

### 9.1 Por que API-first (sem PostgreSQL)?

| Critério | PostgreSQL | API-first |
|---|---|---|
| Deploy | +1 serviço (PG) | Zero extras |
| Complexidade | Driver, pooling, migrations | HTTP simples |
| Segredo | Credenciais PG | Só API key |
| Sync | Schema PG = schema SE9 | Contrato JSON |
| Performance | Queries + ORM | Payload pronto |

**Vencedor: API-first.** O caller é o dono dos dados. O SE9 é um executor.

### 9.2 Por que não adicionar ao SE5?

| SE5 (Make Video Clip) | SE9 (Make Video IMG) |
|---|---|
| Fonte: YouTube shorts | Fonte: Imagens geradas por IA |
| Áudio: Upload manual | Áudio: Gerado automaticamente (SE7) |
| Pipeline: Download → Transform → Validate | Pipeline: Script → Audio → Images → Compose |
| Banco: Nenhum | Banco: Nenhum (API-first) |

São fluxos completamente diferentes. SE9 é mais simples e especializado.

### 9.3 Ken Burns via FFmpeg zoompan

**Por que FFmpeg e não OpenCV?**
- zoompan: 1 linha de filtro, ~50 linhas de código
- OpenCV: ~200 linhas para o mesmo efeito
- FFmpeg é mais eficiente em memória (streaming)
- Qualidade igual ou superior

### 9.4 Sincronização áudio-imagens

Os timestamps `t` do caller estão em **segundos** e são alinhados entre narração e cenas:

```
Narração t=0:  "Eu vi a matéria..."     → início do vídeo
Cena t=0:      "B-roll de arquivos..."  → mesma posição

Narração t=8:  "O documento foi..."     → 8 segundos
Cena t=8:      "Estante de livros..."   → mesma posição
```

O SE9 usa os timestamps para:
1. Definir quanto tempo cada imagem fica na tela
2. Sincronizar crossfade com início de novos segmentos
3. Posicionar legendas (on_screen_text) no momento correto

### 9.5 Worker in-memory vs Celery

**Decisão: Worker in-memory (thread)** — mesmo padrão do SE7.

| Critério | Celery | In-memory |
|---|---|---|
| Deploy | Redis + Worker separado | Tudo junto |
| Complexidade | Config de queue, broker, serializer | Thread + EventLoop |
| 1 job/vídeo | Overkill | Perfeito |
| Retry/Dead letter | Built-in | Manual |
| Escalabilidade | Horizontal | Vertical |

Para SE9 (1 job por vez, ~8min por vídeo), Celery seria overkill.

### 9.6 Redis com fallback in-memory

O SE9 usa `_FakeRedis` quando Redis está indisponível — permite desenvolvimento e testes sem Redis rodando. Em produção, Redis é recomendado para persistência entre restarts.

---

## 10. Riscos e Mitigações

| Risco | Impacto | Mitigation |
|---|---|---|
| SE7 muito lento (CPU) | Alto | Usar GPU se disponível, chunking de texto |
| Imagens não combinam com cena | Médio | Prompt engineering, retry com prompt refinado |
| Ken Burns causa bordas pretas | Baixo | Zoom conservador (0.1% por frame), scale 2x |
| Texto na tela sobrepõe imagem | Médio | MarginV=60, Alignment=2 (bottom center) |
| SE7/SE8 offline | Crítico | Retry com backoff no HTTP client (3 tentativas) |
| Payload do caller muda | Alto | Validação rigorosa via Pydantic |
| Texto >5000 chars (Chatterbox) | Alto | Chunking por parágrafos + concat WAV |
| Redis indisponível | Médio | _FakeRedis in-memory fallback |
| FFmpeg erro em segmento | Médio | Timeout por segmento (60s), erro propagado |
| Temp files leak | Baixo | Cleanup no finally do pipeline |

---

## 11. Status de Implementação

### Fase 1 — Infraestrutura Base ✅
- [x] config.py — BaseServiceSettings com todas as configs
- [x] models.py — CreateVideoRequest, VideoJob, StageInfo, etc.
- [x] constants.py — JOB_PREFIX, ASPECT_RATIOS, ZOOM_STYLES
- [x] http_client.py — ServiceClient, SE7Client, SE8Client com retry
- [x] ffmpeg_utils.py — run_ffmpeg, create_segment, concat_segments, etc.
- [x] requirements.txt — sem celery, com -e ../shared

### Fase 2 — Serviços Core ✅
- [x] audio_generator.py — chunking por parágrafos, concat WAV via ffmpeg
- [x] image_generator.py — SE8 client, progress callback
- [x] video_assembler.py — Ken Burns, crossfade, SRT subtitles, trim
- [x] pipeline.py — orquestra audio → images → assembly

### Fase 3 — API Routes + Worker ✅
- [x] main.py — create_service_app, lifespan com worker start/stop
- [x] worker.py — thread in-memory, asyncio event loop persistente
- [x] routes.py — GET /, POST /jobs, GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}
- [x] download_routes.py — GET /download/{job_id} FileResponse
- [x] health_routes.py — ServiceHealthChecker (SE7, SE8, disk, ffmpeg)
- [x] admin_routes.py — GET /admin/stats, POST /admin/cleanup
- [x] webhook.py — send_webhook POST callback

### Fase 4 — Docker + Tests ✅
- [x] Dockerfile — Python 3.11-slim, ffmpeg, non-root user, healthcheck
- [x] docker-compose.yml — port 8009, ytcaption-net, memory 2G
- [x] .env.example — todas variáveis documentadas
- [x] tests/unit/ — 27 testes (models, chunking, SRT, store)
- [x] tests/e2e/ — 1 teste pipeline completo (mock audio/video + real FFmpeg)
- [x] tests/fixtures/ — 7 CSVs com dados reais

### Validação ✅
- [x] 28/28 testes passando
- [x] Todos imports OK
- [x] Docker compose config válido
- [x] Padrão monorepo (BaseServiceSettings, create_service_app)

---

## 12. Resumo Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO COMPLETO SE9                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │Caller│───▶│   SE9    │───▶│   SE7    │───▶│  Áudio   │     │
│  │(n8n) │    │(API POST)│    │  (TTS)   │    │  .wav    │     │
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
│  Input:  JSON do caller (post_id, narration, scenes, titles)  │
│  Output: MP4 1080x1920 (9:16), H264, 30fps                   │
│  Tempo:  ~7-8 minutos por vídeo                               │
│                                                                 │
│  API:   POST /jobs → GET /jobs/{id} → GET /download/{id}     │
│  Auth:  X-API-Key: se9-test-key-2026                          │
│  Worker: In-memory thread (1 job por vez)                      │
│  Redis:  Job store com fallback in-memory                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Perguntas em Aberto — Resolvidas

| # | Pergunta | Resposta |
|---|---------|---------|
| 1 | URL do n8n? | Não é responsabilidade do SE9 — o caller configura sua URL |
| 2 | n8n já tem HTTP Request? | O SE9 aceita qualquer caller via API REST padrão |
| 3 | Quantos vídeos por dia? | 1 worker thread → ~7 vídeos/hora (limitado pelo SE7) |
| 4 | Precisa de legendas? | Sim — on_screen_text → SRT → burn via ffmpeg |
| 5 | Onde salvar vídeos? | Disco local (/tmp durante processamento, data/outputs para final) |
| 6 | Webhook necessário? | Opcional — webhook_url no payload, POST quando vídeo pronto |

---

## 14. Próximos Passos (Futuro)

- [ ] Métricas Prometheus
- [ ] Paralelismo SE7+SE8 (reduz de ~8min para ~5min)
- [ ] Batch processing (múltiplos vídeos)
- [ ] Suporte a outros aspect ratios (4:5 para Instagram feed)
- [ ] Webhook retry com dead letter
