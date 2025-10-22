# Prometheus Metrics System

## Overview

The **MetricsCollector** provides comprehensive observability for the YTCaption API using Prometheus metrics. This system tracks transcription performance, cache efficiency, worker pool utilization, circuit breaker states, and API health across all application layers.

**Key Features:**
- 📊 **20+ Prometheus Metrics** - Counters, histograms, and gauges
- 🎯 **Multi-dimensional Labels** - Status, model, language, device tracking
- 🔄 **Real-time Monitoring** - Live metrics via `/metrics` endpoint
- 📈 **Performance Insights** - Duration histograms with configurable buckets
- 🚨 **Error Tracking** - API errors and circuit breaker failures
- 💾 **Cache Analytics** - Hit rates and memory usage
- 🔧 **Worker Pool Visibility** - Queue size and utilization tracking

**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│         Presentation Layer                  │
│  ┌─────────────────────────────────────┐   │
│  │   PrometheusMiddleware               │   │
│  │   - Auto-collects HTTP metrics       │   │
│  │   - Request duration tracking        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Infrastructure Layer                  │
│  ┌─────────────────────────────────────┐   │
│  │   MetricsCollector (THIS MODULE)    │◄──┼─── External: /metrics endpoint
│  │   - Centralized metrics collection   │   │
│  │   - Prometheus client wrapper        │   │
│  └─────────────────────────────────────┘   │
│           ▲           ▲           ▲         │
│           │           │           │         │
│      Transcription  Cache    WorkerPool     │
│       Service      System     Managers      │
└─────────────────────────────────────────────┘
```

**Dependencies:**
- `prometheus_client` - Official Prometheus Python client
- `loguru` - Structured logging for metrics events
- `enum` - CircuitBreakerState enum definition

---

## Metric Categories

### 1. Transcription Metrics

#### `transcription_requests_total` (Counter)
Total transcription requests by status, model, and language.

**Labels:**
- `status`: success | error | cached | rate_limited
- `model`: tiny | base | small | medium | large | large-v2 | large-v3
- `language`: auto | en | pt | es | fr | etc.

**Usage:**
```python
from src.infrastructure.monitoring.metrics import MetricsCollector

# Record successful transcription
MetricsCollector.record_transcription_request(
    status="success",
    model="base",
    language="auto"
)
```

#### `transcription_duration_seconds` (Histogram)
Duration of transcription operations in seconds.

**Labels:**
- `model`: Whisper model name
- `language`: Target language
- `status`: success | error | timeout

**Buckets:** `[10, 30, 60, 120, 300, 600, 1200, 1800, 3600]` (10s to 1h)

**Usage:**
```python
import time

start = time.time()
# ... perform transcription
duration = time.time() - start

MetricsCollector.record_transcription_duration(
    duration=duration,
    model="base",
    language="en",
    status="success"
)
```

#### `video_duration_seconds` (Histogram)
Duration of processed videos.

**Labels:**
- `status`: success | error

**Buckets:** `[30, 60, 180, 300, 600, 1800, 3600, 7200, 10800]` (30s to 3h)

---

### 2. Cache Metrics

#### `cache_hit_rate` (Gauge)
Cache hit rate (0.0 to 1.0).

**Labels:**
- `cache_type`: model | transcription

**Usage:**
```python
# Update cache metrics from TranscriptionCache
from src.infrastructure.cache.transcription_cache import get_transcription_cache

cache = get_transcription_cache()
stats = cache.get_stats()

MetricsCollector.update_cache_metrics(
    cache_type="transcription",
    hit_rate=stats["hit_rate"],
    size_bytes=stats["total_size"],
    entries=stats["entries"]
)
```

#### `cache_size_bytes` (Gauge)
Total cache size in bytes.

#### `cache_entries_total` (Gauge)
Number of entries in cache.

---

### 3. Worker Pool Metrics

#### `worker_pool_queue_size` (Gauge)
Number of tasks waiting in the worker pool queue.

**Labels:**
- `pool_name`: transcription | download | preprocessing

**Usage:**
```python
from src.infrastructure.whisper.persistent_worker_pool import PersistentWorkerPool

pool = PersistentWorkerPool.get_instance()

