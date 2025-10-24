# FastAPI Dependency Injection Container

## Overview

The **Dependencies** module implements a centralized **Dependency Injection Container** for managing service lifecycles in the FastAPI application. It follows the **Singleton pattern** to ensure that critical services (especially the worker pool) are shared across all HTTP requests, preventing resource duplication and memory leaks.

**Key Features:**
- 🏗️ **Singleton Pattern** - One instance per service across all requests
- 🔌 **Interface-Based DI** - Depends on abstractions, not implementations
- 🎯 **SOLID Principles** - Dependency Inversion Principle (DIP)
- 🚀 **Lazy Initialization** - Services created only when needed
- 🔄 **Worker Pool Sharing** - Critical for parallel transcription
- ⚡ **FastAPI Integration** - Dependency functions for route injection
- 🛡️ **Error Helpers** - Standardized HTTP exception raising

**Version:** v2.2.1 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│   Presentation Layer (FastAPI Routes)      │
│   - /api/v1/transcribe                      │
│   - /api/v1/video/info                      │
│   - /health                                 │
└─────────────────────────────────────────────┘
                    ↓ Depends()
┌─────────────────────────────────────────────┐
│   DEPENDENCY INJECTION (THIS MODULE)        │◄─── FastAPI DI System
│  ┌─────────────────────────────────────┐   │
│  │   Container (Singleton Factory)      │   │
│  │   - get_video_downloader()           │   │
│  │   - get_transcription_service()      │   │
│  │   - get_storage_service()            │   │
│  │   - get_transcribe_use_case()        │   │
│  │   - get_cleanup_use_case()           │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │   FastAPI Dependency Functions       │   │
│  │   - get_transcribe_use_case()        │   │
│  │   - get_cleanup_use_case()           │   │
│  │   - get_storage_service()            │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │   Error Helpers                      │   │
│  │   - raise_error()                    │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Application & Infrastructure Layers      │
│   - Use Cases                               │
│   - Domain Services                         │
│   - Infrastructure Implementations          │
└─────────────────────────────────────────────┘
```

---

## Core Components

### 1. Container Class

**Purpose:** Centralized singleton factory for all application services.

**Critical Design Decision:**
```python
# ✅ CORRECT: Singleton pattern
_transcription_service: ITranscriptionService = None

# ❌ WRONG: New instance per request
def get_service():
    return TranscriptionService()  # Creates new worker pool!
```

**Why Singleton?**
- **Worker Pool Sharing**: Parallel transcription uses a persistent worker pool that MUST be shared
- **Memory Efficiency**: Avoid creating duplicate heavy services (Whisper models)
- **Connection Pooling**: YouTube downloader may cache connections
- **State Persistence**: Caches and metrics must persist across requests

---

### 2. Service Factories

#### get_video_downloader()

```python
@classmethod
def get_video_downloader(cls) -> IVideoDownloader:
    if cls._video_downloader is None:
        cls._video_downloader = YouTubeDownloader(
            max_filesize=settings.max_video_size_mb * 1024 * 1024,
            timeout=settings.download_timeout
        )
    return cls._video_downloader
```

**Returns:** `IVideoDownloader` (YouTubeDownloader implementation)

**Configuration:**
- `max_filesize`: From `MAX_VIDEO_SIZE_MB` env var
- `timeout`: From `DOWNLOAD_TIMEOUT` env var

**Thread Safety:** ✅ Safe (class variable access is atomic in Python)

---

#### get_transcription_service()

```python
@classmethod
def get_transcription_service(cls) -> ITranscriptionService:
    if cls._transcription_service is None:
        cls._transcription_service = create_transcription_service()
    return cls._transcription_service
