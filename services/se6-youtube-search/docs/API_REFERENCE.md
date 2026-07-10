# API Reference — SE6 YouTube Search

**Version:** 1.0.0  
**Base URL:** `http://localhost:8006`  
**Auth:** `X-API-Key` header  
**Job ID prefix:** `ys_`  
**Cache TTL:** 24h

---

## Fluxo Principal

```
1. POST /search/videos   → Criar job de busca
2. GET  /jobs/{id}/wait  → Aguardar conclusão (long-poll)
3. GET  /jobs/{id}/download → Baixar resultados (JSON)
```

---

## Enums

### `SearchType`

| Valor | Descrição |
|-------|-----------|
| `video_info` | Info de um vídeo |
| `channel_info` | Info de um canal |
| `playlist_info` | Info de uma playlist |
| `video` | Busca de vídeos |
| `related_videos` | Vídeos relacionados |
| `shorts` | Busca de Shorts |

### `JobStatus`

| Valor | Descrição |
|-------|-----------|
| `pending` | Estado inicial |
| `queued` | Na fila |
| `processing` | Processando |
| `completed` | Concluído |
| `failed` | Falhou |
| `cancelled` | Cancelado |

---

## Endpoints — Search

### `POST /search/video-info`

Info de um vídeo.

```bash
curl -X POST "http://localhost:8006/search/video-info?video_id=dQw4w9WgXcQ" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `video_id` | `str` | ✅ | ID do vídeo (11 chars) ou URL completa |

**Response:** `Job` com `search_type: "video_info"`

---

### `POST /search/channel-info`

Info de um canal.

```bash
curl -X POST "http://localhost:8006/search/channel-info?channel_id=UCuAXFkgsw1L7xaCfnd5JJOw&include_videos=true" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `channel_id` | `str` | ✅ | — | ID do canal (geralmente UC...) |
| `include_videos` | `bool` | ❌ | `false` | Incluir vídeos do canal |

---

### `POST /search/playlist-info`

Info de uma playlist.

```bash
curl -X POST "http://localhost:8006/search/playlist-info?playlist_id=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `playlist_id` | `str` | ✅ | ID da playlist |

---

### `POST /search/videos`

Busca de vídeos.

```bash
curl -X POST "http://localhost:8006/search/videos?query=python+tutorial&max_results=10" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `query` | `str` | ✅ | — | 1–500 chars | Texto de busca |
| `max_results` | `int` | ❌ | `10` | 1–50 | Máximo de resultados |

---

### `POST /search/related-videos`

Vídeos relacionados.

```bash
curl -X POST "http://localhost:8006/search/related-videos?video_id=dQw4w9WgXcQ&max_results=10" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `video_id` | `str` | ✅ | — | — | ID do vídeo base |
| `max_results` | `int` | ❌ | `10` | 1–50 | Máximo de resultados |

---

### `POST /search/shorts`

Busca de Shorts.

```bash
curl -X POST "http://localhost:8006/search/shorts?query=receita+rapida&max_results=10" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `query` | `str` | ✅ | — | — | Texto de busca |
| `max_results` | `int` | ❌ | `10` | 1–50 | Máximo de Shorts |

---

## Endpoints — Jobs

### `GET /jobs/{job_id}`

Status do job.

```bash
curl "http://localhost:8006/jobs/ys_abc123def456" -H "X-API-Key: your-api-key"
```

**Response `Job`:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | ID do job |
| `status` | `JobStatus` | Status |
| `search_type` | `SearchType` | Tipo de busca |
| `query` | `str\|null` | Query de busca |
| `video_id` | `str\|null` | ID do vídeo |
| `channel_id` | `str\|null` | ID do canal |
| `playlist_id` | `str\|null` | ID da playlist |
| `max_results` | `int` | Máximo de resultados |
| `result` | `dict\|null` | Dados do resultado |
| `progress` | `float` | Progresso (0–100) |
| `error_message` | `str\|null` | Erro |
| `created_at` | `datetime` | Criação |
| `completed_at` | `datetime\|null` | Conclusão |
| `expires_at` | `datetime\|null` | Expiração |

**Erros:** 404

---

### `GET /jobs/{job_id}/wait`

Long-poll. Aguarda conclusão.

