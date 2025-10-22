# Domain Layer

Complete documentation of the Domain layer (pure business rules).

---

## 📋 Table of Contents

### Entities
- [Transcription](./entities/transcription.md) - Main transcription entity
- [VideoFile](./entities/video-file.md) - Video file entity

### Value Objects
- [YouTubeURL](./value-objects/youtube-url.md) - Validated YouTube URL
- [TranscriptionSegment](./value-objects/transcription-segment.md) - Transcription segment with timestamp

### Interfaces (Contracts)
- [IVideoDownloader](./interfaces/downloader.md) - Interface for video download
- [ITranscriptionService](./interfaces/transcription-service.md) - Interface for transcription service
- [IStorageService](./interfaces/storage-service.md) - Interface for storage management

### Exceptions
- [Domain Exceptions](./exceptions.md) - Domain-specific exceptions

---

## Overview

The **Domain Layer** is the heart of the application, containing all pure business logic without external dependencies.

### Principles

1. **Zero External Dependencies**
   - No frameworks (FastAPI, Whisper, yt-dlp)
   - No I/O (file system, network, database)
   - Pure Python only

2. **Immutability**
   - Value Objects are immutable (`frozen=True`)
   - Entities have controlled mutable state

3. **Constructor Validation**
   - Objects always valid after creation
   - Exceptions raised in `__post_init__`

4. **Rich Domain Model**
   - Business methods in entities
   - Encapsulated behavior

---

## Structure

```
src/domain/
├── entities/               # Objects with identity
│   ├── transcription.py    # Complete transcription with ID
│   └── video_file.py       # Video file with ID
│
├── value_objects/          # Immutable objects
│   ├── youtube_url.py      # Validated URL (frozen)
│   └── transcription_segment.py  # Segment (frozen)
│
├── interfaces/             # Contracts (ABCs)
│   ├── video_downloader.py
│   ├── transcription_service.py
│   └── storage_service.py
│
└── exceptions.py           # Domain exceptions
```

---

## Difference: Entity vs Value Object

### Entity

**Characteristics**:
- Has unique identity (ID)
- Mutable (state can change)
- Comparison by ID
- Has lifecycle

**Example**: `Transcription`
```python
transcription1 = Transcription(id="123")
transcription2 = Transcription(id="123")
transcription1 == transcription2  # True (same ID)

transcription1.add_segment(segment)  # Mutable
```

### Value Object

**Characteristics**:
- No identity (no ID)
- Immutable (`frozen=True`)
- Comparison by value
- No lifecycle

**Example**: `YouTubeURL`
```python
url1 = YouTubeURL("https://youtube.com/watch?v=123")
url2 = YouTubeURL("https://youtube.com/watch?v=123")
url1 == url2  # True (same value)

url1.url = "other"  # ERROR! Immutable
```

---

## Business Rules

### YouTubeURL
- ✅ Accepts: `youtube.com`, `youtu.be`, `m.youtube.com`
- ✅ Extracts video ID automatically
- ❌ Rejects: URLs from other sites

### TranscriptionSegment
- ✅ `start >= 0` (non-negative)
- ✅ `end >= start` (end after start)
- ✅ `text` not empty
- ✅ Duration calculated: `end - start`

### Transcription
- ✅ Generates unique ID (UUID4)
- ✅ Aggregate segments (`add_segment`)
- ✅ Export formats: SRT, VTT, dict
- ✅ Calculate total duration
- ✅ Validate completeness

---

## Usage Examples

### Creating Transcription

```python
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

# 1. Create validated URL
url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")

# 2. Create transcription
transcription = Transcription(
    youtube_url=url,
    language="en"
)

# 3. Add segments
segment1 = TranscriptionSegment(
    text="Hello, world!",
    start=0.0,
    end=2.5
)
transcription.add_segment(segment1)

# 4. Get full text
full_text = transcription.get_full_text()  # "Hello, world!"

# 5. Export to SRT
srt_content = transcription.to_srt()
```

### Automatic Validation

```python
# ❌ Invalid URL
try:
    url = YouTubeURL.create("https://vimeo.com/123")
except ValueError as e:
    print(e)  # "Invalid YouTube URL"

# ❌ Invalid segment
try:
    segment = TranscriptionSegment(
        text="",  # Empty!
        start=0.0,
        end=2.0
    )
except ValueError as e:
    print(e)  # "Text cannot be empty"

# ❌ Invalid time
try:
    segment = TranscriptionSegment(
        text="Hello",
        start=5.0,
        end=2.0  # End before start!
    )
except ValueError as e:
    print(e)  # "End time must be greater than or equal to start time"
```

---

## Interfaces (Contracts)

Interfaces define **contracts** that the Infrastructure Layer must implement.

### Why Interfaces?

**Dependency Inversion Principle (SOLID)**:
- Domain depends on **abstractions** (interfaces)
- Infrastructure implements the interfaces
- Easy to mock in tests
- Easy to swap implementations

**Example**:
```python
# Domain defines the interface
class ITranscriptionService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> Transcription:
        ...

# Infrastructure implements
class WhisperTranscriptionService(ITranscriptionService):
    def transcribe(self, audio_path: Path) -> Transcription:
        # Real implementation with Whisper
        pass

# Application uses the interface
class TranscribeVideoUseCase:
    def __init__(self, transcriber: ITranscriptionService):
        self._transcriber = transcriber  # Depends on interface!
```

---

## Domain Exceptions

Specific exceptions for business errors:

```python
# src/domain/exceptions.py
class DomainException(Exception):
    """Base exception for domain layer"""
    pass

class InvalidYouTubeURLError(DomainException):
    """Invalid YouTube URL format"""
    pass

class InvalidTranscriptionSegmentError(DomainException):
    """Invalid transcription segment"""
    pass
```

**Usage**:
```python
if not self._is_valid_youtube_url(url):
    raise InvalidYouTubeURLError(f"Invalid URL: {url}")
```

---

## Domain Layer Tests

Domain Layer is **100% testable** without mocks:

```python
# tests/unit/domain/test_youtube_url.py
def test_valid_youtube_url():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    assert url.video_id == "123"

def test_invalid_youtube_url():
    with pytest.raises(ValueError):
        YouTubeURL.create("https://vimeo.com/123")

def test_transcription_segment_duration():
    segment = TranscriptionSegment(
        text="Hello",
        start=0.0,
        end=2.5
    )
    assert segment.duration == 2.5
```

**Advantages**:
- Fast tests (<1ms)
- No external dependencies
- No mocks needed
- High coverage (>90%)

---

## Next Steps

- [Transcription Entity](./entities/transcription.md) - Main entity
- [YouTubeURL Value Object](./value-objects/youtube-url.md) - Validated URL
- [Application Layer](../application/README.md) - Use cases

---

[⬅️ Back](../README.md)

**Version**: 3.0.0  
**Última Atualização**: 22 de outubro de 2025  
**Mantido por**: YTCaption Team
