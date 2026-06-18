# SE9 — Make Video IMG

## Documento de Investigação e Arquitetura

**Data:** 2026-06-18 (v3 — API-first, genérico para qualquer fonte de histórias)
**Status:** Implementado

---

## 1. Visão Geral do Projeto

### O que é
Um microservice genérico (SE9) que automatiza a criação de vídeos para redes sociais (TikTok, Reels, Shorts) a partir de **dados enviados pelo n8n**. O n8n coleta histórias de qualquer fonte (Reddit, Twitter, RSS, APIs próprias), gera roteiros com IA, e manda tudo para o SE9 via API REST.

**O SE9 é genérico** — não depende de nenhuma fonte específica. Para criar um novo fluxo:
1. Criar novo database/subscription no n8n para a nova fonte
2. Criar novo workflow no n8n que coleta dados e formata o payload
3. Apontar para o mesmo endpoint POST /jobs do SE9
4. Pronto — o SE9 processa qualquer histórico no formato padrão

### Fluxo completo (exemplo: Reddit)

```
Reddit → n8n (coleta + roteiro) → POST /jobs → SE9 (orquestra)
  ├── SE7 (áudio)  → narração WAV
  ├── SE8 (imagens) → cenas PNG
  └── FFmpeg        → vídeo final MP4
```

### Fluxo genérico (qualquer fonte)

```
Fonte → n8n (coleta + roteiro) → POST /jobs → SE9 (orquestra)
  ├── SE7 (áudio)  → narração WAV
  ├── SE8 (imagens) → cenas PNG
  └── FFmpeg        → vídeo final MP4
```

### Por que API-first (sem PostgreSQL)?

| Antes (PostgreSQL) | Agora (API) |
|---|---|
| Precisa de credenciais PG | Zero dependência de banco |
| Deploy mais complexo | Deploy simples |
| SE9 precisa ler/escrever PG | n8n manda tudo pronto |
| Sync de schema entre n8n e SE9 | Contrato via JSON |
| Query para buscar roteiros | n8n já filtrou o que interessa |

O n8n **já tem todos os dados**. Não precisamos acessar o banco — recebemos o payload pronto via HTTP.

### Dados que o n8n envia

O n8n usa a função `reddit.save_video_script(p_payload jsonb)` para salvar no PG (exemplo para Reddit). Para outras fontes, criar função equivalente. O **mesmo payload** pode ser enviado para o SE9:

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

### 2.1 Criar job de vídeo

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

### 2.2 Consultar status

```http
GET /jobs/{job_id}
X-API-Key: se9-test-key-2026
```

```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_audio",
  "progress": 25,
  "stages": {
    "reading_script": {"status": "completed", "progress": 5},
    "generating_audio": {"status": "processing", "progress": 25},
    "generating_images": {"status": "pending", "progress": 0},
    "assembling_video": {"status": "pending", "progress": 0}
  },
  "audio_job_id": "ag_ff8dbef4587ebe23",
  "images_generated": 0,
  "images_total": 8,
  "created_at": "2026-06-18T15:00:00Z"
}
```

### 2.3 Download do vídeo

```http
GET /download/{job_id}
X-API-Key: se9-test-key-2026
```

Retorna: `video/mp4` binário

