# System API Routes

## Overview

The **System Routes** provide health monitoring, metrics collection, and cache management endpoints for observability and operational control. These endpoints are critical for container orchestration (Kubernetes/Docker), monitoring dashboards (Prometheus/Grafana), and maintenance operations.

**Key Features:**
- 🏥 **Health Checks** - Liveness and readiness probes
- 📊 **Metrics Endpoint** - System statistics and performance data
- 🧹 **Cache Management** - Clear, cleanup, and inspect caches
- 🔧 **Manual Maintenance** - File cleanup and cache expiration
- 📈 **Prometheus Integration** - Metrics export at `/metrics`
- ⚡ **Rate Limiting** - Different limits per endpoint (20-60 req/min)

**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│   Monitoring & Orchestration                │
│   - Kubernetes/Docker                       │
│   - Prometheus/Grafana                      │
│   - Health check dashboards                 │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Presentation Layer                        │
│  ┌─────────────────────────────────────┐   │
│  │   SYSTEM ROUTES (THIS MODULE)       │◄──┼─── Health & Metrics
│  │   - GET /health                      │   │
│  │   - GET /health/ready                │   │
│  │   - GET /metrics                     │   │
│  │   - POST /cache/clear                │   │
│  │   - POST /cleanup/run                │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Infrastructure Services                   │
│   - ModelCache                              │
│   - TranscriptionCache                      │
│   - FileCleanupManager                      │
│   - FFmpegOptimizer                         │
│   - WorkerPool                              │
└─────────────────────────────────────────────┘
```

---

## Endpoints Overview

| Endpoint | Method | Rate Limit | Purpose |
|----------|--------|------------|---------|
| `/health` | GET | 30/min | Basic health check |
| `/health/ready` | GET | 60/min | Detailed readiness probe |
| `/` | GET | None | API root info |
| `/metrics` | GET | 20/min | System metrics (Prometheus) |
| `/cache/clear` | POST | None | Clear all caches |
| `/cache/cleanup-expired` | POST | None | Remove expired entries |
| `/cache/transcriptions` | GET | None | List cached transcriptions |
| `/cleanup/run` | POST | None | Manual file cleanup |

---

## 1. Health Check Endpoint

### GET /health

**Purpose:** Basic health check for load balancers and monitoring systems.

**Rate Limit:** 30 requests/minute per IP

**Response Model:** `HealthCheckDTO`

### Request

```http
GET /health
```

### Success Response (200 OK)

```json
{
  "status": "healthy",
  "version": "2.2.0",
  "whisper_model": "base",
  "storage_usage": {
    "total_files": 145,
    "total_size_mb": 2340.5,
    "temp_files": 23,
    "cache_files": 12
  },
  "uptime_seconds": 3600.45
}
```

**Response Fields:**
- `status` (string): Health status (`"healthy"` or `"unhealthy"`)
- `version` (string): API version (e.g., `"2.2.0"`)
- `whisper_model` (string): Current Whisper model (`"tiny"`, `"base"`, `"small"`, `"medium"`, `"large"`)
- `storage_usage` (object): Storage statistics
  - `total_files` (int): Total files in storage
  - `total_size_mb` (float): Total storage size in MB
  - `temp_files` (int): Temporary files count
  - `cache_files` (int): Cached files count
- `uptime_seconds` (float): Application uptime in seconds

### Error Response (500 Internal Server Error)

```json
{
  "error": "HealthCheckError",
  "message": "Health check failed",
  "request_id": "abc-123-def",
  "details": {
    "error": "Failed to access storage service"
  }
}
```

---

## 2. Readiness Check Endpoint

### GET /health/ready

**Purpose:** Comprehensive readiness probe for Kubernetes/Docker container orchestration. Validates ALL critical components before accepting traffic.

**Rate Limit:** 60 requests/minute per IP

**Response Model:** `ReadinessCheckDTO`

### Request

```http
GET /health/ready
```

### Success Response (200 OK)

```json
{
  "status": "ready",
  "checks": {
    "api": true,
    "model_cache": true,
    "transcription_cache": true,
    "ffmpeg": true,
    "whisper": true,
    "storage": true,
    "file_cleanup": true
  },
  "message": "All systems operational",
  "timestamp": 1640000000.123
}
```

**Checks Performed:**

| Component | Validation |
|-----------|------------|
| `api` | API server responding |
| `model_cache` | Whisper model cache initialized |
| `transcription_cache` | Transcription cache accessible |
| `ffmpeg` | FFmpeg binary available and working |
| `whisper` | Whisper library imported successfully |
| `storage` | Storage service operational |
| `file_cleanup` | Cleanup manager running |

### Detailed Check Results

When you call `/health/ready`, you get detailed information about each component:

**Example with Component Details (200 OK):**
```json
{
  "status": "ready",
  "checks": {
    "api": true,
    "model_cache": true,
    "transcription_cache": true,
    "ffmpeg": true,
    "whisper": true,
    "storage": true,
    "file_cleanup": true
  },
  "message": "All systems operational",
  "timestamp": 1640000000.123
}
```

**Internal Check Details (logged, not returned):**
```json
{
  "model_cache": {
    "status": "healthy",
    "details": "Cache size: 2, Total usage: 145"
  },
  "transcription_cache": {
    "status": "healthy",
    "details": "Size: 45/100, Hit rate: 87%"
  },
  "ffmpeg": {
    "status": "healthy",
    "details": "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c) 2000-2021 the FFmpeg developers"
  },
  "whisper": {
    "status": "healthy",
    "details": "Whisper library loaded, version: 1.0.0"
  },
  "storage": {
    "status": "healthy",
    "details": "Storage accessible, temp files: 23"
  },
  "file_cleanup": {
    "status": "healthy",
    "details": "Tracked files: 67, Running: true"
  }
}
```

### Error Response (503 Service Unavailable)

**Trigger:** One or more components failed validation

```json
{
  "error": "ServiceNotReady",
  "message": "Service not ready. Unhealthy components: ffmpeg, whisper",
  "request_id": "abc-123-def",
  "details": {
    "checks": {
      "api": {"status": "healthy", "details": "API responding"},
      "model_cache": {"status": "healthy", "details": "Cache size: 2, Total usage: 145"},
      "transcription_cache": {"status": "healthy", "details": "Size: 45/100, Hit rate: 87%"},
      "ffmpeg": {"status": "unhealthy", "details": "FFmpeg not found in PATH"},
      "whisper": {"status": "unhealthy", "details": "Failed to import whisper: No module named 'whisper'"},
      "storage": {"status": "healthy", "details": "Storage accessible, temp files: 23"},
      "file_cleanup": {"status": "healthy", "details": "Tracked files: 67, Running: true"}
    },
    "unhealthy_components": ["ffmpeg", "whisper"]
  }
}
```

---

## 3. Metrics Endpoint

### GET /metrics

**Purpose:** Export detailed system metrics for Prometheus/Grafana or custom monitoring.

**Rate Limit:** 20 requests/minute per IP

### Request

```http
GET /metrics
```

### Response (200 OK)

```json
{
  "timestamp": "2024-01-15T14:30:00.123456",
  "request_id": "xyz-789-abc",
  "uptime_seconds": 7200.5,
  "optimizations_version": "2.0",
  "model_cache": {
    "cache_size": 2,
    "total_usage_count": 145,
    "models_loaded": ["base", "small"],
    "memory_usage_mb": 1024.5,
    "hit_rate": 0.92
  },
  "transcription_cache": {
    "cache_size": 45,
    "max_size": 100,
    "total_size_mb": 340.2,
    "hit_rate_percent": 87.3,
    "miss_count": 12,
    "eviction_count": 5
  },
  "file_cleanup": {
    "tracked_files": 67,
    "periodic_cleanup_running": true,
    "last_cleanup_timestamp": 1640000000,
    "total_cleanups": 24,
    "total_files_removed": 1234
  },
  "ffmpeg": {
    "version": "4.4.2",
    "has_hw_acceleration": true,
    "has_cuda": true,
    "has_nvenc": true,
    "has_nvdec": true,
    "has_vaapi": false,
    "has_videotoolbox": false,
    "has_amf": false
  },
  "worker_pool": {
    "pool_size": 4,
    "active_workers": 2,
    "pending_tasks": 3,
    "completed_tasks": 156,
    "failed_tasks": 2
  }
}
```

**Metrics Categories:**

| Category | Information |
|----------|-------------|
| **model_cache** | Whisper model loading statistics |
| **transcription_cache** | Cache performance (hit rate, evictions) |
| **file_cleanup** | File cleanup statistics |
| **ffmpeg** | FFmpeg capabilities and hardware acceleration |
| **worker_pool** | Parallel processing statistics (if enabled) |

---

## 4. Cache Management Endpoints

### POST /cache/clear

**Purpose:** Clear ALL caches (models + transcriptions) for memory management or debugging.

**Rate Limit:** None

#### Request

```http
POST /cache/clear
```

#### Response (200 OK)

```json
{
  "message": "Cache clearing completed",
  "results": {
    "model_cache": {
      "status": "cleared",
      "models_removed": 2
    },
    "transcription_cache": {
      "status": "cleared",
      "entries_removed": 45,
      "size_freed_mb": 340.2
    }
  },
  "timestamp": "2024-01-15T14:30:00.123456"
}
```

**Use Cases:**
- Free memory before large transcription job
- Force model reload after updates
- Debugging cache-related issues
- Manual garbage collection

---

### POST /cache/cleanup-expired

**Purpose:** Remove ONLY expired cache entries (less aggressive than full clear).

**Rate Limit:** None

#### Request

```http
POST /cache/cleanup-expired
```

#### Response (200 OK)

```json
{
  "message": "Expired cache cleanup completed",
  "results": {
    "transcription_cache": {
      "status": "cleaned",
      "expired_entries_removed": 12
    },
    "model_cache": {
      "status": "cleaned",
      "unused_models_removed": 1
    }
  },
  "timestamp": "2024-01-15T14:30:00.123456"
}
```

**Difference from `/cache/clear`:**
- **clear**: Removes ALL entries (aggressive)
- **cleanup-expired**: Removes only entries past TTL (conservative)

---

### GET /cache/transcriptions

**Purpose:** List all cached transcriptions for inspection.

**Rate Limit:** None

#### Request

```http
GET /cache/transcriptions
```

#### Response (200 OK)

```json
{
  "total_entries": 45,
  "cache_stats": {
    "cache_size": 45,
    "max_size": 100,
    "total_size_mb": 340.2,
    "hit_rate_percent": 87.3
  },
  "entries": [
    {
      "hash": "abc123def456",
      "model": "base",
      "language": "en",
      "age_seconds": 1200,
      "access_count": 5,
      "size_mb": 7.5
    },
    {
      "hash": "xyz789uvw012",
      "model": "small",
      "language": "pt",
      "age_seconds": 3600,
      "access_count": 2,
      "size_mb": 12.3
    }
  ],
  "timestamp": "2024-01-15T14:30:00.123456"
}
```

---

## 5. File Cleanup Endpoint

### POST /cleanup/run

**Purpose:** Manually trigger file cleanup (removes old temporary files).

**Rate Limit:** None

#### Request

```http
POST /cleanup/run
```

#### Response (200 OK)

```json
{
  "message": "Cleanup completed successfully",
  "files": {
    "removed_files": 23,
    "freed_space_mb": 145.7,
    "removed_directories": 5,
    "duration_seconds": 2.3
  },
  "timestamp": "2024-01-15T14:30:00.123456"
}
```

#### Error Response (503 Service Unavailable)

```json
{
  "detail": "Cleanup manager not initialized"
}
```

---

## 6. API Root Endpoint

### GET /

**Purpose:** Basic API information and navigation.

**Rate Limit:** None

#### Request

```http
GET /
```

#### Response (200 OK)

```json
{
  "name": "YTCaption API",
  "version": "2.2.0",
  "description": "API para transcrição de vídeos do YouTube usando Whisper",
  "docs": "/docs",
  "health": "/health"
}
```

---

## Usage Examples

### Example 1: Kubernetes Liveness Probe

**Deployment YAML:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ytcaption-api
spec:
  containers:
  - name: api
    image: ytcaption:2.2
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8000
      initialDelaySeconds: 15
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 2
```

