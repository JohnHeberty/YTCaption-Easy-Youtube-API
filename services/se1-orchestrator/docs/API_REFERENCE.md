# API Reference — SE1 Orchestrator

**Version:** 1.0.0  
**Base URL:** `http://localhost:8001`  
**Auth:** `X-API-Key` header  
**Pipeline:** YouTube URL → SE2 (download) → SE3 (normalize) → SE4 (transcribe)

---

## Fluxo Principal

```
1. POST /process       → Iniciar pipeline
2. GET  /jobs/{id}     → Polling de status (5-10s)
3. GET  /jobs/{id}/stream → SSE progresso em tempo real
```

Ou aguardar conclusão:
```
1. POST /process       → Iniciar pipeline
2. GET  /jobs/{id}/wait → Aguardar conclusão (long-poll)
```

---

## Enums

### `PipelineStatus`

| Valor | Descrição |
|-------|-----------|
| `queued` | Job criado, aguardando início |
| `downloading` | Baixando vídeo do YouTube (SE2) |
| `normalizing` | Normalizando áudio (SE3) |
| `transcribing` | Transcrevendo áudio via Whisper (SE4) |
| `completed` | Pipeline concluído com sucesso |
| `failed` | Pipeline falhou |
| `cancelled` | Pipeline cancelado |

### `StageStatus`

| Valor | Descrição |
|-------|-----------|
| `pending` | Estágio não iniciado |
| `processing` | Estágio em execução |
| `completed` | Estágio concluído |
| `failed` | Estágio falhou |
| `skipped` | Estágio pulado |

---

## Endpoints — Health

### `GET /`

Service info.

```bash
curl http://localhost:8001/
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `service` | `str` | Nome do serviço |
| `version` | `str` | Versão |
| `status` | `str` | Estado do serviço |
| `endpoints` | `dict` | Principais endpoints |

---

### `GET /health`

Health check. Verifica Redis e microserviços.

```bash
curl http://localhost:8001/health
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `healthy` / `degraded` / `unhealthy` |
| `service` | `str` | Nome do serviço |
| `version` | `str` | Versão |
| `timestamp` | `datetime` | Timestamp da verificação |
| `microservices` | `dict` | Status dos microserviços |
| `uptime_seconds` | `float\|null` | Tempo de atividade (s) |
| `redis_connected` | `bool` | Redis conectado? |

**Lógica de status:**
- `healthy` — Redis OK E todos os microserviços saudáveis
- `degraded` — Redis OK mas pelo menos 1 microserviço unhealthy
- `unhealthy` — Falha na conexão Redis

---

## Endpoints — Pipeline

### `POST /process`

Inicia pipeline completo: download → normalização → transcrição.

```bash
curl -X POST "http://localhost:8001/process" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "pt",
    "remove_noise": true
  }'
```

| Campo | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `youtube_url` | `str` | ❌ | *(exemplo)* | URL do vídeo YouTube |
| `language` | `str\|null` | ❌ | `"auto"` | Idioma para transcrição (auto, pt, en, es, ...) |
| `language_out` | `str\|null` | ❌ | `null` | Idioma de saída para tradução |
| `remove_noise` | `bool\|null` | ❌ | `true` | Remover ruído de fundo |
| `convert_to_mono` | `bool\|null` | ❌ | `true` | Converter para mono |
| `apply_highpass_filter` | `bool\|null` | ❌ | `false` | Aplicar filtro passa-alta |
| `set_sample_rate_16k` | `bool\|null` | ❌ | `true` | Forçar 16kHz |

**Response 200:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID do job |
| `status` | `PipelineStatus` | Status inicial |
| `message` | `str` | Mensagem de orientação |
| `youtube_url` | `str` | URL recebida |
| `overall_progress` | `float` | Progresso (0.0–100.0) |

**Erros:** 422 (validação), 500 (criação), 503 (Redis indisponível)

---

## Endpoints — Jobs

### `GET /jobs`

Lista jobs recentes.

```bash
curl "http://localhost:8001/jobs?limit=50" -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `limit` | `int` | ❌ | `50` | 1–200 | Máximo de jobs |

**Response:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total` | `int` | Total de jobs |
| `jobs` | `list[JobSummary]` | Lista de jobs |

`JobSummary`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID do job |
| `youtube_url` | `str` | URL do vídeo |
| `status` | `str` | Status |
| `progress` | `float` | Progresso (0–100) |
| `created_at` | `datetime` | Criação |
| `updated_at` | `datetime` | Última atualização |

