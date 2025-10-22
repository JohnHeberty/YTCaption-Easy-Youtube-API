# Transcription DTOs

Data Transfer Objects para transcrição de vídeos.

---

## Visão Geral

DTOs são objetos imutáveis validados com **Pydantic** que transferem dados entre camadas.

**Arquivo**: `src/application/dtos/transcription_dtos.py`

---

## Request DTOs

### TranscribeRequestDTO
DTO para requisição de transcrição.

```python
class TranscribeRequestDTO(BaseModel):
    youtube_url: str                       # URL do YouTube
    language: Optional[str] = "auto"       # Idioma (auto detecção)
    use_youtube_transcript: bool = False   # Usar legendas do YouTube
    prefer_manual_subtitles: bool = True   # Preferir legendas manuais
```

**Validação**: URL deve conter "youtube.com" ou "youtu.be"

**Exemplo**:
```python
request = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="en"
)
```

### ExportCaptionsRequestDTO
DTO para exportação de legendas.

```python
class ExportCaptionsRequestDTO(BaseModel):
    format: str = "srt"  # srt, vtt, json
```

---

## Response DTOs

### TranscribeResponseDTO
DTO para resposta de transcrição.

```python
class TranscribeResponseDTO(BaseModel):
    transcription_id: str              # UUID único
    youtube_url: str                   # URL do vídeo
    video_id: str                      # ID do vídeo
    language: str                      # Idioma detectado
    full_text: str                     # Texto completo
    segments: List[TranscriptionSegmentDTO]  # Segmentos
    total_segments: int                # Número de segmentos
    duration: float                    # Duração (segundos)
    processing_time: Optional[float]   # Tempo de processamento
    source: str                        # "whisper" ou "youtube_transcript"
    transcript_type: Optional[str]     # "manual" ou "auto" (YouTube)
```

**Exemplo**:
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
DTO para informações do vídeo.

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
DTO para health check da API.

```python
class HealthCheckDTO(BaseModel):
    status: str                  # "healthy" ou "unhealthy"
    version: str                 # "3.0.0"
    whisper_model: str           # "base"
    storage_usage: dict          # Uso de armazenamento
    uptime_seconds: float        # Tempo ativo
```

### ErrorResponseDTO
DTO padronizado para erros.

```python
class ErrorResponseDTO(BaseModel):
    error: str               # Tipo do erro
    message: str             # Mensagem legível
    request_id: str          # ID da requisição
    details: Optional[Dict[str, Any]]  # Detalhes extras
```

**Exemplo**:
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
Segmento individual de transcrição.

```python
class TranscriptionSegmentDTO(BaseModel):
    text: str        # Texto do segmento
    start: float     # Tempo inicial (segundos)
    end: float       # Tempo final (segundos)
    duration: float  # Duração (segundos)
```

### SubtitlesInfoDTO
Informações sobre legendas disponíveis.

```python
class SubtitlesInfoDTO(BaseModel):
    available: List[str]        # Todas as legendas
    manual_languages: List[str] # Idiomas com legendas manuais
    auto_languages: List[str]   # Idiomas com legendas automáticas
    total: int                  # Total de legendas
```

### WhisperRecommendationDTO
Recomendação sobre usar Whisper ou YouTube.

```python
class WhisperRecommendationDTO(BaseModel):
    should_use_youtube_transcript: bool
    reason: str
    estimated_time_whisper: Optional[float]
    estimated_time_youtube: Optional[float]
```

### LanguageDetectionDTO
Resultado da detecção de idioma.

```python
class LanguageDetectionDTO(BaseModel):
    detected_language: Optional[str]  # Código ISO 639-1
    confidence: Optional[float]       # 0-1
    method: Optional[str]             # "metadata", "whisper", etc.
```

### ReadinessCheckDTO
Verificação de prontidão da API.

```python
class ReadinessCheckDTO(BaseModel):
    status: str                  # "ready" ou "not_ready"
    checks: Dict[str, bool]      # Status de cada componente
    message: Optional[str]
    timestamp: float
```

---

## Validação Automática

Pydantic valida automaticamente tipos e restrições:

```python
# ✅ Válido
dto = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=123",
    language="en"
)

# ❌ Inválido: URL sem YouTube
dto = TranscribeRequestDTO(
    youtube_url="https://vimeo.com/123"  # ValueError!
)

# ❌ Inválido: tipo incorreto
dto = TranscribeRequestDTO(
    youtube_url=123  # ValidationError!
)
```

---

## Serialização

```python
# Para JSON
response_json = response.model_dump()
# ou
response_json = response.model_dump_json()

# De JSON
response = TranscribeResponseDTO.model_validate(json_data)
# ou
response = TranscribeResponseDTO.model_validate_json(json_string)
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0