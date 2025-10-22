# API Routes

## Overview

The **API Routes** module defines all HTTP endpoints for the YTCaption API, implementing RESTful patterns with comprehensive error handling, rate limiting, and observability.

---

## Module Structure

```
routes/
├── __init__.py
├── transcription.py        # POST /api/v1/transcribe
├── video_info.py          # POST /api/v1/video/info
├── system.py              # Health & metrics endpoints
├── transcription.md        # Documentation
├── video-info.md          # Documentation
├── system.md              # Documentation
└── README.md              # This file
```

---

## Endpoints Overview

### 1. Transcription Route
📄 **Documentation:** [transcription.md](transcription.md) (~420 lines)

**Endpoint:** `POST /api/v1/transcribe`

**Purpose:** Transcribe YouTube videos using Whisper AI

**Rate Limit:** 5 requests/minute per IP

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "auto"
}
```

**Response:**
```json
{
  "transcription_id": "uuid",
  "text": "Full transcription...",
  "segments": [...],
  "metadata": {...}
}
```

**Status Codes:**
- `200 OK` - Transcription successful
- `400 Bad Request` - Invalid URL, audio too long, corrupted audio
- `404 Not Found` - Video not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Processing failed
- `503 Service Unavailable` - Circuit breaker open
- `504 Gateway Timeout` - YouTube download timeout

---

### 2. Video Info Route
📄 **Documentation:** [video-info.md](video-info.md) (~586 lines)

**Endpoint:** `POST /api/v1/video/info`

**Purpose:** Get video metadata without downloading (preview)

**Rate Limit:** 10 requests/minute per IP

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**
```json
{
  "video_id": "VIDEO_ID",
  "title": "Video Title",
  "duration_seconds": 213.5,
  "duration_formatted": "00:03:33",
  "language_detection": {
    "detected_language": "en",
    "confidence": 0.98
  },
  "subtitles": {
    "available": ["en", "es"],
    "manual_languages": ["en"],
    "auto_languages": ["es"],
    "total": 2
  },
  "whisper_recommendation": {
    "should_use_youtube_transcript": true,
    "reason": "Manual subtitles available",
    "estimated_time_whisper": 45.2,
    "estimated_time_youtube": 2.3
  },
  "warnings": [...]
}
```

**Status Codes:**
- `200 OK` - Video info retrieved
- `400 Bad Request` - Invalid URL
- `404 Not Found` - Video unavailable
- `429 Too Many Requests` - Rate limit exceeded
- `503 Service Unavailable` - YouTube API unavailable

---

### 3. System Routes
📄 **Documentation:** [system.md](system.md) (~650 lines)

**Endpoints:**
- `GET /health` - Basic health check (30 req/min)
- `GET /health/ready` - Kubernetes readiness probe (60 req/min)
- `GET /` - API root information
- `GET /metrics` - Prometheus metrics (20 req/min)
- `POST /cache/clear` - Clear all caches
- `POST /cache/cleanup-expired` - Remove expired entries
- `GET /cache/transcriptions` - List cached items
- `POST /cleanup/run` - Manual file cleanup

**Health Response:**
```json
{
  "status": "healthy",
  "version": "2.2.0",
  "whisper_model": "base",
  "storage_usage": {...},
  "uptime_seconds": 3600.5
}
```

**Readiness Response:**
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
  }
}
```

---

## Common Patterns

### Request Headers

**All requests accept:**
```http
Content-Type: application/json
User-Agent: YourApp/1.0
```

### Response Headers

**All responses include:**
```http
X-Request-ID: uuid-v4
X-Process-Time: 2.333s
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
X-RateLimit-Reset: 1640000060
```

### Error Response Format

**All errors follow ErrorResponseDTO:**
```json
{
  "error": "ErrorType",
  "message": "Human-readable message",
  "request_id": "uuid",
  "details": {...}
}
```

---

## Rate Limiting

### Limits by Endpoint

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /api/v1/transcribe | 5 | 1 minute |
| POST /api/v1/video/info | 10 | 1 minute |
| GET /health | 30 | 1 minute |
| GET /health/ready | 60 | 1 minute |
| GET /metrics | 20 | 1 minute |
| POST /cache/* | No limit | - |

### Rate Limit Response

**Status:** `429 Too Many Requests`

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640000060

{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded: 5 per 1 minute",
  "request_id": "uuid",
  "details": {
    "limit": "5/minute",
    "retry_after_seconds": 60
  }
}
```

---

## Circuit Breaker Protection

### YouTube API Circuit Breaker

**Applied to:**
- POST /api/v1/transcribe
- POST /api/v1/video/info

**Thresholds:**
- Failure threshold: 5 consecutive failures
- Timeout: 60 seconds
- Half-open test: 1 request

**Circuit OPEN Response:**
```json
{
  "error": "ServiceTemporarilyUnavailable",
  "message": "YouTube API is temporarily unavailable",
  "request_id": "uuid",
  "details": {
    "retry_after_seconds": 60
  }
}
```

---

## Request Tracking

### Request ID Propagation

**All endpoints include X-Request-ID:**
1. Generated by logging middleware (UUID v4)
2. Attached to `request.state.request_id`
3. Returned in response header
4. Included in all error responses
5. Logged in all operations

**Usage:**
```python
@router.post("/api/v1/transcribe")
async def transcribe(request: Request):
    request_id = request.state.request_id
    logger.info("Processing", extra={"request_id": request_id})
```

---

## Testing

### Integration Test Example

```python
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)

def test_transcribe_endpoint():
    response = client.post("/api/v1/transcribe", json={
        "youtube_url": "https://youtube.com/watch?v=test"
    })
    
    assert response.status_code in [200, 400, 404]
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers

def test_video_info_endpoint():
    response = client.post("/api/v1/video/info", json={
        "youtube_url": "https://youtube.com/watch?v=test"
    })
    
    assert response.status_code in [200, 400, 404]
    data = response.json()
    
    if response.status_code == 200:
        assert "title" in data
        assert "duration_seconds" in data
        assert "subtitles" in data

def test_health_endpoint():
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "version" in data
```

---

## Best Practices

### ✅ DO
- Always validate YouTube URLs
- Include request_id in errors
- Use DTOs for request/response
- Implement rate limiting
- Add circuit breaker protection
- Return detailed error messages
- Log all operations
- Track metrics

### ❌ DON'T
- Don't expose internal errors to clients
- Don't bypass rate limits
- Don't ignore circuit breaker state
- Don't forget request tracking
- Don't skip input validation
- Don't return sensitive data in errors
- Don't block on long operations

---

## Related Documentation

- **Dependencies**: `../dependencies.md` - Dependency injection
- **Middlewares**: `../middlewares/` - Logging & Prometheus
- **DTOs**: `../../../src/application/dtos/` - Request/Response models
- **API Usage Guide**: `../../../docs-en/04-API-USAGE.md` - User guide

---

## Version

**Current Version:** v2.2 (2024)

**Changes:**
- v2.2: Added circuit breaker, enhanced error handling
- v2.1: Added rate limiting, improved logging
- v2.0: Added video info endpoint, health checks
- v1.0: Initial transcription endpoint