MetricsCollector.update_worker_pool_metrics(
    pool_name="transcription",
    queue_size=pool.queue.qsize(),
    active_workers=pool.active_workers,
    max_workers=pool.max_workers
)
```

#### `worker_pool_active_workers` (Gauge)
Number of workers currently processing tasks.

#### `worker_pool_utilization` (Gauge)
Worker pool utilization ratio (0.0 to 1.0).

**Calculation:** `active_workers / max_workers`

---

### 4. Circuit Breaker Metrics

#### `circuit_breaker_state` (Gauge)
Current state of circuit breaker.

**Labels:**
- `circuit_name`: youtube_downloader | whisper_service | storage

**Values:**
- `0` = CLOSED (normal operation)
- `1` = HALF_OPEN (testing recovery)
- `2` = OPEN (blocking requests)

**Usage:**
```python
from src.infrastructure.monitoring.metrics import MetricsCollector, CircuitBreakerState

MetricsCollector.update_circuit_breaker_state(
    circuit_name="youtube_downloader",
    state=CircuitBreakerState.OPEN
)
```

#### `circuit_breaker_failures_total` (Counter)
Total failures detected by circuit breaker.

**Usage:**
```python
MetricsCollector.record_circuit_breaker_failure("youtube_downloader")
```

#### `circuit_breaker_state_transitions_total` (Counter)
Total state transitions.

**Labels:**
- `circuit_name`: Circuit breaker name
- `from_state`: CLOSED | HALF_OPEN | OPEN
- `to_state`: CLOSED | HALF_OPEN | OPEN

**Usage:**
```python
MetricsCollector.record_circuit_breaker_transition(
    circuit_name="youtube_downloader",
    from_state="CLOSED",
    to_state="OPEN"
)
```

---

### 5. Whisper Model Metrics

#### `model_loading_duration_seconds` (Histogram)
Time to load Whisper model into memory.

**Labels:**
- `model_name`: tiny | base | small | medium | large | large-v2 | large-v3
- `device`: cpu | cuda | mps

**Buckets:** `[1, 5, 10, 30, 60, 120, 300]` (1s to 5min)

**Usage:**
```python
import time

start = time.time()
model = whisper.load_model("base", device="cuda")
duration = time.time() - start

MetricsCollector.record_model_loading(
    duration=duration,
    model_name="base",
    device="cuda"
)

MetricsCollector.set_model_info(
    model_name="base",
    device="cuda",
    parameters="74M"
)
```

#### `whisper_model_info` (Info)
Metadata about loaded Whisper model.

**Fields:**
- `model_name`: Model size/version
- `device`: Execution device
- `parameters`: Number of parameters (optional)

---

### 6. Download Metrics

#### `youtube_download_duration_seconds` (Histogram)
Duration of YouTube video downloads.

**Labels:**
- `status`: success | error | timeout

**Buckets:** `[5, 10, 30, 60, 120, 300, 600, 900]` (5s to 15min)

**Usage:**
```python
start = time.time()
# ... download video
duration = time.time() - start

MetricsCollector.record_download_duration(duration, status="success")
MetricsCollector.record_download_size(file_size, status="success")
```

#### `youtube_download_size_bytes` (Histogram)
Size of downloaded video files.

**Buckets:** `[1e6, 10e6, 50e6, 100e6, 500e6, 1e9, 2e9, 5e9]` (1MB to 5GB)

---

### 7. API Metrics

#### `api_requests_in_progress` (Gauge)
Number of API requests currently being processed.

**Labels:**
- `endpoint`: /api/v1/transcribe | /api/v1/video-info | /health

**Usage (Context Manager):**
```python
async def transcribe_endpoint(request: Request):
    with MetricsCollector.track_request_in_progress("/api/v1/transcribe"):
        # Request automatically tracked
        result = await process_transcription(request)
        return result
```

#### `api_errors_total` (Counter)
Total API errors by endpoint and type.

**Labels:**
- `endpoint`: API endpoint path
- `error_type`: ValidationError | TimeoutError | StorageError | etc.
- `status_code`: 400 | 422 | 500 | 503 | etc.

**Usage:**
```python
try:
    # ... process request
except ValidationError as e:
    MetricsCollector.record_api_error(
        endpoint="/api/v1/transcribe",
        error_type="ValidationError",
        status_code=422
    )
    raise
```

---

## Usage Patterns

### Pattern 1: Transcription Flow Metrics

```python
from src.infrastructure.monitoring.metrics import MetricsCollector
import time