---

### `GET /jobs/{job_id}`

Status detalhado do job. Poll a cada 5-10 segundos.

```bash
curl "http://localhost:8001/jobs/abc123" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID do job |
| `youtube_url` | `str` | URL do vídeo |
| `status` | `PipelineStatus` | Status atual |
| `overall_progress` | `float` | Progresso geral (0–100) |
| `created_at` | `datetime` | Criação |
| `updated_at` | `datetime` | Última atualização |
| `completed_at` | `datetime\|null` | Conclusão |
| `stages` | `dict` | Detalhes por estágio |
| `transcription_text` | `str\|null` | Texto completo |
| `transcription_segments` | `list\|null` | Segmentos com timestamps |
| `transcription_file` | `str\|null` | Path do arquivo de transcrição |
| `audio_file` | `str\|null` | Path do áudio normalizado |
| `error_message` | `str\|null` | Erro (se falhou) |

**Estágios em `stages`** (chaves: `download`, `normalization`, `transcription`):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `name` | `str` | Nome do estágio |
| `status` | `StageStatus` | Status |
| `progress` | `float` | Progresso (0–100) |
| `message` | `str` | Mensagem de progresso |

**Erros:** 404 (não encontrado), 500 (erro interno)

---

### `GET /jobs/{job_id}/wait`

Long-poll. Mantém conexão aberta até pipeline terminar.

```bash
curl "http://localhost:8001/jobs/abc123/wait?timeout=1800" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `timeout` | `int` | ❌ | `1800` | 1–7200 | Timeout em segundos |

**Response:** Mesmo que `GET /jobs/{job_id}`.

**Erros:** 404, 408 (timeout), 500

---

### `GET /jobs/{job_id}/stream`

SSE (Server-Sent Events) com progresso em tempo real.

```bash
curl "http://localhost:8001/jobs/abc123/stream?timeout=600" \
  -H "X-API-Key: your-api-key" \
  -H "Accept: text/event-stream"
```

| Query | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------|------|-------------|---------|-------------|-----------|
| `timeout` | `int` | ❌ | `600` | 1–7200 | Timeout do stream (s) |

**Eventos SSE:**

| Evento | Quando | Dados |
|--------|--------|-------|
| `connected` | Conexão estabelecida | `message`, `job_id` |
| `progress` | Mudança de progresso | `job_id`, `status`, `progress`, `stage`, `stages` |
| `completed` | Pipeline concluído | `job_id`, `status`, `progress`, `transcription_file`, `audio_file` |
| `error` | Pipeline falhou | `job_id`, `status`, `error` |
| `timeout` | Stream timeout | `job_id`, `error`, `message` |

**Exemplo:**
```
event: connected
data: {"message": "Conectado ao stream", "job_id": "abc123"}

event: progress
data: {"job_id": "abc123", "status": "downloading", "progress": 33.3, "stages": {"download": 100.0, "normalization": 0.0, "transcription": 0.0}}

event: completed
data: {"job_id": "abc123", "status": "completed", "progress": 100.0}
```

---

## Endpoints — Admin

### `GET /admin/stats`

Estatísticas do orchestrator.

```bash
curl "http://localhost:8001/admin/stats" -H "X-API-Key: your-api-key"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `orchestrator` | `dict` | Versão, ambiente |
| `redis` | `dict` | Métricas Redis |
| `settings` | `dict` | Configurações ativas |

---

### `POST /admin/cleanup`

Remove jobs antigos.

```bash
curl -X POST "http://localhost:8001/admin/cleanup?max_age_hours=24" \
  -H "X-API-Key: your-api-key"
```

| Query | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `max_age_hours` | `int\|null` | ❌ | `null` | Idade máxima (horas) |
| `deep` | `bool` | ❌ | `false` | Limpeza agressiva |
| `remove_logs` | `bool` | ❌ | `false` | Remover logs |

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Resumo |
| `jobs_removed` | `int` | Jobs removidos |
| `logs_cleaned` | `bool` | Logs limpos? |

---

### `POST /admin/factory-reset`

Reset destrutivo de todo o pipeline.

```bash
curl -X POST "http://localhost:8001/admin/factory-reset" \
  -H "X-API-Key: your-api-key"
