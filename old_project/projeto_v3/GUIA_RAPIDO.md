# 🚀 GUIA RÁPIDO PROJETO_V2

## Início Rápido (15 min)

```bash
# 1. Entenda a arquitetura (5 min)
cat ARQUITETURA.md | head -50

# 2. Suba local (5 min)
cd projeto_v2
docker-compose up -d

# 3. Teste (2 min)
curl http://localhost:8000/health/live
curl http://localhost:8001/health/live
```

---

## Arquivos & Propósito

| Arquivo | O quê | Leia se |
|---------|-------|---------|
| **README.md** | Overview do projeto | Quer entender rapidamente |
| **ARQUITETURA.md** | Design decisions, patterns | Arquiteto, Tech Lead |
| **ESPECIFICACAO_SERVICOS.md** | Cada micro-serviço detalhado | Dev implementar serviço |
| **CONFIGURACAO_RESILIENCIA.md** | Circuit breaker, retry, etc (código) | Dev implementar resiliência |
| **DEPLOYMENT.md** | Docker Compose + Kubernetes | DevOps, SRE |
| **MONITORAMENTO.md** | Prometheus, Jaeger, alertas | DevOps, Monitoring |
| **TESTES.md** | Unit, Integration, E2E, Load | QA, Dev |

---

## Stack Tecnológico

```
Python 3.11+ FastAPI
├─ Async: asyncio
├─ Validation: Pydantic
└─ Testing: pytest

Message: RabbitMQ (async) + gRPC (sync)
Database: PostgreSQL 15+
Cache: Redis 7+
Storage: S3-compatible (MinIO/AWS)
Container: Docker + Docker Compose
Orchestration: Kubernetes
Monitoring: Prometheus + Grafana + Jaeger
```

---

## 7 Micro-serviços

```
Port  Serviço              Responsabilidade
────────────────────────────────────────────
8000  API Gateway          Roteamento, Auth, Rate limit
8001  Job Manager          State machine, Saga
8002  Downloader           Download YouTube
8003  Transcriber          Transcrição audio→texto
8004  Storage              S3-compatible (MinIO/AWS)
8005  Notifier             Email, webhooks, push
8006  Admin                Gestão users, quotas, reports
```

---

## Resiliência (TL;DR)

```
Circuit Breaker: Fail-fast (5 fails → espera 60s)
Retry:           Exponential backoff (1s, 2s, 4s...)
Timeout:         30s HTTP, 5s interno, 10s DB
Graceful:        30s para shutdown (sem perder jobs)
Bulkhead:        Isolamento de recursos (threads pool)
Idempotency:     24h cache (não duplica jobs)
```

---

## Deployment

### Local (dev)

```bash
docker-compose up -d

# Services
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Monitoring
http://localhost:3000   # Grafana (admin:admin)
http://localhost:9090   # Prometheus
http://localhost:15672  # RabbitMQ (user:password)
```

### Kubernetes (prod)

```bash
kubectl create namespace ytcaption
kubectl apply -f infra/kubernetes/

# Verify
kubectl get pods -n ytcaption
kubectl get services -n ytcaption

# Logs
kubectl logs -f deployment/api-gateway -n ytcaption

# Scaling
kubectl scale deployment api-gateway --replicas=5 -n ytcaption
```

---

## Monitoramento

### Métricas Key (Prometheus)

```
http_requests_total{service, endpoint, status}
http_request_duration_seconds (p50, p95, p99)
http_errors_total{service, error_type}
job_processing_duration_seconds
queue_depth{queue}
circuit_breaker_state{service, dependency}
```

### Alertas (SLA-based)

```
P95 latency > 500ms       → WARN
Error rate > 1%           → CRITICAL
Service down (1m)         → CRITICAL
Queue depth > 1000        → WARN
Circuit breaker OPEN (5m) → WARN
Memory > 90%              → CRITICAL
```

### Dashboards

```
Grafana → System Overview (QPS, errors, latency)
         Per-service health (requests, latency, errors)
         Performance (histogram, p95, p99)
         SLA Tracking (uptime %, error budget)
```

---

## Logs (Structured JSON)

