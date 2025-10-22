# Presentation Layer - FastAPI REST API

Camada de apresentação - API REST com FastAPI.

---

## Visão Geral

A **Presentation Layer** expõe a funcionalidade via REST API:
- **FastAPI** framework (async/await)
- **OpenAPI/Swagger** documentation automática
- **Pydantic** validation
- **CORS** middleware
- **Rate limiting** por IP
- **Error handling** padronizado
- **Health checks** (liveness/readiness)

---

## Endpoints Principais

### POST `/api/v1/transcribe`
Transcreve vídeo do YouTube.

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
Obtém informações do vídeo.

### POST `/api/v1/transcriptions/{id}/export`
Exporta transcrição (SRT/VTT/JSON).

### GET `/health`
Health check (status, version, uptime).

### GET `/ready`
Readiness check (Whisper model loaded, storage OK).

---

## Middlewares

### ErrorHandlerMiddleware
- Captura exceções
- Retorna `ErrorResponseDTO` padronizado
- Logging de erros

### RateLimitMiddleware
- Limite por IP (60 req/min)
- Rate limiting adaptativo
- Resposta 429 Too Many Requests

### CORSMiddleware
- Permite cross-origin requests
- Configurável por domínio

---

## Dependency Injection

FastAPI `Depends()` para injeção de dependências:

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

## Documentação Automática

FastAPI gera documentação interativa:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Exemplo de Cliente

```python
import httpx

async with httpx.AsyncClient() as client:
    # Transcrever
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
    
    # Exportar SRT
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

**Versão**: 3.0.0

[⬅️ Voltar](../README.md)