async def transcribe_video(url: str, model: str, language: str):
    start = time.time()
    
    try:
        # Download phase
        download_start = time.time()
        video_path = await download_video(url)
        download_duration = time.time() - download_start
        
        MetricsCollector.record_download_duration(download_duration, "success")
        MetricsCollector.record_download_size(video_path.stat().st_size, "success")
        
        # Transcription phase
        transcription = await transcribe(video_path, model, language)
        
        # Success metrics
        duration = time.time() - start
        MetricsCollector.record_transcription_request("success", model, language)
        MetricsCollector.record_transcription_duration(duration, model, language, "success")
        
        return transcription
        
    except Exception as e:
        # Error metrics
        duration = time.time() - start
        MetricsCollector.record_transcription_request("error", model, language)
        MetricsCollector.record_transcription_duration(duration, model, language, "error")
        raise
```

### Pattern 2: Periodic Cache Metrics Update

```python
import asyncio
from src.infrastructure.monitoring.metrics import MetricsCollector
from src.infrastructure.cache.transcription_cache import get_transcription_cache

async def update_cache_metrics_periodically():
    """Background task to update cache metrics every 30 seconds."""
    cache = get_transcription_cache()
    
    while True:
        stats = cache.get_stats()
        
        MetricsCollector.update_cache_metrics(
            cache_type="transcription",
            hit_rate=stats["hit_rate"],
            size_bytes=stats["total_size"],
            entries=stats["entries"]
        )
        
        await asyncio.sleep(30)

# Start background task
asyncio.create_task(update_cache_metrics_periodically())
```

### Pattern 3: Worker Pool Monitoring

```python
from src.infrastructure.monitoring.metrics import MetricsCollector

def report_worker_pool_metrics(pool):
    """Report worker pool metrics to Prometheus."""
    MetricsCollector.update_worker_pool_metrics(
        pool_name="transcription",
        queue_size=pool.queue.qsize(),
        active_workers=len(pool.busy_workers),
        max_workers=pool.max_workers
    )
```

### Pattern 4: Circuit Breaker Integration

```python
from src.infrastructure.monitoring.metrics import MetricsCollector, CircuitBreakerState

class YouTubeDownloadCircuitBreaker:
    def __init__(self):
        self.state = CircuitBreakerState.CLOSED
        self.name = "youtube_downloader"
    
    def open(self):
        old_state = self.state.name
        self.state = CircuitBreakerState.OPEN
        
        MetricsCollector.update_circuit_breaker_state(self.name, self.state)
        MetricsCollector.record_circuit_breaker_transition(self.name, old_state, "OPEN")
    
    def record_failure(self):
        MetricsCollector.record_circuit_breaker_failure(self.name)
```

---

## Configuration

Metrics are configured through `src/config/settings.py`:

```python
# settings.py
class Settings(BaseSettings):
    # Monitoring Configuration
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    METRICS_PATH: str = "/metrics"
```

**Environment Variables:**
```bash
ENABLE_METRICS=true
METRICS_PORT=9090
METRICS_PATH=/metrics
```

---

## Prometheus Queries

### Transcription Performance

```promql
# Average transcription duration by model
rate(transcription_duration_seconds_sum[5m]) 
  / rate(transcription_duration_seconds_count[5m])

# Transcription requests per minute by status
rate(transcription_requests_total[1m]) * 60

# 95th percentile transcription duration
histogram_quantile(0.95, 
  rate(transcription_duration_seconds_bucket[5m]))
```

### Cache Efficiency

```promql
# Cache hit rate over time
cache_hit_rate{cache_type="transcription"}

# Cache memory usage
cache_size_bytes{cache_type="transcription"} / 1024 / 1024  # MB

# Cache entries growth
delta(cache_entries_total{cache_type="transcription"}[1h])
```

### Worker Pool Health

```promql
# Worker pool utilization
worker_pool_utilization{pool_name="transcription"}

# Queue backlog
worker_pool_queue_size{pool_name="transcription"}

# Average active workers
avg_over_time(worker_pool_active_workers{pool_name="transcription"}[5m])
```

### Circuit Breaker Status

```promql
# Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
circuit_breaker_state{circuit_name="youtube_downloader"}

# Failures per minute
rate(circuit_breaker_failures_total[1m]) * 60

# State transitions
increase(circuit_breaker_state_transitions_total[1h])
```

### API Health

```promql
# Requests in progress
sum(api_requests_in_progress)

# Error rate by endpoint
rate(api_errors_total[5m]) * 60

# Error percentage
rate(api_errors_total[5m]) 
  / (rate(transcription_requests_total[5m]) + rate(api_errors_total[5m]))