```

**Returns:** `ITranscriptionService` (WhisperTranscriptionService or ParallelTranscriptionService)

**Critical Implementation:**
- **Lazy Initialization**: Created only when first requested
- **Worker Pool**: For parallel mode, ensures single shared pool
- **Factory Method**: Uses `create_transcription_service()` to select implementation

**Why It Matters:**
```python
# ❌ PROBLEM if not singleton:
# Request 1 creates worker pool A (4 processes)
# Request 2 creates worker pool B (4 processes)
# Result: 8 processes instead of 4 → memory leak

# ✅ SOLUTION with singleton:
# Request 1 creates worker pool (4 processes)
# Request 2 reuses same pool (still 4 processes)
```

---

#### get_storage_service()

```python
@classmethod
def get_storage_service(cls) -> IStorageService:
    if cls._storage_service is None:
        cls._storage_service = LocalStorageService(
            base_temp_dir=settings.temp_dir
        )
    return cls._storage_service
```

**Returns:** `IStorageService` (LocalStorageService implementation)

**Configuration:**
- `base_temp_dir`: From `TEMP_DIR` env var (default: `./temp`)

---

### 3. Use Case Factories

#### get_transcribe_use_case()

```python
@classmethod
def get_transcribe_use_case(cls) -> TranscribeYouTubeVideoUseCase:
    if cls._transcribe_use_case is None:
        cls._transcribe_use_case = TranscribeYouTubeVideoUseCase(
            video_downloader=cls.get_video_downloader(),
            transcription_service=cls.get_transcription_service(),
            storage_service=cls.get_storage_service(),
            cleanup_after_processing=settings.cleanup_after_processing,
            max_video_duration=settings.max_video_duration_seconds,
            audio_validator=audio_validator,        # v2.0
            transcription_cache=transcription_cache  # v2.0
        )
    return cls._transcribe_use_case
```

**Returns:** `TranscribeYouTubeVideoUseCase`

**Dependencies:**
- Video downloader (singleton)
- Transcription service (singleton)
- Storage service (singleton)
- Audio validator (from main.py)
- Transcription cache (from main.py)

**Configuration:**
- `cleanup_after_processing`: Auto-delete files after transcription
- `max_video_duration`: Maximum video duration in seconds

---

#### get_cleanup_use_case()

```python
@classmethod
def get_cleanup_use_case(cls) -> CleanupOldFilesUseCase:
    if cls._cleanup_use_case is None:
        cls._cleanup_use_case = CleanupOldFilesUseCase(
            storage_service=cls.get_storage_service(),
            max_age_hours=settings.max_temp_age_hours
        )
    return cls._cleanup_use_case
```

**Returns:** `CleanupOldFilesUseCase`

**Configuration:**
- `max_age_hours`: Delete files older than this threshold

---

## FastAPI Dependency Functions

These functions are used with `Depends()` in FastAPI routes:

### get_transcribe_use_case()

```python
def get_transcribe_use_case() -> TranscribeYouTubeVideoUseCase:
    return Container.get_transcribe_use_case()
```

**Usage in Routes:**
```python
from fastapi import Depends
from src.presentation.api.dependencies import get_transcribe_use_case