```bash
curl "http://localhost:8006/jobs/ys_abc123def456/wait?timeout=600" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Constraints | Descrição |
|-------|------|---------|-------------|-----------|
| `timeout` | `int` | `600` | 1–3600 | Timeout (s) |

**Erros:** 404, 408 (timeout), 503, 500

---

### `GET /jobs/`

Lista jobs.

```bash
curl "http://localhost:8006/jobs/?limit=50" -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Constraints | Descrição |
|-------|------|---------|-------------|-----------|
| `limit` | `int` | `50` | 1–200 | Máximo de jobs |

---

### `DELETE /jobs/{job_id}`

Deleta job.

```bash
curl -X DELETE "http://localhost:8006/jobs/ys_abc123def456" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Resultado |
| `job_id` | `str` | ID removido |

---

### `GET /jobs/{job_id}/download`

Download dos resultados em JSON.

```bash
curl "http://localhost:8006/jobs/ys_abc123def456/download" \
  -H "X-API-Key: your-api-key" -o results.json
```

**Status:** 200 (JSON), 404, 410 (expirado), 425 (não pronto), 500

Filename: `youtube_search_{search_type}_{job_id}.json`

---

## Endpoints — Admin

### `POST /admin/cleanup`

```bash
curl -X POST "http://localhost:8006/admin/cleanup?deep=true&purge_celery_queue=true" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `deep` | `bool` | `false` | FLUSHDB Redis |
| `purge_celery_queue` | `bool` | `false` | Limpar fila Celery |

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jobs_removed` | `int` | Jobs removidos |
| `message` | `str` | Resumo |
| `redis_flushed` | `bool` | FLUSHDB? |
| `celery_queue_purged` | `bool` | Fila limpa? |
| `celery_tasks_purged` | `int` | Tasks removidas |

---

### `GET /admin/stats`

```bash
curl "http://localhost:8006/admin/stats" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_jobs` | `int` | Total de jobs |
| `by_status` | `dict` | Jobs por status |
| `celery` | `dict` | Stats do Celery |

---

### `GET /admin/queue`

```bash
curl "http://localhost:8006/admin/queue" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `is_running` | `bool` | Workers ativos? |
| `active_workers` | `int` | Workers ativos |
| `registered_tasks` | `list` | Tasks registradas |

---

### `GET /admin/metrics`

Prometheus metrics.

```bash
curl "http://localhost:8006/admin/metrics"
```

Métricas:
- `youtube_search_jobs_total{status="..."}` — gauge por status
- `youtube_search_jobs_store_total` — total de jobs

---

## Endpoints — Health

### `GET /health`

```bash
curl "http://localhost:8006/health"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `healthy` / `degraded` / `unhealthy` |
| `checks` | `dict` | Redis, disco, Celery, ytbpy |

---

## Variáveis de Ambiente

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `APP_NAME` | `str` | `"YouTube Search Service"` | Nome |
| `PORT` | `int` | `8006` | Porta |
| `REDIS_URL` | `str` | *(obrigatório)* | URL Redis |
| `API_KEY` | `str` | *(obrigatório)* | API key |
| `YOUTUBE_DEFAULT_TIMEOUT` | `int` | `10` | Timeout YouTube API |
| `YOUTUBE_MAX_RESULTS` | `int` | `50` | Máx resultados |
| `YOUTUBE_INNERTUBE_API_KEY` | `str` | *(default)* | InnerTube API key |
| `JOB_PROCESSING_TIMEOUT_SECONDS` | `int` | `300` | Timeout do job (5min) |
| `POLL_INTERVAL_SECONDS` | `int` | `2` | Polling interval |
| `CACHE_TTL_HOURS` | `int` | `24` | TTL do cache |

---

## Comportamento Assíncrono

Todos os endpoints `/search/*` seguem o mesmo padrão:
1. Cria `YouTubeSearchJob` com ID determinístico (`ys_` + SHA256)
2. Se job cached existe (completed/processing), retorna imediatamente
3. Senão, salva no Redis e submete ao Celery
4. Retorna job com status `"queued"`
5. Cliente faz polling em `GET /jobs/{id}` ou usa `GET /jobs/{id}/wait`

---

## Exemplo Completo

```bash
# 1. Buscar vídeos
curl -X POST "http://localhost:8006/search/videos?query=python+tutorial" \
  -H "X-API-Key: your-api-key"

# Response: {"id": "ys_abc123", "status": "queued", ...}

# 2. Aguardar conclusão
curl "http://localhost:8006/jobs/ys_abc123/wait?timeout=120" \
  -H "X-API-Key: your-api-key"

# 3. Download resultados
curl "http://localhost:8006/jobs/ys_abc123/download" \
  -H "X-API-Key: your-api-key" -o results.json
```