```

---

## Grafana Integration

**Dashboard Panels:**

1. **Transcription Overview**
   - Request rate (line chart)
   - Success rate percentage (gauge)
   - Average duration by model (bar chart)

2. **Cache Performance**
   - Hit rate over time (area chart)
   - Memory usage (single stat)
   - Entries count (time series)

3. **Worker Pool Health**
   - Active workers (stacked area)
   - Queue size (line chart)
   - Utilization percentage (gauge)

4. **Circuit Breaker Status**
   - State timeline (state timeline panel)
   - Failure rate (graph)
   - Transitions heatmap

5. **Model Performance**
   - Loading time by device (histogram)
   - Model distribution (pie chart)
   - Device utilization (bar chart)

**Alert Rules:**
```yaml
# High error rate
alert: HighTranscriptionErrorRate
expr: rate(transcription_requests_total{status="error"}[5m]) > 0.1
for: 5m

# Circuit breaker open
alert: CircuitBreakerOpen
expr: circuit_breaker_state == 2
for: 1m

# Cache hit rate low
alert: LowCacheHitRate
expr: cache_hit_rate{cache_type="transcription"} < 0.3
for: 10m

# Worker pool saturated
alert: WorkerPoolSaturated
expr: worker_pool_utilization{pool_name="transcription"} > 0.9
for: 5m
```

---

## Testing

### Unit Test Example

```python
# tests/unit/test_metrics.py
import pytest
from src.infrastructure.monitoring.metrics import MetricsCollector, CircuitBreakerState
from prometheus_client import REGISTRY

def test_record_transcription_request():
    """Test transcription request counter."""
    before = REGISTRY.get_sample_value(
        'transcription_requests_total',
        {'status': 'success', 'model': 'base', 'language': 'en'}
    ) or 0
    
    MetricsCollector.record_transcription_request("success", "base", "en")
    
    after = REGISTRY.get_sample_value(
        'transcription_requests_total',
        {'status': 'success', 'model': 'base', 'language': 'en'}
    )
    
    assert after == before + 1

def test_track_request_in_progress():
    """Test context manager for tracking in-progress requests."""
    before = REGISTRY.get_sample_value(
        'api_requests_in_progress',
        {'endpoint': '/api/v1/transcribe'}
    ) or 0
    
    with MetricsCollector.track_request_in_progress("/api/v1/transcribe"):
        during = REGISTRY.get_sample_value(
            'api_requests_in_progress',
            {'endpoint': '/api/v1/transcribe'}
        )
        assert during == before + 1
    
    after = REGISTRY.get_sample_value(
        'api_requests_in_progress',
        {'endpoint': '/api/v1/transcribe'}
    )
    assert after == before

def test_circuit_breaker_state_enum():
    """Test circuit breaker state enum values."""
    assert CircuitBreakerState.CLOSED.value == 0
    assert CircuitBreakerState.HALF_OPEN.value == 1
    assert CircuitBreakerState.OPEN.value == 2
```

---

## Related Documentation

- **PrometheusMiddleware**: `docs-en/architecture/presentation/middlewares/prometheus-middleware.md` (HTTP metrics)
- **TranscriptionCache**: `docs-en/architecture/infrastructure/cache/transcription-cache.md` (Cache metrics source)
- **Deployment Guide**: `docs-en/07-DEPLOYMENT.md` (Prometheus setup)
- **Grafana Dashboards**: `docs-en/diagrams/README.md` (Monitoring visualization)

---

## Best Practices

### ✅ DO
- Record metrics at business logic boundaries (start/end of operations)
- Use context managers for in-progress tracking
- Label metrics with relevant dimensions (model, language, status)
- Update cache metrics periodically (every 30-60s)
- Create Grafana alerts for critical metrics
- Use histogram buckets appropriate for your data ranges

### ❌ DON'T
- Don't record metrics in tight loops (performance impact)
- Don't create unbounded label cardinality (e.g., user IDs)
- Don't block requests while recording metrics
- Don't use metrics for debugging (use logs instead)
- Don't expose sensitive data in metric labels
- Don't forget to handle exceptions when recording metrics

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Complete metrics system with 20+ metrics across all layers |
| v2.1 | 2024 | Added circuit breaker and worker pool metrics |
| v2.0 | 2024 | Prometheus integration with basic counters/histograms |
| v1.0 | 2023 | Initial metrics (transcription requests only) |
