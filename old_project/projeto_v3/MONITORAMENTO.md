# MONITORAMENTO & OBSERVABILIDADE

## 1. Métricas (Prometheus)

### Application Metrics

```
HTTP Requests
├─ http_requests_total{service, endpoint, method, status}
├─ http_request_duration_seconds{service, endpoint} (histogram)
└─ http_errors_total{service, status, error_type}

Job Processing
├─ jobs_created_total{service}
├─ jobs_completed_total{service, status}
├─ job_processing_duration_seconds{service} (histogram)
└─ jobs_failed_total{service, failure_reason}

Circuit Breaker
├─ circuit_breaker_state{service, dependency}  # 0=CLOSED, 1=OPEN, 2=HALF_OPEN
├─ circuit_breaker_calls_total{service, dependency, outcome}
└─ circuit_breaker_failures_total{service, dependency}

Queue (RabbitMQ)
├─ queue_messages_total{queue, action}  # produced, consumed
├─ queue_depth{queue}  # messages waiting
├─ queue_processing_duration_seconds{queue} (histogram)
└─ queue_acks_total{queue, status}

Cache (Redis)
├─ cache_requests_total{service, result}  # hit, miss
├─ cache_hit_ratio{service}
└─ cache_operation_duration_seconds{operation} (histogram)

Database
├─ db_connection_pool_available{service}
├─ db_connection_pool_total{service}
├─ db_query_duration_seconds{query_type} (histogram)
└─ db_errors_total{service}

Storage
├─ storage_upload_duration_seconds (histogram)
├─ storage_download_duration_seconds (histogram)
└─ storage_errors_total{operation}
```

### Instrumentação

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['service', 'endpoint', 'method', 'status']
)

# Histogram (p50, p95, p99)
http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['service', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5]  # 10ms to 5s
)

# Gauge
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state',
    ['service', 'dependency'],
    labelvalues=['0', '1', '2']  # CLOSED, OPEN, HALF_OPEN
)

# Usage
@app.get("/api/v1/jobs")
async def get_jobs():
    start = time.time()
    try:
        result = await job_manager.list()
        http_requests_total.labels(
            service='api-gateway',
            endpoint='/api/v1/jobs',
            method='GET',
            status=200
        ).inc()
        return result
    except Exception as e:
        http_requests_total.labels(
            service='api-gateway',
            endpoint='/api/v1/jobs',
            method='GET',
            status=500
        ).inc()
    finally:
        duration = time.time() - start
        http_request_duration.labels(
            service='api-gateway',
            endpoint='/api/v1/jobs'
        ).observe(duration)
```

---

## 2. Logs (Structured)

### Log Format

```json
{
  "timestamp": "2025-10-23T10:30:45.123Z",
  "level": "INFO",
  "service": "api-gateway",
  "trace_id": "a1b2c3d4e5f6g7h8",
  "request_id": "req-xyz789",
  "user_id": "user-123",
  "endpoint": "/api/v1/jobs",
  "method": "POST",
  "status": 202,
  "duration_ms": 234,
  "message": "Job created successfully",
  "job_id": "job-abc123",
  "tags": ["performance", "user-action"]
}
```

### Implementação

```python
import json
import logging
from pythonjsonlogger import jsonlogger
import uuid

class ContextFilter(logging.Filter):
    def __init__(self):
        self.trace_id = None
        self.request_id = None
    
    def filter(self, record):
        record.trace_id = self.trace_id or str(uuid.uuid4())
        record.request_id = self.request_id or str(uuid.uuid4())
        return True

# Setup
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

context_filter = ContextFilter()
logger.addFilter(context_filter)

