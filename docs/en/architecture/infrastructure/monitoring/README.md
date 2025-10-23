# Monitoring & Observability

## Overview

The **Monitoring Subsystem** provides comprehensive observability through Prometheus metrics, structured logging, and health checks. It enables real-time monitoring, alerting, and performance analysis of the YTCaption API.

---

## Module Structure

```
monitoring/
├── __init__.py
├── metrics.py          # Prometheus metrics definitions
├── metrics.md          # Documentation
└── README.md          # This file
```

---

## Components

### Prometheus Metrics
📄 **Documentation:** [metrics.md](metrics.md) (~270 lines)

**Purpose:** Expose application metrics for Prometheus monitoring

**Key Metrics:**
- `transcription_requests_total` - Counter for total requests
- `transcription_duration_seconds` - Histogram for processing time
- `transcription_errors_total` - Counter for failures
- `cache_hits_total` / `cache_misses_total` - Cache performance
- `model_load_duration_seconds` - Model loading time
- `worker_pool_active_tasks` - Parallel processing metrics

---

## Monitoring Stack

```
┌──────────────────────────────────────┐
│   YTCaption API                      │
│   - Exposes /metrics endpoint        │
│   - Increments counters              │
│   - Records histograms               │
└────────────┬─────────────────────────┘
             │
             ↓ HTTP GET /metrics (15s interval)
┌──────────────────────────────────────┐
│   Prometheus Server                  │
│   - Scrapes metrics                  │
│   - Stores time-series data          │
│   - Evaluates alerting rules         │
└────────────┬─────────────────────────┘
             │
             ↓ PromQL Queries
┌──────────────────────────────────────┐
│   Grafana Dashboard                  │
│   - Visualizes metrics               │
│   - Creates alerts                   │
│   - Historical analysis              │
└──────────────────────────────────────┘
```

---

## Key Metrics

### 1. Request Metrics

**transcription_requests_total**
- Type: Counter
- Labels: `model`, `language`, `status`
- Purpose: Track total transcription requests

**transcription_duration_seconds**
- Type: Histogram
- Labels: `model`, `language`
- Buckets: [1, 5, 10, 30, 60, 120, 300, 600]
- Purpose: Measure processing time distribution

### 2. Cache Metrics

**cache_hits_total / cache_misses_total**
- Type: Counters
- Labels: `cache_type` (`transcription`, `model`)
- Purpose: Monitor cache effectiveness

**Hit Rate Calculation:**
```promql
rate(cache_hits_total[5m]) / 
(rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

### 3. Error Metrics

**transcription_errors_total**
- Type: Counter
- Labels: `error_type`, `model`
- Purpose: Track failure patterns

**Common Error Types:**
- `VideoDownloadError`
- `AudioValidationError`
- `AudioTooLongError`
- `CircuitBreakerOpenError`

### 4. Worker Pool Metrics

**worker_pool_active_tasks**
- Type: Gauge
- Purpose: Current parallel tasks

**worker_pool_completed_tasks_total**
- Type: Counter
- Purpose: Total processed chunks

---

## Configuration

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'ytcaption-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

### Grafana Dashboard

**Panels to Create:**
1. **Request Rate** (Graph)
   ```promql
   rate(transcription_requests_total[5m])
   ```

2. **Error Rate** (Graph)
   ```promql
   rate(transcription_errors_total[5m]) / rate(transcription_requests_total[5m])
   ```

3. **P95 Latency** (Graph)
   ```promql
   histogram_quantile(0.95, rate(transcription_duration_seconds_bucket[5m]))
   ```

4. **Cache Hit Rate** (Gauge)
   ```promql
   rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
   ```

---

## Alerting Rules

### High Error Rate

```yaml
- alert: HighTranscriptionErrorRate
  expr: |
    rate(transcription_errors_total[5m]) / rate(transcription_requests_total[5m]) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High transcription error rate"
    description: "Error rate is {{ $value | humanizePercentage }}"
```

### Slow Transcription

```yaml
- alert: SlowTranscription
  expr: |
    histogram_quantile(0.95, rate(transcription_duration_seconds_bucket[5m])) > 300
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Transcription latency high"
    description: "P95 latency is {{ $value }}s"
```

---

## Usage Examples

### Example 1: Record Request

```python
from src.infrastructure.monitoring.metrics import (
    transcription_requests_total,
    transcription_duration_seconds
)
import time

# Increment request counter
transcription_requests_total.labels(
    model="base",
    language="en",
    status="success"
).inc()

# Record duration
start = time.time()
# ... transcribe ...
duration = time.time() - start

transcription_duration_seconds.labels(
    model="base",
    language="en"
).observe(duration)
```

### Example 2: Track Cache

```python
from src.infrastructure.monitoring.metrics import (
    cache_hits_total,
    cache_misses_total
)

# Check cache
result = cache.get(key)

if result:
    cache_hits_total.labels(cache_type="transcription").inc()
else:
    cache_misses_total.labels(cache_type="transcription").inc()
```

---

## Health Checks

### Liveness Probe

```bash
curl http://localhost:8000/health
# Returns: {"status": "healthy", "version": "2.2.0", ...}
```

### Readiness Probe

```bash
curl http://localhost:8000/health/ready
# Returns: {"status": "ready", "checks": {...}}
```

---

## Best Practices

### ✅ DO
- Set up alerting for critical metrics
- Monitor cache hit rate (target: >80%)
- Track error rate by type
- Use histograms for latency
- Create Grafana dashboards
- Review metrics weekly

### ❌ DON'T
- Don't ignore metric spikes
- Don't over-alert (alert fatigue)
- Don't create high-cardinality labels
- Don't forget to set up retention policies
- Don't expose /metrics publicly without auth

---

## Related Documentation

- **Metrics Implementation**: [metrics.md](metrics.md) - Complete metrics reference
- **Prometheus Middleware**: `../../presentation/middlewares/prometheus.md` - HTTP instrumentation
- **System Routes**: `../../presentation/routes/system.md` - Health checks
- **Deployment**: `../../../07-DEPLOYMENT.md` - Production monitoring setup

---

## Version

**Current Version:** v2.2 (2024)

**Changes:**
- v2.2: Added worker pool metrics, enhanced error tracking
- v2.1: Added cache metrics, improved labeling
- v2.0: Prometheus integration
- v1.0: Initial metrics implementation