### 2.4 Webhook de notificação (opcional)

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
  "download_url": "http://se9-host:8009/download/rbg_a1b2c3d4e5f6",
  "title": "O Passaporte Perdido",
  "hashtags": ["#relatos", "#misterio"],
  "duration_seconds": 96
}
```

### 2.5 Health check

```http
GET /health
```

```json
{
  "status": "healthy",
  "service": "make-video-img",
  "checks": {
    "se7": "ok",
    "se8": "ok",
    "redis": "ok",
    "disk": "ok"
  }
}
```

---

## 3. Pipeline Detalhado

### 3.1 Fase 1 — Receber e validar payload

```
Entrada: POST /jobs com payload completo do n8n
```

1. Validar payload obrigatório: `post_id`, `hook`, `estimated_seconds`, `narration`, `scene_suggestions`
2. Gerar `job_id` único (`rbg_{uuid}`)
3. Salvar job no Redis (status: `queued`)
4. Disparar Celery task
5. Retornar `job_id` imediatamente

### 3.2 Fase 2 — Gerar áudio (SE7)

```
Entrada: narration [{t, text}]
Saída: arquivo WAV com áudio completo
```

1. Concatena todos os `text` dos segmentos de narração em uma string
2. Envia para SE7: `POST http://se7:8007/jobs`
   - `text`: narração concatenada
   - `voice_id`: o que o n8n enviou (padrão: `builtin_feminino`)
   - `exaggeration`, `cfg_weight`, `temperature`: defaults
3. Polling: `GET http://se7:8007/jobs/{ag_job_id}` a cada 5s
4. Download: `GET http://se7:8007/jobs/{ag_job_id}/download`
5. Salvar WAV em `/tmp/rbg_{job_id}/audio.wav`
6. Obter duração real via ffprobe

**Autenticação:** `X-API-Key: se7-test-key-2026`

**Tempo estimado:** ~5min (CPU) ou ~30s (GPU)

### 3.3 Fase 3 — Gerar imagens (SE8)

```
Entrada: scene_suggestions [{t, visual}]
Saída: imagens PNG para cada cena
```

1. Para cada cena em `scene_suggestions`:
   - Enviar para SE8: `POST http://se8:8008/v1/generation/text-to-image`
     - `prompt`: valor de `visual` (ex: "B-roll de arquivos antigos, fotos em preto e branco")
     - `width`: 1024 (ou conforme aspect_ratio)
     - `height`: 1024
     - `steps`: 30
     - `performance`: "Quality"
   - Polling: `GET http://se8:8008/v1/generation/query-job?job_id={se8_job_id}`
   - Download: `GET http://se8:8008/files/{date}/{filename}`
   - Salvar em `/tmp/rbg_{job_id}/scene_{t}.png`

2. Progresso: atualizar a cada imagem concluída

**Autenticação:** `X-API-Key: se8-test-key-2026`

**Tempo estimado:** ~10s por imagem × 8 cenas = ~80s

**Paralelismo possível:** SE8 processa 1 job por vez. Mas podemos enviar todas as imagens em sequência sem esperar cada uma individualmente.

### 3.4 Fase 4 — Montar vídeo (FFmpeg)

```
Entrada: áudio WAV + imagens PNG + timestamps
Saída: vídeo MP4 final
```

**Algoritmo:**

```
1. Calcular duração de cada cena:
   - Para cada cena i: dur_i = t[i+1] - t[i]
   - Última cena: dur = audio_duration - t[last]

2. Para cada cena, criar segmento de vídeo com Ken Burns:
   ffmpeg -loop 1 -i scene_{t}.png -t {dur_i} \
     -vf "zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s=1080x1920:fps=30" \
     -c:v libx264 -pix_fmt yuv420p segment_{i}.mp4

3. Concatenar segmentos com crossfade:
   ffmpeg -i seg0.mp4 -i seg1.mp4 ... -i segN.mp4 \
     -filter_complex "
       [0:v][1:v]xfade=transition=fade:duration=0.5:offset={off0}[v01];
       [v01][2:v]xfade=transition=fade:duration=0.5:offset={off1}[v02];
       ...
     " \
     -map "[vlast]" -c:v libx264 -preset fast -crf 23 video_no_audio.mp4

4. Adicionar áudio:
   ffmpeg -i video_no_audio.mp4 -i audio.wav \
     -c:v copy -c:a aac -b:a 192k video_with_audio.mp4

5. Adicionar texto na tela (on_screen_text) como legendas:
   ffmpeg -i video_with_audio.mp4 \
     -vf "subtitles=subtitles.srt:force_style='FontSize=22,...'" \
     -c:a copy final.mp4

6. Trim para duração do áudio:
   ffmpeg -i final.mp4 -t {audio_duration} \
     -c:v libx264 -c:a aac output.mp4
```