# Middleware
@app.middleware("http")
async def logging_middleware(request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    context_filter.trace_id = trace_id
    
    response = await call_next(request)
    
    logger.info(
        "HTTP Request",
        extra={
            "endpoint": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "service": "api-gateway"
        }
    )
    
    return response
```

### Log Levels

```
DEBUG   - Development only
INFO    - Important events (job created, download started)
WARN    - Degradation (circuit open, high latency)
ERROR   - Failures (download failed, transcribe timeout)
CRITICAL - System down (DB unreachable)
```

### Centralized Logging

**ELK Stack** (optional, for prod):
```
Fluent-bit → Elasticsearch → Kibana

Query example:
service:api-gateway AND level:ERROR AND status >= 500
```

---

## 3. Distributed Tracing (Jaeger)

### Trace Context

```
trace_id: a1b2c3d4e5f6g7h8 (global unique)
span_id: 123456789 (per operation)
parent_span_id: 987654321 (parent operation)
```

### Propagation

```python
from opentelemetry import trace
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Setup
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

tracer = trace.get_tracer(__name__)

# Usage
@app.post("/api/v1/jobs")
async def create_job(request: JobRequest):
    with tracer.start_as_current_span("create_job") as span:
        span.set_attribute("user_id", request.user_id)
        span.set_attribute("url", request.url)
        
        # Call downstream
        job = await call_job_manager(request)
        
        span.set_attribute("job_id", job.id)
        return job

async def call_job_manager(request):
    with tracer.start_as_current_span("call_job_manager"):
        # RPC call
        response = await grpc_client.create_job(request)
        return response
```

### Traces Esperadas

```
Request: POST /api/v1/jobs
└─ Span: create_job (10ms)
   ├─ Span: validate_request (2ms)
   ├─ Span: call_job_manager (5ms)
   │  └─ Span: grpc_call (3ms)
   └─ Span: return_response (1ms)

Total: 10ms
```

### Visualização

```
Jaeger UI: http://localhost:16686

Query: service=api-gateway AND operation=create_job
├─ Duration: 10ms (p50), 15ms (p95)
├─ Error rate: 0.5%
└─ Latency by span: [visualiza cada step]
```

---

## 4. Dashboards (Grafana)

### Dashboard 1: System Overview

```
Panels:
├─ Total Requests (counter)
├─ Error Rate (gauge, red if > 1%)
├─ P95 Latency (gauge, yellow if > 500ms)
├─ Active Jobs (gauge)
├─ Queue Depth (gauge, red if > 1000)
├─ Pod Replicas (gauge)
└─ Disk Usage (gauge, red if > 80%)

Time range: Last 24h
Refresh: 30s
```

### Dashboard 2: Per-Service Health

```
For each service (api-gateway, job-manager, etc):
├─ Status: HEALTHY / DEGRADED / DOWN
├─ Requests per second
├─ Error rate per endpoint
├─ P95 latency per endpoint
├─ Circuit breaker state
└─ Database connections
```

### Dashboard 3: Performance

```
├─ HTTP latency distribution (histogram)
├─ Queue processing latency
├─ Database query latency
├─ Cache hit ratio
├─ Memory usage
└─ CPU usage
```

### Dashboard 4: SLA Tracking

```
├─ Uptime % (target: 99.9%)
├─ Error budget used (%)
├─ MTTR (mean time to repair)
├─ Failed deployments
└─ Incidents
```

---

## 5. Alertas

### SLA-Based Alerts

```
Alert                        Condition              Severity
─────────────────────────────────────────────────────────────
P95 Latency High            > 500ms (5m)          WARN
Error Rate High             > 1% (5m)             CRITICAL
Service Down                status != 200 (1m)    CRITICAL
Queue Depth High            > 1000                WARN
Pod Crash Loop              > 2 restarts/10m      CRITICAL
Memory Usage High           > 90%                 WARN
CPU Usage High              > 80% (5m)            WARN
DB Connection Pool Exhausted > 80%                CRITICAL
Circuit Breaker Open        state = OPEN (5m)     WARN
No New Jobs                 rate = 0 (15m)        INFO
```

### Alerting Rules

```yaml
groups:
- name: ytcaption
  interval: 30s
  rules:
  
  - alert: HighErrorRate
    expr: rate(http_errors_total[5m]) > 0.01
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate in {{ $labels.service }}"
      description: "Error rate is {{ $value | humanizePercentage }}"
  
  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency in {{ $labels.service }}"
  
  - alert: CircuitBreakerOpen
    expr: circuit_breaker_state{state="1"} == 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Circuit breaker OPEN: {{ $labels.dependency }}"
  
  - alert: QueueBacklog
    expr: queue_depth > 1000
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Queue backlog high: {{ $labels.queue }}"
```

### Notification Channels

```
Alertmanager config:
├─ Slack: #alerts channel
├─ Email: ops@company.com
├─ PagerDuty: For critical alerts
└─ SMS: For critical incidents
```

---

## 6. SLA Tracking

### Uptime Calculation

```
SLA Target: 99.9% (43.2 minutes downtime/month)

Formula:
Uptime = (1 - downtime_minutes / total_minutes) * 100

Measurement:
├─ Synthetic monitoring: Probe every 1min
├─ Real user monitoring: Aggregate errors
└─ Combine: Uptime = (1 - sum_errors / sum_requests)
```

### Error Budget

```
Budget per month: 0.1% of requests

Example:
- Total requests: 1 billion
- Allowed errors: 1 million
- Actual errors: 500k
- Budget used: 50%
- Budget remaining: 50%
```

### Monthly Report

```
Uptime:              99.95% (↑ +0.05)
Error rate:          0.03% (↓ -0.02)
P95 latency:         125ms (↓ -50ms)
P99 latency:         250ms (↓ -100ms)
Incidents:           2
  ├─ Incident 1: Database failover (5min, recovered)
  └─ Incident 2: RabbitMQ OOM (15min, manual restart)
Deployments:         8
Failed deploys:      0
MTTR:                10 min (↓ -5min)
Avg resolution time: 8 min (↓ -2min)
```

---

## 7. Incident Response

### On-Call Runbook

**1. Alert Received**
```
1. Acknowledge alert (PagerDuty)
2. Check Grafana: Is it real or false alarm?
3. Check logs: Error patterns?
4. Check traces: Where is the latency?
```

**2. Triage**
```
Severity:
├─ CRITICAL: P1 (drop everything, fix now)
├─ HIGH: P2 (fix within 1h)
└─ MEDIUM: P3 (fix within business hours)

Scope:
├─ Single service → Toggle kill switch?
├─ Multiple services → Infrastructure issue?
└─ All services → Global outage
```

**3. Remediation**
```
High Latency:
  1. Check circuit breaker state
  2. Check database query performance
  3. Check queue depth
  4. If degraded: Scale up replicas

High Error Rate:
  1. Check logs for error type
  2. Check circuit breaker (maybe trip it to fail-fast)
  3. Rollback recent deployment?
  4. Restart service if memory leak

Service Down:
  1. Check pod logs
  2. Check service dependencies
  3. Restart pod
  4. Check persistent storage (PV)
```

**4. Communication**
```
t=0: Alert received, acknowledge
t=5: Update status page: "Investigating"
t=15: Status page: "Identified root cause"
t=20: Status page: "Implementing fix"
t=25: Fix deployed, monitoring
t=30: Status page: "Resolved"
t=+24h: Post-mortem email
```

### Post-Mortem Template

```markdown
## Incident Report

**When**: 2025-10-23 10:30-10:45 (15 min)
**What**: API Gateway returned 503 errors for 10%% of requests
**Impact**: 100k requests failed, 5k users affected

## Timeline
- 10:30: Error rate spike detected (alert triggered)
- 10:32: On-call acknowledged
- 10:35: Root cause identified: Memory leak in job-manager
- 10:40: Service restarted, error rate normalized
- 10:45: All systems normal

## Root Cause
Job manager holding open DB connections in error handler.
Connection pool exhausted after 2 hours.

## Actions
1. Fix: Close DB connections in error handler (PR #123)
2. Monitoring: Add alert for "connections > 80%"
3. Testing: Add test for connection leak scenarios
```

---

**Próximo**: Leia `TESTES.md`
