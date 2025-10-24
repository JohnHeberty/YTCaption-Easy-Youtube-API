# Logging Middleware

## Overview

The **Logging Middleware** system provides comprehensive request/response logging with unique request tracking IDs for debugging, monitoring, and observability. It combines two components: a basic `LoggingMiddleware` class and an advanced Request ID middleware function registered in the FastAPI application.

**Key Features:**
- 🔍 **Request Tracking** - UUID-based request IDs for distributed tracing
- 📝 **Structured Logging** - JSON-formatted logs with rich context
- ⏱️ **Performance Monitoring** - Request duration tracking
- 🎯 **Detailed Context** - Client IP, User-Agent, query params
- ❌ **Exception Handling** - Captures unhandled errors with stack traces
- 📊 **Prometheus Integration** - Feeds metrics collection
- 🏥 **Health Check Exclusion** - Avoids log spam from probes

**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│   HTTP Request (Client)                     │
│   GET /api/v1/transcribe                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   LOGGING MIDDLEWARES (THIS MODULE)         │◄─── Intercepts ALL requests
│  ┌─────────────────────────────────────┐   │
│  │   1. Request ID Middleware           │   │
│  │      - Generate UUID                 │   │
│  │      - Attach to request.state       │   │
│  │      - Log incoming request          │   │
│  └─────────────────────────────────────┘   │
│                    ↓                        │
│  ┌─────────────────────────────────────┐   │
│  │   2. LoggingMiddleware (Legacy)      │   │
│  │      - Additional logging            │   │
│  │      - Backward compatibility        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Route Handlers                            │
│   - Transcription endpoint                  │
│   - Video info endpoint                     │
│   - System endpoints                        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Response + Headers                        │
│   X-Request-ID: abc-123-def                 │
│   X-Process-Time: 0.123s                    │
└─────────────────────────────────────────────┘
```

---

## Components

### 1. Request ID Middleware (Primary)

**Location:** `src/presentation/api/main.py`

**Implementation:**
```python
import uuid
import time
import traceback
from loguru import logger
from fastapi import Request
from fastapi.responses import JSONResponse

@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    """
    Adds unique request_id and detailed logging.
    CRITICAL for debugging 500 errors.
    """
    # 1. Generate unique request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    
    # 2. Log incoming request
    logger.info(
        f"⬇️  INCOMING REQUEST",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )
    
    try:
        # 3. Process request
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # 4. Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.3f}s"
        
        # 5. Log outgoing response
        logger.info(
            f"⬆️  OUTGOING RESPONSE",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "process_time": f"{process_time:.3f}s",
                "path": request.url.path
            }
        )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        
        # 6. Log unhandled exceptions
        logger.error(
            f"❌ UNHANDLED EXCEPTION IN MIDDLEWARE",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "process_time": f"{process_time:.3f}s",
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )
        
        # 7. Return structured error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": f"An unexpected error occurred: {type(e).__name__}",
                "request_id": request_id,
                "details": str(e) if settings.app_environment == "development" else None
            },
            headers={"X-Request-ID": request_id}
        )
```

**Features:**
- UUID generation with `uuid.uuid4()`
- Attached to `request.state.request_id` for access in routes
- Logs with emojis (⬇️ incoming, ⬆️ outgoing, ❌ errors)
- Exception catching with full traceback
- Development vs production error details

---

### 2. LoggingMiddleware (Legacy)

**Location:** `src/presentation/api/middlewares/logging.py`

**Implementation:**
```python
import time
from typing import Callable
from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for HTTP request logging (backward compatibility)."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        start_time = time.time()
        
        client_host = request.client.host if request.client else "unknown"
        
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"from {client_host}"
        )
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.3f}s"
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"error={str(e)} time={process_time:.3f}s"
            )
            raise
