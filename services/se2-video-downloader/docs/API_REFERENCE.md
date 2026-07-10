# API Reference — SE2 Video Downloader

**Version:** 3.0.0  
**Base URL:** `http://localhost:8002`  
**Auth:** `X-API-Key` header  
**Job ID prefix:** `vd_`  
**Cache TTL:** 24h

---

## Fluxo Principal

```
1. POST /jobs           → Criar job de download
2. GET  /jobs/{id}      → Polling de status
3. GET  /jobs/{id}/download → Baixar vídeo
```

---

## Enums

### `VideoQuality`

| Valor | Descrição |
|-------|-----------|
| `best` | Melhor qualidade (MP4 progressive) |
| `worst` | Pior qualidade |
| `720p` | Máximo 720p |
| `480p` | Máximo 480p |
| `360p` | Máximo 360p |
| `audio` | Apenas áudio (Opus) |

### `JobStatus`

| Valor | Descrição |
|-------|-----------|
| `pending` | Estado inicial |
| `queued` | Na fila |
| `processing` | Processando |
| `completed` | Concluído |
| `failed` | Falhou |

---

## Endpoints — Jobs

### `POST /jobs`

Cria job de download.

```bash
curl -X POST "http://localhost:8002/jobs" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720p"}'
```

| Campo | Tipo | Obrigatório | Default | Valores | Descrição |
|-------|------|-------------|---------|---------|-----------|
| `url` | `str` | ✅ | — | — | URL do vídeo YouTube (5–2000 chars) |
| `quality` | `str` | ❌ | `"best"` | `best` / `worst` / `720p` / `480p` / `360p` / `audio` | Qualidade desejada |

**Response 201:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | ID do job |
| `status` | `JobStatus` | Status inicial |
| `url` | `str` | URL alvo |
| `quality` | `str` | Qualidade aplicada |
| `progress` | `float` | Progresso (0–100) |
| `created_at` | `datetime` | Criação |
| `expires_at` | `datetime` | Expiração do cache |

**Comportamento:**
- Se job com mesmo ID já existe (completed/queued/processing), retorna existente
- Se job falhou, é re-enfileirado
- Job ID determinístico: `vd_` + SHA256(video_id + quality)

---

### `GET /jobs/{job_id}`

Status detalhado do job.

```bash
curl "http://localhost:8002/jobs/vd_abc123" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | ID do job |
| `status` | `JobStatus` | Status |
| `progress` | `float` | Progresso (0–100) |
| `progress_message` | `str\|null` | Mensagem de progresso |
| `url` | `str` | URL do vídeo |
| `quality` | `str` | Qualidade |
| `filename` | `str\|null` | Nome do arquivo |
| `file_path` | `str\|null` | Path do arquivo |
| `file_size` | `int\|null` | Tamanho (bytes) |
| `created_at` | `datetime` | Criação |
| `started_at` | `datetime\|null` | Início |
| `completed_at` | `datetime\|null` | Conclusão |
| `expires_at` | `datetime` | Expiração |
| `error_message` | `str\|null` | Erro |
| `error_type` | `str\|null` | Tipo do erro |
| `retry_count` | `int` | Tentativas |

**Erros:** 404, 410 (expirado)

---

### `GET /jobs/{job_id}/download`

Baixa arquivo do vídeo.

```bash
curl "http://localhost:8002/jobs/vd_abc123/download" \
  -H "X-API-Key: your-api-key" -o video.mp4
```

**Status:** 200 (file), 404, 410 (expirado), 425 (não pronto)

---

### `GET /jobs`

Lista jobs.

```bash
curl "http://localhost:8002/jobs?limit=20" -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Constraints | Descrição |
|-------|------|---------|-------------|-----------|
| `limit` | `int` | `20` | 1–200 | Máximo de jobs |

---

### `DELETE /jobs/{job_id}`

Deleta job e arquivos.

```bash
curl -X DELETE "http://localhost:8002/jobs/vd_abc123" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Resultado |
| `job_id` | `str` | ID removido |
| `files_deleted` | `int` | Arquivos removidos |

---

### `GET /jobs/orphaned`

Detecta jobs órfãos (stuck > 30min).

```bash
curl "http://localhost:8002/jobs/orphaned?max_age_minutes=30" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `max_age_minutes` | `int` | `30` | Idade mínima |

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `"success"` |
| `count` | `int` | Jobs órfãos |
| `orphaned_jobs` | `list` | Lista de jobs |

