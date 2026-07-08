# API.md — SE9 Make Video IMG

**Versão**: 2.0
**Data**: 2026-07-08
**Porta**: 8009
**Auth**: `X-API-Key` header (via `common.fastapi_utils`)
**Padrão**: Segue estrutura SE11 clothes-removal (schemas.py separado, FlexibleSchema, Enums, Field descriptions)

---

## 1. Visão Geral

O SE9 (make-video-img) é um serviço de geração de vídeos curtos a partir de narração TTS + imagens geradas por IA.

**Pipeline**: Narration → SE7 TTS → SE8 Fooocus → FFmpeg Ken Burns + Crossfade → MP4

### 1.1 Endpoints

| Método | Rota | Status | Descrição |
|--------|------|--------|-----------|
| GET | `/` | 200 | Service info (descoberta de endpoints) |
| POST | `/jobs` | 201 | Criar job de geração de vídeo |
| GET | `/jobs` | 200 | Listar jobs (paginado) |
| GET | `/jobs/{job_id}` | 200 | Status do job |
| DELETE | `/jobs/{job_id}` | 200 | Deletar job |
| GET | `/download/{job_id}` | 200 | Download do vídeo final |
| GET | `/health` | 200 | Health check (SE7 + SE8 + disco + ffmpeg) |
| GET | `/ping` | 200 | Ping |
| GET | `/config` | 200 | Configuração do serviço |
| GET | `/transitions` | 200 | Transições FFmpeg disponíveis |
| GET | `/admin/stats` | 200 | Estatísticas do sistema |
| POST | `/admin/cleanup` | 200 | Limpeza de jobs falhos |

### 1.2 Autenticação

Todas as rotas (exceto `/health`, `/ping`) requerem header `X-API-Key`.

```bash
curl -H "X-API-Key: se9-test-key-2026" http://localhost:8009/jobs
```

---

## 2. Schemas

### 2.1 Enums

#### VideoJobStatus
Status do ciclo de vida do job.

| Valor | Descrição |
|-------|-----------|
| `queued` | Aguardando worker |
| `generating_audio` | SE7 TTS processando |
| `generating_images` | SE8 Fooocus processando |
| `assembling_video` | FFmpeg montando vídeo |
| `completed` | Vídeo pronto para download |
| `failed` | Erro ocorrido |

#### StageStatus
Status individual de cada estágio do pipeline.

| Valor | Descrição |
|-------|-----------|
| `pending` | Não iniciado |
| `processing` | Em processamento |
| `completed` | Concluído |
| `failed` | Falhou |

#### ZoomStyle
Direção do zoom Ken Burns.

| Valor | Descrição |
|-------|-----------|
| `zoom_in` | Zoom de 1.0x → 1.2x |
| `zoom_out` | Zoom de 1.2x → 1.0x |
| `random` | Alterna aleatoriamente |

### 2.2 Request Models

#### NarrationSegment
Segmento de narração com timestamp.

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `t` | float | ✅ | Tempo de início em segundos |
| `text` | str | ✅ | Texto da narração (max 5000 chars) |

#### SceneSuggestion
Prompt visual para uma cena.

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `t` | float | ✅ | Tempo de início em segundos |
| `visual` | str | ✅ | Prompt de geração de imagem (max 2000 chars) |
| `negative_prompt` | str \| null | ❌ | O que evitar na imagem (max 2000 chars) |
| `camera_movement` | str \| null | ❌ | Direção do zoom: `static`, `slow_push_in`, `slow_pull_out`, `random` |
| `transition` | str \| null | ❌ | Transição FFmpeg xfade após esta cena (ex: `dissolve`, `fadeblack`) |

#### OnScreenText
Legenda com timing.

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `t` | float | ✅ | Tempo de início em segundos |
| `text` | str | ✅ | Texto da legenda (max 500 chars) |
| `end_seconds` | float \| null | ❌ | Tempo de fim (se null, fica até próxima legenda) |

