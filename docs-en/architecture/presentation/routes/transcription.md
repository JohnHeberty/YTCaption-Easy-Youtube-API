# Transcription API Route

## Overview

The **POST /api/v1/transcribe** endpoint is the primary API for transcribing YouTube videos. It downloads the video, extracts audio, and generates timestamped transcriptions using either YouTube's native transcripts or Whisper AI models.

**Key Features:**
- 🎬 **YouTube Video Support** - Automatic download and audio extraction
- 🤖 **Dual Transcription Modes** - Native YouTube transcripts or Whisper AI
- ⚡ **Rate Limiting** - 5 requests/minute per IP (configurable)
- 🔒 **Circuit Breaker Protection** - Prevents cascading failures
- 📊 **Prometheus Metrics** - Request tracking and performance monitoring
- 🆔 **Request Tracking** - Unique request IDs for debugging
- ⏱️ **Automatic Timeout** - Based on video duration

**Endpoint:** `POST /api/v1/transcribe`  
**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│   Client (Browser/App)                      │
│   - Sends POST /api/v1/transcribe          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Presentation Layer                        │
│  ┌─────────────────────────────────────┐   │
│  │   Rate Limiting Middleware          │   │ ← 5 req/min/IP
│  │   (SlowAPI)                          │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │   Logging Middleware                 │   │ ← Request/response logs
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │   transcribe_video() ROUTE          │◄──┼─── THIS ENDPOINT
│  │   (THIS MODULE)                      │   │
│  │   - Request validation               │   │
│  │   - Error handling                   │   │
│  │   - Response formatting              │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Application Layer                         │
│  ┌─────────────────────────────────────┐   │
│  │   TranscribeYouTubeVideoUseCase     │   │
│  │   - Orchestrates workflow            │   │
│  │   - Business logic                   │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Dependencies:**
- `fastapi` - Web framework
- `slowapi` - Rate limiting
- `loguru` - Structured logging
- **DTOs**: `TranscribeRequestDTO`, `TranscribeResponseDTO`, `ErrorResponseDTO`
- **Use Case**: `TranscribeYouTubeVideoUseCase`

---

## Request Specification

### HTTP Method & Endpoint

```http
POST /api/v1/transcribe
Content-Type: application/json
```

### Request Body (TranscribeRequestDTO)

```python
@dataclass
class TranscribeRequestDTO:
    youtube_url: str            # Full YouTube video URL
    language: str = "auto"      # Language code or 'auto' for detection
```

**JSON Schema:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "auto"
}
```

### Request Parameters

#### `youtube_url` (required)

**Type:** `string`  
**Format:** Full YouTube URL

**Supported Formats:**
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID&t=30s`
- `https://m.youtube.com/watch?v=VIDEO_ID`

**Validation:**
- Must be valid YouTube URL
- Video must be publicly accessible
- Video must not be age-restricted (without auth)

**Examples:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

#### `language` (optional)

**Type:** `string`  
**Default:** `"auto"`

**Supported Values:**
- `"auto"` - Automatic language detection
- ISO 639-1 codes: `"en"`, `"pt"`, `"es"`, `"fr"`, `"de"`, etc.

**Examples:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
  "language": "en"
}
```

---

## Response Specification

### Success Response (200 OK)

**TranscribeResponseDTO:**
```python
@dataclass
class TranscribeResponseDTO:
    transcription_id: str           # Unique transcription ID
    youtube_url: str                # Original YouTube URL
    video_title: str                # Video title
    video_duration: float           # Duration in seconds
    language: str                   # Detected/specified language
    text: str                       # Full transcription text
    segments: List[TranscriptionSegment]  # Timestamped segments
    total_segments: int             # Number of segments
    processing_time: float          # Processing time in seconds
    source: str                     # "youtube_native" or "whisper"
    model: Optional[str]            # Whisper model name (if used)
```

**Example Response:**
```json
{
  "transcription_id": "a7f3c8d2-4e1b-9f6a-2d5c-8b3e1a9f4c2d",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "video_title": "Rick Astley - Never Gonna Give You Up",
  "video_duration": 213.5,
  "language": "en",
  "text": "We're no strangers to love. You know the rules and so do I...",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "We're no strangers to love"
    },
    {
      "id": 1,
      "start": 3.5,
      "end": 7.2,
      "text": "You know the rules and so do I"
    }
  ],
  "total_segments": 45,
  "processing_time": 12.3,
  "source": "youtube_native",
  "model": null
}
```

**Response Headers:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: a7f3c8d2-4e1b-9f6a-2d5c-8b3e1a9f4c2d
X-Process-Time: 12.34
```

---

## Error Responses

### 400 Bad Request - Validation Error

**Trigger:** Invalid YouTube URL, malformed request

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

### 400 Bad Request - Audio Too Long

**Trigger:** Video exceeds maximum duration (default: 2 hours)

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

### 400 Bad Request - Audio Corrupted

**Trigger:** Downloaded audio file is corrupted

```json
{
  "error": "AudioCorruptedError",
  "message": "Audio file is corrupted",
  "request_id": "abc-123-def",
  "details": {
    "file_path": "/tmp/video.mp4",
    "reason": "Invalid data found when processing input"
  }
}
```