```

**Purpose:** Maintained for backward compatibility. The Request ID middleware (Component 1) is the primary logging system.

---

## Request Lifecycle

### 1. Incoming Request

**Log Example:**
```json
{
  "time": "2024-01-15T14:30:00.123456+00:00",
  "level": "INFO",
  "message": "⬇️  INCOMING REQUEST",
  "extra": {
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "method": "POST",
    "path": "/api/v1/transcribe",
    "query_params": "{}",
    "client_ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  }
}
```

### 2. Outgoing Response (Success)

**Log Example:**
```json
{
  "time": "2024-01-15T14:30:02.456789+00:00",
  "level": "INFO",
  "message": "⬆️  OUTGOING RESPONSE",
  "extra": {
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status_code": 200,
    "process_time": "2.333s",
    "path": "/api/v1/transcribe"
  }
}
```

**Response Headers:**
```http
HTTP/1.1 200 OK
X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
X-Process-Time: 2.333s
```

### 3. Unhandled Exception

**Log Example:**
```json
{
  "time": "2024-01-15T14:30:01.789012+00:00",
  "level": "ERROR",
  "message": "❌ UNHANDLED EXCEPTION IN MIDDLEWARE",
  "extra": {
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "method": "POST",
    "path": "/api/v1/transcribe",
    "process_time": "1.665s",
    "exception_type": "ValueError",
    "exception_message": "Invalid YouTube URL format",
    "traceback": "Traceback (most recent call last):\n  File \"...\", line 123, in transcribe\n    ..."
  }
}
```

**Error Response (Development):**
```json
{
  "error": "InternalServerError",
  "message": "An unexpected error occurred: ValueError",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "details": "Invalid YouTube URL format"
}
```

**Error Response (Production):**
```json
{
  "error": "InternalServerError",
  "message": "An unexpected error occurred: ValueError",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "details": null
}
```

---

## Response Headers

### X-Request-ID

**Purpose:** Unique identifier for request tracing

**Format:** UUID v4 string

**Example:**
```http
X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Usage:**
- Track request across distributed systems
- Correlate logs from different services
- Debug user-reported issues ("My request ID was: ...")
- Link errors to specific user actions

### X-Process-Time

**Purpose:** Request processing duration

**Format:** Seconds with 3 decimal places + "s" suffix

**Example:**
```http
X-Process-Time: 2.333s
```

**Usage:**
- Performance monitoring
- Identify slow endpoints
- SLA tracking
- Client-side timeout configuration

---

## Logging Format

### Structured Logging with Loguru

**Configuration:**
```python
from loguru import logger

# Logs written to:
# - stdout (console)
# - logs/api_{date}.log (file)
# - JSON format for parsing
```

**Log Fields:**
- `time`: ISO 8601 timestamp
- `level`: INFO, WARNING, ERROR, CRITICAL
- `message`: Human-readable description
- `extra`: Dictionary with structured data
  - `request_id`: UUID
  - `method`: HTTP method
  - `path`: URL path
  - `status_code`: HTTP status
  - `process_time`: Duration
  - `client_ip`: Client IP address
  - `user_agent`: Browser/client info
  - `exception_type`: Error class name
  - `traceback`: Stack trace (errors)

---

## Usage Examples

### Example 1: Access Request ID in Route

```python
from fastapi import Request, Depends
from src.presentation.api.dependencies import get_transcribe_use_case

@router.post("/api/v1/transcribe")
async def transcribe_video(
    request: Request,
    dto: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    # Access request ID attached by middleware
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Starting transcription",
        extra={
            "request_id": request_id,
            "youtube_url": dto.youtube_url
        }
    )
    
    try:
        result = await use_case.execute(dto.youtube_url, dto.language)
        return result
    
    except Exception as e:
        logger.error(
            "Transcription failed",
            extra={
                "request_id": request_id,
                "error": str(e)
            }
        )
        raise
```

### Example 2: Propagate Request ID to Dependencies

```python
from src.presentation.api.dependencies import raise_error

def validate_video(url: str, request_id: str):
    """Propagate request ID to error responses."""
    
    if not is_valid_youtube_url(url):
        raise_error(
            status_code=400,
            error_type="ValidationError",
            message="Invalid YouTube URL",
            request_id=request_id,  # Include for tracing
            details={"url": url}
        )
```

### Example 3: Log Aggregation with ELK/Loki

**Docker Compose with Loki:**
```yaml
services:
  api:
    image: ytcaption:2.2
    logging:
      driver: "loki"
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
        loki-external-labels: "service=ytcaption-api"
```

**Query Logs by Request ID (Loki):**
```logql
{service="ytcaption-api"} 
  |= "request_id" 
  |= "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### Example 4: Performance Monitoring

```python
import re
from collections import defaultdict

def analyze_logs(log_file: str):
    """Analyze X-Process-Time from logs."""
    
    endpoint_times = defaultdict(list)
    
    with open(log_file) as f:
        for line in f:
            if "OUTGOING RESPONSE" in line:
                # Extract endpoint and time
                match = re.search(r'"path": "(/api/v1/\w+)".*"process_time": "([\d.]+)s"', line)
                if match:
                    endpoint = match.group(1)
                    time_ms = float(match.group(2)) * 1000
                    endpoint_times[endpoint].append(time_ms)
    
    # Calculate statistics
    for endpoint, times in endpoint_times.items():
        avg = sum(times) / len(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"{endpoint}: avg={avg:.1f}ms, p95={p95:.1f}ms")

# Output:
# /api/v1/transcribe: avg=2330.5ms, p95=4567.2ms
# /api/v1/video/info: avg=1200.3ms, p95=2100.5ms
# /health: avg=12.5ms, p95=45.2ms
```

### Example 5: Client-Side Request Tracking

**JavaScript:**
```javascript
async function transcribeVideo(url) {
  const response = await fetch('/api/v1/transcribe', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({youtube_url: url})
  });
  
  // Extract request ID from response
  const requestId = response.headers.get('X-Request-ID');
  const processTime = response.headers.get('X-Process-Time');
  
  console.log(`Request ${requestId} completed in ${processTime}`);
  
  if (!response.ok) {
    const error = await response.json();
    console.error(`Error (${requestId}): ${error.message}`);
    // User can report: "My request ID: {requestId}"
  }
  
  return response.json();
}
```

---

## Testing

### Unit Test Example

```python
# tests/unit/test_logging_middleware.py
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)