#### CreateVideoRequest
Request principal para criação de job.

| Campo | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `post_id` | str | ✅ | — | ID do post upstream (1-100 chars) |
| `hook` | str | ✅ | — | Título/hook do vídeo (max 500 chars) |
| `estimated_seconds` | int | ✅ | — | Duração alvo em segundos (5-600) |
| `language` | str | ❌ | `"pt-BR"` | Idioma para TTS |
| `content_rating` | str | ❌ | `"Geral"` | Classificação (metadata) |
| `narration` | NarrationSegment[] | ✅ | — | Segmentos de narração (min 1) |
| `scene_suggestions` | SceneSuggestion[] | ✅ | — | Prompts de cena (min 1, max 20) |
| `on_screen_text` | OnScreenText[] | ❌ | `[]` | Legendas com timing |
| `title_options` | str[] | ❌ | `[]` | Títulos alternativos (metadata) |
| `hashtags` | str[] | ❌ | `[]` | Hashtags (metadata) |
| `safety_notes` | str[] | ❌ | `[]` | Notas de segurança (metadata) |
| `voice_id` | str | ❌ | `"builtin_feminino"` | ID da voz TTS |
| `aspect_ratio` | str | ❌ | `"9:16"` | Proporção: `9:16`, `16:9`, `1:1` |
| `zoom_style` | ZoomStyle | ❌ | `"random"` | Direção do zoom Ken Burns |
| `webhook_url` | str \| null | ❌ | `null` | URL para notificação de conclusão |
| `normalize_text` | bool | ❌ | `true` | Normalizar texto antes do TTS |
| `global_style` | object \| null | ❌ | `null` | Metadados de estilo (não usado no pipeline) |

### 2.3 Response Models

#### CreateVideoResponse (HTTP 201)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | str | ID único do job (prefixo: `rbg_`) |
| `status` | VideoJobStatus | Status inicial (`queued`) |
| `post_id` | str | ID do post |
| `estimated_seconds` | int | Duração alvo |
| `scenes_count` | int | Número de cenas |
| `message` | str | Mensagem legível |

#### JobStatusResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | str | ID do job |
| `status` | VideoJobStatus | Status atual |
| `progress` | float | Progresso geral (0-100%) |
| `stages` | object | Detalhes dos estágios (status, progress, error, timestamps) |
| `created_at` | str | Timestamp de criação (ISO 8601) |
| `error` | str \| null | Mensagem de erro se falhou |

**Progresso ponderado**: audio=0-40%, images=40-70%, assembly=70-100%

#### ListJobsResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jobs` | JobListItem[] | Lista de jobs (mais recente primeiro) |
| `total` | int | Total de jobs no sistema |

#### JobListItem

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | str | ID do job |
| `status` | VideoJobStatus | Status atual |
| `progress` | float | Progresso geral |
| `post_id` | str \| null | ID do post |
| `created_at` | str \| null | Timestamp de criação |

#### DeleteJobResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `detail` | str | Mensagem de confirmação |

#### ConfigResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `service` | str | Nome do serviço |
| `version` | str | Versão |
| `defaults` | object | Configurações padrão (voice_id, aspect_ratio, fps, etc.) |
| `supported_aspect_ratios` | str[] | Proporções suportadas |
| `supported_zoom_styles` | str[] | Estilos de zoom suportados |
| `upstream` | object | URLs dos serviços upstream (SE7, SE8) |

#### TransitionsResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `transitions` | str[] | Nomes das transições FFmpeg disponíveis |
| `total` | int | Total de transições |
| `default` | str | Modo padrão (`random`) |

#### HealthResponse (HTTP 200)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | str | Status do serviço |
| `service` | str | Nome do serviço |
| `version` | str | Versão |

#### ErrorResponse (HTTP 4xx/5xx)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `detail` | str | Mensagem de erro legível |

---

## 3. Endpoints — Detalhes

### 3.1 GET / — Service Info

**Summary**: Descoberta de endpoints.
**Auth**: Não requerida.