### 404 Not Found - Video Download Error

**Trigger:** Video not found, private, age-restricted, or download failed

```json
{
  "error": "VideoDownloadError",
  "message": "Video is unavailable",
  "request_id": "abc-123-def",
  "details": {
    "url": "https://www.youtube.com/watch?v=INVALID"
  }
}
```

### 429 Too Many Requests - Rate Limit Exceeded

**Trigger:** More than 5 requests per minute from same IP

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

**Response Headers:**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640000000
```

### 500 Internal Server Error - Transcription Error

**Trigger:** Whisper transcription failed

```json
{
  "error": "TranscriptionError",
  "message": "Failed to transcribe audio",
  "request_id": "abc-123-def",
  "details": {}
}
```

### 503 Service Unavailable - Circuit Breaker Open

**Trigger:** YouTube API circuit breaker is open (too many failures)

```json
{
  "error": "ServiceTemporarilyUnavailable",
  "message": "YouTube API is temporarily unavailable. Circuit breaker 'youtube_downloader' is open. Please try again later.",
  "request_id": "abc-123-def",
  "details": {
    "retry_after_seconds": 60
  }
}
```

**Response Headers:**
```http
HTTP/1.1 503 Service Unavailable
Retry-After: 60
```

### 504 Gateway Timeout - Operation Timeout

**Trigger:** Transcription took longer than allowed timeout

```json
{
  "error": "OperationTimeoutError",
  "message": "Transcription operation timed out after 300s",
  "request_id": "abc-123-def",
  "details": {
    "operation": "transcription",
    "timeout_seconds": 300
  }
}
```

---

## Rate Limiting

### Configuration

**Default Limit:** 5 requests per minute per IP address

**Implementation:** SlowAPI (based on Flask-Limiter)

**Key Function:** `get_remote_address()` - Extracts client IP

**Decorator:**
```python
@limiter.limit("5/minute")
async def transcribe_video(...):
    ...
```

### Rate Limit Headers

**Every Response:**
```http
X-RateLimit-Limit: 5           # Requests per window
X-RateLimit-Remaining: 3       # Remaining in current window
X-RateLimit-Reset: 1640000000  # Unix timestamp of window reset
```

### Customizing Limits

**Environment Variable:**
```bash
RATE_LIMIT_TRANSCRIBE="10/minute"  # 10 requests per minute
RATE_LIMIT_TRANSCRIBE="100/hour"   # 100 requests per hour
```

**Per-User/API-Key Limits (Advanced):**
```python
@limiter.limit("5/minute", key_func=lambda: request.state.user_id)
```

---

## Circuit Breaker Protection

### YouTube API Circuit Breaker

**Purpose:** Prevent cascading failures when YouTube API is down

**Configuration:**
- `failure_threshold`: 5 consecutive failures
- `timeout_seconds`: 60 seconds
- `half_open_max_calls`: 3 test calls

**States:**
- **CLOSED** (Normal): All requests pass through
- **OPEN** (Blocking): Returns 503 immediately
- **HALF_OPEN** (Testing): Limited test calls

**Example Flow:**
```
Request → Circuit CLOSED → Download → Success → Response
Request → Circuit CLOSED → Download → Failure (5x) → Circuit OPEN
Request → Circuit OPEN → 503 Response (no download attempt)
Wait 60s → Circuit HALF_OPEN → Download → Success (3x) → Circuit CLOSED
```

---

## Request Tracking

### Request ID

**Generation:** UUID v4 by LoggingMiddleware

**Header:** `X-Request-ID`

**Usage:**
```python
request_id = getattr(request.state, "request_id", "unknown")
logger.info("Processing request", extra={"request_id": request_id})
```

**Response Header:**
```http
X-Request-ID: a7f3c8d2-4e1b-9f6a-2d5c-8b3e1a9f4c2d
```

### Process Time Tracking

**Calculation:** Measured by LoggingMiddleware

**Header:** `X-Process-Time` (seconds)

**Example:**
```http
X-Process-Time: 12.34
```

---

## Usage Examples

### Example 1: Basic Transcription (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "language": "auto"
  }'
```

### Example 2: Python Requests

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/transcribe",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "language": "en"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Title: {data['video_title']}")
    print(f"Duration: {data['video_duration']}s")
    print(f"Segments: {data['total_segments']}")
    print(f"Text: {data['text'][:100]}...")
elif response.status_code == 429:
    print(f"Rate limited. Retry after {response.headers['Retry-After']}s")
else:
    error = response.json()
    print(f"Error: {error['error']} - {error['message']}")
```

### Example 3: JavaScript Fetch

```javascript
const response = await fetch('http://localhost:8000/api/v1/transcribe', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    language: 'auto'
  })
});

const requestId = response.headers.get('X-Request-ID');
const processTime = response.headers.get('X-Process-Time');

