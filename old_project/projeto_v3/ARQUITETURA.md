# ARQUITETURA v2.0 - Design Decisions

## 1. Visão Geral

**Objetivo**: Transformar monólito em 7 micro-serviços resilientes, escaláveis e observáveis.

**Drivers Arquiteturais**:
- Escalabilidade: Suportar 10k+ req/s (vs 100 req/s atual)
- Resiliência: 99.9% uptime (vs 95% atual)
- Latência: 50ms p95 (vs 3-5 min atual)
- Time: 2-3 pessoas, 20 semanas
- Custo: Sem infraestrutura cara, cloud-agnostic

## 2. Micro-serviços

### 2.1 API Gateway (Port 8000)

**Responsabilidade**: Roteamento, autenticação, rate limiting, agregação

**Padrões**:
- Route pattern: `/api/v1/{service}/{resource}`
- Auth: JWT (HS256), RBAC por endpoint
- Rate limiting: Sliding window (10k req/min global, 100 req/min por user)
- Request tracing: Gera `trace_id`, injeta em headers

**Dependências**:
- Auth service (verificação JWT)
- Todos serviços (routing)

**Health**:
```
GET /health/live      # Process alive?
GET /health/ready     # Dependencies OK?
Timeout: 1s
Fail threshold: 2 consecutive
```

### 2.2 Job Manager (Port 8001)

**Responsabilidade**: Orquestração de jobs, state machine, retry

**Padrões**:
- State: NEW → QUEUED → PROCESSING → COMPLETED/FAILED
- Saga pattern: Compensa falhas de downstream
- Idempotency: idempotency_key (24h cache)
- Retry: Exponential backoff (1s, 2s, 4s, 8s, 16s) + jitter

**Dependências**:
- Message broker (RabbitMQ)
- Database (job state)

**Health**:
```
GET /health/live      # OK
GET /health/ready     # DB + RabbitMQ OK?
```

### 2.3 Downloader (Port 8002)

**Responsabilidade**: Download de vídeos YouTube

**Padrões**:
- Circuit breaker: 5 falhas → wait 60s
- Timeout: 30s por request
- Retry: 3 tentativas
- Rate limiter: 10 parallel downloads, 5 req/s youtube
- Bulk: Quebra 4GB em chunks 50MB

**Dependências**:
- YouTube API
- Storage service (upload chunks)
- Message broker (progress events)

**Health**:
```
GET /health/live      # OK
GET /health/ready     # YouTube API + Storage OK?
```

### 2.4 Transcriber (Port 8003)

**Responsabilidade**: Transcrição de audio → texto

**Padrões**:
- Model cache: Reuse model 100+ vezes (RAM)
- Worker pool: 4 workers paralelos (GPU/CPU bound)
- Timeout: 5m por arquivo
- Retry: 2 tentativas (timeout não é retryable)

**Dependências**:
- Storage service (download audio)
- Message broker (results)

**Health**:
```
GET /health/live      # OK
GET /health/ready     # Model loaded? Storage OK?
```

### 2.5 Storage (Port 8004)

**Responsabilidade**: S3-compatible storage (MinIO/AWS S3)

**Padrões**:
- Replication: Todos uploads em 2 AZ mínimo
- Versioning: Habilitado
- Lifecycle: 90d archive → glacier
- Multipart upload: Chunks > 100MB

**Dependências**:
- MinIO/S3
- Database (metadata)

**Health**:
```
GET /health/live      # OK
GET /health/ready     # Bucket accessible?
```

### 2.6 Notifier (Port 8005)

**Responsabilidade**: Notificações por email, webhook, push

**Padrões**:
- Queue: Processa async de RabbitMQ
- Retry: 3 tentativas, exponential backoff
- Deduplication: 1h window
- Template engine: Jinja2

**Dependências**:
- Email provider (SMTP)
- Webhook endpoints (user-defined)
- Message broker

**Health**:
```
GET /health/live      # OK
GET /health/ready     # SMTP OK?
```

### 2.7 Admin (Port 8006)

**Responsabilidade**: Gestão (users, quotas, reports)

**Padrões**:
- RBAC: admin, manager, viewer
- Audit log: Toda mudança registrada
- Cache: Redis (5m TTL)

**Dependências**:
- Database
- Redis

**Health**:
```
GET /health/live      # OK
GET /health/ready     # DB + Redis OK?
```

## 3. Communication Patterns

### 3.1 Async (RabbitMQ)

**Fluxos Assíncronos**:
```
job-manager → download service
download → storage
transcriber → notifier
```

**Garantias**:
- At-least-once delivery
- Dead Letter Queue (DLQ) por 3 dias
- Acknowledgment: Manual (app ack)

**Queues**:
```
jobs.created              # Job manager publica
jobs.download             # Downloader consome
jobs.transcribe           # Transcriber consome
jobs.completed            # Admin/Notifier consomem
jobs.failed               # DLQ monitor
```

### 3.2 Sync (gRPC)

**Chamadas Síncronas** (poucas):
```
api-gateway → job-manager (criar job)
api-gateway → admin (consultar status)
job-manager → storage (metadados)
```

**Timeouts**:
```
api-gateway: 5s
job-manager: 2s interno
```

## 4. Data Consistency

### 4.1 Database

**PostgreSQL 15+**

**Strategy**:
- Master-Master replication (2 datacenters)
- Automatic failover (PgBouncer + VIP)
- Backups: Daily full + hourly WAL (30d retention)
- RTO: 5 minutes | RPO: 0 (WAL streaming)

**Schema Pattern**:
```
- Events table (immutable append-only)
- Snapshots (materialized views, updated 5m)
- Indexes: (job_id, status), (created_at, status)
```

### 4.2 Idempotency