```bash
curl http://localhost:8009/
```

**Response 200**:
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
    "GET /health": "Health check",
    "GET /config": "Service configuration",
    "GET /transitions": "Available transitions",
    "GET /admin/stats": "System statistics",
    "POST /admin/cleanup": "Cleanup temp files and failed jobs"
  }
}
```

### 3.2 POST /jobs — Criar Job

**Summary**: Criar job de geração de vídeo.
**Auth**: Requerida.
**Status**: 201 Created.

```bash
curl -X POST http://localhost:8009/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: se9-test-key-2026" \
  -d '{
    "post_id": "1ra5656",
    "hook": "Fiz meu pai vender o sítio assombrado dele",
    "estimated_seconds": 30,
    "narration": [
      {"t": 0, "text": "Meu pai comprou um sítio perto da família materna."},
      {"t": 5, "text": "Uma semana depois, ouvi ruídos à noite."}
    ],
    "scene_suggestions": [
      {
        "t": 0,
        "visual": "Estabelecing shot vertical, paisagem rural genérica.",
        "negative_prompt": "pessoas, casas, carros.",
        "camera_movement": "static",
        "transition": "dissolve"
      },
      {
        "t": 5,
        "visual": "Medium shot interior at night, soft low light.",
        "camera_movement": "slow_push_in"
      }
    ],
    "on_screen_text": [
      {"t": 1.2, "text": "Meu pai comprou um sítio.", "end_seconds": 4.5}
    ],
    "voice_id": "builtin_feminino",
    "aspect_ratio": "9:16"
  }'
```

**Response 201**:
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "queued",
  "post_id": "1ra5656",
  "estimated_seconds": 30,
  "scenes_count": 2,
  "message": "Video generation started"
}
```

**Errors**:
- 422: Validation error (campos obrigatórios ausentes, tipos inválidos)
- 500: Internal server error

### 3.3 GET /jobs — Listar Jobs

**Summary**: Listar todos os jobs (paginado).
**Auth**: Requerida.

```bash
curl "http://localhost:8009/jobs?limit=10&offset=0" \
  -H "X-API-Key: se9-test-key-2026"
```

**Query Parameters**:

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `limit` | int | 50 | Máximo de jobs (1-200) |
| `offset` | int | 0 | Jobs a pular (paginação) |

**Response 200**:
```json
{
  "jobs": [
    {
      "job_id": "rbg_a1b2c3d4e5f6",
      "status": "completed",
      "progress": 100.0,
      "post_id": "1ra5656",
      "created_at": "2026-07-08T14:30:00.000-03:00"
    }
  ],
  "total": 38
}
```

### 3.4 GET /jobs/{job_id} — Status do Job

**Summary**: Status e progresso do job.
**Auth**: Requerida.

```bash
curl http://localhost:8009/jobs/rbg_a1b2c3d4e5f6 \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_images",
  "progress": 55.0,
  "stages": {
    "generating_audio": {
      "status": "completed",
      "progress": 100.0,
      "started_at": "2026-07-08T14:30:00.000-03:00",
      "completed_at": "2026-07-08T14:30:25.000-03:00"
    },
    "generating_images": {
      "status": "processing",
      "progress": 50.0,
      "started_at": "2026-07-08T14:30:25.000-03:00"
    },
    "assembling_video": {
      "status": "pending",
      "progress": 0.0
    }
  },
  "created_at": "2026-07-08T14:30:00.000-03:00",
  "error": null
}
```

**Errors**:
- 404: Job not found

### 3.5 DELETE /jobs/{job_id} — Deletar Job

**Summary**: Deletar job e arquivos de output.
**Auth**: Requerida.

```bash
curl -X DELETE http://localhost:8009/jobs/rbg_a1b2c3d4e5f6 \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "detail": "Job rbg_a1b2c3d4e5f6 deleted"
}
```

**Errors**:
- 404: Job not found

### 3.6 GET /download/{job_id} — Download

