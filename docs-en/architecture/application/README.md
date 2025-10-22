# Application Layer

Application layer - Use Case orchestration.

---

## Table of Contents

**Use Cases**:
- [Transcribe Video](use-cases/transcribe-video.md) - Orchestrates download + transcription
- [Cleanup Files](use-cases/cleanup-files.md) - Removes old temporary files

**DTOs** (Data Transfer Objects):
- [Transcription DTOs](dtos/transcription-dtos.md) - Request/Response DTOs

---

## Overview

The **Application Layer** is responsible for:
- Orchestrating business flows (Use Cases)
- Coordinating multiple domain services
- Transforming data between layers (DTOs)
- Managing transactions and rollbacks

**Principles**:
- ✅ **Single Responsibility**: Each Use Case has a specific responsibility
- ✅ **Dependency Inversion**: Depends on domain interfaces, not implementations
- ✅ **Separation of Concerns**: Orchestration logic separated from business logic
- ✅ **Testability**: Easy to test with interface mocks

---

## Structure

```
src/application/
├── use_cases/              # Use cases
│   ├── transcribe_video.py   # Main Use Case
│   └── cleanup_files.py       # File cleanup
└── dtos/                   # Data Transfer Objects
    └── transcription_dtos.py  # Transcription DTOs
```

---

## Use Cases

### TranscribeYouTubeVideoUseCase
**Responsibility**: Orchestrate the complete transcription process.

**Flow**:
1. Validate YouTube URL
2. Check cache (v2.2.1)
3. Create temporary directory
4. Download video
5. Validate audio (v2.0)
6. Transcribe with Whisper (with timeout v2.1)
7. Save to cache
8. Clean temporary files
9. Return response

**Handled Exceptions**:
- `ValidationError` - Invalid URL or corrupted audio
- `VideoDownloadError` - Download failure
- `TranscriptionError` - Transcription failure
- `OperationTimeoutError` - Transcription timeout (v2.1)

### CleanupOldFilesUseCase
**Responsibility**: Remove old temporary files.

**Flow**:
1. Get storage usage (before)
2. Remove files older than max_age_hours
3. Get storage usage (after)
4. Return statistics

---

## DTOs (Data Transfer Objects)

DTOs are immutable objects that transfer data between layers:

### Request DTOs
- `TranscribeRequestDTO` - Transcription request
- `ExportCaptionsRequestDTO` - Caption export

### Response DTOs
- `TranscribeResponseDTO` - Response with complete transcription
- `VideoInfoResponseDTO` - Video information
- `HealthCheckDTO` - API status
- `ErrorResponseDTO` - Standardized error response

### Auxiliary DTOs
- `TranscriptionSegmentDTO` - Individual segment
- `SubtitlesInfoDTO` - Subtitle information
- `WhisperRecommendationDTO` - Whisper vs YouTube recommendation

**Validation**: DTOs use Pydantic for automatic data validation.

---

## Usage Example

```python
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

# Create Use Case (inject dependencies)
use_case = TranscribeYouTubeVideoUseCase(
    video_downloader=downloader,
    transcription_service=whisper_service,
    storage_service=storage,
    cleanup_after_processing=True,
    max_video_duration=10800  # 3 hours
)

# Create request
request = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="auto"
)

# Execute Use Case
try:
    response = await use_case.execute(request)
    print(f"Transcription ID: {response.transcription_id}")
    print(f"Language: {response.language}")
    print(f"Time: {response.processing_time:.2f}s")
    print(f"Text: {response.full_text}")
except ValidationError as e:
    print(f"Invalid data: {e}")
except TranscriptionError as e:
    print(f"Transcription error: {e}")
```

---

## Dependency Injection

Use Cases receive **interfaces** as dependencies:

```python
class TranscribeYouTubeVideoUseCase:
    def __init__(
        self,
        video_downloader: IVideoDownloader,      # Interface
        transcription_service: ITranscriptionService,  # Interface
        storage_service: IStorageService,        # Interface
        # ...
    ):
        self.video_downloader = video_downloader
        self.transcription_service = transcription_service
        self.storage_service = storage_service
```

**Benefits**:
- Testability (use mocks)
- Flexibility (swap implementations)
- Decoupling (Application doesn't know Infrastructure)

---

## Tests

```python
async def test_transcribe_use_case_success():
    # Create mocks
    mock_downloader = AsyncMock(spec=IVideoDownloader)
    mock_downloader.download.return_value = VideoFile(
        file_path=Path("video.mp4"),
        file_size_bytes=1024
    )
    
    mock_transcription = AsyncMock(spec=ITranscriptionService)
    mock_transcription.transcribe.return_value = Transcription(
        segments=[TranscriptionSegment("Hello", 0, 2)],
        language="en"
    )
    
    mock_storage = AsyncMock(spec=IStorageService)
    
    # Create Use Case with mocks
    use_case = TranscribeYouTubeVideoUseCase(
        video_downloader=mock_downloader,
        transcription_service=mock_transcription,
        storage_service=mock_storage
    )
    
    # Execute
    request = TranscribeRequestDTO(youtube_url="https://youtu.be/123")
    response = await use_case.execute(request)
    
    # Assertions
    assert response.language == "en"
    assert response.total_segments == 1
    mock_downloader.download.assert_called_once()
    mock_transcription.transcribe.assert_called_once()
```

---

**Version**: 3.0.0

[⬅️ Back](../README.md)