**Key Pattern**:
```
idempotency_key = hash(user_id + request_id + timestamp)
Cache: Redis, 24h TTL
Lookup: antes de processar
```

## 5. Resiliência

### 5.1 Circuit Breaker

**Configuração por Serviço**:
```
YouTube API:       fail_max=5,   reset_timeout=60s
PostgreSQL:        fail_max=10,  reset_timeout=30s
Redis:             fail_max=3,   reset_timeout=20s
RabbitMQ:          fail_max=7,   reset_timeout=45s
```

**Estados**:
```
CLOSED → (fail_max failures) → OPEN → (reset_timeout) → HALF_OPEN → CLOSED/OPEN
```

### 5.2 Retry Strategy

**Algoritmo**:
```
wait = min(base * 2^attempt, max_wait) + random(0, jitter)

base = 1s
max_wait = 32s
jitter = 0.1 * wait

Attempt 1: ~1s
Attempt 2: ~2-3s
Attempt 3: ~4-6s
```

**Retryable Errors**:
- 408 (timeout)
- 429 (rate limit)
- 5xx (server error)
- Connection errors

**Non-retryable**:
- 400, 401, 403, 404 (client)
- 409 (conflict - já processado)

### 5.3 Timeout

**Por camada**:
```
HTTP request:     30s
Downstream call:  5s
Database query:   10s
```

### 5.4 Graceful Shutdown

**Timeline** (30s):
```
t=0-2s:   Log shutdown
t=2s:     Health checks return 503 (remove from LB)
t=2-5s:   Stop accepting new requests
t=5-20s:  Drain in-flight requests
t=20-30s: Close connections (DB, RabbitMQ)
t=30s:    SIGKILL
```

### 5.5 Bulkhead Pattern

**Isolamento de Recursos**:
```
- Transcriber: 4 worker threads (não bloqueia gateway)
- Download: 10 max parallel (não consome toda conexão)
- Notifier: 20 worker threads (não dá timeout em outros)
```

## 6. Observabilidade

### 6.1 Logging

**Structured Logging** (JSON):
```json
{
  "timestamp": "2025-10-23T10:30:45Z",
  "service": "downloader",
  "level": "INFO",
  "trace_id": "a1b2c3d4",
  "message": "Download completed",
  "job_id": "job-123",
  "duration_ms": 5234,
  "status": "success"
}
```

**Levels**:
- DEBUG: Development only
- INFO: Important events
- WARN: Degradation
- ERROR: Failures
- CRITICAL: System down

### 6.2 Metrics

**Prometheus**:
```
http_requests_total{service, endpoint, method, status}
http_request_duration_seconds{service, endpoint} (histogram)
job_processing_seconds{service, status} (histogram)
circuit_breaker_state{service, dependency}
queue_depth{queue}
database_connections{pool}
cache_hit_ratio{}
```

### 6.3 Tracing

**Jaeger**:
```
Trace ID: injeta em todos requests (headers, logs)
Span: Por chamada (HTTP, DB, queue, RPC)
Baggage: trace_id, user_id, request_id
```

### 6.4 Alertas

**SLA-based**:
```
p95_latency > 500ms        → WARN
error_rate > 1%            → CRITICAL
uptime < 99.9%             → CRITICAL
queue_depth > 1000         → WARN
cache_hit_ratio < 50%      → INFO
```

## 7. Security

### 7.1 Authentication

**JWT (HS256)**:
```
Header: "Authorization: Bearer {token}"
Payload: {user_id, roles, exp}
Secret: Rotate 90 dias
```

### 7.2 Authorization

**RBAC**:
```
admin:   Tudo
manager: Criar/ler jobs
viewer:  Apenas read
```

### 7.3 Secrets Management

**Environment Variables**:
```
DB_HOST, DB_PASSWORD
API_KEYS (YouTube, etc)
ENCRYPTION_KEY (data-at-rest)
```

**Kubernetes Secrets**:
```
kubectl create secret generic app-secrets
```

## 8. Testing Strategy

### 8.1 Unit Tests

**Per service**:
- Controllers: Input validation, response format
- Services: Business logic
- Utils: Edge cases
- Target: 80% coverage

### 8.2 Integration Tests

**Across boundaries**:
- Service + Database
- Service + Message broker
- Service + External API (mock)
- Target: Happy path + error cases

### 8.3 Contract Tests

**Producer-consumer**:
- Message schema
- API contract
- Ensures breaking changes caught early

### 8.4 E2E Tests

**Full flow**:
```
curl /api/v1/jobs -X POST (create)
   ↓
check job status
   ↓
curl /api/v1/jobs/{id}/results (get result)
```

## 9. Deployment

### 9.1 Environments

```
dev:   Docker Compose local
staging: 1 replica Kubernetes (cost: $50/month)
prod:  3+ replicas, multi-AZ, SLA 99.9%
```

### 9.2 CI/CD

**GitHub Actions** (or equivalent):
```
push → test → build image → push to registry → deploy to staging
approval → deploy to production
```

### 9.3 Scaling

**Horizontal** (Kubernetes HPA):
```
target_cpu: 70%
target_memory: 80%
min_replicas: 2
max_replicas: 10
scale_down_window: 5m
```

## 10. Cost Model

**Per month**:
```
RabbitMQ (managed):      $100
PostgreSQL (managed):    $200
Redis (managed):         $50
Kubernetes (3 nodes):    $300
Storage (S3 equiv):      $100-500 (usage-based)
Monitoring:              $50
─────────────────────────────
Total:                   ~$800-1200/month
```

**vs Monolith**: 5x cheaper at scale (was vertical scaling only)

---

**Próximo**: Leia `ESPECIFICACAO_SERVICOS.md`