**Summary**: Download do vídeo final (MP4).
**Auth**: Requerida.

```bash
curl -O http://localhost:8009/download/rbg_a1b2c3d4e5f6 \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**: FileResponse (video/mp4)

**Errors**:
- 400: Job not completed
- 404: Job not found or video file not found

### 3.7 GET /health — Health Check

**Summary**: Health check com verificação de SE7, SE8, disco e FFmpeg.
**Auth**: Não requerida.

```bash
curl http://localhost:8009/health
```

**Response 200**:
```json
{
  "status": "ok",
  "service": "make-video-img",
  "version": "1.0.0",
  "checks": {
    "se7": {"status": "ok"},
    "se8": {"status": "ok"},
    "disk": {"status": "ok", "free_gb": 8.8},
    "ffmpeg": {"status": "ok"}
  }
}
```

### 3.8 GET /ping — Ping

**Summary**: Teste de conectividade.
**Auth**: Não requerida.

```bash
curl http://localhost:8009/ping
```

**Response 200**:
```json
{"pong": true}
```

### 3.9 GET /config — Configuração

**Summary**: Configuração atual do serviço (sem segredos).
**Auth**: Requerida.

```bash
curl http://localhost:8009/config \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "service": "make-video-img",
  "version": "1.0.0",
  "defaults": {
    "voice_id": "builtin_feminino",
    "aspect_ratio": "9:16",
    "zoom_style": "random",
    "fps": 30,
    "width": 1080,
    "height": 1920,
    "crossfade_duration": 0.3,
    "image_steps": 30,
    "image_performance": "Quality"
  },
  "supported_aspect_ratios": ["9:16", "16:9", "1:1"],
  "supported_zoom_styles": ["zoom_in", "zoom_out", "random"],
  "upstream": {
    "se7": "http://localhost:8007",
    "se8": "http://localhost:8008"
  }
}
```

### 3.10 GET /transitions — Transições

**Summary**: Transições FFmpeg xfade disponíveis.
**Auth**: Requerida.

```bash
curl http://localhost:8009/transitions \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "transitions": [
    "circleopen", "circleclose", "wipeleft", "wiperight",
    "wipeup", "wipedown", "slideleft", "slideright",
    "dissolve", "pixelize", "radial", "zoomin",
    "fadefast", "fadeslow", "smoothleft", "smoothright"
  ],
  "total": 32,
  "default": "random"
}
```

### 3.11 GET /admin/stats — Estatísticas

**Summary**: Estatísticas do sistema (jobs, disco).
**Auth**: Requerida.

```bash
curl http://localhost:8009/admin/stats \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "service": "make-video-img",
  "version": "1.0.0",
  "jobs": {
    "total": 38,
    "by_status": {
      "completed": 30,
      "failed": 5,
      "queued": 3
    }
  },
  "disk": {
    "/tmp": {
      "total_gb": 100.0,
      "used_gb": 91.2,
      "free_gb": 8.8
    }
  }
}
```

### 3.12 POST /admin/cleanup — Limpeza

**Summary**: Limpar jobs falhos (diretórios + Redis).
**Auth**: Requerida.

```bash
curl -X POST http://localhost:8009/admin/cleanup \
  -H "X-API-Key: se9-test-key-2026"
```

**Response 200**:
```json
{
  "detail": "Cleaned up 5 failed jobs (dirs + Redis keys)"
}
```

---

## 4. Fluxos

### 4.1 Fluxo de Criação de Job

```
1. POST /jobs → CreateVideoRequest
2. SE9 gera job_id = "rbg_" + uuid4().hex[:12]
3. Cria VideoJob com status "queued"
4. Salva no Redis (sorted set + key)
5. Inicia worker (se não estiver rodando)
6. Retorna CreateVideoResponse (HTTP 201)
```

### 4.2 Fluxo de Processamento

```
1. Worker detecta job "queued" no Redis
2. Status → "generating_audio"
   - Concatena narration segments
   - Chama SE7 TTS (POST /jobs)
   - Polling até "completed"
   - Download WAV
   - Progresso: 0-40%