def test_request_id_header_added():
    """Test that X-Request-ID header is added to responses."""
    response = client.get("/health")
    
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length

def test_process_time_header_added():
    """Test that X-Process-Time header is added."""
    response = client.get("/health")
    
    assert "X-Process-Time" in response.headers
    assert response.headers["X-Process-Time"].endswith("s")
    
    time_value = float(response.headers["X-Process-Time"].rstrip("s"))
    assert 0 < time_value < 10  # Reasonable range

def test_request_id_unique_per_request():
    """Test that each request gets a unique ID."""
    response1 = client.get("/health")
    response2 = client.get("/health")
    
    id1 = response1.headers["X-Request-ID"]
    id2 = response2.headers["X-Request-ID"]
    
    assert id1 != id2

def test_error_includes_request_id():
    """Test that errors include request_id in response."""
    response = client.post("/api/v1/transcribe", json={
        "youtube_url": "invalid-url"
    })
    
    assert response.status_code == 400
    error = response.json()
    
    assert "request_id" in error
    assert error["request_id"] == response.headers["X-Request-ID"]
```

### Integration Test with Logging

```python
# tests/integration/test_logging.py
import json
from io import StringIO
from loguru import logger

def test_request_logging(tmp_path):
    """Test that requests are logged with correct format."""
    
    log_file = tmp_path / "test.log"
    
    # Configure logger to write to test file
    logger.add(log_file, format="{message}", serialize=True)
    
    # Make request
    response = client.get("/health")
    
    # Read logs
    with open(log_file) as f:
        logs = [json.loads(line) for line in f if line.strip()]
    
    # Find incoming request log
    incoming = next(
        (log for log in logs if "INCOMING REQUEST" in log["message"]),
        None
    )
    
    assert incoming is not None
    assert incoming["extra"]["method"] == "GET"
    assert incoming["extra"]["path"] == "/health"
    assert "request_id" in incoming["extra"]
```

---

## Related Documentation

- **Dependencies**: `docs-en/architecture/presentation/dependencies.md` (raise_error helper)
- **Metrics Module**: `docs-en/architecture/infrastructure/monitoring/metrics.md` (Prometheus integration)
- **Error Handling**: `src/application/dtos/transcription_dtos.py` (ErrorResponseDTO)
- **Loguru Docs**: https://loguru.readthedocs.io/

---

## Best Practices

### ✅ DO
- Always propagate `request_id` to error responses
- Log at INFO level for normal requests
- Log at ERROR level for exceptions
- Include request_id in structured logs (extra field)
- Use request_id for distributed tracing
- Add timing information for performance monitoring
- Sanitize sensitive data before logging (passwords, tokens)

### ❌ DON'T
- Don't log request/response bodies without sanitization
- Don't create new request IDs in routes (use middleware's)
- Don't log health check requests (spam)
- Don't expose sensitive error details in production
- Don't forget to include exc_info=True for exception logs
- Don't modify request_id after it's set
- Don't log passwords, API keys, or tokens

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Added Request ID middleware, unhandled exception logging |
| v2.1 | 2024 | Enhanced structured logging with Loguru |
| v2.0 | 2024 | Added X-Process-Time header, improved error handling |
| v1.0 | 2023 | Initial LoggingMiddleware implementation |