@router.post("/api/v1/transcribe")
async def transcribe_video(
    request: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    result = await use_case.execute(request.youtube_url, request.language)
    return result
```

### get_cleanup_use_case()

```python
def get_cleanup_use_case() -> CleanupOldFilesUseCase:
    return Container.get_cleanup_use_case()
```

**Usage in Routes:**
```python
@router.post("/cleanup")
async def cleanup_files(
    use_case: CleanupOldFilesUseCase = Depends(get_cleanup_use_case)
):
    await use_case.execute()
```

### get_storage_service()

```python
def get_storage_service() -> IStorageService:
    return Container.get_storage_service()
```

**Usage in Routes:**
```python
@router.get("/health")
async def health_check(
    storage: IStorageService = Depends(get_storage_service)
):
    usage = await storage.get_storage_usage()
    return {"storage": usage}
```

---

## Error Handling Helper

### raise_error()

**Purpose:** Standardized HTTP exception raising with `ErrorResponseDTO`.

**Function Signature:**
```python
def raise_error(
    status_code: int,
    error_type: str,
    message: str,
    request_id: str,
    details: Optional[Dict[str, Any]] = None
) -> None
```

**Parameters:**
- `status_code` (int): HTTP status code (400, 404, 500, etc.)
- `error_type` (str): Error class name (e.g., `"AudioTooLongError"`)
- `message` (str): Human-readable error message
- `request_id` (str): Request tracking ID
- `details` (dict): Additional error context (optional)

**Raises:** `HTTPException` with standardized detail format

### Example Usage

```python
from src.presentation.api.dependencies import raise_error

def validate_video_duration(duration: float, request_id: str):
    MAX_DURATION = 7200  # 2 hours
    
    if duration > MAX_DURATION:
        raise_error(
            status_code=400,
            error_type="AudioTooLongError",
            message=f"Audio exceeds maximum duration of {MAX_DURATION}s",
            request_id=request_id,
            details={
                "duration": duration,
                "max_duration": MAX_DURATION,
                "video_length_formatted": f"{duration/60:.1f} minutes"
            }
        )
```

**Generated HTTP Response:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "AudioTooLongError",
  "message": "Audio exceeds maximum duration of 7200s",
  "request_id": "abc-123-def",
  "details": {
    "duration": 7250.5,
    "max_duration": 7200,
    "video_length_formatted": "120.8 minutes"
  }
}
```

---

## Configuration

All services are configured via environment variables in `settings.py`:

| Service | Environment Variable | Default |
|---------|---------------------|---------|
| VideoDownloader | `MAX_VIDEO_SIZE_MB` | 500 MB |
| VideoDownloader | `DOWNLOAD_TIMEOUT` | 300s |
| StorageService | `TEMP_DIR` | `./temp` |
| TranscribeUseCase | `CLEANUP_AFTER_PROCESSING` | `true` |
| TranscribeUseCase | `MAX_VIDEO_DURATION_SECONDS` | 7200s |
| CleanupUseCase | `MAX_TEMP_AGE_HOURS` | 24h |

---

## Usage Examples

### Example 1: Route with Dependency Injection

```python
from fastapi import APIRouter, Depends
from src.presentation.api.dependencies import get_transcribe_use_case
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

router = APIRouter()

@router.post("/api/v1/transcribe")
async def transcribe_video(
    request: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    """
    Transcribe YouTube video.
    
    The use_case is automatically injected by FastAPI.
    It's a singleton, so all requests share the same instance.
    """
    result = await use_case.execute(
        youtube_url=request.youtube_url,
        language=request.language
    )
    
    return {
        "transcription_id": result.transcription_id,
        "text": result.text,
        "language": result.language
    }
```

### Example 2: Multiple Dependencies

```python
from fastapi import Depends
from src.presentation.api.dependencies import (
    get_storage_service,
    get_transcribe_use_case
)

@router.get("/stats")
async def get_statistics(
    storage: IStorageService = Depends(get_storage_service),
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    """Multiple dependencies injected simultaneously."""
    
    storage_stats = await storage.get_storage_usage()
    
    # Access transcription service from use case
    transcription_service = use_case.transcription_service
    
    return {
        "storage": storage_stats,
        "service_type": type(transcription_service).__name__
    }
```

### Example 3: Error Handling with raise_error()

```python
from fastapi import Request, Depends
from src.presentation.api.dependencies import (
    get_transcribe_use_case,
    raise_error
)
from src.domain.exceptions import VideoDownloadError

@router.post("/api/v1/transcribe")
async def transcribe_video(
    request: Request,
    dto: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        result = await use_case.execute(dto.youtube_url, dto.language)
        return result
    
    except VideoDownloadError as e:
        raise_error(
            status_code=404,
            error_type="VideoDownloadError",
            message=str(e),
            request_id=request_id,
            details={"url": dto.youtube_url}
        )
    
    except Exception as e:
        raise_error(
            status_code=500,
            error_type="InternalServerError",
            message="Failed to transcribe video",
            request_id=request_id,
            details={"error": str(e)}
        )
```

### Example 4: Testing with Dependency Override

```python
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app
from src.presentation.api.dependencies import get_transcribe_use_case

# Mock use case
class MockTranscribeUseCase:
    async def execute(self, url: str, language: str):
        return MockTranscriptionResult()

def get_mock_use_case():
    return MockTranscribeUseCase()

# Override dependency for testing
app.dependency_overrides[get_transcribe_use_case] = get_mock_use_case

client = TestClient(app)

def test_transcribe_with_mock():
    response = client.post("/api/v1/transcribe", json={
        "youtube_url": "https://youtube.com/watch?v=test"
    })
    
    assert response.status_code == 200
```

### Example 5: Manual Service Access (Advanced)

```python
from src.presentation.api.dependencies import Container

# Direct access to services (outside FastAPI context)
def background_cleanup_task():
    """Background task that accesses services directly."""
    
    storage_service = Container.get_storage_service()
    cleanup_use_case = Container.get_cleanup_use_case()
    
    # Perform cleanup
    await cleanup_use_case.execute()
    
    # Get storage stats
    stats = await storage_service.get_storage_usage()
    print(f"Cleanup completed. Storage: {stats['total_size_mb']:.1f} MB")
```

---

## Thread Safety

### Singleton Pattern Thread Safety

**Python's Class Variables:**
```python
class Container:
    _service: Service = None  # Class variable
    
    @classmethod
    def get_service(cls):
        if cls._service is None:  # ⚠️ Potential race condition
            cls._service = Service()  # Multiple threads could enter here
        return cls._service
```

**Issue:** Not thread-safe in multi-threaded environments (Uvicorn workers).

**Solutions:**

#### 1. Thread-Safe Singleton (Production)

```python
import threading

class Container:
    _service: Service = None
    _lock = threading.Lock()
    
    @classmethod
    def get_service(cls):
        if cls._service is None:
            with cls._lock:  # Double-checked locking
                if cls._service is None:
                    cls._service = Service()
        return cls._service
```

#### 2. FastAPI Lifespan (Recommended)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize services ONCE at startup
    Container.get_transcription_service()
    Container.get_storage_service()
    yield
    # Cleanup at shutdown

app = FastAPI(lifespan=lifespan)
```

**Current Implementation:**
- Uses simple class variables (acceptable for Uvicorn single-worker mode)
- Services created lazily on first request
- No explicit locking (Python GIL provides basic protection)

---

## Related Documentation

- **Use Cases**: `src/application/use_cases/` (Business logic)
- **Interfaces**: `src/domain/interfaces/` (Abstractions)
- **Implementations**: `src/infrastructure/` (Concrete classes)
- **Configuration**: `docs-en/architecture/config/README.md` (Environment settings)
- **Error Handling**: `src/application/dtos/transcription_dtos.py` (ErrorResponseDTO)

---

## Best Practices

### ✅ DO
- Use `Depends()` for route dependencies
- Access services via Container in non-route code
- Use `raise_error()` for consistent error responses
- Test with dependency overrides
- Initialize heavy services in `lifespan()` for production
- Keep Container methods simple (no business logic)
- Use interfaces (`IService`) not concrete classes

### ❌ DON'T
- Don't create services manually in routes (`service = Service()`)
- Don't bypass Container singleton pattern
- Don't store request-specific state in Container
- Don't use Container for request-scoped dependencies
- Don't forget to propagate request_id in errors
- Don't mix sync/async service calls
- Don't create new Container instances

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2.1 | 2024 | Added `raise_error()` helper for standardized exceptions |
| v2.2 | 2024 | Enhanced logging, improved worker pool management |
| v2.0 | 2024 | Added audio validator and transcription cache injection |
| v1.0 | 2023 | Initial dependency injection container |
