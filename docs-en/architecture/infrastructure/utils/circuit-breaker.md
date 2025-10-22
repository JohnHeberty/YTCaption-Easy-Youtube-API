# Circuit Breaker Pattern

## Overview

The **CircuitBreaker** implements the Circuit Breaker pattern to protect the application from cascading failures when external services (YouTube API, storage, etc.) become unstable. It automatically detects repeated failures, temporarily blocks requests to failing services, and periodically tests for recovery.

**Key Features:**
- 🔒 **Automatic Fault Detection** - Monitors failure patterns
- 🚫 **Fast Fail** - Blocks requests during outages (no waiting)
- 🔄 **Auto Recovery Testing** - Periodically checks if service recovered
- 📊 **Sliding Window Monitoring** - Tracks call history for failure rate
- 🔐 **Thread-Safe** - RLock for concurrent access
- 📈 **Statistics Tracking** - Detailed metrics for monitoring

**Three States:**
1. **CLOSED** (Normal): All calls pass through
2. **OPEN** (Blocking): Service unavailable, reject all calls
3. **HALF_OPEN** (Testing): Allow limited calls to test recovery

**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│       Presentation Layer                    │
│  ┌─────────────────────────────────────┐   │
│  │   API Endpoints                      │   │
│  │   - /api/v1/transcribe               │   │
│  │   - /api/v1/video-info               │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Application Layer                     │
│  ┌─────────────────────────────────────┐   │
│  │   TranscribeVideoUseCase            │   │
│  │   - Orchestrates operations          │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Infrastructure Layer                  │
│  ┌─────────────────────────────────────┐   │
│  │   YouTubeDownloader                  │◄──┼─── Protected by CircuitBreaker
│  │   (Protected Service)                │   │
│  └─────────────────────────────────────┘   │
│                                              │
│  ┌─────────────────────────────────────┐   │
│  │   CircuitBreaker (THIS MODULE)      │   │
│  │   - State management                 │   │
│  │   - Failure detection                │   │
│  │   - Auto recovery testing            │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Protected Services:**
- YouTube Downloader (`YouTubeDownloader`)
- External transcription APIs
- Storage services
- Any external dependency

---

## Circuit States

### State Machine Diagram

```
     ┌─────────┐
     │ CLOSED  │  (Normal operation)
     └────┬────┘
          │
          │ ≥ failure_threshold failures
          ↓
     ┌─────────┐
     │  OPEN   │  (Blocking all requests)
     └────┬────┘
          │
          │ timeout_seconds elapsed
          ↓
   ┌──────────────┐
   │  HALF_OPEN   │  (Testing recovery)
   └──┬────────┬──┘
      │        │
      │        │ Any failure → OPEN
      │        │
      │        │ success_threshold successes
      │        ↓
      └─────→ CLOSED
```

### State Descriptions

#### 1. CLOSED (Normal Operation)

**Behavior:**
- All calls pass through normally
- Monitors failure count
- Resets failure count on successful calls

**Transition to OPEN:**
- When `failure_count >= failure_threshold`

**Example:**
```
CLOSED → failure → failure → failure → failure → failure → OPEN
         (count=1)  (count=2)  (count=3)  (count=4)  (count=5)
```

#### 2. OPEN (Blocking)

**Behavior:**
- **Rejects ALL calls immediately** without attempting
- Throws `CircuitBreakerOpenError`
- Returns `Retry-After` header value
- Waits for `timeout_seconds` before testing recovery

**Transition to HALF_OPEN:**
- When `timeout_seconds` elapsed since last failure

**Example:**
```
OPEN (t=0s) → OPEN (t=30s) → OPEN (t=59s) → HALF_OPEN (t=60s)
```

**Fast Fail Benefit:**
- No wasted time waiting for failing service
- Preserves system resources
- Better user experience (immediate error response)

#### 3. HALF_OPEN (Testing Recovery)

**Behavior:**
- Allows **limited** number of test calls (`half_open_max_calls`)
- First failure → immediately OPEN again
- Track successes toward threshold

**Transition to CLOSED:**
- When `success_count >= success_threshold`

**Transition to OPEN:**
- On **any** failure during testing

**Example (Success):**
```
HALF_OPEN → success (1/2) → success (2/2) → CLOSED ✅
```

**Example (Failure):**
```
HALF_OPEN → success (1/2) → failure → OPEN ❌
```

---

## Configuration Parameters

### Constructor Parameters