```

**⚠️ Destrutivo:** FLUSHDB Redis, remove logs, chama cleanup em SE2/SE3/SE4.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Resumo |
| `orchestrator` | `dict` | Resultado local (jobs_removed, redis_flushed, logs_cleaned) |
| `microservices` | `dict` | Resultado por microserviço |
| `warning` | `str` | Aviso de impacto |

**Microserviços chamados:**
- SE2: `POST /admin/cleanup?deep=true&purge_celery_queue=true`
- SE3: `POST /admin/cleanup?deep=true&purge_celery_queue=true`
- SE4: `POST /admin/cleanup?deep=true&purge_celery_queue=true`

---

## Error Response

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [...]
}
```

| Formato | Status | Exemplo |
|---------|--------|---------|
| Validação | 422 | `{"error": "VALIDATION_ERROR", "details": [...]}` |
| HTTP | 400/404/408/500/503 | `{"error": "HTTP_ERROR", "message": "...", "status_code": 404}` |
| Interno | 500 | `{"error": "INTERNAL_ERROR", "message": "..."}` |

---

## Variáveis de Ambiente

### URLs dos Microserviços (obrigatórias)

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `VIDEO_DOWNLOADER_URL` | `str` | *(obrigatório)* | URL do SE2 |
| `AUDIO_NORMALIZATION_URL` | `str` | *(obrigatório)* | URL do SE3 |
| `AUDIO_TRANSCRIBER_URL` | `str` | *(obrigatório)* | URL do SE4 |

### Timeouts HTTP (segundos)

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `VIDEO_DOWNLOADER_TIMEOUT` | `int` | `300` | Timeout HTTP SE2 |
| `AUDIO_NORMALIZATION_TIMEOUT` | `int` | `180` | Timeout HTTP SE3 |
| `AUDIO_TRANSCRIBER_TIMEOUT` | `int` | `600` | Timeout HTTP SE4 |

### Job Polling (segundos)

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `VIDEO_DOWNLOADER_JOB_TIMEOUT` | `int` | `1800` | Polling timeout SE2 |
| `AUDIO_NORMALIZATION_JOB_TIMEOUT` | `int` | `3600` | Polling timeout SE3 |
| `AUDIO_TRANSCRIBER_JOB_TIMEOUT` | `int` | `2400` | Polling timeout SE4 |
| `POLL_INTERVAL_INITIAL` | `float` | `2.0` | Intervalo inicial |
| `POLL_INTERVAL_MAX` | `float` | `30.0` | Intervalo máximo |
| `MAX_POLL_ATTEMPTS` | `int` | `300` | Máximo de tentativas |

### Retry & Circuit Breaker

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `MICROSERVICE_MAX_RETRIES` | `int` | `3` | Retries por request |
| `MICROSERVICE_RETRY_DELAY` | `float` | `2.0` | Delay entre retries |
| `CIRCUIT_BREAKER_MAX_FAILURES` | `int` | `10` | Falhas antes de abrir |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `int` | `20` | Timeout de recuperação |

### Parâmetros de Áudio

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `DEFAULT_LANGUAGE` | `str` | `"auto"` | Idioma default |
| `DEFAULT_REMOVE_NOISE` | `bool` | `true` | Remover ruído |
| `DEFAULT_CONVERT_MONO` | `bool` | `true` | Converter mono |
| `DEFAULT_HIGHPASS_FILTER` | `bool` | `false` | Filtro passa-alta |
| `DEFAULT_SAMPLE_RATE_16K` | `bool` | `true` | 16kHz |

### Base

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `APP_NAME` | `str` | `"youtube-caption-orchestrator"` | Nome |
| `PORT` | `int` | `8001` | Porta |
| `REDIS_URL` | `str` | *(obrigatório)* | URL Redis |
| `API_KEY` | `str` | *(obrigatório)* | API key |
| `CACHE_TTL_HOURS` | `int` | `24` | TTL do cache |
| `JOB_TIMEOUT_MINUTES` | `int` | `60` | Timeout do job |

---

## Exemplo Completo — E2E

```bash
# 1. Iniciar pipeline
curl -X POST "http://localhost:8001/process" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "language": "pt"}'

# Response: {"job_id": "abc123", "status": "queued", ...}

# 2. Poll status
while true; do
  STATUS=$(curl -s "http://localhost:8001/jobs/abc123" \
    -H "X-API-Key: your-api-key" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done

# 3. Get transcription
curl "http://localhost:8001/jobs/abc123" \
  -H "X-API-Key: your-api-key" | jq '.transcription_text'
```