**Efeito Ken Burns (zoompan filter):**

| Estilo | Expressão zoom | Efeito |
|---|---|---|
| Zoom in | `z='1+0.001*in'` | Aproxima suavemente |
| Zoom out | `z='1.05-0.001*in'` | Afasta suavemente |
| Pan left | `x='iw*0.1-in*0.05'` | Desliza para esquerda |
| Pan right | `x='in*0.05'` | Desliza para direita |
| Random | Escolhe uma das acima por cena | Variação visual |

**Parâmetros configuráveis:**
- `zoom_speed`: 0.001 (0.1% por frame)
- `crossfade_duration`: 0.5s
- `output_resolution`: 1080x1920 (9:16)
- `fps`: 30
- `crf`: 23 (qualidade)

### 3.5 Fase 5 — Entregar resultado

1. Salvar vídeo final em `data/outputs/{job_id}_final.mp4`
2. Atualizar job status para `completed`
3. Se `webhook_url` foi informado, fazer POST com dados do vídeo
4. Limpar temporários

---

## 4. Jobs e Estados

### 4.1 Modelo de Job

```python
class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING_AUDIO = "generating_audio"
    WAITING_AUDIO = "waiting_audio"
    GENERATING_IMAGES = "generating_images"
    WAITING_IMAGES = "waiting_images"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 4.2 Progresso

| Estágio | Progresso | Dependência |
|---|---|---|
| QUEUED | 0% | — |
| GENERATING_AUDIO | 5% | SE7 |
| WAITING_AUDIO | 5-30% | SE7 |
| GENERATING_IMAGES | 30-70% | SE8 |
| WAITING_IMAGES | 30-70% | SE8 |
| ASSEMBLING_VIDEO | 70-95% | FFmpeg local |
| COMPLETED | 100% | — |

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
- **Gargalo:** SE7 (CPU) — se mover para GPU, cai para ~1min

### 5.3 Otimização: paralelismo

```
Fase 1:  [====SE7====]                    (5min)
Fase 2:                [==SE8==][==SE8==]  (80s, pode ser paralelo com SE7 no futuro)
Fase 3:                              [FFMPEG] (30s)
```

Hoje: sequencial (SE7 → SE8 → FFmpeg)
Futuro: SE8 imagens em paralelo com SE7 áudio (reduz para ~5min total)

---

## 6. Estrutura do Microservice

```
services/se9-make-video-img/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py              # Settings (Redis, SE7, SE8)
│   │   ├── models.py              # Pydantic models (payload, job, response)
│   │   └── constants.py           # Defaults, aspect ratios, zoom styles
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # POST /jobs, GET /jobs/{id}
│   │   ├── health_routes.py       # /health, /ping
│   │   └── download_routes.py     # GET /download/{id}
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_generator.py     # Coleta com SE7
│   │   ├── image_generator.py     # Coleta com SE8
│   │   ├── video_assembler.py     # Montagem FFmpeg (Ken Burns)
│   │   └── pipeline.py            # Orquestra tudo
│   └── infrastructure/
│       ├── __init__.py
│       ├── redis_store.py         # Job store (shared/job_utils)
│       ├── http_client.py         # Client para SE7/SE8
│       └── subprocess_utils.py    # FFmpeg wrapper
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── .env
└── .env.example
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
celery

# HTTP (comunicar com SE7/SE8)
httpx

# Common library
-e ./common
```

**Sem dependência de PostgreSQL, psycopg2, sqlalchemy, ou qualquer driver de banco.**

---

## 7. Configuração (.env)

```bash
# === APPLICAÇÃO ===
APP_NAME=Make Video IMG
VERSION=1.0.0
PORT=8009
API_KEY=se9-test-key-2026

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