Cada job órfão:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID |
| `status` | `str` | Status |
| `created_at` | `str` | Criação |
| `age_minutes` | `float` | Idade (min) |
| `url` | `str` | URL |

---

### `POST /jobs/orphaned/cleanup`

Limpa jobs órfãos.

```bash
curl -X POST "http://localhost:8002/jobs/orphaned/cleanup?mark_as_failed=true" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `max_age_minutes` | `int` | `30` | Idade mínima |
| `mark_as_failed` | `bool` | `true` | `true` = marcar failed, `false` = deletar |

---

## Endpoints — Admin

### `GET /admin/stats`

```bash
curl "http://localhost:8002/admin/stats" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_jobs` | `int` | Total de jobs |
| `by_status` | `dict` | Jobs por status |
| `cache` | `dict` | Métricas de cache |
| `celery` | `dict` | Estado do Celery |

---

### `GET /admin/queue`

```bash
curl "http://localhost:8002/admin/queue" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `"success"` |
| `queue` | `dict` | Info da fila Celery |

---

### `POST /admin/cleanup`

```bash
curl -X POST "http://localhost:8002/admin/cleanup?deep=true&purge_celery_queue=true" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `deep` | `bool` | `false` | Limpeza total (FLUSHDB) |
| `purge_celery_queue` | `bool` | `false` | Limpar fila Celery |

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jobs_removed` | `int` | Jobs removidos |
| `files_deleted` | `int` | Arquivos removidos |
| `space_freed_mb` | `float` | Espaço liberado (MB) |
| `redis_flushed` | `bool\|null` | FLUSHDB executado? |
| `celery_queue_purged` | `bool\|null` | Fila Celery limpa? |

---

### `POST /admin/fix-stuck-jobs`

Corrige jobs travados em `queued`.

```bash
curl -X POST "http://localhost:8002/admin/fix-stuck-jobs?max_age_minutes=30" \
  -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `fixed_count` | `int` | Jobs corrigidos |
| `max_age_minutes` | `int` | Idade mínima |
| `message` | `str` | Resumo |

---

## Endpoints — Health

### `GET /health`

```bash
curl "http://localhost:8002/health"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `healthy` / `degraded` / `unhealthy` |
| `service` | `str` | `"video-downloader"` |
| `checks` | `dict` | Redis, Celery worker, cache dir |

---

### `GET /metrics`

Prometheus metrics.

```bash
curl "http://localhost:8002/metrics"
```

Métricas:
- `video_downloader_jobs_total{status="..."}` — gauge por status
- `video_downloader_jobs_store_total` — total de jobs

---

### `GET /user-agents/stats`

Estatísticas dos User-Agents.

```bash
curl "http://localhost:8002/user-agents/stats" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_user_agents` | `int` | Total de UAs |
| `quarantined_count` | `int` | UAs em quarentena |
| `available_count` | `int` | UAs disponíveis |
| `average_quality` | `float` | Score médio (0–1) |

---

### `POST /user-agents/reset/{user_agent_id}`

Remove UA da quarentena.

```bash
curl -X POST "http://localhost:8002/user-agents/reset/Mozilla/5.0..." \
  -H "X-API-Key: your-api-key"
```

---

## Variáveis de Ambiente

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `APP_NAME` | `str` | `"Video Downloader Service"` | Nome |
| `PORT` | `int` | `8002` | Porta |
| `REDIS_URL` | `str` | *(obrigatório)* | URL Redis |
| `API_KEY` | `str` | *(obrigatório)* | API key |
| `CACHE_TTL_HOURS` | `int` | `24` | TTL do cache |
| `MAX_FILE_SIZE_MB` | `int` | `10240` | Máx upload (10GB) |
| `MAX_CONCURRENT_DOWNLOADS` | `int` | `2` | Downloads paralelos |
| `DEFAULT_QUALITY` | `str` | `"best"` | Qualidade default |
| `JOB_PROCESSING_TIMEOUT_SECONDS` | `int` | `1800` | Timeout do job (30min) |
| `CACHE_DIR` | `str` | `"./data/cache"` | Diretório de cache |
| `DOWNLOADS_DIR` | `str` | `"./data/downloads"` | Diretório de downloads |

---

## Exemplo Completo

```bash
# 1. Criar download
curl -X POST "http://localhost:8002/jobs" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720p"}'

# 2. Poll
curl "http://localhost:8002/jobs/vd_abc123" -H "X-API-Key: your-api-key"

# 3. Download
curl "http://localhost:8002/jobs/vd_abc123/download" \
  -H "X-API-Key: your-api-key" -o video.mp4
```