### Example 2: Python Health Check Monitor

```python
import requests
import time

def monitor_health(url: str = "http://localhost:8000"):
    """Monitor API health every 30 seconds."""
    
    while True:
        try:
            # Check basic health
            health = requests.get(f"{url}/health", timeout=5)
            
            if health.status_code == 200:
                data = health.json()
                print(f"✅ Healthy | Uptime: {data['uptime_seconds']:.0f}s | Model: {data['whisper_model']}")
            else:
                print(f"❌ Unhealthy | Status: {health.status_code}")
            
            # Check readiness
            ready = requests.get(f"{url}/health/ready", timeout=5)
            
            if ready.status_code == 200:
                print("✅ All components ready")
            else:
                error = ready.json()
                unhealthy = error.get('details', {}).get('unhealthy_components', [])
                print(f"⚠️  Not ready | Failed: {', '.join(unhealthy)}")
        
        except Exception as e:
            print(f"❌ Connection failed: {e}")
        
        time.sleep(30)

# Run monitor
monitor_health()
```

### Example 3: Prometheus Metrics Scraping

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'ytcaption-api'
    scrape_interval: 30s
    metrics_path: /metrics
    static_configs:
      - targets: ['localhost:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'ytcaption-production'
```

**Grafana Dashboard Query:**
```promql
# Cache hit rate over time
rate(transcription_cache_hits_total[5m]) / 
rate(transcription_cache_requests_total[5m]) * 100

# Active worker pool utilization
worker_pool_active / worker_pool_size * 100

# FFmpeg hardware acceleration usage
ffmpeg_hw_acceleration_enabled
```

### Example 4: Cache Management Script

```python
import requests

def manage_caches(base_url: str = "http://localhost:8000"):
    """Cache management operations."""
    
    # 1. Get current metrics
    metrics = requests.get(f"{base_url}/metrics").json()
    
    cache_size = metrics['transcription_cache']['cache_size']
    max_size = metrics['transcription_cache']['max_size']
    hit_rate = metrics['transcription_cache']['hit_rate_percent']
    
    print(f"Cache: {cache_size}/{max_size} ({hit_rate:.1f}% hit rate)")
    
    # 2. List cached transcriptions
    cached = requests.get(f"{base_url}/cache/transcriptions").json()
    
    print(f"\nCached Transcriptions ({cached['total_entries']}):")
    for entry in cached['entries'][:5]:  # First 5
        print(f"  - Hash: {entry['hash'][:12]}... | "
              f"Model: {entry['model']} | "
              f"Age: {entry['age_seconds']/60:.1f}m | "
              f"Hits: {entry['access_count']}")
    
    # 3. Cleanup expired if cache is full
    if cache_size / max_size > 0.9:
        print("\n⚠️  Cache >90% full, cleaning expired entries...")
        cleanup = requests.post(f"{base_url}/cache/cleanup-expired").json()
        print(f"✅ Removed {cleanup['results']['transcription_cache']['expired_entries_removed']} entries")
    
    # 4. Clear all if needed
    # response = requests.post(f"{base_url}/cache/clear")
    # print(response.json())

# Run
manage_caches()
```

### Example 5: Automated Maintenance

```python
import requests
import schedule
import time

def cleanup_files():
    """Run file cleanup every 6 hours."""
    response = requests.post("http://localhost:8000/cleanup/run")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Cleanup: Removed {data['files']['removed_files']} files, "
              f"freed {data['files']['freed_space_mb']:.1f} MB")
    else:
        print(f"❌ Cleanup failed: {response.status_code}")

