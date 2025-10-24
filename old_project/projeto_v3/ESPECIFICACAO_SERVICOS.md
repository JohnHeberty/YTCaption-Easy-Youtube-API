# ESPECIFICAÇÃO DE SERVIÇOS

## API Gateway (Port 8000)

### Responsabilidades
- Roteamento HTTP para micro-serviços
- Autenticação (JWT)
- Rate limiting global
- Request tracing
- Aggregation de respostas

### Endpoints

```
POST   /api/v1/auth/login              → Gera JWT
POST   /api/v1/jobs                    → Cria job
GET    /api/v1/jobs/{job_id}           → Status
GET    /api/v1/jobs/{job_id}/results   → Resultado
GET    /api/v1/admin/users             → Admin only
GET    /health/live                    → Liveness
GET    /health/ready                   → Readiness
```

### Request/Response

**POST /api/v1/jobs**:
```json
Request:
{
  "url": "https://youtube.com/watch?v=xxx",
  "language": "pt-BR",
  "idempotency_key": "abc123def456"
}

Response 202 (Accepted):
{
  "job_id": "job-abc123",
  "status": "queued",
  "created_at": "2025-10-23T10:30:45Z"
}
```

### Rate Limiting

```
Global:    10k req/min (sliding window)
Per-user:  100 req/min
Per-IP:    1k req/min

Response 429: Retry-After header incluído
```

### Circuit Breaker

```
Dependency     Fail Max  Reset Timeout
─────────────────────────────────────
job-manager    5         60s
downloader     5         60s
transcriber    5         60s
storage        5         60s
notifier       5         60s
admin          5         60s
```

---

## Job Manager (Port 8001)

### Responsabilidades
- State machine de jobs
- Saga orchestration (retry job inteiro se falhar)
- Idempotency
- Long-polling support

### State Machine

```
NEW ─→ QUEUED ─→ PROCESSING ─→ COMPLETED
         ↓                        ↑
         └──→ FAILED (→ RETRY) ──┘
```

**Transições**:
- NEW → QUEUED: Imediato (validação OK)
- QUEUED → PROCESSING: Download start
- PROCESSING → COMPLETED: Transcrição OK
- Qualquer → FAILED: Erro não-retryable

### Saga Pattern

```
1. Create job (job-manager)
2. Publish jobs.created → download service
3. Download falha? 
   - Retry 3x (exponential backoff)
   - Falha permanente? → Mark job FAILED
   - Compensate: Nada a fazer (job deletável)
4. Download completa?
   - Publish jobs.transcribe
5. Transcribe falha?
   - Retry 3x
   - Falha? → Mark job FAILED
   - Compensate: Deletar arquivo storage
6. Transcribe completa?
   - Publish jobs.completed
   - Mark job COMPLETED
```

### Idempotency

```
Key: hash(user_id + request_id + endpoint)
TTL: 24 horas
Lookup: Antes de processar
Response: Mesma resposta anterior (não duplica)
```

### Database Schema

```sql
jobs (
  id UUID PRIMARY KEY,
  user_id UUID,
  url VARCHAR NOT NULL,
  status VARCHAR(20),
  idempotency_key VARCHAR(256),
  result_summary TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  completed_at TIMESTAMP,
  INDEX (user_id, status),
  INDEX (created_at)
);

job_events (
  id BIGSERIAL PRIMARY KEY,
  job_id UUID,
  event_type VARCHAR(50),
  payload JSON,
  created_at TIMESTAMP,
  INDEX (job_id, created_at)
);
```

### Long Polling

```
GET /api/v1/jobs/{job_id}?wait=true&timeout=60s

Bloqueia até:
- Job mudar de status (polling 100ms)
- Timeout 60s (return atual status)
```

### Retry Logic

```
Tentar 1: Imediato
Tentar 2: +1s
Tentar 3: +3s
Tentar 4: +7s
Total max: ~12s, depois FAILED
```

---

## Downloader (Port 8002)

### Responsabilidades
- Download de vídeos YouTube
- Chunk management (quebra em 50MB)
- Mux vídeo + audio
- Estima tempo

### Algorithm

```
1. Resolve URL → Get metadata (title, duration, quality)
2. Estima tempo: duration_seconds * 0.1 (heurística)
3. Select quality: 1080p ou lower se fail
4. Download video stream
5. Download audio stream
6. Mux → ffmpeg (3 tentativas)
7. Split em chunks 50MB (opcional, para resumable upload)
8. Upload para storage
9. Publish jobs.transcribe
```

### Circuit Breaker (YouTube API)

```
Fail max: 5
Reset: 60s
Fail condition: Timeout > 30s OR HTTP 5xx

Back-off: 1s, 2s, 4s, 8s, 16s
```

### Parallel Downloads

```
Max 10 parallel
Quota: 5 req/s YouTube
Queue: FIFO priority

High priority: < 30min
Normal: 30-120min
Low: > 120min
```

### Timeout Handling

```
Total timeout: 30m (por vídeo)
Segment timeout: 5m (por chunk)

Se timeout: Retry 1x completo, depois FAILED
```

### Storage Upload

```
multipart_upload:
  - Chunk size: 100MB
  - Retry: 3x
  - Timeout: 5m por chunk
  
Metadata:
  {
    "job_id": "job-xxx",
    "original_url": "youtube.com/...",
    "duration_seconds": 3600,
    "file_size_bytes": 1073741824,
    "chunks": 3,
    "uploaded_at": "2025-10-23T10:30:45Z"
  }
```