3. Status → "generating_images"
   - Para cada scene_suggestion:
     - Adiciona cinematic_suffix ao prompt
     - Chama SE8 (POST /v1/generation/text-to-image)
     - Download PNG
   - Progresso: 40-70%
4. Status → "assembling_video"
   - Calcula duração por cena
   - Cria segmentos Ken Burns (FFmpeg)
   - Concatena com crossfade
   - Adiciona áudio
   - Trim para duração final
   - Progresso: 70-100%
5. Status → "completed"
   - Salva video_path no Redis
   - Envia webhook (se configurado)
```

### 4.3 Fluxo de Polling

```
1. Cliente faz GET /jobs/{job_id} a cada 5-10s
2. Verifica campo "status"
3. Se "completed" → GET /download/{job_id}
4. Se "failed" → verificar campo "error"
5. Se "queued"/"generating_*" → continuar polling
```

### 4.4 Fluxo de Webhook

```
1. Job completa ou falha
2. SE9 envia POST para webhook_url
3. Payload: {event, job_id, post_id, status, download_url, hashtags, duration}
4. Retry: 3 tentativas, backoff exponencial (2s, 4s, 8s)
```

---

## 5. Conversão make-video.json → API

### 5.1 Mapeamento de Campos

| Campo JSON | Campo API | Transformação |
|------------|-----------|---------------|
| `output.post_id` | `post_id` | Direto |
| `output.title` | `hook` | Direto |
| `output.total_duration_seconds` | `estimated_seconds` | Direto |
| `output.language` | `language` | Direto |
| `output.aspect_ratio` | `aspect_ratio` | Direto |
| `output.scenes[].narration_text` | `narration[].text` | `[{t: start_seconds, text}]` |
| `output.scenes[].start_seconds` | `narration[].t` | Direto |
| `output.scenes[].image.prompt` | `scene_suggestions[].visual` | Direto |
| `output.scenes[].image.negative_prompt` | `scene_suggestions[].negative_prompt` | Direto |
| `output.scenes[].motion.camera_movement` | `scene_suggestions[].camera_movement` | Mapear: "static"→"static", "slow_push_in"→"slow_push_in" |
| `output.scenes[].motion.transition` | `scene_suggestions[].transition` | Mapear: "corte seco"→null, "fade curto"→"fadeblack" |
| `output.scenes[].captions[].global_start_seconds` | `on_screen_text[].t` | Usar global (não local) |
| `output.scenes[].captions[].text` | `on_screen_text[].text` | Direto |
| `output.scenes[].captions[].global_end_seconds` | `on_screen_text[].end_seconds` | Usar global (não local) |
| `output.global_style` | `global_style` | Direto (metadata) |

### 5.2 Script de Conversão

```python
#!/usr/bin/env python3
"""Convert make-video.json → CreateVideoRequest for SE9 API."""
import json
import sys

TRANSITION_MAP = {
    "corte seco": None,
    "fade curto": "fadeblack",
    "fade": "fadefast",
    "dissolve": "dissolve",
}

CAMERA_MAP = {
    "static": "static",
    "slow_push_in": "slow_push_in",
    "slow_pull_out": "slow_pull_out",
}