def cleanup_expired_cache():
    """Clean expired cache entries every hour."""
    response = requests.post("http://localhost:8000/cache/cleanup-expired")
    if response.status_code == 200:
        data = response.json()
        removed = data['results']['transcription_cache']['expired_entries_removed']
        print(f"✅ Cache cleanup: Removed {removed} expired entries")

# Schedule tasks
schedule.every(6).hours.do(cleanup_files)
schedule.every(1).hours.do(cleanup_expired_cache)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Response Headers

All endpoints include tracking headers:

```http
HTTP/1.1 200 OK
X-Request-ID: abc-123-def-456
X-Process-Time: 0.023s
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 27
X-RateLimit-Reset: 1640000060
```

---

## Testing

### Integration Test Example

```python
# tests/integration/test_system_routes.py
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)

def test_health_check_success():
    """Test basic health check."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] > 0

def test_readiness_check_all_components():
    """Test detailed readiness check."""
    response = client.get("/health/ready")
    
    assert response.status_code in [200, 503]
    data = response.json()
    
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert all(data["checks"].values())  # All checks True
    else:
        # Service not ready
        assert "unhealthy_components" in data["details"]

def test_metrics_endpoint():
    """Test metrics retrieval."""
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "model_cache" in data
    assert "transcription_cache" in data

def test_cache_clear():
    """Test cache clearing."""
    response = client.post("/cache/clear")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "results" in data
    assert "model_cache" in data["results"]
    assert "transcription_cache" in data["results"]

def test_cleanup_expired():
    """Test expired cache cleanup."""
    response = client.post("/cache/cleanup-expired")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["message"] == "Expired cache cleanup completed"

def test_manual_cleanup():
    """Test manual file cleanup."""
    response = client.post("/cleanup/run")
    
    assert response.status_code in [200, 503]
    
    if response.status_code == 200:
        data = response.json()
        assert "files" in data
        assert "removed_files" in data["files"]

def test_api_root():
    """Test API root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "name" in data
    assert "version" in data
    assert "docs" in data
```

