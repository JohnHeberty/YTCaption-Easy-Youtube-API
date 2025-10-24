# 📊 Monitoring & Observability

Complete guide to monitoring YTCaption API with Prometheus and Grafana.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Stack Components](#stack-components)
3. [Quick Start](#quick-start)
4. [Prometheus Configuration](#prometheus-configuration)
5. [Grafana Dashboards](#grafana-dashboards)
6. [Available Metrics](#available-metrics)
7. [Alerting Rules](#alerting-rules)
8. [Log Aggregation](#log-aggregation)
9. [Performance Monitoring](#performance-monitoring)
10. [Troubleshooting Monitoring](#troubleshooting-monitoring)

---

## Overview

YTCaption includes a complete monitoring stack (v2.2+) for observability:

**Features**:
- ✅ **Prometheus**: Metrics collection and time-series database
- ✅ **Grafana**: Visualization dashboards with pre-configured panels
- ✅ **26+ metrics**: Transcription, YouTube Resilience v3.0, cache, worker pool, circuit breaker
- ✅ **Real-time monitoring**: 10s scrape interval
- ✅ **Pre-built dashboards**: System Overview, API Performance, YouTube Resilience, Transcription Stats
- ✅ **Alerting**: Optional AlertManager integration

**Architecture**:
```
YTCaption API (/metrics endpoint)
     ↓ (scrape every 10s)
Prometheus (port 9090)
     ↓ (data source)
Grafana (port 3000)
     ↓ (dashboards + alerts)
  Visualization
```

---

## Stack Components

### Prometheus (v2.48.0)

**Purpose**: Metrics collection and storage

**Capabilities**:
- Scrapes `/metrics` endpoint every 10s
- Stores time-series data (15 days retention)
- Query language (PromQL) for data analysis
- Alerting rules (with AlertManager)

**Endpoints**:
- `http://localhost:9090` - Web UI
- `http://localhost:9090/graph` - Query browser
- `http://localhost:9090/alerts` - Alert rules

---

### Grafana (v10.2.2)

**Purpose**: Metrics visualization

**Capabilities**:
- Pre-configured dashboards (4 dashboards included)
- Real-time charts and graphs
- Alert notifications (Discord, Slack, email)
- User authentication
- Dashboard templates

**Endpoints**:
- `http://localhost:3000` - Web UI
- Default credentials: `admin` / `whisper2024`

---

## Quick Start

### Enable Monitoring Stack

**Already enabled by default** in `docker-compose.yml`:

```yaml
services:
  whisper-api:
    # ... API config
  
  prometheus:
    image: prom/prometheus:v2.48.0
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
  
  grafana:
    image: grafana/grafana:10.2.2
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
```

---

### Access Dashboards

**Step 1**: Start application
```bash
docker compose up -d
```

**Step 2**: Access Grafana
```
URL: http://localhost:3000
User: admin
Pass: whisper2024
```

**Step 3**: View dashboards
- Navigate to **Dashboards** → **Browse**
- Select **"YouTube Resilience v3.0"** or **"System Overview"**

**Step 4**: Test metrics
```bash
# Generate some traffic
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Check metrics endpoint
curl http://localhost:8000/metrics
```

**Step 5**: Refresh Grafana dashboard to see live data

---

## Prometheus Configuration

### Scrape Configuration

**File**: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s      # Default scrape interval
  evaluation_interval: 15s  # Alert rule evaluation interval
  external_labels:
    monitor: 'whisper-api-monitor'

# Scrape configurations
scrape_configs:
  # Whisper API metrics
  - job_name: 'whisper-api'
    static_configs:
      - targets: ['whisper-api:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s      # Fast scraping for real-time data
    scrape_timeout: 5s
  
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

**Key settings**:
- **scrape_interval**: `10s` - Collects metrics every 10 seconds
- **targets**: `whisper-api:8000` - Docker service name
- **metrics_path**: `/metrics` - Prometheus endpoint

---

### Data Retention

**Default retention**: 15 days (configured in `docker-compose.yml`)

```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=15d'
    - '--storage.tsdb.path=/prometheus'
```

**Change retention**:
```yaml
# Edit docker-compose.yml
prometheus:
  command:
    - '--storage.tsdb.retention.time=30d'  # 30 days
    # or
    - '--storage.tsdb.retention.size=50GB'  # 50GB limit
```

**Apply changes**:
```bash
docker compose down
docker compose up -d
```

---

### Query Examples (PromQL)

**1. Transcription request rate (per second)**:
```promql
rate(transcription_requests_total[5m])
```

**2. Average transcription duration (last 5 minutes)**:
```promql
rate(transcription_duration_seconds_sum[5m]) / rate(transcription_duration_seconds_count[5m])
```

**3. YouTube download success rate**:
```promql
rate(youtube_downloads_total{status="success"}[5m]) / rate(youtube_downloads_total[5m])
```

**4. Circuit breaker state** (0=closed, 1=half_open, 2=open):
```promql
circuit_breaker_state{circuit_name="youtube"}
```

**5. Worker pool utilization** (percentage):
```promql
worker_pool_utilization{pool_name="transcription"} * 100
```

**6. Cache hit rate** (percentage):
```promql
cache_hit_rate{cache_type="transcription"} * 100
```

---

## Grafana Dashboards

### Pre-configured Dashboards

YTCaption includes **4 pre-built dashboards** (auto-loaded on startup):

#### 1. **System Overview**
**Purpose**: Server resource monitoring

**Panels**:
- CPU usage (%)
- RAM usage (MB)
- Disk I/O (MB/s)
- Network traffic (KB/s)
- API requests in progress
- Error rate

**Use cases**: Server health, capacity planning

---

#### 2. **API Performance**
**Purpose**: API metrics and latency

**Panels**:
- Request rate (req/s) by endpoint
- Response time (p50, p95, p99)
- Error rate (%) by status code
- Active requests
- Request duration histogram
- Top slowest endpoints

**Use cases**: Performance optimization, SLA monitoring

---

#### 3. **YouTube Resilience v3.0** ⭐
**Purpose**: YouTube download monitoring (v3.0 features)

**Panels** (26 metrics):

**Download Metrics**:
- Download rate by strategy (7 strategies)
- Success rate (%) per strategy
- Download duration (p50, p95)
- Download size (MB)
- Failures by error type

**Rate Limiting**:
- Requests per minute (current vs limit)
- Requests per hour (current vs limit)
- Rate limit wait time
- Cooldown status

**Circuit Breaker**:
- Circuit state (closed/half_open/open)
- Failure count
- State transitions timeline
- Recovery attempts

**Tor Proxy**:
- Tor downloads (count)
- Tor success rate
- Circuit rotation count
- IP rotation frequency

**User Agent Rotation**:
- UA rotation rate
- UA distribution (17 agents)

**Multi-Strategy Fallback**:
- Strategy priority order
- Fallback count by strategy
- Strategy switch timeline

**Use cases**: YouTube blocking detection, resilience monitoring, strategy optimization

---

#### 4. **Transcription Stats**
**Purpose**: Transcription workload monitoring

**Panels**:
- Transcriptions per hour
- Average duration by model
- Video duration distribution
- Worker pool queue size
- Active workers
- Cache hit rate
- Model loading time
- Parallel vs single-core usage

**Use cases**: Capacity planning, model selection, cache optimization

---

### Creating Custom Dashboards

**Step 1**: Access Grafana
```
http://localhost:3000
```

**Step 2**: Create new dashboard
- Click **"+"** → **"Dashboard"**
- Click **"Add new panel"**

**Step 3**: Configure panel
```
Query: rate(transcription_requests_total[5m])
Legend: {{status}} - {{model}}
Title: Transcription Request Rate
```

**Step 4**: Save dashboard
- Click **"Save dashboard"**
- Name: "My Custom Dashboard"

**Step 5**: Export (optional)
- Click **"Share"** → **"Export"**
- Save JSON to `monitoring/grafana/dashboards/my-dashboard.json`

**Step 6**: Commit to repository
```bash
git add monitoring/grafana/dashboards/my-dashboard.json
git commit -m "feat: Add custom Grafana dashboard"
```

---

### Dashboard Variables

**Dynamic filtering** using Grafana variables:

**Example**: Filter by Whisper model

**Step 1**: Add variable
- Dashboard settings → **"Variables"** → **"Add variable"**
- Name: `model`
- Type: `Query`
- Query: `label_values(transcription_requests_total, model)`

**Step 2**: Use in panel query
```promql
rate(transcription_requests_total{model="$model"}[5m])
```

**Result**: Dropdown to filter by model (tiny, base, small, medium, large)

---

## Available Metrics

YTCaption exposes **26+ Prometheus metrics** via `/metrics` endpoint.

### Transcription Metrics

**1. `transcription_requests_total`** (Counter)
- **Description**: Total transcription requests
- **Labels**: `status`, `model`, `language`
- **Values**: `success`, `error`
- **Example**: `transcription_requests_total{status="success",model="base",language="en"} 1234`

**2. `transcription_duration_seconds`** (Histogram)
- **Description**: Transcription duration
- **Labels**: `model`, `language`, `status`
- **Buckets**: 10s, 30s, 60s, 120s, 300s, 600s, 1200s, 1800s, 3600s
- **Example**: `transcription_duration_seconds_sum{model="base"} 5678.9`

**3. `video_duration_seconds`** (Histogram)
- **Description**: Video duration processed
- **Labels**: `status`
- **Buckets**: 30s, 60s, 180s, 300s, 600s, 1800s, 3600s, 7200s, 10800s

---

### YouTube Resilience Metrics (v3.0)

**4. `youtube_downloads_total`** (Counter)
- **Description**: Total YouTube downloads
- **Labels**: `status`, `strategy`
- **Strategies**: `default`, `fragment`, `best_audio`, `best_video`, `worst`, `tor`, `transcript`
- **Example**: `youtube_downloads_total{status="success",strategy="default"} 456`

**5. `youtube_download_duration_seconds`** (Histogram)
- **Description**: Download duration
- **Labels**: `status`
- **Buckets**: 5s, 10s, 30s, 60s, 120s, 300s, 600s, 900s

**6. `youtube_download_size_bytes`** (Histogram)
- **Description**: Downloaded file size
- **Labels**: `status`
- **Buckets**: 1MB, 10MB, 50MB, 100MB, 500MB, 1GB, 2GB, 5GB

**7. `youtube_download_errors_total`** (Counter)
- **Description**: Download errors by type
- **Labels**: `error_type`, `strategy`
- **Error types**: `http_403`, `network_unreachable`, `video_unavailable`, `age_restricted`, `timeout`, `other`

**8. `youtube_rate_limit_waits_total`** (Counter)
- **Description**: Rate limit wait occurrences
- **Labels**: `window` (`minute`, `hour`)

**9. `youtube_rate_limit_wait_duration_seconds`** (Histogram)
- **Description**: Time spent waiting for rate limits

**10. `youtube_tor_downloads_total`** (Counter)
- **Description**: Downloads via Tor proxy
- **Labels**: `status`

**11. `youtube_tor_circuit_rotations_total`** (Counter)
- **Description**: Tor circuit rotation count

**12. `youtube_user_agent_rotations_total`** (Counter)
- **Description**: User-Agent rotation count

**13. `youtube_strategy_fallbacks_total`** (Counter)
- **Description**: Strategy fallback occurrences
- **Labels**: `from_strategy`, `to_strategy`

---

### Circuit Breaker Metrics

**14. `circuit_breaker_state`** (Gauge)
- **Description**: Circuit breaker state (0=closed, 1=half_open, 2=open)
- **Labels**: `circuit_name`
- **Values**: `0` (closed, normal), `1` (half_open, testing), `2` (open, blocked)
- **Example**: `circuit_breaker_state{circuit_name="youtube"} 0`

**15. `circuit_breaker_failures_total`** (Counter)
- **Description**: Total failures recorded
- **Labels**: `circuit_name`

**16. `circuit_breaker_state_transitions_total`** (Counter)
- **Description**: State transitions
- **Labels**: `circuit_name`, `from_state`, `to_state`

---

### Cache Metrics

**17. `cache_hit_rate`** (Gauge)
- **Description**: Cache hit rate (0.0-1.0)
- **Labels**: `cache_type` (`model`, `transcription`)
- **Example**: `cache_hit_rate{cache_type="transcription"} 0.85` (85%)

**18. `cache_size_bytes`** (Gauge)
- **Description**: Cache size in bytes
- **Labels**: `cache_type`

**19. `cache_entries_total`** (Gauge)
- **Description**: Number of cache entries
- **Labels**: `cache_type`

---

### Worker Pool Metrics (Parallel Transcription v2.0)

**20. `worker_pool_queue_size`** (Gauge)
- **Description**: Worker pool queue size
- **Labels**: `pool_name`

**21. `worker_pool_active_workers`** (Gauge)
- **Description**: Active workers count
- **Labels**: `pool_name`

**22. `worker_pool_utilization`** (Gauge)
- **Description**: Worker utilization (0.0-1.0)
- **Labels**: `pool_name`
- **Example**: `worker_pool_utilization{pool_name="transcription"} 0.75` (75%)

---

### Model Metrics

**23. `model_loading_duration_seconds`** (Histogram)
- **Description**: Whisper model loading time
- **Labels**: `model_name`, `device`
- **Buckets**: 1s, 5s, 10s, 30s, 60s, 120s, 300s

**24. `whisper_model_info`** (Info)
- **Description**: Loaded model information
- **Labels**: `model_name`, `device`, `parameters`

---

### API Metrics

**25. `api_requests_in_progress`** (Gauge)
- **Description**: Requests currently being processed
- **Labels**: `endpoint`

**26. `api_errors_total`** (Counter)
- **Description**: API errors by type
- **Labels**: `endpoint`, `error_type`, `status_code`

---

### Viewing Raw Metrics

**Access metrics endpoint**:
```bash
curl http://localhost:8000/metrics
```

**Example output**:
```
# HELP transcription_requests_total Total transcription requests
# TYPE transcription_requests_total counter
transcription_requests_total{status="success",model="base",language="en"} 1234.0
transcription_requests_total{status="error",model="base",language="en"} 12.0

# HELP circuit_breaker_state Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
# TYPE circuit_breaker_state gauge
circuit_breaker_state{circuit_name="youtube"} 0.0

# HELP cache_hit_rate Cache hit rate (0.0-1.0)
# TYPE cache_hit_rate gauge
cache_hit_rate{cache_type="transcription"} 0.85

# HELP worker_pool_utilization Worker pool utilization (0.0-1.0)
# TYPE worker_pool_utilization gauge
worker_pool_utilization{pool_name="transcription"} 0.75
```

---

## Alerting Rules

### Prometheus AlertManager (Optional)

**Enable alerting** in `monitoring/prometheus.yml`:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "alerts/*.yml"
```

---

### Alert Rules Examples

**File**: `monitoring/alerts/ytcaption.yml`

```yaml
groups:
  - name: ytcaption_alerts
    interval: 30s
    rules:
      # Alert: High error rate
      - alert: HighErrorRate
        expr: |
          (
            rate(transcription_requests_total{status="error"}[5m]) 
            / 
            rate(transcription_requests_total[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 10%)"
      
      # Alert: Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{circuit_name="youtube"} == 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "YouTube circuit breaker is OPEN"
          description: "YouTube downloads are blocked due to repeated failures"
      
      # Alert: Low cache hit rate
      - alert: LowCacheHitRate
        expr: cache_hit_rate{cache_type="transcription"} < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }} (threshold: 50%)"
      
      # Alert: Worker pool saturation
      - alert: WorkerPoolSaturated
        expr: worker_pool_utilization{pool_name="transcription"} > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Worker pool is saturated"
          description: "Worker utilization is {{ $value | humanizePercentage }} (threshold: 90%)"
      
      # Alert: High download failure rate
      - alert: HighYouTubeFailureRate
        expr: |
          (
            rate(youtube_downloads_total{status="error"}[10m]) 
            / 
            rate(youtube_downloads_total[10m])
          ) > 0.3
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High YouTube download failure rate"
          description: "Failure rate is {{ $value | humanizePercentage }} (threshold: 30%)"
      
      # Alert: API down
      - alert: APIDown
        expr: up{job="whisper-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "YTCaption API is down"
          description: "API has been unreachable for 1 minute"
```

---

### Grafana Alerts (Alternative)

**Configure alerts in Grafana** (simpler than AlertManager):

**Step 1**: Edit panel
- Open dashboard → Edit panel
- Navigate to **"Alert"** tab

**Step 2**: Create alert rule
```
Name: High Error Rate
Evaluate every: 1m
For: 5m

Condition:
  WHEN avg() OF query(A, 5m, now) IS ABOVE 0.1
  
Query A: rate(transcription_requests_total{status="error"}[5m])
```

**Step 3**: Add notification channel
- **Grafana** → **"Alerting"** → **"Notification channels"**
- Add **Discord**, **Slack**, or **Email**

**Step 4**: Test alert
- Click **"Test"** to send test notification

---

### Discord Webhook Example

**Step 1**: Create Discord webhook
- Discord server → **Server Settings** → **Integrations** → **Webhooks**
- Copy webhook URL

**Step 2**: Add to Grafana
- **Alerting** → **"Notification channels"** → **"New channel"**
- Type: **Discord**
- Webhook URL: `https://discord.com/api/webhooks/...`

**Step 3**: Test
- Click **"Send Test"**
- Check Discord channel for notification

**Example notification**:
```
🚨 YTCaption Alert: High Error Rate
Error rate is 15% (threshold: 10%)
Time: 2025-10-22 15:30:45 UTC
```

---

## Log Aggregation

### Built-in Logging

YTCaption uses **Loguru** for structured logging:

**Log levels**:
- `DEBUG`: Detailed info (metrics, cache hits)
- `INFO`: General info (requests, downloads)
- `WARNING`: Warnings (retries, fallbacks)
- `ERROR`: Errors (failures, exceptions)
- `CRITICAL`: Critical errors (circuit breaker open)

**View logs**:
```bash
docker compose logs -f whisper-api --tail=100
```

**Filter by level**:
```bash
docker compose logs whisper-api | grep ERROR
docker compose logs whisper-api | grep "Circuit breaker"
```

---

### ELK Stack (Optional)

For advanced log aggregation, integrate **ELK Stack** (Elasticsearch, Logstash, Kibana):

**Add to `docker-compose.yml`**:
```yaml
services:
  elasticsearch:
    image: elasticsearch:8.11.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
  
  logstash:
    image: logstash:8.11.0
    ports:
      - "5000:5000"
    volumes:
      - ./monitoring/logstash/logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  
  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
```

**Configure log shipping** in YTCaption (future feature).

---

## Performance Monitoring

### Key Metrics to Watch

**1. Response Time** (target: <1s for /health):
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**2. Throughput** (requests per second):
```promql
rate(transcription_requests_total[5m])
```

**3. Error Rate** (target: <5%):
```promql
rate(transcription_requests_total{status="error"}[5m]) / rate(transcription_requests_total[5m])
```

**4. Cache Hit Rate** (target: >70%):
```promql
cache_hit_rate{cache_type="transcription"}
```

**5. Worker Utilization** (target: 50-80%):
```promql
worker_pool_utilization{pool_name="transcription"}
```

**6. YouTube Success Rate** (target: >90%):
```promql
rate(youtube_downloads_total{status="success"}[5m]) / rate(youtube_downloads_total[5m])
```

---

### Performance Optimization Tips

**If error rate is high**:
- Check circuit breaker state (may be open)
- Review YouTube rate limiting settings
- Check Tor proxy status (if enabled)
- See [Troubleshooting Guide](./05-troubleshooting.md)

**If response time is slow**:
- Increase `PARALLEL_WORKERS` (if CPU available)
- Use smaller Whisper model (`tiny` or `base`)
- Increase cache size
- Check disk I/O (may be bottleneck)

**If worker pool is saturated**:
- Increase `PARALLEL_WORKERS`
- Increase `MAX_CONCURRENT_REQUESTS`
- Add more CPU cores
- Use GPU for transcription

**If cache hit rate is low**:
- Increase cache size (adjust in code)
- Check if cache is being cleared frequently
- Review cache eviction policy

---

## Troubleshooting Monitoring

### Prometheus Not Scraping

**Check Prometheus targets**:
```
http://localhost:9090/targets
```

**Expected**: `whisper-api` target should be **UP**

**If DOWN**:
```bash
# Check API is running
docker compose ps whisper-api

# Check /metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus logs
docker compose logs prometheus

# Restart Prometheus
docker compose restart prometheus
```

---

### Grafana Not Showing Data

**Check data source**:
- Grafana → **Configuration** → **Data sources**
- Prometheus URL should be: `http://prometheus:9090`
- Click **"Save & Test"** (should show green checkmark)

**If failed**:
```bash
# Check Prometheus is running
docker compose ps prometheus

# Test connection from Grafana container
docker compose exec grafana curl http://prometheus:9090/api/v1/status/config

# Restart Grafana
docker compose restart grafana
```

---

### Missing Metrics

**If specific metrics are missing**:

**Check API logs**:
```bash
docker compose logs whisper-api | grep "Metric recorded"
```

**Generate traffic**:
```bash
# Generate transcription request
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**Verify metrics appear**:
```bash
curl http://localhost:8000/metrics | grep transcription_requests_total
```

---

### Dashboard Not Loading

**Clear browser cache**:
- Ctrl+Shift+R (Windows/Linux)
- Cmd+Shift+R (Mac)

**Re-import dashboard**:
- Grafana → **Dashboards** → **Import**
- Upload JSON from `monitoring/grafana/dashboards/youtube-resilience-v3.json`

**Check dashboard provisioning**:
```bash
# Check volume mount
docker compose exec grafana ls -la /etc/grafana/provisioning/dashboards

# Restart Grafana to re-provision
docker compose restart grafana
```

---

## Monitoring Checklist

- [ ] **Prometheus**: Running on port 9090
- [ ] **Grafana**: Running on port 3000, accessible with credentials
- [ ] **Metrics endpoint**: `/metrics` returns data
- [ ] **Scraping**: Prometheus targets show UP status
- [ ] **Data source**: Grafana connected to Prometheus
- [ ] **Dashboards**: 4 pre-built dashboards visible
- [ ] **Alerts**: Alert rules configured (optional)
- [ ] **Notifications**: Notification channels tested (optional)
- [ ] **Retention**: 15 days retention configured
- [ ] **Backups**: Grafana dashboard JSONs committed to repository

---

## Next Steps

- [Deployment Guide](./06-deployment.md) - Production deployment strategies
- [Troubleshooting Guide](./05-troubleshooting.md) - Common issues & solutions
- [API Usage Guide](./04-api-usage.md) - Endpoint reference

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team