def convert(input_path: str) -> dict:
    with open(input_path) as f:
        data = json.load(f)

    entry = data[0] if isinstance(data, list) else data
    output = entry["output"]

    narration = [{"t": s["start_seconds"], "text": s["narration_text"]}
                 for s in output["scenes"]]

    scene_suggestions = []
    for s in output["scenes"]:
        sug = {"t": s["start_seconds"], "visual": s["image"]["prompt"]}
        if s["image"].get("negative_prompt"):
            sug["negative_prompt"] = s["image"]["negative_prompt"]
        cam = s.get("motion", {}).get("camera_movement")
        if cam and cam in CAMERA_MAP:
            sug["camera_movement"] = CAMERA_MAP[cam]
        trans = s.get("motion", {}).get("transition")
        if trans and trans in TRANSITION_MAP and TRANSITION_MAP[trans]:
            sug["transition"] = TRANSITION_MAP[trans]
        scene_suggestions.append(sug)

    on_screen_text = []
    for s in output["scenes"]:
        for cap in s.get("captions", []):
            entry = {"t": cap["global_start_seconds"], "text": cap["text"]}
            if "global_end_seconds" in cap:
                entry["end_seconds"] = cap["global_end_seconds"]
            on_screen_text.append(entry)

    return {
        "post_id": output["post_id"],
        "hook": output["title"],
        "estimated_seconds": output["total_duration_seconds"],
        "language": output.get("language", "pt-BR"),
        "narration": narration,
        "scene_suggestions": scene_suggestions,
        "on_screen_text": on_screen_text,
        "voice_id": "builtin_feminino",
        "aspect_ratio": output.get("aspect_ratio", "9:16"),
        "zoom_style": "random",
        "global_style": output.get("global_style"),
    }

if __name__ == "__main__":
    print(json.dumps(convert(sys.argv[1]), indent=2, ensure_ascii=False))
```

---

## 6. Erros

### 6.1 Códigos de Erro HTTP

| Código | Significado | Quando |
|--------|-------------|--------|
| 400 | Bad Request | Job não está completed (download) |
| 401 | Unauthorized | API key ausente ou inválida |
| 404 | Not Found | Job não encontrado |
| 422 | Validation Error | Campos obrigatórios ausentes ou tipos inválidos |
| 500 | Internal Server Error | Erro interno |

### 6.2 Formato de Erro

```json
{
  "detail": "Job not found"
}
```

### 6.3 Erros Específicos do Pipeline

| Erro | Estágio | Causa | Ação |
|------|---------|-------|------|
| SE7 timeout | audio | TTS demorou >600s | Retry automático (3x) |
| SE7 job failed | audio | Modelo não carregou | Verificar VRAM, reiniciar SE7 |
| SE8 timeout | images | Fooocus demorou >300s | Retry automático (3x) |
| SE8 empty response | images | Prompt rejeitado | Verificar prompt |
| FFmpeg failed | assembly | Erro no ffmpeg | Verificar logs, disco |
| No images | assembly | 0 imagens geradas | Verificar SE8 |

---

## 7. Configuração

### 7.1 Variáveis de Ambiente (.env)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `REDIS_URL` | `redis://localhost:6379/9` | URL do Redis |
| `API_KEY` | `se9-test-key-2026` | API key para autenticação |
| `SE7_URL` | `http://localhost:8007` | URL do SE7 (TTS) |
| `SE7_API_KEY` | `se7-test-key-2026` | API key do SE7 |
| `SE8_URL` | `http://localhost:8008` | URL do SE8 (Fooocus) |
| `SE8_API_KEY` | `se8-test-key-2026` | API key do SE8 |
| `DEFAULT_VOICE_ID` | `builtin_feminino` | Voz TTS padrão |
| `DEFAULT_ASPECT_RATIO` | `9:16` | Proporção padrão |
| `DEFAULT_FPS` | `30` | FPS padrão |
| `DEFAULT_ZOOM_SPEED` | `0.004` | Velocidade do Ken Burns |
| `DEFAULT_CROSSFADE_DURATION` | `0.3` | Duração do crossfade (segundos) |
| `DEFAULT_IMAGE_STEPS` | `30` | Steps do Fooocus |
| `DEFAULT_IMAGE_PERFORMANCE` | `Quality` | Modo de performance do Fooocus |
| `TTS_EXAGGERATION` | `0.5` | Exagero do TTS (0-1) |
| `TTS_CFG_WEIGHT` | `0.5` | Peso CFG do TTS (0-1) |
| `TTS_TEMPERATURE` | `0.8` | Temperatura do TTS (0-1) |
| `SE7_TIMEOUT` | `600` | Timeout do SE7 (segundos) |
| `SE8_TIMEOUT` | `300` | Timeout do SE8 (segundos) |
| `FFMPEG_SEGMENT_TIMEOUT` | `60` | Timeout por segmento FFmpeg |
| `FFMPEG_TOTAL_TIMEOUT` | `300` | Timeout total FFmpeg |
| `TITLE_CARD_DURATION` | `0.5` | Duração do title card (segundos) |
| `EXTERNAL_URL` | `` | URL externa para webhooks |