---

## Related Documentation

- **Metrics Module**: `docs-en/architecture/infrastructure/monitoring/metrics.md` (Prometheus metrics)
- **TranscriptionCache**: `docs-en/architecture/infrastructure/cache/transcription-cache.md` (Cache implementation)
- **FileCleanupManager**: `docs-en/architecture/infrastructure/storage/file-cleanup-manager.md` (Cleanup logic)
- **Deployment Guide**: `docs-en/07-DEPLOYMENT.md` (Kubernetes/Docker setup)

---

## Best Practices

### ✅ DO
- Use `/health` for load balancer health checks
- Use `/health/ready` for Kubernetes readiness probes
- Set appropriate initial delays for probes (15-30s)
- Monitor metrics endpoint with Prometheus
- Schedule periodic cache cleanup
- Clear caches before major version upgrades
- Use `/cleanup/run` in cron jobs for file management
- Check readiness before deploying new versions

### ❌ DON'T
- Don't use `/health/ready` for liveness (too strict)
- Don't poll `/metrics` more than once per minute
- Don't clear caches during peak traffic
- Don't ignore 503 responses from `/health/ready`
- Don't skip readiness checks in container orchestration
- Don't assume all components are always healthy
- Don't expose cache management endpoints publicly without auth

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Added Circuit Breaker health checks, enhanced metrics |
| v2.1 | 2024 | Added rate limiting, improved logging |
| v2.0 | 2024 | Added `/metrics`, cache management, file cleanup endpoints |
| v1.0 | 2023 | Initial health check and readiness probes |