---

## Transcriber (Port 8003)

### Responsabilidades
- Transcrição de audio → texto
- Suporta múltiplos idiomas
- Model caching
- Parallel processing

### Model Management

```
Load model: whisper-large (1.4GB RAM)
Cache em memória: Reuse 100+ vezes
TTL: Até service shutdown
Fallback: whisper-base se memória < 500MB
```

### Processing Pipeline

```
1. Download audio do storage
2. Split em segmentos 30s (whisper limit)
3. Transcrever paralelo (4 workers max)
4. Agregar transcripts
5. Post-process: Capitalize, punctuation
6. Upload transcript
7. Publish jobs.completed
```

### Worker Pool

```
Workers: 4 (CPU-bound)
Queue: In-memory (não RabbitMQ, já é distribuído)
Timeout: 5m (por arquivo)
Retry: 2x (timeout não é retryable)
```

### Language Support

```
pt-BR, en-US, es-ES, fr-FR, de-DE
Default: Auto-detect
```

### Output Format

```json
{
  "job_id": "job-xxx",
  "transcript": "Olá mundo...",
  "segments": [
    {
      "id": 0,
      "start_time": "00:00:00",
      "end_time": "00:00:05",
      "text": "Olá"
    }
  ],
  "confidence": 0.92,
  "language_detected": "pt-BR"
}
```

---

## Storage (Port 8004)

### Responsabilidades
- S3-compatible storage (MinIO ou AWS S3)
- Multipart upload
- Versioning
- Replication

### Bucket Structure

```
ytcaption-prod/
├── videos/{job_id}/
│   ├── original.mp4
│   ├── metadata.json
│   └── chunks/
│       ├── chunk-000
│       ├── chunk-001
│       └── chunk-002
├── transcripts/{job_id}/
│   ├── transcript.json
│   └── segments.json
└── temp/
    └── (cleanup 24h auto)
```

### Replication

```
Primary: AZ-1
Replica: AZ-2 (sync replication)

Cross-region: Optional (us-east + eu-west)
Failover: Automatic DNS switch
```

### Lifecycle Policies

```
Videos:       Keep 90 days, then glacier
Transcripts:  Keep forever
Temp:         Auto-delete 24h
```

### Multipart Upload

```
Chunk size: 100MB
Retry: 3x
Timeout: 5m per chunk
Resume: Supported (ETag validation)
```

### API

```
PUT   /storage/upload/{job_id}
GET   /storage/download/{job_id}
DELETE /storage/{job_id}
HEAD  /storage/{job_id}        (metadata)
```

---

## Notifier (Port 8005)

### Responsabilidades
- Email notifications
- Webhook dispatching
- Push notifications
- Deduplication

### Events

```
job.completed  → Email to user
job.failed     → Email + admin alert
               → Webhook (if defined)
```

### Deduplication

```
Key: hash(user_id + job_id + event_type)
TTL: 1 hour
Prevent duplicate notifications
```

### Email Template

```
Subject: Seu vídeo foi transcrito!
Body:
  Olá {user_name},
  
  O vídeo foi transcrito com sucesso.
  Clique aqui para visualizar: {results_url}
  
  Confiança: {confidence}%
  Idioma: {language}
  
  YTCaption Team
```

### Webhook

```
POST {user_webhook_url}
Body:
{
  "event": "job.completed",
  "job_id": "job-xxx",
  "status": "completed",
  "results_url": "...",
  "timestamp": "2025-10-23T10:30:45Z"
}

Retry: 3x (exponential backoff)
Timeout: 10s
```

### Queue-based Processing

```
Subscribe: jobs.completed queue
Batch size: 10 emails/batch
Delay: 0-5s random (prevent thundering herd)
```

---

## Admin (Port 8006)

### Responsabilidades
- User management
- Quota management
- Reports & analytics
- Audit logs

### Endpoints (RBAC)

```
GET    /admin/users              (admin only)
POST   /admin/users              (admin only)
PUT    /admin/users/{user_id}    (admin only)

GET    /admin/quotas/{user_id}   (manager+)
PUT    /admin/quotas/{user_id}   (admin only)

GET    /admin/reports            (manager+)
GET    /admin/audit-log          (admin only)

GET    /health/live              (all)
GET    /health/ready             (all)
```

### User Schema

```sql
users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE,
  name VARCHAR(255),
  role VARCHAR(20),  -- admin, manager, viewer
  quota_monthly INT DEFAULT 100,
  quota_used INT DEFAULT 0,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

audit_log (
  id BIGSERIAL PRIMARY KEY,
  admin_id UUID,
  action VARCHAR(50),
  resource VARCHAR(50),
  resource_id UUID,
  changes JSON,
  created_at TIMESTAMP,
  INDEX (admin_id, created_at)
);
```

### Quota Management

```
Monthly quota: 100 jobs/month (default)
Used: Incremented on job completion
Reset: 1st of every month
Overage: User cannot create new job
```

### Reporting

```
GET /admin/reports?period=month&user_id=xxx

Response:
{
  "jobs_total": 45,
  "jobs_successful": 43,
  "jobs_failed": 2,
  "total_duration": 36000,
  "avg_duration": 800,
  "storage_used_gb": 150,
  "errors": [
    {
      "count": 5,
      "error_type": "network_timeout"
    }
  ]
}
```

---

**Próximo**: Leia `CONFIGURACAO_RESILIENCIA.md`