if (response.ok) {
  const data = await response.json();
  console.log(`Transcription ID: ${data.transcription_id}`);
  console.log(`Processing time: ${processTime}s`);
  console.log(`Segments: ${data.total_segments}`);
} else if (response.status === 429) {
  const retryAfter = response.headers.get('Retry-After');
  console.log(`Rate limited. Retry after ${retryAfter}s`);
} else {
  const error = await response.json();
  console.error(`Error (${requestId}): ${error.message}`);
}
```

### Example 4: Error Handling Pattern

```python
import requests
import time

def transcribe_with_retry(youtube_url: str, max_retries: int = 3):
    """Transcribe video with automatic retry on rate limit."""
    
    for attempt in range(max_retries):
        response = requests.post(
            "http://localhost:8000/api/v1/transcribe",
            json={"youtube_url": youtube_url, "language": "auto"}
        )
        
        if response.status_code == 200:
            return response.json()
        
        elif response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        elif response.status_code == 503:
            error = response.json()
            retry_after = error['details'].get('retry_after_seconds', 60)
            print(f"Service unavailable. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        else:
            error = response.json()
            raise Exception(f"{error['error']}: {error['message']}")
    
    raise Exception(f"Failed after {max_retries} retries")
```

---

## Performance Characteristics

### Processing Time Estimates

| Video Duration | YouTube Native | Whisper (base/CUDA) | Whisper (large/CPU) |
|----------------|----------------|---------------------|---------------------|
| 5 minutes | 2-5 seconds | 0.5-1 min | 3-5 min |
| 30 minutes | 3-8 seconds | 2-4 min | 15-30 min |
| 1 hour | 4-10 seconds | 5-10 min | 30-60 min |
| 2 hours | 5-15 seconds | 10-20 min | 60-120 min |

**Factors Affecting Performance:**
- **Transcription Source**: YouTube native is 10-50x faster
- **Model Size**: larger models = slower but more accurate
- **Device**: CUDA is 3-10x faster than CPU
- **Video Quality**: Higher quality = larger files = slower

### Timeout Configuration

**Default Timeout:** Based on video duration

**Formula:**
```python
timeout = video_duration * 2 + 120  # 2x duration + 2min buffer
```

**Examples:**
- 10-minute video: 22-minute timeout
- 1-hour video: 122-minute timeout

---

## Testing

### Unit Test Example

```python
# tests/integration/test_transcription_route.py
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)

def test_transcribe_success():
    """Test successful transcription."""
    response = client.post(
        "/api/v1/transcribe",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "language": "en"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "transcription_id" in data
    assert "text" in data
    assert "segments" in data
    assert data["language"] == "en"
    assert len(data["segments"]) > 0

def test_transcribe_invalid_url():
    """Test validation error for invalid URL."""
    response = client.post(
        "/api/v1/transcribe",
        json={
            "youtube_url": "not-a-youtube-url",
            "language": "en"
        }
    )
    
    assert response.status_code == 400
    error = response.json()
    assert error["error"] == "ValidationError"
    assert "request_id" in error

def test_rate_limiting():
    """Test rate limiting (5 requests per minute)."""
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    
    # Make 5 requests (should succeed)
    for i in range(5):
        response = client.post("/api/v1/transcribe", json={"youtube_url": url})
        assert response.status_code in [200, 400, 404]  # Any non-rate-limit
    
    # 6th request should be rate limited
    response = client.post("/api/v1/transcribe", json={"youtube_url": url})
    assert response.status_code == 429
    assert "Retry-After" in response.headers

def test_circuit_breaker_response():
    """Test circuit breaker open response."""
    # Mock circuit breaker to be open
    # (Requires dependency injection or test fixtures)
    
    response = client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "https://www.youtube.com/watch?v=test"}
    )
    
    if response.status_code == 503:
        error = response.json()
        assert "Circuit breaker" in error["message"]
        assert "retry_after_seconds" in error["details"]
```

---

## Related Documentation

- **Use Case**: `src/application/use_cases/transcribe_video.py` (Business logic)
- **DTOs**: `src/application/dtos/transcription_dtos.py` (Request/response models)
- **Dependencies**: `docs-en/architecture/presentation/dependencies.md` (Dependency injection)
- **Middlewares**: `docs-en/architecture/presentation/middlewares/` (Logging, metrics)
- **API Usage Guide**: `docs-en/04-API-USAGE.md` (User documentation)
- **Error Handling**: `docs-en/08-TROUBLESHOOTING.md` (Common errors)

---

## Best Practices

### ✅ DO
- Always validate YouTube URLs before making requests
- Handle rate limit errors with exponential backoff
- Use request IDs for debugging and tracking
- Implement timeout handling in clients
- Check circuit breaker state (503) before retrying
- Log all errors with request IDs

### ❌ DON'T
- Don't ignore rate limit headers
- Don't retry immediately on 429/503 (respect Retry-After)
- Don't send requests without error handling
- Don't assume transcription will always succeed
- Don't rely solely on YouTube native transcripts (may not exist)
- Don't forget to handle network timeouts

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Added Circuit Breaker protection, Prometheus metrics integration |
| v2.1 | 2024 | Added rate limiting (5 req/min), improved error handling order |
| v2.0 | 2024 | YouTube Resilience v3.0, automatic timeout based on duration |
| v1.0 | 2023 | Initial transcription endpoint |