```python
CircuitBreaker(
    name: str,                      # Service name (for logging)
    failure_threshold: int = 5,     # Failures before opening
    timeout_seconds: int = 60,      # Time in OPEN before testing
    half_open_max_calls: int = 3,   # Max calls during testing
    success_threshold: int = 2,     # Successes needed to close
    window_size: int = 10           # Sliding window size
)
```

**Parameter Recommendations:**

| Service Type | failure_threshold | timeout_seconds | half_open_max_calls | success_threshold |
|--------------|-------------------|-----------------|---------------------|-------------------|
| **YouTube API** | 5 | 60 | 3 | 2 |
| **Internal Service** | 3 | 30 | 2 | 2 |
| **Database** | 10 | 120 | 5 | 3 |
| **Critical Service** | 8 | 90 | 4 | 3 |

**Tuning Guidelines:**
- **Lower** `failure_threshold` → More sensitive to failures
- **Higher** `timeout_seconds` → Longer recovery testing interval
- **Lower** `half_open_max_calls` → Cautious recovery testing
- **Higher** `success_threshold` → More confident recovery confirmation

---

## Core Methods

### 1. Call Protection

#### `call(func: Callable, *args, **kwargs) -> Any`

Executes function protected by circuit breaker.

**Algorithm:**
```python
1. Check state:
   - OPEN → Raise CircuitBreakerOpenError (fast fail)
   - HALF_OPEN → Check if within max_calls limit
   - CLOSED → Proceed

2. Execute function:
   try:
       result = func(*args, **kwargs)
       _on_success()
       return result
   except Exception as e:
       _on_failure(e)
       raise

3. Update state based on result
```

**Usage:**
```python
breaker = CircuitBreaker(
    name="youtube_api",
    failure_threshold=5,
    timeout_seconds=60
)

# Protect synchronous function
def download_video(url: str):
    result = breaker.call(youtube_downloader.download, url)
    return result

# Protect async function (use separate async circuit breaker)
```

**Exceptions:**
- `CircuitBreakerOpenError` - Circuit is OPEN, service unavailable
- Original exceptions - Passed through from protected function

---

### 2. State Transitions

#### `_transition_to_open()`

Transitions circuit to OPEN state.

**Actions:**
1. Set `state = OPEN`
2. Increment `state_changes`
3. Reset `half_open_calls` and `success_count`
4. Log error with failure count

**Trigger:**
- `failure_count >= failure_threshold` in CLOSED state
- Any failure in HALF_OPEN state

#### `_transition_to_half_open()`

Transitions circuit to HALF_OPEN for recovery testing.

**Actions:**
1. Set `state = HALF_OPEN`
2. Reset `half_open_calls` and `success_count`
3. Log info with test parameters

**Trigger:**
- `timeout_seconds` elapsed in OPEN state

#### `_transition_to_closed()`

Transitions circuit back to CLOSED (normal operation).

**Actions:**
1. Set `state = CLOSED`
2. Reset all counters
3. Log success recovery message

**Trigger:**
- `success_count >= success_threshold` in HALF_OPEN state

---

### 3. Success/Failure Callbacks

#### `_on_success()`

Called after successful function execution.

**Behavior by State:**

**CLOSED:**
- Reset `failure_count = 0`
- Add `True` to sliding window

**HALF_OPEN:**
- Increment `success_count`
- Check if `success_count >= success_threshold`
- If yes → Transition to CLOSED

**OPEN:**
- Not called (calls blocked)

#### `_on_failure(exception: Exception)`

Called after function execution fails.

**Behavior by State:**

**CLOSED:**
- Increment `failure_count`
- Update `last_failure_time`
- Check if `failure_count >= failure_threshold`
- If yes → Transition to OPEN

**HALF_OPEN:**
- Immediately transition to OPEN (any failure = service still unstable)

**OPEN:**
- Not called (calls blocked)

---

### 4. Timing Methods

#### `_should_attempt_reset() -> bool`

Checks if enough time has passed to attempt recovery.

**Logic:**
```python
if not last_failure_time:
    return True

time_since_failure = now - last_failure_time
return time_since_failure >= timeout
```

#### `_time_until_retry() -> float`

Returns seconds until next retry attempt.

**Usage:**
```python
try:
    result = breaker.call(service_func)
except CircuitBreakerOpenError as e:
    print(f"Service unavailable. Retry in {e.retry_after:.0f}s")
```

---

### 5. Management Methods

#### `reset()`

Manually resets circuit breaker to CLOSED state.