# === CELERY ===
CELERY_BROKER_URL=redis://192.168.1.110:6379/9
CELERY_RESULT_BACKEND=redis://192.168.1.110:6379/9
CELERY_TASK_TIME_LIMIT=1800
```

---

## 8. Integração com n8n

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
  "duration_seconds": 96,
  "file_size_mb": 12.5
}
```

O n8n pode usar esse webhook para:
- Atualizar `post_social_status`
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
| Flexibilidade | Query任意 | O que n8n enviar |

**Vencedor: API-first.** O n8n é o dono dos dados. O SE9 é um executor.

### 9.2 Por que não adicionar ao SE5?

| SE5 (Make Video Clip) | SE9 (Make Video IMG) |
|---|---|
| Fonte: YouTube shorts | Fonte: Imagens geradas |
| Áudio: Upload manual | Áudio: Gerado automaticamente |
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

Os timestamps `t` do n8n estão em **segundos** e são alinhados entre narração e cenas:

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

---

## 10. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| SE7 muito lento (CPU) | Alto | Usar GPU se disponível, ou chunking |
| Imagens não combinam com cena | Médio | Prompt engineering, retry com prompt refinado |
| Ken Burns causa bordas pretas | Baixo | Zoom conservador (2-3%), padding 5% |
| Texto na tela sobrepõe imagem | Médio | Posicionar bottom 20% |
| SE7/SE8 offline | Crítico | Retry com backoff, fila Redis |
| Payload do n8n muda | Alto | Validação rigorosa, versionamento da API |
| Texto >5000 chars (Chatterbox) | Alto | Chunking em段落 + concat WAV |

---

## 11. Prioridades de Implementação

### Fase 1 — MVP (1-2 dias)
- [ ] Configuração básica (Redis, SE7, SE8 URLs)
- [ ] Modelo de payload (Pydantic)
- [ ] POST /jobs + GET /jobs/{id}
- [ ] audio_generator.py (chamar SE7)
- [ ] image_generator.py (chamar SE8)
- [ ] video_assembler.py (Ken Burns básico)
- [ ] Pipeline Celery task

### Fase 2 — Refinamento (1 dia)
- [ ] Crossfade entre cenas
- [ ] Texto na tela (on_screen_text → SRT → burn)
- [ ] Webhook de notificação
- [ ] Retry com backoff
- [ ] Download de vídeo

### Fase 3 — Produção (1 dia)
- [ ] Dockerfile + docker-compose
- [ ] Testes E2E com payload real do n8n
- [ ] Monitoramento e métricas
- [ ] Batch processing (múltiplos vídeos)

---

## 12. Resumo Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO COMPLETO SE9                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ n8n  │───▶│   SE9    │───▶│   SE7    │───▶│  Áudio   │     │
│  │(n8n)     │(API POST)│    │  (TTS)   │    │  .wav    │     │
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
│  Input:  JSON do n8n (post_id, narration, scenes, titles)     │
│  Output: MP4 1080x1920 (9:16), H264, 30fps                   │
│  Tempo:  ~7-8 minutos por vídeo                               │
│                                                                 │
│  API:   POST /jobs → GET /jobs/{id} → GET /download/{id}     │
│  Auth:  X-API-Key: se9-test-key-2026                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Perguntas em Aberto

1. **Qual a URL do n8n?** Para configurar CORS/callback
2. **O n8n já tem o node HTTP Request configurado?** Preciso saber o formato exato
3. **Quantos vídeos por dia?** Para dimensionar workers
4. **Precisa de legendas (on_screen_text)?** ou só áudio + imagem?
5. **Onde salvar os vídeos gerados?** Disco local, S3, ou o próprio SE9 serve?
6. **Webhook de retorno é necessário?** ou o n8n faz polling no /jobs/{id}?
