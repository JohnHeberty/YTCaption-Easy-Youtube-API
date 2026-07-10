# API Reference — SE3 Audio Normalization

**Version:** 2.0.0  
**Base URL:** `http://localhost:8003`  
**Auth:** `X-API-Key` header  
**Job ID prefix:** `an_`  
**Output:** Sempre `.webm` (codec: libopus, bitrate: 128k)

---

## Fluxo Principal

```
1. POST /jobs           → Criar job de normalização
2. GET  /jobs/{id}      → Polling de status
3. GET  /jobs/{id}/download → Baixar áudio normalizado
```

---

## Formatos Suportados

**Entrada (áudio):** mp3, wav, m4a, ogg, flac, aac, wma, opus, webm  
**Entrada (vídeo):** mp4, avi, mov, mkv, flv, wmv, webm, m4v  
**Saída:** Sempre `.webm` (libopus 128k)

---

## Enums

### `JobStatus`

| Valor | Descrição |
|-------|-----------|
| `pending` | Estado inicial |
| `queued` | Na fila |
| `processing` | Processando |
| `completed` | Concluído |
| `failed` | Falhou |
| `cancelled` | Cancelado |

### `StageStatus`

| Valor | Descrição |
|-------|-----------|
| `pending` | Não iniciado |
| `processing` | Em execução |
| `completed` | Concluído |
| `failed` | Falhou |
| `skipped` | Pulado |
| `waiting_retry` | Aguardando retry |

---

## Endpoints — Jobs

### `POST /jobs`

Cria job de normalização de áudio.

```bash
curl -X POST "http://localhost:8003/jobs" \
  -H "X-API-Key: your-api-key" \
  -F "file=@audio.mp3" \
  -F "remove_noise=true" \
  -F "convert_to_mono=true"
```

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Obrigatório | Default | Valores | Descrição |
|-------|------|-------------|---------|---------|-----------|
| `file` | `UploadFile` | ✅ | — | mp3, wav, m4a, ogg, flac, mp4, etc. | Arquivo de áudio/vídeo |
| `remove_noise` | `str` | ❌ | `"false"` | `true/false/1/0/yes/no/on/off` | Redução de ruído |
| `convert_to_mono` | `str` | ❌ | `"false"` | `true/false/1/0/yes/no/on/off` | Converter para mono |
| `apply_highpass_filter` | `str` | ❌ | `"false"` | `true/false/1/0/yes/no/on/off` | Filtro passa-alta |
| `set_sample_rate_16k` | `str` | ❌ | `"false"` | `true/false/1/0/yes/no/on/off` | Sample rate 16kHz |
| `isolate_vocals` | `str` | ❌ | `"false"` | `true/false/1/0/yes/no/on/off` | Isolar vocais (demucs) |

**Response 200:** `AudioNormJob` (ver abaixo)

**Comportamento:**
- Se job cached existe, retorna sem reprocessar
- Jobs órfãos/failed são re-enfileirados
- Submissão via Celery, fallback para processamento direto

**Erros:** 400 (validação), 413 (arquivo grande), 415 (formato inválido), 500, 503 (Redis)

---

### `GET /jobs/{job_id}`

Status detalhado.

```bash
curl "http://localhost:8003/jobs/an_abc123" -H "X-API-Key: your-api-key"
```

**Response `AudioNormJob`:**

Campos herdados de `StandardJob`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | ID do job |
| `status` | `JobStatus` | Status |
| `progress` | `float` | Progresso (0–100) |
| `progress_message` | `str\|null` | Mensagem de progresso |
| `created_at` | `datetime` | Criação |
| `started_at` | `datetime\|null` | Início |
| `completed_at` | `datetime\|null` | Conclusão |
| `expires_at` | `datetime` | Expiração |
| `error_message` | `str\|null` | Erro |
| `stages` | `dict` | Estágios |

Campos SE3:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `input_file` | `str\|null` | Path do arquivo de entrada |
| `output_file` | `str\|null` | Path do arquivo processado |
| `filename` | `str\|null` | Nome original |
| `file_size_input` | `int\|null` | Tamanho entrada (bytes) |
| `file_size_output` | `int\|null` | Tamanho saída (bytes) |
| `remove_noise` | `bool` | Ruído removido? |
| `convert_to_mono` | `bool` | Mono? |
| `apply_highpass_filter` | `bool` | Passa-alta? |
| `set_sample_rate_16k` | `bool` | 16kHz? |
| `isolate_vocals` | `bool` | Vocais isolados? |

**Erros:** 400 (ID inválido), 404, 410 (expirado), 500

---

### `GET /jobs/{job_id}/download`

Baixa áudio processado.

```bash
curl "http://localhost:8003/jobs/an_abc123/download" \
  -H "X-API-Key: your-api-key" -o normalized.webm
```

**Status:** 200 (file), 400 (ID inválido), 404, 410, 425 (não pronto)

