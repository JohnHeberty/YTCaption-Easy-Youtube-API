# Domain Exceptions

Custom domain exception hierarchy.

---

## Overview

The domain defines an exception hierarchy to represent business errors:
- **Granularity**: Specific exceptions for precise debugging
- **Inheritance**: All derive from `DomainException`
- **Context**: Exceptions carry relevant information (file, timeout, etc.)

**File**: `src/domain/exceptions.py`

---

## Hierarchy

```
DomainException (base)
├── VideoDownloadError
│   └── NetworkError
├── TranscriptionError
│   ├── AudioTooLongError
│   ├── AudioCorruptedError
│   ├── ModelLoadError
│   ├── WorkerPoolError
│   └── FFmpegError
├── StorageError
├── ValidationError
│   ├── AudioTooLongError
│   └── AudioCorruptedError
├── ResourceNotFoundError
├── ServiceUnavailableError
├── OperationTimeoutError
├── QuotaExceededError
└── CacheError
```

---

## Base Exceptions

### `DomainException`
Root exception for all domain errors.

```python
try:
    await service.transcribe(video)
except DomainException as e:
    # Catch ANY domain error
    log.error(f"Domain error: {e}")
```

### `VideoDownloadError`
Error downloading video from YouTube.

```python
try:
    video = await downloader.download(url, path)
except VideoDownloadError as e:
    print(f"Download failed: {e}")
```

### `TranscriptionError`
Error transcribing audio.

```python
try:
    transcription = await service.transcribe(video)
except TranscriptionError as e:
    print(f"Transcription failed: {e}")
```

---

## Granular Exceptions (v2.1)

### `AudioTooLongError`
Audio exceeds maximum allowed duration.

```python
try:
    validate_audio_duration(video, max_duration=3600)
except AudioTooLongError as e:
    print(f"Audio too long: {e.duration}s (max: {e.max_duration}s)")
```

**Attributes**:
- `duration: float` - Actual audio duration
- `max_duration: float` - Maximum allowed duration

### `AudioCorruptedError`
Audio file corrupted or unreadable.

```python
try:
    await service.transcribe(video)
except AudioCorruptedError as e:
    print(f"Corrupted file: {e.file_path}")
    print(f"Reason: {e.reason}")
```

**Attributes**:
- `file_path: str` - File path
- `reason: str` - Corruption reason

### `ModelLoadError`
Error loading Whisper model.

```python
try:
    service = WhisperService(model="large")
except ModelLoadError as e:
    print(f"Failed to load '{e.model_name}': {e.reason}")
```

**Attributes**:
- `model_name: str` - Model name (tiny, base, etc.)
- `reason: str` - Error reason

### `WorkerPoolError`
Error in transcription worker pool.

```python
try:
    result = await parallel_service.transcribe(video)
except WorkerPoolError as e:
    print(f"Worker {e.worker_id} failed: {e.reason}")
```

**Attributes**:
- `worker_id: int` - Worker ID (optional)
- `reason: str` - Error reason

### `FFmpegError`
Error executing FFmpeg.

```python
try:
    await ffmpeg_optimizer.optimize(audio_path)
except FFmpegError as e:
    print(f"Command: {e.command}")
    print(f"Error: {e.stderr[:200]}")
```

**Attributes**:
- `command: str` - FFmpeg command executed
- `stderr: str` - Error output (stderr)

### `OperationTimeoutError`
Operation exceeded time limit.

```python
try:
    video = await downloader.download(url, timeout=300)
except OperationTimeoutError as e:
    print(f"Operation '{e.operation}' timeout after {e.timeout}s")
```

**Attributes**:
- `operation: str` - Operation name
- `timeout: float` - Time limit in seconds

### `QuotaExceededError`
Usage quota/limit exceeded.

```python
try:
    await rate_limiter.acquire()
except QuotaExceededError as e:
    print(f"Quota exceeded: {e.current}/{e.limit} {e.resource}")
```

**Attributes**:
- `resource: str` - Limited resource
- `limit: int` - Maximum limit
- `current: int` - Current usage

---

## Usage Example

```python
from src.domain.exceptions import (
    DomainException,
    TranscriptionError,
    AudioTooLongError,
    ModelLoadError
)

async def transcribe_video(video: VideoFile):
    try:
        # Validate duration
        if video.duration > 3600:
            raise AudioTooLongError(
                duration=video.duration,
                max_duration=3600
            )
        
        # Load model
        try:
            service = WhisperService(model="large")
        except Exception as e:
            raise ModelLoadError(
                model_name="large",
                reason=str(e)
            )
        
        # Transcribe
        return await service.transcribe(video)
    
    except AudioTooLongError as e:
        log.warning(f"Audio too long: {e.duration}s")
        raise
    
    except ModelLoadError as e:
        log.error(f"Error loading model: {e.reason}")
        # Fallback to smaller model
        service = WhisperService(model="base")
        return await service.transcribe(video)
    
    except TranscriptionError as e:
        log.error(f"Transcription error: {e}")
        raise
    
    except DomainException as e:
        log.error(f"Domain error: {e}")
        raise
```

---

## Tests

```python
def test_audio_too_long_error():
    error = AudioTooLongError(duration=7200, max_duration=3600)
    assert error.duration == 7200
    assert error.max_duration == 3600
    assert "7200" in str(error)
    assert "3600" in str(error)

def test_model_load_error():
    error = ModelLoadError(model_name="large", reason="CUDA out of memory")
    assert error.model_name == "large"
    assert "CUDA" in error.reason

def test_ffmpeg_error():
    error = FFmpegError(
        command="ffmpeg -i input.mp4",
        stderr="Invalid codec"
    )
    assert error.command == "ffmpeg -i input.mp4"
    assert "Invalid" in error.stderr
```

---

[⬅️ Back](README.md)

**Version**: 3.0.0