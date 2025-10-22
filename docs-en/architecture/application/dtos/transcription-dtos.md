# Transcription DTOs

Data Transfer Objects for video transcription.

---

## Overview

DTOs are immutable objects validated with **Pydantic** that transfer data between layers.

**File**: `src/application/dtos/transcription_dtos.py`

---

## Request DTOs

### TranscribeRequestDTO
DTO for transcription request.

```python
class TranscribeRequestDTO(BaseModel):
    youtube_url: str                       # YouTube URL
    language: Optional[str] = "auto"       # Language (auto detection)
    use_youtube_transcript: bool = False   # Use YouTube captions
    prefer_manual_subtitles: bool = True   # Prefer manual subtitles
```

**Validation**: URL must contain "youtube.com" or "youtu.be"

**Example**:
```python
request = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="en"
)
```

### ExportCaptionsRequestDTO
DTO for caption export.

```python
class ExportCaptionsRequestDTO(BaseModel):
    format: str = "srt"  # srt, vtt, json
```

---

## Response DTOs

### TranscribeResponseDTO
DTO for transcription response.

```python
class TranscribeResponseDTO(BaseModel):
    transcription_id: str              # Unique UUID
    youtube_url: str                   # Video URL
    video_id: str                      # Video ID
    language: str                      # Detected language
    full_text: str                     # Full text
    segments: List[TranscriptionSegmentDTO]  # Segments
    total_segments: int                # Number of segments
    duration: float                    # Duration (seconds)
    processing_time: Optional[float]   # Processing time
    source: str                        # "whisper" or "youtube_transcript"
    transcript_type: Optional[str]     # "manual" or "auto" (YouTube)
```

**Example**:
```json
{
  "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "full_text": "Never gonna give you up...",
  "segments": [...],
  "total_segments": 50,
  "duration": 213.5,
  "processing_time": 45.2,
  "source": "whisper"
}
```

### VideoInfoResponseDTO
DTO for video information.

```python
class VideoInfoResponseDTO(BaseModel):
    video_id: str
    title: str
    duration_seconds: int
    duration_formatted: str            # "HH:MM:SS"
    uploader: Optional[str]
    upload_date: Optional[str]
    view_count: Optional[int]
    description_preview: str
    language_detection: Optional[LanguageDetectionDTO]
    subtitles: SubtitlesInfoDTO
    whisper_recommendation: Optional[WhisperRecommendationDTO]
    warnings: List[str] = []
```

### HealthCheckDTO
DTO for API health check.

```python
class HealthCheckDTO(BaseModel):
    status: str                  # "healthy" or "unhealthy"
    version: str                 # "3.0.0"
    whisper_model: str           # "base"
    storage_usage: dict          # Storage usage
    uptime_seconds: float        # Uptime
```

### ErrorResponseDTO
Standardized DTO for errors.

```python
class ErrorResponseDTO(BaseModel):
    error: str               # Error type
    message: str             # Human-readable message
    request_id: str          # Request ID
    details: Optional[Dict[str, Any]]  # Extra details
```

**Example**:
```json
{
  "error": "AudioTooLongError",
  "message": "Audio duration (7250s) exceeds maximum allowed (7200s)",
  "request_id": "abc-123-def-456",
  "details": {
    "duration": 7250,
    "max_duration": 7200
  }
}
```

---

## Auxiliary DTOs

### TranscriptionSegmentDTO
Individual transcription segment.

```python
class TranscriptionSegmentDTO(BaseModel):
    text: str        # Segment text
    start: float     # Start time (seconds)
    end: float       # End time (seconds)
    duration: float  # Duration (seconds)
```

### SubtitlesInfoDTO
Information about available subtitles.

```python
class SubtitlesInfoDTO(BaseModel):
    available: List[str]        # All subtitles
    manual_languages: List[str] # Languages with manual subtitles
    auto_languages: List[str]   # Languages with auto subtitles
    total: int                  # Total subtitles
```

### WhisperRecommendationDTO
Recommendation about using Whisper or YouTube.

```python
class WhisperRecommendationDTO(BaseModel):
    should_use_youtube_transcript: bool
    reason: str
    estimated_time_whisper: Optional[float]
    estimated_time_youtube: Optional[float]
```

### LanguageDetectionDTO
Language detection result.

```python
class LanguageDetectionDTO(BaseModel):
    detected_language: Optional[str]  # ISO 639-1 code
    confidence: Optional[float]       # 0-1
    method: Optional[str]             # "metadata", "whisper", etc.
```

### ReadinessCheckDTO
API readiness check.

```python
class ReadinessCheckDTO(BaseModel):
    status: str                  # "ready" or "not_ready"
    checks: Dict[str, bool]      # Status of each component
    message: Optional[str]
    timestamp: float
```

---

## Automatic Validation

Pydantic automatically validates types and constraints:

```python
# ✅ Valid
dto = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=123",
    language="en"
)

# ❌ Invalid: URL without YouTube
dto = TranscribeRequestDTO(
    youtube_url="https://vimeo.com/123"  # ValueError!
)

# ❌ Invalid: incorrect type
dto = TranscribeRequestDTO(
    youtube_url=123  # ValidationError!
)
```

---

## Serialization

```python
# To JSON
response_json = response.model_dump()
# or
response_json = response.model_dump_json()

# From JSON
response = TranscribeResponseDTO.model_validate(json_data)
# or
response = TranscribeResponseDTO.model_validate_json(json_string)
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0