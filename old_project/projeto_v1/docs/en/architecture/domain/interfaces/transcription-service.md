# ITranscriptionService Interface

Interface (ABC) that defines the contract for transcription services.

---

## Overview

`ITranscriptionService` is an **Interface** that:
- Defines the contract for audio/video transcription
- Follows the **Dependency Inversion Principle** (SOLID)
- Allows multiple implementations (Whisper, OpenAI API, etc.)

**File**: `src/domain/interfaces/transcription_service.py`

---

## Methods

### `transcribe(video_file, language="auto") -> Transcription`
Transcribes a video file.

**Parameters**:
- `video_file: VideoFile` - Video file to transcribe
- `language: str` - Video language (`"auto"` for automatic detection)

**Returns**: `Transcription` - Entity with the complete transcription

**Exceptions**: `TranscriptionError` - Transcription error

```python
service: ITranscriptionService = WhisperService()
transcription = await service.transcribe(video_file, language="pt")
print(transcription.get_full_text())
```

### `detect_language(video_file) -> str`
Detects the audio language.

**Parameters**:
- `video_file: VideoFile` - Video file

**Returns**: `str` - Detected language code (ISO 639-1)

**Exceptions**: `TranscriptionError` - Detection error

```python
language = await service.detect_language(video_file)
print(f"Detected language: {language}")  # "pt"
```

---

## Implementations

### `WhisperTranscriptionService` (Infrastructure)
Implementation using **OpenAI Whisper** (v2.0 with Parallel Processing).

**Location**: `src/infrastructure/whisper/transcription_service.py`

**Features**:
- Models: tiny, base, small, medium, large
- Automatic language detection
- Intelligent audio chunking
- GPU acceleration (CUDA/CPU fallback)

### `ParallelWhisperService` (v2.0+)
Implementation with **parallel processing**.

**Location**: `src/infrastructure/whisper/parallel_transcription_service.py`

**Features**:
- Persistent worker pool
- Parallel chunk processing
- 7-10x speedup (vs sequential)
- Memory-efficient chunking

---

## Usage Example

```python
from src.domain.interfaces import ITranscriptionService
from src.infrastructure.whisper import ParallelWhisperService

async def transcribe_video(
    service: ITranscriptionService,
    video_file: VideoFile
):
    # Detect language
    language = await service.detect_language(video_file)
    print(f"Language: {language}")
    
    # Transcribe
    transcription = await service.transcribe(video_file, language)
    
    # Export SRT
    srt_path = Path("output.srt")
    srt_path.write_text(transcription.to_srt())
    
    return transcription

# Inject implementation
service = ParallelWhisperService(model="base", num_workers=4)
result = await transcribe_video(service, video_file)
```

---

## Dependency Inversion

```python
# ❌ WRONG: Depend on concrete implementation
from src.infrastructure.whisper import WhisperTranscriptionService

class TranscribeUseCase:
    def __init__(self):
        self.service = WhisperTranscriptionService()  # Coupling

# ✅ CORRECT: Depend on abstraction
from src.domain.interfaces import ITranscriptionService

class TranscribeUseCase:
    def __init__(self, service: ITranscriptionService):
        self.service = service  # Flexible
```

**Benefits**:
- Test with mock (without loading Whisper)
- Switch implementation (Whisper → OpenAI API)
- Domain decoupled from infrastructure

---

## Tests

```python
class MockTranscriptionService(ITranscriptionService):
    async def transcribe(self, video_file, language="auto"):
        return Transcription(
            youtube_url="https://youtu.be/123",
            segments=[
                TranscriptionSegment("Test", start=0, end=2)
            ],
            language="en"
        )
    
    async def detect_language(self, video_file):
        return "en"

# Use mock in tests
async def test_transcribe_use_case():
    mock_service = MockTranscriptionService()
    use_case = TranscribeUseCase(service=mock_service)
    
    result = await use_case.execute(video_file)
    assert result.language == "en"
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0