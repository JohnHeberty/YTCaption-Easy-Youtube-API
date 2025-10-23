# TranscribeYouTubeVideoUseCase

Main Use Case that orchestrates YouTube video transcription process.

---

## Responsibility

Coordinate video download + transcription + cache + cleanup.

**File**: `src/application/use_cases/transcribe_video.py`

---

## Execution Flow

```
1. Validate YouTube URL
2. Check if should use YouTube Transcript
   ├── YES → Get YouTube captions (fast)
   └── NO → Continue with Whisper
3. Create temporary directory
4. Download video
5. [v2.2.1] Check cache using file_hash
   ├── HIT → Return cached result
   └── MISS → Continue processing
6. [v2.0] Validate audio (duration, integrity)
7. [v2.1] Transcribe with Whisper + global timeout
8. [v2.2.1] Save to cache
9. Clean temporary files
10. Return response
```

---

## Constructor Parameters

```python
def __init__(
    self,
    video_downloader: IVideoDownloader,
    transcription_service: ITranscriptionService,
    storage_service: IStorageService,
    cleanup_after_processing: bool = True,
    max_video_duration: int = 10800,  # 3h
    audio_validator=None,  # v2.0
    transcription_cache=None  # v2.0
)
```

---

## Main Method

### `execute(request: TranscribeRequestDTO) -> TranscribeResponseDTO`

**Input**: `TranscribeRequestDTO`
- `youtube_url` - YouTube URL
- `language` - Language ("auto" for automatic detection)
- `use_youtube_transcript` - Use YouTube captions (v2.0)
- `prefer_manual_subtitles` - Prefer manual subtitles (v2.0)

**Output**: `TranscribeResponseDTO`
- `transcription_id` - Unique UUID
- `youtube_url` - Video URL
- `video_id` - Video ID
- `language` - Detected language
- `full_text` - Full text
- `segments` - List of segments with timestamps
- `total_segments` - Number of segments
- `duration` - Total duration (seconds)
- `processing_time` - Processing time (seconds)
- `source` - "whisper" or "youtube_transcript"

**Exceptions**:
- `ValidationError` - Invalid URL, corrupted audio
- `VideoDownloadError` - Download failure
- `TranscriptionError` - Transcription failure
- `OperationTimeoutError` - Transcription timeout (v2.1)

---

## Complete Example

```python
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

# Create Use Case
use_case = TranscribeYouTubeVideoUseCase(
    video_downloader=downloader,
    transcription_service=whisper_service,
    storage_service=storage,
    cleanup_after_processing=True,
    max_video_duration=10800,
    audio_validator=validator,  # v2.0
    transcription_cache=cache    # v2.0
)

# Example 1: Transcription with Whisper
request1 = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="auto"
)
response1 = await use_case.execute(request1)

# Example 2: Use YouTube captions (fast)
request2 = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    use_youtube_transcript=True,
    prefer_manual_subtitles=True
)
response2 = await use_case.execute(request2)

# Process response
print(f"ID: {response1.transcription_id}")
print(f"Language: {response1.language}")
print(f"Segments: {response1.total_segments}")
print(f"Duration: {response1.duration:.1f}s")
print(f"Processing: {response1.processing_time:.2f}s")
print(f"Source: {response1.source}")
print(f"\nFull text:\n{response1.full_text}")
```

---

## Features by Version

### v2.0
- ✅ Transcription cache
- ✅ Audio validation before processing
- ✅ YouTube Transcript support (fast)
- ✅ Processing time estimation

### v2.1
- ✅ Global transcription timeout
- ✅ Granular exceptions (`AudioTooLongError`, `OperationTimeoutError`)
- ✅ Improved logging

### v2.2.1
- ✅ Cache reimplemented with `file_hash` (after download)
- ✅ More reliable cache (doesn't depend on URL, uses file hash)

---

## Dynamic Timeout (v2.1)

The Use Case calculates timeout dynamically based on:
- Audio duration
- Whisper model used
- Processing factors (realtime factor)

```python
# Factors per model
tiny:   2.0x realtime  # ~2x faster than duration
base:   1.5x realtime
small:  0.8x realtime
medium: 0.4x realtime
large:  0.2x realtime

# Example: 60s audio with "base" model
base_time = 60 / 1.5 = 40s
overhead = 40 * 0.2 = 8s
safety = 40 * 0.5 = 20s
timeout = 40 + 8 + 20 = 68s
```

---

## Cache (v2.2.1)

**Cache Key**: `file_hash + model_name + language`

```python
# Hash calculated AFTER download
file_hash = compute_file_hash(video_file.file_path)

# Check cache
cached = cache.get(
    file_hash=file_hash,
    model_name="base",
    language="en"
)

if cached:
    return cached  # Cache HIT
else:
    # Cache MISS → process
    result = await transcribe(video_file)
    
    # Save to cache
    cache.put(
        file_hash=file_hash,
        transcription_data=result,
        model_name="base",
        language="en"
    )
```

**Benefits**:
- Same video processed only once
- Cache works even with different URLs
- Based on actual file content (SHA256 hash)

---

## Tests

```python
async def test_transcribe_success():
    use_case = TranscribeYouTubeVideoUseCase(
        video_downloader=mock_downloader,
        transcription_service=mock_transcription,
        storage_service=mock_storage
    )
    
    request = TranscribeRequestDTO(
        youtube_url="https://youtu.be/dQw4w9WgXcQ",
        language="en"
    )
    
    response = await use_case.execute(request)
    
    assert response.language == "en"
    assert response.total_segments > 0
    assert response.source == "whisper"

async def test_transcribe_with_cache():
    cache = TranscriptionCache()
    use_case = TranscribeYouTubeVideoUseCase(
        transcription_cache=cache,
        # ...
    )
    
    # First execution (cache MISS)
    response1 = await use_case.execute(request)
    
    # Second execution (cache HIT)
    response2 = await use_case.execute(request)
    
    assert response1.transcription_id == response2.transcription_id
    assert response2.processing_time < response1.processing_time

async def test_transcribe_timeout():
    # Simulate slow transcription
    async def slow_transcribe(*args, **kwargs):
        await asyncio.sleep(100)
    
    mock_service = AsyncMock()
    mock_service.transcribe = slow_transcribe
    
    use_case = TranscribeYouTubeVideoUseCase(
        transcription_service=mock_service,
        # ...
    )
    
    with pytest.raises(OperationTimeoutError):
        await use_case.execute(request)
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0