```json
{
  "timestamp": "2025-10-23T10:30:45Z",
  "service": "api-gateway",
  "level": "INFO",
  "trace_id": "a1b2c3d4",
  "message": "Job created",
  "job_id": "job-123",
  "duration_ms": 234
}
```

---

## Testes

### Executar

```bash
# Unit (rápido)
pytest services/*/tests/ -v --cov

# Integration (requer containers)
pytest services/*/tests/ -v -m integration

# E2E (full flow)
pytest tests/e2e/ -v -m e2e

# Load (1000 req/s)
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### Coverage

```
Target: 70%+ overall
├─ Unit: 80%+ (business logic)
├─ Integration: 60%+ (boundaries)
└─ E2E: Critical paths only
```

---

## Troubleshooting

### 503 Service Unavailable

```
1. Check: curl http://service:port/health/ready
2. Verify: Dependencies (DB, RabbitMQ, Redis)
3. Check logs: Service startup errors
4. Restart: kubectl rollout restart deployment/service
```

### 504 Request Timeout

```
1. Check P95 latency: Prometheus dashboard
2. Check queue depth: High = slow processing
3. Check database: Query performance
4. Scale up: kubectl scale deployment service --replicas=5
```

### High Memory Usage

```
1. Check: Model cache (transcriber)
2. Check: Connection pool leaks
3. Restart: Rolling restart (rolling update)
4. Investigate: Heap dump, profiling
```

### Circuit Breaker Open

```
1. Identify: Which dependency? (YouTube, DB, Redis)
2. Check: Error logs
3. Verify: Dependency is back online
4. Manual reset: DELETE /admin/circuit-breaker/{service}
```

---

## Plano de Implementação (20 semanas)

```
Semana 1-2:     Setup (Docker, Kubernetes, CI/CD)
Semana 3-6:     API Gateway + Job Manager
Semana 7-10:    Downloader + Transcriber
Semana 11-14:   Storage + Notifier + Admin
Semana 15-18:   Integration + Testing + Monitoring
Semana 19-20:   Performance tuning + Production readiness
```

---

## Checklist Pré-Produção

```
□ Resiliência implementada (circuit breaker, retry, timeout)
□ Health checks (liveness, readiness)
□ Graceful shutdown (30s, drain requests)
□ Logging estruturado (JSON com trace_id)
□ Métricas (Prometheus exporter)
□ Alertas (SLA-based)
□ Testes (unit 80%, integration 60%, E2E critical paths)
□ Disaster recovery (backups diários, teste restauração)
□ Load testing (1000 req/s, P95 < 500ms)
□ Security review (SQL injection, XSS, auth)
□ Documentation (runbooks, sla, contacts)
```

---

## Contatos & Links

```
Team:
├─ Tech Lead: [nome]
├─ DevOps: [nome]
└─ QA: [nome]

Repositories:
├─ Main: YTCaption-Easy-Youtube-API
└─ Docs: (esse arquivo)

Monitoring:
├─ Prometheus: http://prom.internal:9090
├─ Grafana: http://grafana.internal:3000
├─ Jaeger: http://jaeger.internal:16686
└─ PagerDuty: [link]

Runbooks:
├─ Incident Response: MONITORAMENTO.md seção 7
├─ Backup/Restore: DEPLOYMENT.md seção 4
└─ Scaling: kubectl scale deployment
```

---

## próximas ações

1. **Ler**: ARQUITETURA.md (15 min) → entender design
2. **Suba local**: docker-compose up -d (5 min)
3. **Verifique**: curl /health/live em cada serviço (2 min)
4. **Escolha serviço**: Qual vai implementar primeiro?
5. **Estude**: ESPECIFICACAO_SERVICOS.md para seu serviço
6. **Código**: Use CONFIGURACAO_RESILIENCIA.md como referência
7. **Teste**: Veja TESTES.md para test strategy
8. **Deploy**: Use DEPLOYMENT.md para local/prod

---

**Status**: ✅ Arquitetura v2.0 pronta para desenvolvimento

**Próximo passo**: Escolha seu serviço e comece a codificar!

```
git clone [repo]
cd projeto_v2/services/[seu-servico]
cat README.md (cada serviço tem seu README)
```
