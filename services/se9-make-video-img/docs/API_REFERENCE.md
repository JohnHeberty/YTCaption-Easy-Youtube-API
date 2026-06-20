# API Reference - SE9 Make Video IMG

**Versao:** 1.0.0 | **Base URL:** http://localhost:8009 | **Auth:** `X-API-Key: se9-test-key-2026`

## Fluxo principal

1. Criar: `POST /jobs` com payload do n8n
2. Consultar: `GET /jobs/{job_id}` (polling)
3. Download: `GET /download/{job_id}` quando status=`completed`

---

## POST /jobs

Criar job de geracao de video.

**Request:**
```json
{
  "post_id": "1q5o4zw",
  "hook": "No Reveillon, um papo que quase virou algo mais...",
  "estimated_seconds": 96,
  "language": "pt-BR",
  "narration": [
    {"t": 0, "text": "Eu vi a materia e fiquei perplexo..."},
    {"t": 8, "text": "O documento foi encontrado no fim de 2025..."}
  ],
  "scene_suggestions": [
    {"t": 0, "visual": "B-roll de arquivos antigos, fotos em preto e branco."},
    {"t": 8, "visual": "Imagem de uma estante de livros em um apartamento."}
  ],
  "on_screen_text": [
    {"t": 0, "text": "15 anos depois..."}
  ],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16",
  "zoom_style": "random"
}
```

**Response 201:**
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

**Campos obrigatorios:** `post_id`, `hook`, `estimated_seconds`, `narration`, `scene_suggestions`

**Campos opcionais:** `language` (default: pt-BR), `content_rating`, `on_screen_text`, `title_options`, `hashtags`, `safety_notes`, `voice_id` (default: builtin_feminino), `aspect_ratio` (default: 9:16), `zoom_style` (default: random), `webhook_url`

---

## GET /jobs/{job_id}

Consultar status do job.

**Response 200:**
```json
{
  "job_id": "rbg_a1b2c3d4e5f6",
  "status": "generating_audio",
  "progress": 25,
  "stages": {
    "generating_audio": {"status": "processing", "progress": 25},
    "generating_images": {"status": "pending", "progress": 0},
    "assembling_video": {"status": "pending", "progress": 0}
  },
  "created_at": "2026-06-19T15:00:00"
}
```

**Status possiveis:** `queued`, `generating_audio`, `generating_images`, `assembling_video`, `completed`, `failed`

---

## GET /jobs

Listar todos os jobs.

**Response 200:**
```json
[
  {
    "job_id": "rbg_a1b2c3d4e5f6",
    "post_id": "1q5o4zw",
    "status": "completed",
    "progress": 100,
    "created_at": "2026-06-19T15:00:00"
  }
]
```

---

## DELETE /jobs/{job_id}

Deletar job e seus arquivos.

**Response 200:** `{"message": "Job deleted"}`

---

## GET /download/{job_id}

Download do video MP4 final.

**Response 200:** `video/mp4` (FileResponse)

**Erros:**
- 404: Job nao encontrado
- 425: Video ainda nao pronto (status != completed)

---

## GET /health

Health check detalhado.

**Response 200:**
```json
{
  "status": "healthy",
  "service": "se9-make-video-img",
  "checks": {
    "se7": {"status": "ok"},
    "se8": {"status": "ok"},
    "disk": {"status": "ok"},
    "ffmpeg": {"status": "ok"}
  }
}
```

---

## GET /ping

Ping simples.

**Response 200:** `{"pong": true}`

---

## GET /admin/stats

Estatisticas do sistema.

**Response 200:** Contagem de jobs por status + uso de disco.

---

## POST /admin/cleanup

Limpar jobs com status `failed`.

**Response 200:** `{"message": "...", "removed": N}`
