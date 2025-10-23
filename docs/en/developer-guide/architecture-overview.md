# 🏛️ Architecture Overview

Complete guide to YTCaption's Clean Architecture implementation with SOLID principles.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Clean Architecture](#clean-architecture)
3. [SOLID Principles](#solid-principles)
4. [Project Structure](#project-structure)
5. [Layers in Detail](#layers-in-detail)
6. [Data Flow](#data-flow)
7. [Dependency Injection](#dependency-injection)
8. [Design Patterns](#design-patterns)
9. [Adding New Features](#adding-new-features)
10. [Best Practices](#best-practices)

---

## Overview

YTCaption follows **Clean Architecture** with **SOLID principles** to ensure:

- ✅ **Separation of concerns**: Each layer has a specific responsibility
- ✅ **Testability**: Easy to write unit and integration tests
- ✅ **Maintainability**: Easy to understand and modify code
- ✅ **Framework independence**: Business logic doesn't depend on frameworks
- ✅ **Scalability**: Easy to add new features without breaking existing ones

**Key architectural decisions**:
- **Domain-Driven Design (DDD)**: Business logic in Domain layer
- **Dependency Inversion**: Depend on interfaces, not implementations
- **Use Case Pattern**: Each feature is a separate use case
- **Repository Pattern**: Abstract data access
- **Strategy Pattern**: Multiple download strategies (v3.0)
- **Circuit Breaker Pattern**: Resilience against failures (v3.0)

---

## Clean Architecture

### Layers (Inside-Out)

```
┌────────────────────────────────────────────────────┐
│              4. Infrastructure                     │  ← Frameworks, External tools
│   (FastAPI, Whisper, YouTube, FFmpeg, Tor)        │
├────────────────────────────────────────────────────┤
│         3. Presentation (Interface Adapters)       │  ← API Controllers, DTOs
│              (Routes, Schemas)                     │
├────────────────────────────────────────────────────┤
│          2. Application (Use Cases)                │  ← Business workflows
│   (TranscribeVideo, DownloadAudio, CleanupFiles)  │
├────────────────────────────────────────────────────┤
│         1. Domain (Enterprise Business Rules)      │  ← Core business logic
│   (Entities, Value Objects, Interfaces, Rules)    │
└────────────────────────────────────────────────────┘
```

### Dependency Rule

**Dependencies always point inward**:

```
Infrastructure ───→ Application ───→ Domain
Presentation   ───→ Application ───→ Domain
```

**Forbidden dependencies**:
- ❌ Domain → Application
- ❌ Domain → Infrastructure
- ❌ Application → Presentation
- ❌ Application → Infrastructure (direct, only via interfaces)

**Example**:
```python
# ✅ CORRECT: Use Case depends on interface (Domain)
class TranscribeVideoUseCase:
    def __init__(self, downloader: IDownloader):  # Interface from Domain
        self._downloader = downloader

# ❌ WRONG: Use Case depends on implementation (Infrastructure)
class TranscribeVideoUseCase:
    def __init__(self):
        self._downloader = YouTubeDownloader()  # Concrete implementation
```

---

## SOLID Principles

### S - Single Responsibility Principle

**Each class has ONE responsibility.**

✅ **Good example**:
```python
# src/infrastructure/youtube/downloader.py
class YouTubeDownloader(IDownloader):
    """Single responsibility: Download audio from YouTube"""
    def download(self, url: YouTubeURL) -> Path:
        pass

# src/infrastructure/whisper/transcription_service.py
class TranscriptionService(ITranscriptionService):
    """Single responsibility: Transcribe audio"""
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        pass

# src/infrastructure/storage/local_storage.py
class LocalStorageService(IStorageService):
    """Single responsibility: Manage file storage"""
    def cleanup(self, path: Path) -> None:
        pass
```

❌ **Bad example** (God class):
```python
class YouTubeTranscriber:
    """Does EVERYTHING: download + transcribe + cleanup + cache + metrics"""
    def download_and_transcribe_and_cleanup(self, url: str):
        # Too many responsibilities!
        pass
```

**Benefits**:
- Easier to test
- Easier to understand
- Easier to modify
- Less prone to bugs

---

### O - Open/Closed Principle

**Open for extension, closed for modification.**

✅ **Good example**:
```python
# src/domain/interfaces/transcription_service.py
class ITranscriptionService(ABC):
    """Interface (abstract): can be extended"""
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        ...

# Add new implementation WITHOUT modifying existing code
class WhisperTranscriptionService(ITranscriptionService):
    """Whisper implementation"""
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        return whisper.transcribe(audio_path)

class GoogleSpeechService(ITranscriptionService):
    """Google Speech implementation (future)"""
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        return google_speech.transcribe(audio_path)

# Use Case works with ANY implementation
def process(service: ITranscriptionService):
    return service.transcribe("audio.wav")
```

**v3.0 example** (Download strategies):
```python
# src/infrastructure/youtube/download_strategies.py
class DownloadStrategy(ABC):
    """Base strategy (open for extension)"""
    @abstractmethod
    def download(self, url: str, options: dict) -> Path:
        ...

# 7 concrete strategies (closed for modification)
class DirectStrategy(DownloadStrategy): ...
class CookiesStrategy(DownloadStrategy): ...
class MobileUAStrategy(DownloadStrategy): ...
# ... 4 more strategies

# Add new strategy WITHOUT modifying existing ones
class NewStrategy(DownloadStrategy):
    def download(self, url: str, options: dict) -> Path:
        # New implementation
        pass
```

---

### L - Liskov Substitution Principle

**Subclasses must be substitutable for their base classes.**

✅ **Good example**:
```python
def transcribe_audio(service: ITranscriptionService, audio: Path) -> TranscriptionResult:
    """Works with ANY ITranscriptionService implementation"""
    return service.transcribe(audio)

# Both work correctly
transcribe_audio(WhisperTranscriptionService(), "audio.wav")
transcribe_audio(GoogleSpeechService(), "audio.wav")
```

❌ **Bad example** (violates LSP):
```python
class BaseTranscriber:
    def transcribe(self, audio: Path) -> TranscriptionResult:
        # Returns TranscriptionResult
        pass

class BrokenTranscriber(BaseTranscriber):
    def transcribe(self, audio: Path) -> dict:  # ❌ Different return type!
        # Violates LSP, breaks client code
        pass
```

---

### I - Interface Segregation Principle

**Specific interfaces are better than general ones.**

✅ **Good example**:
```python
# src/domain/interfaces/ (separate interfaces)

class IDownloader(ABC):
    """Only download methods"""
    @abstractmethod
    def download(self, url: YouTubeURL) -> Path:
        ...

class ITranscriptionService(ABC):
    """Only transcription methods"""
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        ...

class IStorageService(ABC):
    """Only storage methods"""
    @abstractmethod
    def cleanup(self, path: Path) -> None:
        ...
    
    @abstractmethod
    def get_temp_dir(self) -> Path:
        ...
```

❌ **Bad example** (fat interface):
```python
class IVideoProcessor(ABC):
    """Too general, forces clients to implement everything"""
    def download(self, url: str): ...
    def transcribe(self, audio: str): ...
    def cleanup(self, path: str): ...
    def cache_result(self, key: str, value: any): ...
    def send_notification(self, message: str): ...
    # Client forced to implement ALL methods (even unused ones)
```

---

### D - Dependency Inversion Principle

**Depend on abstractions, not concretions.**

✅ **Good example**:
```python
# src/application/use_cases/transcribe_video.py
class TranscribeVideoUseCase:
    def __init__(
        self,
        downloader: IDownloader,           # ✅ Depends on interface
        transcriber: ITranscriptionService, # ✅ Depends on interface
        storage: IStorageService           # ✅ Depends on interface
    ):
        self._downloader = downloader
        self._transcriber = transcriber
        self._storage = storage
    
    def execute(self, url: YouTubeURL) -> TranscriptionResult:
        audio = self._downloader.download(url)
        result = self._transcriber.transcribe(audio)
        self._storage.cleanup(audio)
        return result
```

❌ **Bad example**:
```python
class TranscribeVideoUseCase:
    def __init__(self):
        # ❌ Direct dependency on concrete implementations
        self._downloader = YouTubeDownloader()
        self._transcriber = WhisperService()
        self._storage = LocalStorage()
    
    # Hard to test, hard to replace implementations
```

**Benefits**:
- Easy to test (mock dependencies)
- Easy to swap implementations
- Loose coupling

---

## Project Structure

```
src/
├── domain/                              # 1. Domain Layer (Core)
│   ├── entities/                        # Business entities with identity
│   │   ├── transcription.py             # TranscriptionResult
│   │   └── video_file.py                # VideoFile
│   ├── value_objects/                   # Value objects (immutable)
│   │   ├── transcription_segment.py     # TranscriptionSegment
│   │   └── youtube_url.py               # YouTubeURL
│   ├── interfaces/                      # Contracts (Abstract Base Classes)
│   │   ├── video_downloader.py          # IDownloader
│   │   ├── transcription_service.py     # ITranscriptionService
│   │   └── storage_service.py           # IStorageService
│   └── exceptions.py                    # Domain-specific exceptions
│
├── application/                         # 2. Application Layer (Use Cases)
│   ├── dtos/                            # Data Transfer Objects
│   │   └── transcription_dtos.py        # Request/Response DTOs (internal)
│   └── use_cases/                       # Business workflows
│       ├── transcribe_video.py          # Main transcription flow
│       └── cleanup_files.py             # File cleanup workflow
│
├── infrastructure/                      # 4. Infrastructure Layer (Implementations)
│   ├── whisper/                         # Whisper transcription implementation
│   │   ├── transcription_service.py     # Single-core transcription
│   │   ├── parallel_transcription_service.py  # v2.0 Parallel processing
│   │   ├── model_cache.py               # Model caching (LRU)
│   │   ├── persistent_worker_pool.py    # Worker pool management
│   │   ├── transcription_factory.py     # Factory pattern (single/parallel)
│   │   ├── chunk_preparation_service.py # Audio chunking
│   │   └── temp_session_manager.py      # Session tracking
│   │
│   ├── youtube/                         # YouTube download implementation (v3.0 ↓)
│   │   ├── downloader.py                # Main downloader (facade)
│   │   ├── download_config.py           # 🆕 v3.0 Centralized configuration
│   │   ├── download_strategies.py       # 🆕 v3.0 7 download strategies
│   │   ├── rate_limiter.py              # 🆕 v3.0 Rate limiting + Circuit Breaker
│   │   ├── user_agent_rotator.py        # 🆕 v3.0 17 User-Agent rotation
│   │   ├── proxy_manager.py             # 🆕 v3.0 Tor proxy management
│   │   ├── metrics.py                   # 🆕 v3.0 26 Prometheus metrics
│   │   └── transcript_service.py        # YouTube transcript API fallback
│   │
│   ├── storage/                         # File storage implementation
│   │   ├── local_storage.py             # Local filesystem
│   │   └── file_cleanup_manager.py      # Automated cleanup
│   │
│   ├── cache/                           # Caching implementation
│   │   └── transcription_cache.py       # LRU cache with TTL
│   │
│   ├── validators/                      # Validation services
│   │   └── audio_validator.py           # Audio file validation
│   │
│   ├── utils/                           # Utility services
│   │   └── ffmpeg_optimizer.py          # FFmpeg operations
│   │
│   └── monitoring/                      # Monitoring implementation
│       └── metrics.py                   # Prometheus metrics collector
│
├── presentation/                        # 3. Presentation Layer (API)
│   └── api/
│       ├── main.py                      # FastAPI application entry point
│       ├── dependencies.py              # Dependency injection container
│       ├── routes/                      # API endpoints
│       │   ├── transcription.py         # POST /api/v1/transcribe
│       │   ├── video_info.py            # POST /api/v1/video/info
│       │   └── system.py                # GET /health, /metrics
│       └── middlewares/                 # HTTP middlewares
│           ├── error_handler.py         # Global error handling
│           ├── rate_limiter.py          # API rate limiting
│           └── cors.py                  # CORS configuration
│
└── config/                              # Configuration
    └── settings.py                      # Environment variables (Pydantic)
```

---

## Layers in Detail

### 1. Domain Layer (Core Business Logic)

**Purpose**: Contains pure business logic and rules.

**What's inside**:
- **Entities**: Objects with identity (e.g., `TranscriptionResult` with ID)
- **Value Objects**: Immutable objects (e.g., `TranscriptionSegment`, `YouTubeURL`)
- **Interfaces**: Contracts for infrastructure (e.g., `IDownloader`)
- **Exceptions**: Domain-specific errors (e.g., `InvalidYouTubeURLError`)

**Rules**:
- ❌ NO dependencies on other layers
- ❌ NO external frameworks (FastAPI, Whisper, yt-dlp)
- ❌ NO I/O operations (file system, network, database)
- ✅ Only pure Python code

**Example - Entity**:
```python
# src/domain/entities/transcription.py
from dataclasses import dataclass
from typing import List
from .transcription_segment import TranscriptionSegment

@dataclass
class TranscriptionResult:
    """Entity: Transcription result with identity (id)"""
    id: str
    video_url: str
    video_title: str
    transcription_text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float
    
    def total_segments(self) -> int:
        """Business rule: count segments"""
        return len(self.segments)
    
    def is_short_video(self) -> bool:
        """Business rule: video < 60s is short"""
        return self.duration < 60
```

**Example - Value Object**:
```python
# src/domain/value_objects/youtube_url.py
from dataclasses import dataclass
import re

@dataclass(frozen=True)  # Immutable
class YouTubeURL:
    """Value Object: Immutable YouTube URL"""
    url: str
    
    def __post_init__(self):
        """Validate URL on creation"""
        if not self._is_valid():
            raise InvalidYouTubeURLError(f"Invalid URL: {self.url}")
    
    def _is_valid(self) -> bool:
        """Business rule: validate YouTube URL format"""
        pattern = r'(youtube\.com|youtu\.be)'
        return bool(re.search(pattern, self.url))
    
    def video_id(self) -> str:
        """Extract video ID from URL"""
        # Implementation
        pass
```

**Example - Interface**:
```python
# src/domain/interfaces/transcription_service.py
from abc import ABC, abstractmethod
from pathlib import Path
from ..entities.transcription import TranscriptionResult

class ITranscriptionService(ABC):
    """Contract for transcription implementations"""
    
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        """Transcribe audio file"""
        ...
    
    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if language is supported"""
        ...
```

---

### 2. Application Layer (Use Cases)

**Purpose**: Orchestrates business workflows.

**What's inside**:
- **Use Cases**: High-level business operations
- **DTOs**: Data transfer between layers

**Rules**:
- ✅ Depends on Domain (interfaces only)
- ❌ NO direct dependencies on Infrastructure
- ✅ Coordinates multiple domain services
- ✅ Implements transaction boundaries

**Example**:
```python
# src/application/use_cases/transcribe_video.py
from pathlib import Path
from src.domain.interfaces import IDownloader, ITranscriptionService, IStorageService
from src.domain.value_objects import YouTubeURL
from src.domain.entities import TranscriptionResult
from src.domain.exceptions import *

class TranscribeVideoUseCase:
    """
    Use Case: Transcribe video from YouTube URL.
    
    Workflow:
    1. Validate URL
    2. Download audio
    3. Transcribe audio
    4. Cleanup temporary files
    5. Return result
    """
    
    def __init__(
        self,
        downloader: IDownloader,
        transcriber: ITranscriptionService,
        storage: IStorageService
    ):
        """Inject dependencies via constructor"""
        self._downloader = downloader
        self._transcriber = transcriber
        self._storage = storage
    
    def execute(self, video_url: str, language: str = "en") -> TranscriptionResult:
        """Execute the use case"""
        try:
            # 1. Validate URL (Domain logic)
            url = YouTubeURL(video_url)
            
            # 2. Download audio (Infrastructure via interface)
            audio_path = self._downloader.download(url)
            
            # 3. Transcribe (Infrastructure via interface)
            result = self._transcriber.transcribe(audio_path, language)
            
            # 4. Cleanup (Infrastructure via interface)
            self._storage.cleanup(audio_path)
            
            # 5. Return result (Domain entity)
            return result
            
        except InvalidYouTubeURLError as e:
            raise DomainValidationError(f"Invalid URL: {e}")
        except DownloadError as e:
            raise ApplicationError(f"Download failed: {e}")
        except TranscriptionError as e:
            raise ApplicationError(f"Transcription failed: {e}")
```

**Benefits**:
- Clear business flow
- Easy to test (mock interfaces)
- Reusable across different interfaces (API, CLI, GUI)

---

### 3. Presentation Layer (API)

**Purpose**: HTTP interface for clients.

**What's inside**:
- **Routes**: FastAPI endpoints
- **Schemas**: Request/Response models (Pydantic)
- **Middlewares**: CORS, error handling, rate limiting
- **Dependencies**: Dependency injection

**Rules**:
- ✅ Depends on Application (Use Cases)
- ✅ Validates HTTP input
- ✅ Serializes HTTP output
- ❌ NO business logic here

**Example - Route**:
```python
# src/presentation/api/routes/transcription.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.application.use_cases import TranscribeVideoUseCase
from ..dependencies import get_transcribe_use_case

router = APIRouter(prefix="/api/v1", tags=["transcription"])

class TranscriptionRequest(BaseModel):
    """Request schema (validation)"""
    youtube_url: str
    language: str = "en"

class TranscriptionResponse(BaseModel):
    """Response schema (serialization)"""
    video_url: str
    video_title: str
    transcription: str
    language: str
    segments: list

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(
    request: TranscriptionRequest,
    use_case: TranscribeVideoUseCase = Depends(get_transcribe_use_case)
):
    """
    Transcribe video from YouTube URL.
    
    - **youtube_url**: YouTube video URL
    - **language**: Language code (default: "en")
    """
    try:
        # Delegate to use case (Application layer)
        result = use_case.execute(request.youtube_url, request.language)
        
        # Serialize result (Domain entity → Response DTO)
        return TranscriptionResponse(
            video_url=result.video_url,
            video_title=result.video_title,
            transcription=result.transcription_text,
            language=result.language,
            segments=[s.to_dict() for s in result.segments]
        )
    
    except DomainValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApplicationError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 4. Infrastructure Layer (Implementations)

**Purpose**: External frameworks, tools, I/O.

**What's inside**:
- **Whisper**: Transcription implementation
- **YouTube**: Download implementation (v3.0 with resilience)
- **Storage**: File system operations
- **Cache**: Redis/Memory cache
- **Monitoring**: Prometheus metrics

**Rules**:
- ✅ Implements Domain interfaces
- ✅ Uses external frameworks (Whisper, yt-dlp, FFmpeg)
- ✅ Performs I/O operations

**Example**:
```python
# src/infrastructure/whisper/transcription_service.py
import whisper
from pathlib import Path
from src.domain.interfaces import ITranscriptionService
from src.domain.entities import TranscriptionResult, TranscriptionSegment

class WhisperTranscriptionService(ITranscriptionService):
    """Whisper implementation of ITranscriptionService"""
    
    def __init__(self, model: str = "base", device: str = "cpu"):
        """Load Whisper model on initialization"""
        self._model = whisper.load_model(model, device=device)
        self._device = device
    
    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        """Transcribe audio using Whisper"""
        # Call external library (Whisper)
        result = self._model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe"
        )
        
        # Convert to Domain entity
        segments = [
            TranscriptionSegment(
                start=s["start"],
                end=s["end"],
                text=s["text"]
            )
            for s in result["segments"]
        ]
        
        return TranscriptionResult(
            id=str(uuid.uuid4()),
            video_url="",  # Set by use case
            video_title="",  # Set by use case
            transcription_text=result["text"],
            segments=segments,
            language=result["language"],
            duration=result["segments"][-1]["end"]
        )
    
    def supports_language(self, language: str) -> bool:
        """Check if Whisper supports language"""
        supported = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
        return language in supported
```

---

## Data Flow

### Request → Response Flow

```
1. HTTP Request
   │
   ↓
┌─────────────────────────────────────────────┐
│  Presentation Layer (FastAPI Route)        │
│  • Receive HTTP POST /api/v1/transcribe   │
│  • Validate request (Pydantic)            │
│  • Extract: youtube_url, language         │
└────────────────┬────────────────────────────┘
                 │ TranscriptionRequest (DTO)
                 ↓
┌─────────────────────────────────────────────┐
│  Application Layer (Use Case)              │
│  TranscribeVideoUseCase.execute()          │
│  • Validate URL (Domain)                   │
│  • Download audio (via IDownloader)        │
│  • Transcribe audio (via ITranscription)   │
│  • Cleanup files (via IStorage)            │
└────────────────┬────────────────────────────┘
                 │ TranscriptionResult (Entity)
     ┌───────────┼───────────┐
     ↓           ↓           ↓
┌──────────────────────────────────────────────┐
│  Infrastructure Layer                        │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐│
│  │ YouTubeDownloader│  │ WhisperService   ││
│  │ (IDownloader)    │  │ (ITranscription) ││
│  │                  │  │                  ││
│  │ • v3.0 Resilience│  │ • Model loading  ││
│  │ • 7 Strategies   │  │ • Transcription  ││
│  │ • Rate limiting  │  │ • Parallel (v2.0)││
│  │ • Circuit breaker│  │ • Cache          ││
│  └──────────────────┘  └──────────────────┘│
│                                              │
│  ┌──────────────────┐                       │
│  │ LocalStorage     │                       │
│  │ (IStorage)       │                       │
│  │ • Cleanup files  │                       │
│  └──────────────────┘                       │
└──────────────────────────────────────────────┘
                 │ TranscriptionResult
                 ↓
┌─────────────────────────────────────────────┐
│  Presentation Layer (Response)             │
│  • Map Entity → Response DTO               │
│  • Serialize to JSON                       │
└────────────────┬────────────────────────────┘
                 │ TranscriptionResponse (JSON)
                 ↓
2. HTTP Response (200 OK)
```

---

## Dependency Injection

### Container (FastAPI Dependencies)

```python
# src/presentation/api/dependencies.py
from functools import lru_cache
from src.config import settings
from src.domain.interfaces import *
from src.infrastructure.youtube import YouTubeDownloader
from src.infrastructure.whisper import (
    TranscriptionService,
    ParallelTranscriptionService,
    TranscriptionFactory
)
from src.infrastructure.storage import LocalStorageService
from src.application.use_cases import TranscribeVideoUseCase

# ===========================
# Infrastructure dependencies
# ===========================

@lru_cache()
def get_downloader() -> IDownloader:
    """Singleton YouTube downloader"""
    return YouTubeDownloader(
        max_retries=settings.YOUTUBE_MAX_RETRIES,
        enable_tor=settings.ENABLE_TOR_PROXY,
        tor_proxy_url=settings.TOR_PROXY_URL
    )

@lru_cache()
def get_transcription_service() -> ITranscriptionService:
    """Singleton transcription service (single or parallel)"""
    factory = TranscriptionFactory()
    return factory.create_service(
        model=settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        enable_parallel=settings.ENABLE_PARALLEL_TRANSCRIPTION,
        parallel_workers=settings.PARALLEL_WORKERS
    )

@lru_cache()
def get_storage_service() -> IStorageService:
    """Singleton storage service"""
    return LocalStorageService(temp_dir=settings.TEMP_DIR)

# ===========================
# Application dependencies
# ===========================

def get_transcribe_use_case(
    downloader: IDownloader = Depends(get_downloader),
    transcriber: ITranscriptionService = Depends(get_transcription_service),
    storage: IStorageService = Depends(get_storage_service)
) -> TranscribeVideoUseCase:
    """Create TranscribeVideoUseCase with injected dependencies"""
    return TranscribeVideoUseCase(
        downloader=downloader,
        transcriber=transcriber,
        storage=storage
    )
```

### Benefits of Dependency Injection

1. **Testability**: Easy to mock dependencies
```python
# tests/application/test_transcribe_use_case.py
def test_transcribe_video():
    # Mock dependencies
    downloader_mock = Mock(spec=IDownloader)
    transcriber_mock = Mock(spec=ITranscriptionService)
    storage_mock = Mock(spec=IStorageService)
    
    # Configure mocks
    downloader_mock.download.return_value = Path("audio.wav")
    transcriber_mock.transcribe.return_value = TranscriptionResult(...)
    
    # Test use case with mocks
    use_case = TranscribeVideoUseCase(downloader_mock, transcriber_mock, storage_mock)
    result = use_case.execute("https://youtube.com/watch?v=123")
    
    # Assert
    assert result.transcription_text == "Expected text"
    downloader_mock.download.assert_called_once()
    storage_mock.cleanup.assert_called_once()
```

2. **Flexibility**: Swap implementations easily
```python
# Development: Use fast implementation
def get_transcription_service() -> ITranscriptionService:
    return MockTranscriptionService()  # Instant, for testing

# Production: Use real implementation
def get_transcription_service() -> ITranscriptionService:
    return WhisperTranscriptionService(model="medium", device="cuda")
```

3. **Singleton pattern**: `@lru_cache()` ensures single instance
```python
# Both calls return SAME instance
service1 = get_transcription_service()
service2 = get_transcription_service()
assert service1 is service2  # True
```

---

## Design Patterns

### 1. Strategy Pattern (v3.0 Download Strategies)

**Problem**: YouTube blocks downloads with different errors.

**Solution**: Multiple strategies with priority-based fallback.

**Implementation**:
```python
# src/infrastructure/youtube/download_strategies.py
class DownloadStrategy(ABC):
    """Base strategy"""
    @abstractmethod
    def download(self, url: str, options: dict) -> Path:
        pass

class DirectStrategy(DownloadStrategy):
    """Strategy 1: Direct download (priority 1)"""
    def download(self, url: str, options: dict) -> Path:
        return yt_dlp.download(url, options)

class CookiesStrategy(DownloadStrategy):
    """Strategy 2: Use browser cookies (priority 2)"""
    def download(self, url: str, options: dict) -> Path:
        options['cookiesfrombrowser'] = 'chrome'
        return yt_dlp.download(url, options)

class TorProxyStrategy(DownloadStrategy):
    """Strategy 7: Use Tor proxy (priority 7, last resort)"""
    def download(self, url: str, options: dict) -> Path:
        options['proxy'] = 'socks5://tor-proxy:9050'
        return yt_dlp.download(url, options)

# Orchestrator (Context)
class YouTubeDownloader:
    def __init__(self):
        self.strategies = [
            DirectStrategy(),
            CookiesStrategy(),
            MobileUAStrategy(),
            RefererStrategy(),
            ExtractFormatStrategy(),
            EmbeddedStrategy(),
            TorProxyStrategy()
        ]
    
    def download(self, url: str) -> Path:
        """Try strategies sequentially"""
        for strategy in self.strategies:
            try:
                return strategy.download(url, options)
            except Exception as e:
                logger.warning(f"Strategy {strategy} failed: {e}")
                continue
        
        raise AllStrategiesFailedError("All 7 strategies failed")
```

**Benefits**:
- Easy to add new strategies (Open/Closed Principle)
- Each strategy is independent and testable
- Priority-based fallback increases success rate

---

### 2. Circuit Breaker Pattern (v3.0 Resilience)

**Problem**: Repeated failures can lead to permanent bans.

**Solution**: Temporarily block requests after threshold failures.

**Implementation**:
```python
# src/infrastructure/youtube/rate_limiter.py
class CircuitBreaker:
    """
    Circuit Breaker states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing recovery, limited requests
    """
    
    def __init__(self, threshold: int = 10, timeout: int = 180):
        self.threshold = threshold  # Max failures before opening
        self.timeout = timeout  # Seconds to wait before retry
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = None
    
    def call(self, func: Callable) -> Any:
        """Execute function through circuit breaker"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Reset failures on success"""
        self.failures = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
    
    def _on_failure(self):
        """Increment failures, open circuit if threshold reached"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.threshold:
            self.state = "OPEN"
            logger.critical(f"Circuit breaker OPEN after {self.failures} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if timeout has passed"""
        return time.time() - self.last_failure_time > self.timeout
```

**Usage**:
```python
circuit_breaker = CircuitBreaker(threshold=10, timeout=180)

def download_video(url: str) -> Path:
    return circuit_breaker.call(lambda: _download_internal(url))
```

**Benefits**:
- Prevents cascading failures
- Automatic recovery after timeout
- Protects from permanent bans

---

### 3. Factory Pattern (v2.0 Transcription Service)

**Problem**: Choose between single-core and parallel transcription.

**Solution**: Factory creates appropriate service based on configuration.

**Implementation**:
```python
# src/infrastructure/whisper/transcription_factory.py
class TranscriptionFactory:
    """Factory for creating transcription services"""
    
    def create_service(
        self,
        model: str,
        device: str,
        enable_parallel: bool,
        parallel_workers: int
    ) -> ITranscriptionService:
        """
        Create transcription service based on configuration.
        
        Returns:
            - ParallelTranscriptionService if enable_parallel=True
            - TranscriptionService otherwise
        """
        if enable_parallel and parallel_workers > 1:
            return ParallelTranscriptionService(
                model=model,
                device=device,
                max_workers=parallel_workers
            )
        else:
            return TranscriptionService(
                model=model,
                device=device
            )
```

**Benefits**:
- Centralized creation logic
- Easy to add new service types
- Configuration-driven selection

---

### 4. Repository Pattern (Cache)

**Problem**: Abstract cache storage (memory, Redis, file).

**Solution**: Repository interface with multiple implementations.

**Implementation**:
```python
# src/domain/interfaces/cache_repository.py
class ICacheRepository(ABC):
    """Repository for cached transcriptions"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[TranscriptionResult]:
        ...
    
    @abstractmethod
    def set(self, key: str, value: TranscriptionResult, ttl: int) -> None:
        ...
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

# src/infrastructure/cache/memory_cache_repository.py
class MemoryCacheRepository(ICacheRepository):
    """In-memory cache (LRU)"""
    def __init__(self, max_size: int = 100):
        self._cache = {}
        self._lru = deque(maxlen=max_size)
    
    def get(self, key: str) -> Optional[TranscriptionResult]:
        return self._cache.get(key)
    
    # ... implementation

# src/infrastructure/cache/redis_cache_repository.py
class RedisCacheRepository(ICacheRepository):
    """Redis cache (future)"""
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url)
    
    def get(self, key: str) -> Optional[TranscriptionResult]:
        data = self._redis.get(key)
        return pickle.loads(data) if data else None
    
    # ... implementation
```

**Benefits**:
- Easy to switch cache backends
- Testable with fake/mock repositories
- Business logic doesn't know about cache details

---

## Adding New Features

### Example: Add Vimeo Support

**Step 1**: Create interface (if needed)
```python
# src/domain/interfaces/video_downloader.py
class IVideoDownloader(ABC):
    """General video downloader interface"""
    
    @abstractmethod
    def download(self, url: str) -> Path:
        ...
    
    @abstractmethod
    def supports_url(self, url: str) -> bool:
        """Check if URL is supported by this downloader"""
        ...
```

**Step 2**: Implement for Vimeo
```python
# src/infrastructure/vimeo/downloader.py
class VimeoDownloader(IVideoDownloader):
    """Vimeo video downloader"""
    
    def download(self, url: str) -> Path:
        # Implementation using vimeo_downloader library
        pass
    
    def supports_url(self, url: str) -> bool:
        return "vimeo.com" in url
```

**Step 3**: Update use case
```python
# src/application/use_cases/transcribe_video.py
class TranscribeVideoUseCase:
    def __init__(
        self,
        downloaders: List[IVideoDownloader],  # Multiple downloaders
        transcriber: ITranscriptionService,
        storage: IStorageService
    ):
        self._downloaders = downloaders
        # ... rest
    
    def execute(self, video_url: str, language: str = "en") -> TranscriptionResult:
        # Select appropriate downloader
        downloader = next(
            (d for d in self._downloaders if d.supports_url(video_url)),
            None
        )
        
        if not downloader:
            raise UnsupportedURLError(f"No downloader for: {video_url}")
        
        # Rest of the flow...
```

**Step 4**: Register in DI container
```python
# src/presentation/api/dependencies.py
@lru_cache()
def get_youtube_downloader() -> IVideoDownloader:
    return YouTubeDownloader()

@lru_cache()
def get_vimeo_downloader() -> IVideoDownloader:
    return VimeoDownloader()

def get_transcribe_use_case(
    youtube: IVideoDownloader = Depends(get_youtube_downloader),
    vimeo: IVideoDownloader = Depends(get_vimeo_downloader),
    transcriber: ITranscriptionService = Depends(get_transcription_service),
    storage: IStorageService = Depends(get_storage_service)
) -> TranscribeVideoUseCase:
    return TranscribeVideoUseCase(
        downloaders=[youtube, vimeo],
        transcriber=transcriber,
        storage=storage
    )
```

**Done!** No changes to existing code, only additions.

---

## Best Practices

### 1. Naming Conventions

- **Interfaces**: Prefix with `I` (e.g., `ITranscriptionService`)
- **Implementations**: No prefix (e.g., `WhisperTranscriptionService`)
- **Use Cases**: `VerbNounUseCase` (e.g., `TranscribeVideoUseCase`)
- **DTOs**: `EntityRequest`/`EntityResponse` (e.g., `TranscriptionRequest`)
- **Exceptions**: Suffix with `Error` (e.g., `DownloadError`)

### 2. Error Handling

**Domain exceptions** (business rule violations):
```python
# src/domain/exceptions.py
class DomainException(Exception):
    """Base domain exception"""
    pass

class InvalidYouTubeURLError(DomainException):
    """Invalid YouTube URL format"""
    pass
```

**Application exceptions** (workflow failures):
```python
# src/application/exceptions.py
class ApplicationError(Exception):
    """Base application exception"""
    pass

class TranscriptionFailedError(ApplicationError):
    """Transcription workflow failed"""
    pass
```

**Infrastructure exceptions** (external tool failures):
```python
# src/infrastructure/exceptions.py
class InfrastructureError(Exception):
    """Base infrastructure exception"""
    pass

class WhisperModelLoadError(InfrastructureError):
    """Failed to load Whisper model"""
    pass
```

### 3. Logging

**Use structured logging** (loguru):
```python
from loguru import logger

class TranscriptionService:
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        logger.info(f"Starting transcription: {audio_path}")
        
        try:
            result = self._model.transcribe(str(audio_path))
            logger.info(
                f"Transcription complete: {len(result['text'])} chars, "
                f"{len(result['segments'])} segments"
            )
            return self._convert_to_entity(result)
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise TranscriptionError(f"Failed to transcribe: {e}") from e
```

### 4. Testing

**Unit tests** (Domain/Application):
```python
# tests/domain/test_youtube_url.py
def test_youtube_url_validation():
    # Valid URLs
    assert YouTubeURL("https://youtube.com/watch?v=123").is_valid()
    assert YouTubeURL("https://youtu.be/123").is_valid()
    
    # Invalid URLs
    with pytest.raises(InvalidYouTubeURLError):
        YouTubeURL("https://vimeo.com/123")
```

**Integration tests** (Infrastructure):
```python
# tests/infrastructure/test_whisper_service.py
@pytest.mark.integration
def test_real_transcription():
    """Test with real Whisper model"""
    service = WhisperTranscriptionService(model="tiny")
    result = service.transcribe(Path("tests/fixtures/sample.wav"))
    
    assert result.transcription_text
    assert len(result.segments) > 0
```

### 5. Documentation

**Docstrings** (Google style):
```python
def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
    """
    Transcribe audio file using Whisper.
    
    Args:
        audio_path: Path to audio file (WAV format)
        language: Language code (e.g., "en", "es", "fr")
    
    Returns:
        TranscriptionResult with text and segments
    
    Raises:
        TranscriptionError: If transcription fails
        FileNotFoundError: If audio file doesn't exist
    
    Example:
        >>> service = WhisperTranscriptionService("base")
        >>> result = service.transcribe(Path("audio.wav"), language="en")
        >>> print(result.transcription_text)
    """
    pass
```

---

## Architecture Benefits

### ✅ Testability

- Mock dependencies easily
- Test layers independently
- Fast unit tests (no I/O)

### ✅ Maintainability

- Clear separation of concerns
- Easy to locate code
- Changes isolated to specific layers

### ✅ Scalability

- Add features without breaking existing code
- Parallel processing easy (independent use cases)
- Microservices-ready (use cases can be separate services)

### ✅ Framework Independence

- Migrate FastAPI → Flask: Only change Presentation layer
- Replace Whisper → Google Speech: Only change Infrastructure layer
- Swap cache backend: Only change Infrastructure layer

### ✅ Business Focus

- Domain layer contains ONLY business rules
- Business logic testable without frameworks
- Easy for non-technical stakeholders to review Domain layer

---

## Next Steps

- [Contributing Guide](./contributing.md) - How to contribute code
- [Testing Guide](./testing.md) - Testing strategy and examples
- [User Guide](../user-guide/) - For end users

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team