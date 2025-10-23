# Presentation Layer - FastAPI REST API

Presentation layer - REST API with FastAPI.

---

## Overview

The **Presentation Layer** exposes functionality via REST API:
- **FastAPI** framework (async/await)
- **OpenAPI/Swagger** automatic documentation
- **Pydantic** validation
- **CORS** middleware
- **Rate limiting** per IP
- **Error handling** standardized
- **Health checks** (liveness/readiness)

---

## Main Endpoints

### POST `/api/v1/transcribe`
Transcribes YouTube video.

**Request**:
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "auto",
  "use_youtube_transcript": false
}
```

**Response**:
```json
{
  "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "full_text": "Never gonna give you up...",
  "segments": [...],
  "duration": 213.5,
  "processing_time": 18.3
}
```

### GET `/api/v1/video-info/{video_id}`
Gets video information.

### POST `/api/v1/transcriptions/{id}/export`
Exports transcription (SRT/VTT/JSON).

### GET `/health`
Health check (status, version, uptime).

### GET `/ready`
Readiness check (Whisper model loaded, storage OK).

---

## Middlewares

### ErrorHandlerMiddleware
- Captures exceptions
- Returns standardized `ErrorResponseDTO`
- Error logging

### RateLimitMiddleware
- Limit per IP (60 req/min)
- Adaptive rate limiting
- 429 Too Many Requests response

### CORSMiddleware
- Allows cross-origin requests
- Configurable per domain

---

## Dependency Injection

FastAPI `Depends()` for dependency injection:

```python
from fastapi import Depends

def get_transcribe_use_case() -> TranscribeYouTubeVideoUseCase:
    downloader = get_downloader()
    transcription = get_transcription_service()
    storage = get_storage_service()
    
    return TranscribeYouTubeVideoUseCase(
        video_downloader=downloader,
        transcription_service=transcription,
        storage_service=storage
    )

@router.post("/transcribe")
async def transcribe(
    request: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
):
    return await use_case.execute(request)
```

---

## Automatic Documentation

FastAPI generates interactive documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Client Example

```python
import httpx

async with httpx.AsyncClient() as client:
    # Transcribe
    response = await client.post(
        "http://localhost:8000/api/v1/transcribe",
        json={
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
            "language": "auto"
        },
        timeout=300.0
    )
    
    result = response.json()
    transcription_id = result["transcription_id"]
    
    # Export SRT
    srt_response = await client.post(
        f"http://localhost:8000/api/v1/transcriptions/{transcription_id}/export",
        json={"format": "srt"}
    )
    
    srt_content = srt_response.text
```

---

## Deployment

```bash
# Development
uvicorn src.presentation.api.main:app --reload

# Production
uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker-compose up -d
```

---

**Version**: 3.0.0

[⬅️ Back](../README.md)
