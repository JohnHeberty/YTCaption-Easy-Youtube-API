# 🔌 API Usage Guide

Complete guide to all API endpoints with request/response examples.

---

## 📋 Table of Contents

1. [Base URL & Authentication](#base-url--authentication)
2. [Core Endpoints](#core-endpoints)
   - [POST /api/v1/transcribe](#post-apiv1transcribe)
   - [POST /api/v1/video/info](#post-apiv1videoinfo)
3. [Health & System Endpoints](#health--system-endpoints)
   - [GET /health](#get-health)
   - [GET /health/ready](#get-healthready)
   - [GET /metrics](#get-metrics)
4. [Cache Management Endpoints](#cache-management-endpoints)
5. [Error Codes Reference](#error-codes-reference)
6. [Rate Limiting](#rate-limiting)
7. [Usage Examples](#usage-examples)

---

## Base URL & Authentication

### Base URL

**Local development:**
```
http://localhost:8000
```

**Production (with domain):**
```
https://your-domain.com
```

### Authentication

❌ **No authentication required** (public API by default).

⚠️ **Production recommendation**: Configure Nginx with basic auth or API keys for security.

---

## Core Endpoints

### POST /api/v1/transcribe

**Transcribes audio from YouTube video using Whisper AI or native YouTube transcripts.**

#### Request

**Headers:**
```http
Content-Type: application/json
```

**Body:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "use_youtube_transcript": false,
  "language": "auto"
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `youtube_url` | string | ✅ Yes | - | Full YouTube video URL |
| `use_youtube_transcript` | boolean | ❌ No | `false` | Use YouTube's native transcripts (fast) |
| `language` | string | ❌ No | `"auto"` | Language code (ISO 639-1) or "auto" for detection |

#### Response Success (200 OK)

```json
{
  "transcription_id": "abc-123-def-456",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 213.0,
  "language": "en",
  "transcription_text": "We're no strangers to love. You know the rules and so do I...",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "We're no strangers to love."
    },
    {
      "start": 5.2,
      "end": 8.8,
      "text": "You know the rules and so do I."
    }
  ],
  "total_segments": 42,
  "processing_time": 45.3,
  "model_used": "base",
  "transcription_method": "whisper",
  "cache_hit": false
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `transcription_id` | string | Unique transcription identifier (UUID) |
| `youtube_url` | string | Original YouTube URL |
| `title` | string | Video title from YouTube |
| `duration_seconds` | float | Audio duration in seconds |
| `language` | string | Detected or specified language (ISO 639-1) |
| `transcription_text` | string | Full transcription text (all segments concatenated) |
| `segments` | array | List of timestamped transcription segments |
| `segments[].start` | float | Segment start time (seconds) |
| `segments[].end` | float | Segment end time (seconds) |
| `segments[].text` | string | Segment transcription text |
| `total_segments` | integer | Total number of segments |
| `processing_time` | float | Processing time in seconds |
| `model_used` | string | Whisper model used (`tiny`, `base`, `small`, `medium`, `large`) |
| `transcription_method` | string | Method used (`whisper`, `youtube_transcript`) |
| `cache_hit` | boolean | Whether result was retrieved from cache |

#### Response Errors

**400 Bad Request - Validation Error:**
```json
{
  "error": "ValidationError",
  "message": "Must be a valid YouTube URL",
  "request_id": "abc-123-def",
  "details": {
    "url": "invalid-url"
  }
}
```

**400 Bad Request - Audio Too Long:**
```json
{
  "error": "AudioTooLongError",
  "message": "Audio duration (7250s) exceeds maximum allowed (7200s)",
  "request_id": "abc-123-def",
  "details": {
    "duration": 7250,
    "max_duration": 7200
  }
}
```

**404 Not Found - Video Download Error:**
```json
{
  "error": "VideoDownloadError",
  "message": "Failed to download video: Video unavailable",
  "request_id": "abc-123-def",
  "details": {
    "url": "https://www.youtube.com/watch?v=DELETED_VIDEO"
  }
}
```

**429 Too Many Requests - Rate Limit:**
```json
{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded: 5 per 1 minute",
  "request_id": "abc-123-def",
  "details": {
    "limit": "5/minute",
    "retry_after_seconds": 60
  }
}
```

**503 Service Unavailable - Circuit Breaker Open:**
```json
{
  "error": "ServiceTemporarilyUnavailable",
  "message": "YouTube API is temporarily unavailable. Circuit breaker 'youtube_download' is open. Please try again later.",
  "request_id": "abc-123-def",
  "details": {
    "retry_after_seconds": 60
  }
}
```

**504 Gateway Timeout - Operation Timeout:**
```json
{
  "error": "OperationTimeoutError",
  "message": "Operation timed out after 900 seconds",
  "request_id": "abc-123-def",
  "details": {
    "operation": "video_download",
    "timeout_seconds": 900
  }
}
```

#### Rate Limits

- **Limit**: 5 requests per minute per IP address
- **Header**: `X-RateLimit-Limit: 5`
- **Reset**: `X-RateLimit-Reset: 1634567890`

#### Processing Time Estimates

| Video Duration | Method | Estimated Time |
|----------------|--------|----------------|
| 5 min | YouTube transcript | 2-5 seconds |
| 5 min | Whisper (base model) | 15-30 seconds |
| 30 min | YouTube transcript | 5-10 seconds |
| 30 min | Whisper (base model) | 90-180 seconds |
| 1 hour | YouTube transcript | 10-15 seconds |
| 1 hour | Whisper (base model) | 180-360 seconds |

---

### POST /api/v1/video/info

**Gets video information without downloading or transcribing.**

#### Request

**Headers:**
```http
Content-Type: application/json
```

**Body:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `youtube_url` | string | ✅ Yes | Full YouTube video URL |

#### Response Success (200 OK)

```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 213,
  "duration_formatted": "00:03:33",
  "uploader": "Rick Astley",
  "upload_date": "20091025",
  "view_count": 1400000000,
  "description_preview": "The official video for "Never Gonna Give You Up" by Rick Astley...",
  "language_detection": {
    "detected_language": "en",
    "confidence": 0.95,
    "method": "youtube_metadata"
  },
  "subtitles": {
    "available": ["en", "es", "pt", "fr"],
    "manual_languages": ["en"],
    "auto_languages": ["es", "pt", "fr"],
    "total": 4
  },
  "whisper_recommendation": {
    "should_use_youtube_transcript": true,
    "reason": "Manual English subtitles available with high confidence",
    "estimated_time_whisper": 45,
    "estimated_time_youtube": 3
  },
  "warnings": [
    "Manual subtitles available in 1 languages. You can use YouTube transcripts instead of Whisper for faster results."
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `video_id` | string | YouTube video ID |
| `title` | string | Video title |
| `duration_seconds` | integer | Duration in seconds |
| `duration_formatted` | string | Formatted duration (HH:MM:SS) |
| `uploader` | string | Channel name |
| `upload_date` | string | Upload date (YYYYMMDD format) |
| `view_count` | integer | Number of views |
| `description_preview` | string | First 200 characters of description |
| `language_detection` | object | Detected language information |
| `language_detection.detected_language` | string | ISO 639-1 language code |
| `language_detection.confidence` | float | Confidence score (0-1) |
| `language_detection.method` | string | Detection method used |
| `subtitles` | object | Available subtitles information |
| `subtitles.available` | array | All available subtitle languages |
| `subtitles.manual_languages` | array | Manually created subtitles |
| `subtitles.auto_languages` | array | Auto-generated captions |
| `subtitles.total` | integer | Total subtitle languages |
| `whisper_recommendation` | object | Recommendation for transcription method |
| `whisper_recommendation.should_use_youtube_transcript` | boolean | Whether to use YouTube transcripts |
| `whisper_recommendation.reason` | string | Explanation for recommendation |
| `whisper_recommendation.estimated_time_whisper` | integer | Estimated Whisper time (seconds) |
| `whisper_recommendation.estimated_time_youtube` | integer | Estimated YouTube API time (seconds) |
| `warnings` | array | List of warnings/notices |

#### Rate Limits

- **Limit**: 10 requests per minute per IP address

---

## Health & System Endpoints

### GET /health

**Basic health check - returns API status and system information.**

#### Request

```http
GET /health
```

#### Response Success (200 OK)

```json
{
  "status": "healthy",
  "version": "3.0.0",
  "whisper_model": "base",
  "storage_usage": {
    "temp_files": 5,
    "total_size_mb": 234.5
  },
  "uptime_seconds": 3625.8
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Health status (`healthy` or `unhealthy`) |
| `version` | string | Application version |
| `whisper_model` | string | Currently loaded Whisper model |
| `storage_usage` | object | Temporary storage usage |
| `storage_usage.temp_files` | integer | Number of temporary files |
| `storage_usage.total_size_mb` | float | Total size of temp files (MB) |
| `uptime_seconds` | float | Uptime since last restart |

#### Rate Limits

- **Limit**: 30 requests per minute per IP address

---

### GET /health/ready

**Kubernetes/Docker readiness probe - validates all critical components.**

#### Request

```http
GET /health/ready
```

#### Response Success (200 OK)

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
  "timestamp": 1697728945.123
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Overall status (`ready` or `not_ready`) |
| `checks` | object | Health status of each component |
| `checks.api` | boolean | API responding |
| `checks.model_cache` | boolean | Whisper model cache operational |
| `checks.transcription_cache` | boolean | Transcription cache operational |
| `checks.ffmpeg` | boolean | FFmpeg available and working |
| `checks.whisper` | boolean | Whisper library loaded |
| `checks.storage` | boolean | Storage service accessible |
| `checks.file_cleanup` | boolean | File cleanup manager running |
| `message` | string | Overall status message |
| `timestamp` | float | Unix timestamp |

#### Response Error (503 Service Unavailable)

```json
{
  "error": "ServiceNotReady",
  "message": "Service not ready. Unhealthy components: ffmpeg, storage",
  "request_id": "abc-123-def",
  "details": {
    "checks": {
      "api": {"status": "healthy", "details": "API responding"},
      "ffmpeg": {"status": "unhealthy", "details": "FFmpeg not found in PATH"},
      "storage": {"status": "unhealthy", "details": "Error: Permission denied"}
    },
    "unhealthy_components": ["ffmpeg", "storage"]
  }
}
```

#### Rate Limits

- **Limit**: 60 requests per minute per IP address

---

### GET /metrics

**Returns detailed system metrics (cache, performance, etc.).**

#### Request

```http
GET /metrics
```

#### Response Success (200 OK)

```json
{
  "timestamp": "2025-10-22T14:30:45.123Z",
  "request_id": "abc-123-def",
  "uptime_seconds": 86400.5,
  "optimizations_version": "2.0",
  "model_cache": {
    "cache_size": 2,
    "total_usage_count": 1547,
    "hit_rate_percent": 78.5,
    "models": {
      "base": {
        "loaded": true,
        "usage_count": 1200,
        "last_used": 1697728945.123
      },
      "small": {
        "loaded": true,
        "usage_count": 347,
        "last_used": 1697728800.456
      }
    }
  },
  "transcription_cache": {
    "cache_size": 42,
    "max_size": 100,
    "hit_rate_percent": 45.2,
    "total_size_mb": 156.8,
    "oldest_entry_age_hours": 12.5,
    "newest_entry_age_hours": 0.2
  },
  "file_cleanup": {
    "tracked_files": 15,
    "periodic_cleanup_running": true,
    "last_cleanup_timestamp": 1697728000.0,
    "files_cleaned_last_run": 8,
    "size_freed_mb_last_run": 234.5
  },
  "ffmpeg": {
    "version": "N-111383-g3b0726c3a5",
    "has_hw_acceleration": true,
    "has_cuda": false,
    "has_nvenc": false,
    "has_nvdec": false,
    "has_vaapi": false,
    "has_videotoolbox": false,
    "has_amf": false
  },
  "worker_pool": {
    "active_workers": 2,
    "max_workers": 4,
    "queue_size": 0,
    "completed_tasks": 156,
    "failed_tasks": 3
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | Current timestamp (ISO 8601) |
| `request_id` | string | Request identifier |
| `uptime_seconds` | float | Uptime since last restart |
| `optimizations_version` | string | Version of optimizations (2.0) |
| `model_cache` | object | Whisper model cache statistics |
| `model_cache.cache_size` | integer | Number of models in cache |
| `model_cache.total_usage_count` | integer | Total model usage count |
| `model_cache.hit_rate_percent` | float | Cache hit rate percentage |
| `model_cache.models` | object | Per-model statistics |
| `transcription_cache` | object | Transcription cache statistics |
| `transcription_cache.cache_size` | integer | Number of cached transcriptions |
| `transcription_cache.max_size` | integer | Maximum cache size |
| `transcription_cache.hit_rate_percent` | float | Cache hit rate percentage |
| `transcription_cache.total_size_mb` | float | Total cache size (MB) |
| `file_cleanup` | object | File cleanup manager statistics |
| `ffmpeg` | object | FFmpeg capabilities |
| `worker_pool` | object | Worker pool statistics (if parallel enabled) |

#### Rate Limits

- **Limit**: 20 requests per minute per IP address

---

## Cache Management Endpoints

### POST /cache/clear

**Clears all caches (models and transcriptions).**

#### Request

```http
POST /cache/clear
```

#### Response Success (200 OK)

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
      "entries_removed": 42,
      "size_freed_mb": 156.8
    }
  },
  "timestamp": "2025-10-22T14:30:45.123Z"
}
```

---

### POST /cache/cleanup-expired

**Removes only expired cache entries.**

#### Request

```http
POST /cache/cleanup-expired
```

#### Response Success (200 OK)

```json
{
  "message": "Expired cache cleanup completed",
  "results": {
    "transcription_cache": {
      "status": "cleaned",
      "expired_entries_removed": 8
    },
    "model_cache": {
      "status": "cleaned",
      "unused_models_removed": 1
    }
  },
  "timestamp": "2025-10-22T14:30:45.123Z"
}
```

---

### GET /cache/transcriptions

**Lists all cached transcriptions.**

#### Request

```http
GET /cache/transcriptions
```

#### Response Success (200 OK)

```json
{
  "total_entries": 42,
  "cache_stats": {
    "cache_size": 42,
    "max_size": 100,
    "hit_rate_percent": 45.2
  },
  "entries": [
    {
      "file_hash": "a1b2c3d4e5f6...",
      "model": "base",
      "language": "en",
      "age_hours": 2.5,
      "access_count": 15,
      "size_mb": 3.2
    }
  ],
  "timestamp": "2025-10-22T14:30:45.123Z"
}
```

---

### POST /cleanup/run

**Manually triggers cleanup of old temporary files.**

#### Request

```http
POST /cleanup/run
```

#### Response Success (200 OK)

```json
{
  "message": "Cleanup completed successfully",
  "files": {
    "removed": 8,
    "size_freed_mb": 234.5,
    "empty_dirs_removed": 3
  },
  "timestamp": "2025-10-22T14:30:45.123Z"
}
```

---

## Error Codes Reference

### HTTP Status Codes

| Code | Name | Description |
|------|------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid request (validation error, malformed URL, etc.) |
| 404 | Not Found | Video not found or unavailable |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Transcription or processing error |
| 503 | Service Unavailable | Circuit breaker open or service unavailable |
| 504 | Gateway Timeout | Operation took too long |

### Error Types

| Error Type | HTTP Code | Description | Solution |
|------------|-----------|-------------|----------|
| `ValidationError` | 400 | Invalid YouTube URL or parameters | Check URL format |
| `AudioTooLongError` | 400 | Video exceeds max duration | Reduce MAX_VIDEO_DURATION_SECONDS |
| `AudioCorruptedError` | 400 | Downloaded audio is corrupted | Retry or report video |
| `VideoDownloadError` | 404 | Failed to download video | Check if video exists, retry with different strategy |
| `NetworkError` | 404 | Network connectivity issues | Check internet connection |
| `RateLimitExceeded` | 429 | Too many requests | Wait and retry |
| `TranscriptionError` | 500 | Whisper processing failed | Check logs, try different model |
| `ServiceTemporarilyUnavailable` | 503 | Circuit breaker open | Wait for service recovery |
| `OperationTimeoutError` | 504 | Operation timed out | Increase timeout or use shorter video |

---

## Rate Limiting

### Per-Endpoint Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /api/v1/transcribe` | 5 requests | 1 minute |
| `POST /api/v1/video/info` | 10 requests | 1 minute |
| `GET /health` | 30 requests | 1 minute |
| `GET /health/ready` | 60 requests | 1 minute |
| `GET /metrics` | 20 requests | 1 minute |

### Rate Limit Headers

```http
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1697728945
```

### Exceeded Rate Limit Response

```json
{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded: 5 per 1 minute",
  "request_id": "abc-123-def",
  "details": {
    "limit": "5/minute",
    "retry_after_seconds": 60
  }
}
```

---

## Usage Examples

### 1. cURL Examples

**Basic transcription:**
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'
```

**Use YouTube transcript (fast):**
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

**Get video info:**
```bash
curl -X POST http://localhost:8000/api/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'
```

**Health check:**
```bash
curl http://localhost:8000/health
```

**Readiness check:**
```bash
curl http://localhost:8000/health/ready
```

**Get metrics:**
```bash
curl http://localhost:8000/metrics
```

**Clear all caches:**
```bash
curl -X POST http://localhost:8000/cache/clear
```

---

### 2. Python (requests) Examples

**Basic transcription:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/transcribe",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "use_youtube_transcript": False,
        "language": "auto"
    }
)

data = response.json()
print(f"Title: {data['title']}")
print(f"Duration: {data['duration_seconds']}s")
print(f"Method: {data['transcription_method']}")
print(f"Processing time: {data['processing_time']}s")
print(f"Transcription: {data['transcription_text'][:200]}...")
```

**Get video info:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/video/info",
    json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
)

info = response.json()
print(f"Title: {info['title']}")
print(f"Duration: {info['duration_formatted']}")
print(f"Views: {info['view_count']:,}")

if info['whisper_recommendation']['should_use_youtube_transcript']:
    print(f"✅ Recommendation: Use YouTube transcript ({info['whisper_recommendation']['reason']})")
```

**Health check with retry:**
```python
import requests
import time

def wait_until_healthy(url, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{url}/health")
            if response.json()['status'] == 'healthy':
                return True
        except:
            pass
        time.sleep(5)
    return False

if wait_until_healthy("http://localhost:8000"):
    print("✅ API is healthy!")
else:
    print("❌ API failed to become healthy")
```

---

### 3. JavaScript (fetch) Examples

**Basic transcription:**
```javascript
const response = await fetch('http://localhost:8000/api/v1/transcribe', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    use_youtube_transcript: false,
    language: 'auto'
  })
});

const data = await response.json();
console.log('Title:', data.title);
console.log('Duration:', data.duration_seconds, 'seconds');
console.log('Transcription:', data.transcription_text);
```

**Get video info:**
```javascript
const response = await fetch('http://localhost:8000/api/v1/video/info', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
  })
});

const info = await response.json();
console.log('Title:', info.title);
console.log('Duration:', info.duration_formatted);
console.log('Subtitles available:', info.subtitles.total);
```

---

### 4. PowerShell Examples

**Basic transcription:**
```powershell
$body = @{
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    use_youtube_transcript = $false
    language = "auto"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/transcribe" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

Write-Host "Title: $($response.title)"
Write-Host "Duration: $($response.duration_seconds) seconds"
Write-Host "Processing time: $($response.processing_time) seconds"
```

**Health check:**
```powershell
$health = Invoke-RestMethod -Uri "http://localhost:8000/health"
if ($health.status -eq "healthy") {
    Write-Host "✅ API is healthy"
    Write-Host "Version: $($health.version)"
    Write-Host "Model: $($health.whisper_model)"
} else {
    Write-Host "❌ API is unhealthy"
}
```

---

## 📚 Next Steps

- **[Troubleshooting](./05-troubleshooting.md)** - Common problems and solutions
- **[Deployment](./06-deployment.md)** - Production deployment guide
- **[Monitoring](./07-monitoring.md)** - Prometheus & Grafana setup

---

**Version**: 3.0.0  
**Last Updated**: October 2025  
**Contributors**: YTCaption Team

[← Back to User Guide](./README.md)