**Use Cases:**
- After manual service recovery
- Testing
- Administrative override

**Usage:**
```python
# After fixing external service
breaker.reset()
logger.info("Circuit breaker manually reset after service recovery")
```

#### `get_stats() -> dict`

Returns comprehensive circuit breaker statistics.

**Returns:**
```python
{
    "name": "youtube_api",
    "state": "closed",
    "total_calls": 1523,
    "total_successes": 1498,
    "total_failures": 25,
    "current_failure_count": 0,
    "failure_threshold": 5,
    "last_failure_time": "2024-01-15T14:32:10",
    "time_until_retry": 0,
    "state_changes": 8,
    "window_size": 10,
    "failure_rate_percent": 1.64,
    "half_open_calls": 0
}
```

---

## Usage Patterns

### Pattern 1: YouTube Downloader Protection

```python
from src.infrastructure.utils.circuit_breaker import CircuitBreaker
from src.infrastructure.youtube.downloader import YouTubeDownloader

class ProtectedYouTubeDownloader:
    def __init__(self):
        self.downloader = YouTubeDownloader()
        self.circuit_breaker = CircuitBreaker(
            name="youtube_api",
            failure_threshold=5,
            timeout_seconds=60,
            half_open_max_calls=3,
            success_threshold=2
        )
    
    async def download(self, url: str) -> Path:
        """Download video with circuit breaker protection."""
        try:
            # Wrap download call
            def _download():
                return self.downloader.download_sync(url)
            
            result = self.circuit_breaker.call(_download)
            return result
        
        except CircuitBreakerOpenError as e:
            logger.error(f"YouTube service unavailable: {e}")
            raise ServiceUnavailableError(
                "youtube_api",
                f"YouTube download service temporarily unavailable. Retry in {e.retry_after:.0f}s"
            )
```

### Pattern 2: Multiple Protected Services

```python
class ServiceRegistry:
    """Registry of circuit breakers for multiple services."""
    
    def __init__(self):
        self.breakers = {
            "youtube_api": CircuitBreaker(
                name="youtube_api",
                failure_threshold=5,
                timeout_seconds=60
            ),
            "storage_service": CircuitBreaker(
                name="storage_service",
                failure_threshold=3,
                timeout_seconds=30
            ),
            "transcription_cache": CircuitBreaker(
                name="transcription_cache",
                failure_threshold=10,
                timeout_seconds=120
            )
        }
    
    def get_breaker(self, service_name: str) -> CircuitBreaker:
        return self.breakers.get(service_name)
    
    def get_all_stats(self) -> dict:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }
```

### Pattern 3: Monitoring Integration

```python
import asyncio
from src.infrastructure.monitoring.metrics import MetricsCollector

async def monitor_circuit_breakers():
    """Background task to report circuit breaker metrics."""
    registry = ServiceRegistry()
    
    while True:
        for name, breaker in registry.breakers.items():
            stats = breaker.get_stats()
            
            # Update Prometheus metrics
            state_value = {
                "closed": 0,
                "half_open": 1,
                "open": 2
            }[stats["state"]]
            
            MetricsCollector.update_circuit_breaker_state(
                circuit_name=name,
                state=CircuitBreakerState(state_value)
            )
            
            # Log if OPEN
            if stats["state"] == "open":
                logger.warning(
                    f"Circuit breaker OPEN: {name}",
                    extra={
                        "retry_in": stats["time_until_retry"],
                        "total_failures": stats["total_failures"]
                    }
                )
        
        await asyncio.sleep(10)  # Update every 10 seconds

# Start monitoring
asyncio.create_task(monitor_circuit_breakers())
```

### Pattern 4: Decorator Pattern (Advanced)

```python
def circuit_breaker(name: str, **kwargs):
    """Decorator for protecting functions with circuit breaker."""
    breaker = CircuitBreaker(name=name, **kwargs)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@circuit_breaker(name="youtube_api", failure_threshold=5, timeout_seconds=60)
def download_video(url: str):
    return youtube_downloader.download(url)
```

---

## Exception Handling

### CircuitBreakerOpenError

```python
class CircuitBreakerOpenError(ServiceUnavailableError):
    """Raised when circuit breaker is OPEN."""
    
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after  # Seconds until retry
```