Filename: `normalized_{job_id}.webm`

---

### `GET /jobs`

Lista jobs recentes.

```bash
curl "http://localhost:8003/jobs?limit=20" -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Constraints | Descrição |
|-------|------|---------|-------------|-----------|
| `limit` | `int` | `20` | 1–200 | Máximo de jobs |

---

### `DELETE /jobs/{job_id}`

Remove job e arquivos.

```bash
curl -X DELETE "http://localhost:8003/jobs/an_abc123" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Resultado |
| `job_id` | `str` | ID removido |
| `files_deleted` | `int` | Arquivos removidos |

---

### `POST /jobs/{job_id}/heartbeat`

Atualiza heartbeat do job (para detecção de órfãos).

```bash
curl -X POST "http://localhost:8003/jobs/an_abc123/heartbeat" \
  -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | ID do job |
| `status` | `str` | `"ok"` |
| `last_heartbeat` | `str\|null` | Timestamp ISO 8601 |

---

## Endpoints — Admin

### `GET /admin/stats`

```bash
curl "http://localhost:8003/admin/stats" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_jobs` | `int` | Total de jobs |
| `by_status` | `dict` | Jobs por status |
| `cache` | `dict` | Métricas de cache |

---

### `GET /admin/queue`

```bash
curl "http://localhost:8003/admin/queue" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `"success"` |
| `queue` | `dict` | Info da fila |

---

### `POST /admin/cleanup`

```bash
curl -X POST "http://localhost:8003/admin/cleanup?deep=true" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `deep` | `bool` | `false` | FLUSHDB Redis |

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jobs_removed` | `int` | Jobs removidos |
| `files_deleted` | `int` | Arquivos removidos |
| `space_freed_mb` | `float` | Espaço liberado (MB) |
| `redis_flushed` | `bool\|null` | FLUSHDB? |
| `message` | `str\|null` | Resumo |

---

## Endpoints — Health

### `GET /health`

```bash
curl "http://localhost:8003/health"
```

Verifica: Redis, espaço em disco, FFmpeg.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `healthy` / `degraded` / `unhealthy` |
| `checks` | `dict` | Redis, disco, FFmpeg |

**Thresholds de disco:**
- Error: ≤5% livre
- Warning: ≤10% livre

---

### `GET /metrics`

Prometheus metrics.

```bash
curl "http://localhost:8003/metrics"
```

Métricas:
- `audio_normalization_jobs_total{status="..."}` — gauge por status
- `audio_normalization_jobs_store_total` — total de jobs

---

## Variáveis de Ambiente

### Processamento de Áudio

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `AUDIO_ENABLE_CHUNKING` | `bool` | `true` | Habilitar chunking |
| `AUDIO_CHUNK_SIZE_MB` | `int` | `30` | Tamanho do chunk (MB) |
| `AUDIO_CHUNK_DURATION_SEC` | `int` | `60` | Duração do chunk (s) |
| `NOISE_REDUCTION_MAX_DURATION_SEC` | `int` | `300` | Máx duração p/ noise reduction |
| `VOCAL_ISOLATION_MAX_DURATION_SEC` | `int` | `180` | Máx duração p/ isolamento vocal |

### FFmpeg

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `FFMPEG_THREADS` | `int` | `0` | Threads (0=auto) |
| `FFMPEG_PRESET` | `str` | `"medium"` | Preset de encoding |
| `FFMPEG_AUDIO_CODEC` | `str` | `"libopus"` | Codec de saída |
| `FFMPEG_AUDIO_BITRATE` | `str` | `"128k"` | Bitrate |

### Base

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `APP_NAME` | `str` | `"Audio Normalization Service"` | Nome |
| `PORT` | `int` | `8003` | Porta |
| `REDIS_URL` | `str` | *(obrigatório)* | URL Redis |
| `API_KEY` | `str` | *(obrigatório)* | API key |
| `MAX_FILE_SIZE_MB` | `int` | `2048` | Máx upload (MB) |
| `MAX_DURATION_MINUTES` | `int` | `120` | Máx duração (min) |
| `UPLOAD_DIR` | `str` | `"./data/uploads"` | Dir uploads |
| `PROCESSED_DIR` | `str` | `"./data/processed"` | Dir processados |

---

## Exemplo Completo

```bash
# 1. Normalizar áudio
curl -X POST "http://localhost:8003/jobs" \
  -H "X-API-Key: your-api-key" \
  -F "file=@podcast.mp3" \
  -F "remove_noise=true" \
  -F "convert_to_mono=true" \
  -F "set_sample_rate_16k=true"

# 2. Poll
curl "http://localhost:8003/jobs/an_abc123" -H "X-API-Key: your-api-key"

# 3. Download
curl "http://localhost:8003/jobs/an_abc123/download" \
  -H "X-API-Key: your-api-key" -o normalized.webm
```