### 7.2 Defaults de Vídeo

| Parâmetro | Valor | Efeito |
|-----------|-------|--------|
| Width | 1080 | Largura do vídeo |
| Height | 1920 | Altura do vídeo (9:16) |
| FPS | 30 | Frames por segundo |
| Zoom range | 1.0 → 1.20 | Amplitude do Ken Burns |
| Crossfade | 0.3s | Duração das transições |
| Image steps | 30 | Quality mode (60 internos) |
| Image performance | "Quality" | dpmpp_2m_ssd_gpu, karras |

---

## 8. Testes

### 8.1 Testes Unitários

```bash
cd /root/YTCaption-Easy-Youtube-API/services/se9-make-video-img
python -m pytest tests/unit/ -v
```

**Cobertura**: models, routes, admin_routes, download_routes, webhook, pipeline, worker, store, http_client, audio_chunking, video_assembler_srt.

### 8.2 Testes E2E

```bash
python -m pytest tests/e2e/ -v
```

**Nota**: Testes E2E requerem SE7 e SE8 rodando.

### 8.3 Teste Manual com make-video.json

```bash
# 1. Converter
python3 -c "
import json, sys
# ... (script de conversão da seção 5.2)
" make-video.json > /tmp/payload.json

# 2. Enviar
curl -X POST http://localhost:8009/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: se9-test-key-2026" \
  -d @/tmp/payload.json

# 3. Polling
curl http://localhost:8009/jobs/{job_id} \
  -H "X-API-Key: se9-test-key-2026"

# 4. Download
curl -O http://localhost:8009/download/{job_id} \
  -H "X-API-Key: se9-test-key-2026"
```

---

## 9. Arquitetura

### 9.1 Estrutura de Diretórios

```
app/
├── api/
│   ├── routes.py           # Jobs CRUD
│   ├── admin_routes.py     # Stats + cleanup
│   ├── download_routes.py  # Video download
│   ├── health_routes.py    # Health check
│   ├── webhook.py          # Webhook sender
│   └── schemas.py          # API schemas (request/response)
├── core/
│   ├── config.py           # Settings (MakeVideoImgSettings)
│   ├── constants.py        # Constants (transitions, aspect ratios)
│   └── models.py           # Domain models (VideoJob, StageInfo)
├── infrastructure/
│   ├── ffmpeg_utils.py     # FFmpeg commands
│   ├── http_client.py      # SE7/SE8 HTTP clients
│   └── redis_store.py      # Redis job store
├── services/
│   ├── pipeline.py         # Pipeline orchestrator
│   ├── audio_generator.py  # SE7 TTS wrapper
│   ├── image_generator.py  # SE8 Fooocus wrapper
│   └── video_assembler.py  # FFmpeg assembly
├── main.py                 # FastAPI app
└── worker.py               # Background worker
```

### 9.2 Dependências Upstream

| Serviço | Comunicação | Quando |
|---------|-------------|--------|
| SE7 (audio-generation) | HTTP REST | Stage 1: TTS |
| SE8 (image-generation) | HTTP REST | Stage 2: Fooocus |
| Redis | redis-py | Armazenamento de jobs |
| FFmpeg | subprocess | Stage 3: Assembly |

### 9.3 Worker

- **Tipo**: Thread daemon com event loop persistente
- **Polling**: A cada 2 segundos
- **Concorrência**: 1 job por vez (sequencial)
- **Lifecycle**: Auto-start no primeiro job, auto-stop quando não há jobs