**Handling Example:**
```python
from fastapi import HTTPException

async def transcribe_endpoint(request: TranscriptionRequest):
    try:
        result = await transcription_service.transcribe(request.url)
        return result
    
    except CircuitBreakerOpenError as e:
        # Return 503 Service Unavailable with Retry-After header
        raise HTTPException(
            status_code=503,
            detail=f"{e.service_name} temporarily unavailable",
            headers={"Retry-After": str(int(e.retry_after))}
        )
```

---

## Thread Safety

**Mechanism:** `threading.RLock()` (Reentrant Lock)

**Protected Operations:**
- State transitions
- Counter updates
- Statistics access

**Usage:**
```python
with self.lock:
    self.state = CircuitState.OPEN
    self.failure_count = 0
    # ... atomic state changes
```

**Thread-Safe Methods:**
- `call()` - Protected execution
- `_on_success()` - Safe counter updates
- `_on_failure()` - Safe state transitions
- `get_stats()` - Consistent snapshot
- `reset()` - Safe manual reset

---

## Testing

### Unit Test Example

```python
# tests/unit/test_circuit_breaker.py
import pytest
from src.infrastructure.utils.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError

def test_initial_state():
    """Test circuit breaker starts in CLOSED state."""
    breaker = CircuitBreaker(name="test", failure_threshold=3)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0

def test_transition_to_open():
    """Test circuit opens after threshold failures."""
    breaker = CircuitBreaker(name="test", failure_threshold=3)
    
    def failing_func():
        raise Exception("Service error")
    
    # Trigger failures
    for i in range(3):
        with pytest.raises(Exception):
            breaker.call(failing_func)
    
    # Should be OPEN after 3 failures
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3

def test_open_blocks_calls():
    """Test OPEN circuit blocks calls with CircuitBreakerOpenError."""
    breaker = CircuitBreaker(name="test", failure_threshold=2, timeout_seconds=60)
    
    # Force to OPEN
    def failing_func():
        raise Exception("Error")
    
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_func)
    
    # Next call should be blocked
    def success_func():
        return "success"
    
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        breaker.call(success_func)
    
    assert exc_info.value.service_name == "test"
    assert exc_info.value.retry_after > 0

def test_half_open_recovery():
    """Test HALF_OPEN state allows limited calls."""
    breaker = CircuitBreaker(
        name="test",
        failure_threshold=2,
        timeout_seconds=1,  # 1 second timeout
        success_threshold=2
    )
    
    # Open circuit
    def failing_func():
        raise Exception("Error")
    
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for timeout
    import time
    time.sleep(1.1)
    
    # Next call should trigger HALF_OPEN
    def success_func():
        return "success"
    
    # First success in HALF_OPEN
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == CircuitState.HALF_OPEN
    
    # Second success → CLOSED
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED

def test_reset():
    """Test manual reset."""
    breaker = CircuitBreaker(name="test", failure_threshold=2)
    
    # Open circuit
    def failing_func():
        raise Exception("Error")
    
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Manual reset
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0

def test_statistics():
    """Test get_stats() returns correct data."""
    breaker = CircuitBreaker(name="test", failure_threshold=3)
    
    stats = breaker.get_stats()
    
    assert stats["name"] == "test"
    assert stats["state"] == "closed"
    assert stats["total_calls"] == 0
    assert stats["failure_threshold"] == 3
```

---

## Related Documentation

- **Service Exceptions**: `src/domain/exceptions.py` (ServiceUnavailableError)
- **Prometheus Metrics**: `docs-en/architecture/infrastructure/monitoring/metrics.md` (Circuit breaker metrics)
- **YouTube Downloader**: `src/infrastructure/youtube/downloader.py` (Main protected service)
- **API Error Handling**: `docs-en/08-TROUBLESHOOTING.md`

---

## Best Practices

### ✅ DO
- Use different thresholds for different service types
- Monitor circuit breaker states with Prometheus
- Log state transitions for debugging
- Return `Retry-After` headers in HTTP 503 responses
- Reset manually only after confirming service recovery
- Set appropriate timeout based on service recovery time

### ❌ DON'T
- Don't use same circuit breaker instance for multiple services
- Don't set `failure_threshold` too low (avoid false positives)
- Don't set `timeout_seconds` too short (service needs time to recover)
- Don't ignore `CircuitBreakerOpenError` (handle gracefully)
- Don't wrap non-failing operations (adds unnecessary overhead)
- Don't manually force states (use reset() only)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Initial Circuit Breaker implementation with 3-state FSM |
| v2.1 | 2024 | Added Prometheus metrics integration |
| v2.0 | 2024 | YouTube Resilience v3.0 pattern |
