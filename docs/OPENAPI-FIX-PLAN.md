# Plano de Correção - OpenAPI Inconsistencies

## 📋 Overview

**Objetivo:** Corrigir todas as inconsistências entre OpenAPI `/docs` e comportamento real da API  
**Esforço Total:** ~8 horas  
**Prioridade:** ALTA  
**Versão Alvo:** v2.2.1

---

## 🎯 FASE 1: Correções Críticas [3h]

### ✅ Task 1.1: Criar VideoInfoResponseDTO [1h]

**Prioridade:** 🔴 CRÍTICA  
**Arquivo:** `src/application/dtos/transcription_dtos.py`

#### Checklist
- [ ] Criar `SubtitlesInfoDTO`
- [ ] Criar `LanguageDetectionDTO`
- [ ] Criar `WhisperRecommendationDTO`
- [ ] Criar `VideoInfoResponseDTO`
- [ ] Adicionar examples em `Config.json_schema_extra`
- [ ] Atualizar `video_info.py` para usar `response_model=VideoInfoResponseDTO`
- [ ] Testar manualmente em `/docs`
- [ ] Validar schema gerado no OpenAPI

**Código:**
```python
# Adicionar em src/application/dtos/transcription_dtos.py

class SubtitlesInfoDTO(BaseModel):
    """Informações sobre legendas disponíveis."""
    available: List[str] = Field(..., description="Idiomas disponíveis")
    manual_languages: List[str] = Field(..., description="Idiomas com legendas manuais")
    auto_languages: List[str] = Field(..., description="Idiomas com legendas automáticas")
    total: int = Field(..., description="Total de legendas")


class LanguageDetectionDTO(BaseModel):
    """Resultado da detecção de idioma."""
    detected_language: Optional[str] = Field(None, description="Idioma detectado")
    confidence: Optional[float] = Field(None, description="Confiança (0-1)")
    method: Optional[str] = Field(None, description="Método de detecção")


class WhisperRecommendationDTO(BaseModel):
    """Recomendação de uso do Whisper vs YouTube."""
    should_use_youtube_transcript: bool = Field(..., description="Usar transcrição do YouTube?")
    reason: str = Field(..., description="Razão da recomendação")
    estimated_time_whisper: Optional[float] = Field(None, description="Tempo estimado Whisper (s)")
    estimated_time_youtube: Optional[float] = Field(None, description="Tempo estimado YouTube (s)")


class VideoInfoResponseDTO(BaseModel):
    """Resposta de informações do vídeo."""
    video_id: str
    title: str
    duration_seconds: int
    duration_formatted: str
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    description_preview: str
    language_detection: Optional[LanguageDetectionDTO] = None
    subtitles: SubtitlesInfoDTO
    whisper_recommendation: Optional[WhisperRecommendationDTO] = None
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "dQw4w9WgXcQ",
                "title": "Rick Astley - Never Gonna Give You Up",
                "duration_seconds": 213,
                "duration_formatted": "00:03:33",
                "uploader": "Rick Astley",
                "upload_date": "20091024",
                "view_count": 1400000000,
                "description_preview": "Official video...",
                "language_detection": {
                    "detected_language": "en",
                    "confidence": 0.95,
                    "method": "metadata"
                },
                "subtitles": {
                    "available": ["en", "es"],
                    "manual_languages": ["en"],
                    "auto_languages": ["es"],
                    "total": 2
                },
                "whisper_recommendation": {
                    "should_use_youtube_transcript": True,
                    "reason": "Manual subtitles available",
                    "estimated_time_whisper": 45.0,
                    "estimated_time_youtube": 2.0
                },
                "warnings": []
            }
        }
```

```python
# Atualizar em src/presentation/api/routes/video_info.py

@router.post(
    "/info",
    response_model=VideoInfoResponseDTO,  # ← ADICIONAR
    status_code=200,
    summary="Get video information",
    description="Get video metadata without downloading audio",
    responses={
        400: {"model": ErrorResponseDTO, "description": "Invalid URL"},
        404: {"model": ErrorResponseDTO, "description": "Video not found"},
        429: {"model": ErrorResponseDTO, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponseDTO, "description": "Server error"}
    }
)
async def get_video_info(...):
    # ... código existente ...
    
    # Garantir que resposta está no formato correto
    return VideoInfoResponseDTO(
        video_id=info.get('video_id'),
        title=info.get('title'),
        duration_seconds=duration,
        duration_formatted=duration_formatted,
        uploader=info.get('uploader'),
        upload_date=info.get('upload_date'),
        view_count=info.get('view_count'),
        description_preview=description_preview,
        language_detection=LanguageDetectionDTO(**info.get('language_detection', {})) if info.get('language_detection') else None,
        subtitles=SubtitlesInfoDTO(
            available=info.get('available_subtitles', []),
            manual_languages=info.get('subtitle_languages', []),
            auto_languages=info.get('auto_caption_languages', []),
            total=len(info.get('available_subtitles', []))
        ),
        whisper_recommendation=WhisperRecommendationDTO(**info.get('whisper_recommendation', {})) if info.get('whisper_recommendation') else None,
        warnings=warnings
    )
```

**Validação:**
```bash
# 1. Testar endpoint
curl -X POST http://localhost:8000/api/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}'

# 2. Verificar schema no OpenAPI
curl http://localhost:8000/openapi.json | jq '.components.schemas.VideoInfoResponseDTO'
```

---

### ✅ Task 1.2: Padronizar ErrorResponseDTO [2h]

**Prioridade:** 🔴 CRÍTICA  
**Arquivos:** `transcription_dtos.py` + todos os arquivos de rotas

#### Checklist
- [ ] Atualizar `ErrorResponseDTO` para incluir `request_id`
- [ ] Criar helper function `build_error_response()`
- [ ] Atualizar `transcription.py` (9 exceptions)
- [ ] Atualizar `video_info.py` (3 exceptions)
- [ ] Atualizar `system.py` (5 exceptions)
- [ ] Adicionar `responses={...}` em todos decoradores `@router`
- [ ] Testar manualmente cada tipo de erro
- [ ] Verificar schemas no `/docs`

**Código:**

```python
# Atualizar em src/application/dtos/transcription_dtos.py

class ErrorResponseDTO(BaseModel):
    """DTO padronizado para erros."""
    error: str = Field(..., description="Tipo/classe do erro")
    message: str = Field(..., description="Mensagem legível")
    request_id: str = Field(..., description="ID da requisição")  # ← ADICIONAR
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "AudioTooLongError",
                "message": "Audio duration (7250s) exceeds maximum (7200s)",
                "request_id": "abc-123-def-456",
                "details": {
                    "duration": 7250,
                    "max_duration": 7200
                }
            }
        }
```

```python
# Criar helper em src/presentation/api/routes/__init__.py ou dependencies.py

from fastapi import HTTPException, status as http_status
from fastapi.encoders import jsonable_encoder
from src.application.dtos.transcription_dtos import ErrorResponseDTO

def raise_error(
    status_code: int,
    error_type: str,
    message: str,
    request_id: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Helper para lançar HTTPException com ErrorResponseDTO.
    
    Args:
        status_code: Código HTTP (400, 404, 500, etc.)
        error_type: Nome da exception (AudioTooLongError, etc.)
        message: Mensagem de erro legível
        request_id: ID da requisição
        details: Dicionário com detalhes adicionais
    """
    error_response = ErrorResponseDTO(
        error=error_type,
        message=message,
        request_id=request_id,
        details=details or {}
    )
    
    raise HTTPException(
        status_code=status_code,
        detail=jsonable_encoder(error_response)
    )
```

```python
# Exemplo de uso em src/presentation/api/routes/transcription.py

# ANTES (INCONSISTENTE)
except AudioTooLongError as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "AudioTooLongError",
            "message": str(e),
            "request_id": request_id,
            "details": {...}
        }
    )

# DEPOIS (PADRONIZADO)
except AudioTooLongError as e:
    raise_error(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        error_type="AudioTooLongError",
        message=str(e),
        request_id=request_id,
        details={
            "duration": e.duration,
            "max_duration": e.max_duration
        }
    )
```

```python
# Atualizar decoradores em todos endpoints

@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    status_code=200,
    responses={  # ← ADICIONAR/ATUALIZAR
        400: {
            "model": ErrorResponseDTO,
            "description": "Bad Request (validation, audio too long, corrupted)",
            "content": {
                "application/json": {
                    "example": {
                        "error": "AudioTooLongError",
                        "message": "Audio exceeds max duration",
                        "request_id": "abc-123",
                        "details": {"duration": 7250, "max_duration": 7200}
                    }
                }
            }
        },
        404: {
            "model": ErrorResponseDTO,
            "description": "Video not found or download error"
        },
        429: {
            "model": ErrorResponseDTO,
            "description": "Rate limit exceeded (5 req/min)"
        },
        500: {
            "model": ErrorResponseDTO,
            "description": "Internal server error"
        },
        503: {
            "model": ErrorResponseDTO,
            "description": "Service unavailable (Circuit Breaker open)"
        },
        504: {
            "model": ErrorResponseDTO,
            "description": "Gateway timeout"
        }
    },
    summary="Transcribe YouTube video",
    description="""
    Transcribe a YouTube video using Whisper AI or YouTube's native transcripts.
    
    **Rate Limit:** 5 requests per minute per IP address
    
    **Processing Time:** 
    - With YouTube transcripts: ~2-5 seconds
    - With Whisper: ~30-60 seconds (depends on video duration and model)
    """
)
```

**Arquivos a modificar:**
1. `src/presentation/api/routes/transcription.py`:
   - `AudioTooLongError` (linha ~127)
   - `CircuitBreakerOpenError` (linha ~151)
   - `AudioCorruptedError` (linha ~170)
   - `ValidationError` (linha ~188)
   - `OperationTimeoutError` (linha ~207)
   - `VideoDownloadError/NetworkError` (linha ~229)
   - `TranscriptionError` (linha ~249)
   - Exception genérica (linha ~265)

2. `src/presentation/api/routes/video_info.py`:
   - `ValidationError` (linha ~68)
   - `VideoDownloadError` (linha ~169)
   - Exception genérica (linha ~188)

3. `src/presentation/api/routes/system.py`:
   - Exception em `/health` (linha ~76)
   - Exception em `/health/ready` (linha ~220)
   - Exception em `/metrics` (linha ~401)
   - Demais exceptions em endpoints admin

**Validação:**
```bash
# Testar erro 400
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "invalid"}' | jq

# Deve retornar:
{
  "detail": {
    "error": "ValidationError",
    "message": "Must be a valid YouTube URL",
    "request_id": "...",
    "details": {}
  }
}

# Verificar schema no OpenAPI
curl http://localhost:8000/openapi.json | jq '.components.schemas.ErrorResponseDTO'
```

---

## 🎯 FASE 2: Correções Médias [3h]

### ✅ Task 2.1: Criar ReadinessCheckDTO [0.5h]

**Prioridade:** 🟡 MÉDIA  
**Arquivo:** `src/application/dtos/transcription_dtos.py` + `system.py`

#### Checklist
- [ ] Criar `ReadinessCheckDTO`
- [ ] Atualizar `/health/ready` para usar `response_model`
- [ ] Testar endpoint
- [ ] Validar schema no `/docs`

**Código:**
```python
# src/application/dtos/transcription_dtos.py

class ReadinessCheckDTO(BaseModel):
    """Resposta de readiness check."""
    status: str = Field(..., description="Status (ready/not_ready)")
    checks: Dict[str, bool] = Field(..., description="Status de cada verificação")
    message: Optional[str] = Field(None, description="Mensagem adicional")
    timestamp: float = Field(..., description="Timestamp da verificação")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready",
                "checks": {
                    "storage": True,
                    "whisper_model": True,
                    "worker_pool": True
                },
                "message": "All systems operational",
                "timestamp": 1234567890.123
            }
        }
```

```python
# src/presentation/api/routes/system.py

@router.get(
    "/health/ready",
    response_model=ReadinessCheckDTO,  # ← ADICIONAR
    status_code=200,
    responses={
        503: {"model": ErrorResponseDTO, "description": "Not ready"}
    },
    summary="Readiness check",
    description="Check if API is ready to accept requests"
)
async def readiness_check(...):
    # Retornar DTO
    return ReadinessCheckDTO(
        status="ready",
        checks=checks,
        message=message,
        timestamp=time.time()
    )
```

---

### ✅ Task 2.2: Documentar Headers [1h]

**Prioridade:** 🟡 MÉDIA  
**Arquivos:** Todos endpoints

#### Checklist
- [ ] Adicionar `headers` em `responses` de todos endpoints
- [ ] Documentar `X-Request-ID`
- [ ] Documentar `X-Process-Time`
- [ ] Testar manualmente
- [ ] Verificar no `/docs`

**Código:**
```python
# Exemplo para TODOS os endpoints

@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    responses={
        200: {
            "description": "Transcription successful",
            "headers": {  # ← ADICIONAR
                "X-Request-ID": {
                    "description": "Unique request identifier for tracking and debugging",
                    "schema": {"type": "string", "format": "uuid"}
                },
                "X-Process-Time": {
                    "description": "Processing time in seconds (e.g., '12.345s')",
                    "schema": {"type": "string", "pattern": r"^\d+\.\d{3}s$"}
                }
            }
        },
        400: {"model": ErrorResponseDTO, "headers": {...}},  # ← MESMO PARA ERROS
        # ... demais responses
    }
)
```

**Aplicar em:**
- `/api/v1/transcribe`
- `/api/v1/video/info`
- `/health`
- `/health/ready`
- `/metrics`
- Demais endpoints admin

---

### ✅ Task 2.3: Documentar Rate Limits [1h]

**Prioridade:** 🟡 MÉDIA  
**Arquivos:** Todos endpoints com rate limit

#### Checklist
- [ ] Identificar todos endpoints com `@limiter.limit()`
- [ ] Adicionar rate limit na `description` de cada endpoint
- [ ] Criar exemplo de erro 429 padronizado
- [ ] Documentar `retry_after_seconds` nos erros 429
- [ ] Atualizar response 429 em todos decoradores

**Rate Limits atuais:**
```python
# transcription.py
@limiter.limit("5/minute")       # POST /transcribe

# video_info.py
@limiter.limit("10/minute")      # POST /video/info

# system.py
@limiter.limit("30/minute")      # GET /health
@limiter.limit("30/minute")      # GET /health/ready
@limiter.limit("10/minute")      # GET /metrics
@limiter.limit("5/minute")       # POST /admin/* (todos)
```

**Código:**
```python
# Atualizar description de TODOS os endpoints

@limiter.limit("5/minute")
@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    description="""
    Transcribe a YouTube video using Whisper AI or YouTube's native transcripts.
    
    **⚡ Rate Limit:** 5 requests per minute per IP address
    
    If rate limit is exceeded, returns HTTP 429 with retry-after information.
    
    **Processing Time:**
    - YouTube transcripts: 2-5 seconds
    - Whisper transcription: 30-120 seconds (depends on video duration and model)
    
    **Model Recommendations:**
    - `tiny`: Fastest, lower accuracy (~5x faster than base)
    - `base`: Good balance (default)
    - `small/medium/large`: Higher accuracy, slower processing
    """,
    responses={
        429: {
            "model": ErrorResponseDTO,
            "description": "Rate limit exceeded - 5 requests per minute per IP",
            "content": {
                "application/json": {
                    "example": {
                        "error": "RateLimitExceeded",
                        "message": "Rate limit exceeded: 5 per 1 minute",
                        "request_id": "abc-123-def",
                        "details": {
                            "limit": "5/minute",
                            "retry_after_seconds": 60
                        }
                    }
                }
            }
        }
    }
)
```

---

### ✅ Task 2.4: Padronizar Nomenclatura Logs [0.5h]

**Prioridade:** 🟡 MÉDIA  
**Arquivo:** `transcription.py`

#### Checklist
- [ ] Identificar campos com nomenclatura diferente
- [ ] Alinhar logs com nomes dos DTOs
- [ ] Manter consistência em todo o código

**Código:**
```python
# ANTES (INCONSISTENTE)
logger.info(
    "✅ Transcription successful",
    extra={
        "request_id": request_id,
        "transcription_id": response.transcription_id,
        "segments_count": response.total_segments,  # ← DIFERENTE DO DTO
        "processing_time": response.processing_time
    }
)

# DEPOIS (CONSISTENTE)
logger.info(
    "✅ Transcription successful",
    extra={
        "request_id": request_id,
        "transcription_id": response.transcription_id,
        "total_segments": response.total_segments,  # ← IGUAL AO DTO
        "processing_time": response.processing_time
    }
)
```

**Campos a corrigir:**
- `segments_count` → `total_segments` (transcription.py, linha ~114)

---

## 🎯 FASE 3: Melhorias + Documentação [2h]

### ✅ Task 3.1: Criar API Contract Documentation [1h]

**Prioridade:** 🟢 BAIXA  
**Arquivo:** `docs/API-CONTRACT.md`

#### Checklist
- [ ] Documentar estrutura de erros
- [ ] Documentar headers de response
- [ ] Documentar rate limits por endpoint
- [ ] Documentar status codes
- [ ] Adicionar exemplos de cada erro
- [ ] Linkar do README.md principal

**Estrutura sugerida:**
```markdown
# API Contract v2.2

## Base URL
- Local: `http://localhost:8000`
- Production: `https://api.example.com`

## Authentication
(futuro - Fase 4 do Roadmap)

## Rate Limits
| Endpoint | Limit | Per |
|----------|-------|-----|
| POST /api/v1/transcribe | 5 | minute |
| POST /api/v1/video/info | 10 | minute |
| GET /health | 30 | minute |

## Response Headers
- `X-Request-ID`: UUID for tracking
- `X-Process-Time`: Processing duration

## Error Format
All errors follow `ErrorResponseDTO`:
```json
{
  "error": "ErrorType",
  "message": "Human message",
  "request_id": "uuid",
  "details": {}
}
```

## Status Codes
- 200: Success
- 400: Bad Request (validation, audio issues)
- 404: Resource not found (video)
- 429: Rate limit exceeded
- 500: Internal server error
- 503: Service unavailable (Circuit Breaker)
- 504: Gateway timeout

## Endpoints
### POST /api/v1/transcribe
(detalhes completos)
...
```

---

### ✅ Task 3.2: Testes de Conformidade OpenAPI [1h]

**Prioridade:** 🟢 BAIXA  
**Arquivo:** `tests/integration/test_openapi_compliance.py`

#### Checklist
- [ ] Criar teste para cada endpoint
- [ ] Validar estrutura de responses
- [ ] Validar estrutura de erros
- [ ] Validar tipos de campos
- [ ] Validar campos obrigatórios
- [ ] Adicionar ao CI/CD

**Código:**
```python
# tests/integration/test_openapi_compliance.py

import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)


def test_video_info_response_schema():
    """Valida schema de /video/info."""
    response = client.post(
        "/api/v1/video/info",
        json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Campos obrigatórios
    assert "video_id" in data
    assert "title" in data
    assert "duration_seconds" in data
    assert "duration_formatted" in data
    assert "subtitles" in data
    assert "warnings" in data
    
    # Tipos corretos
    assert isinstance(data["video_id"], str)
    assert isinstance(data["duration_seconds"], int)
    assert isinstance(data["warnings"], list)
    assert isinstance(data["subtitles"], dict)
    
    # Subtitles tem estrutura correta
    assert "available" in data["subtitles"]
    assert "manual_languages" in data["subtitles"]
    assert "total" in data["subtitles"]


def test_error_response_schema():
    """Valida schema de ErrorResponseDTO."""
    response = client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "invalid-url"}
    )
    
    assert response.status_code == 400
    error = response.json()["detail"]
    
    # Campos obrigatórios do ErrorResponseDTO
    assert "error" in error
    assert "message" in error
    assert "request_id" in error  # ← IMPORTANTE
    
    # Tipos corretos
    assert isinstance(error["error"], str)
    assert isinstance(error["message"], str)
    assert isinstance(error["request_id"], str)


def test_response_headers():
    """Valida headers customizados."""
    response = client.get("/health")
    
    assert response.status_code == 200
    
    # Headers obrigatórios
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
    
    # Formatos corretos
    assert len(response.headers["X-Request-ID"]) == 36  # UUID
    assert response.headers["X-Process-Time"].endswith("s")


def test_rate_limit_error_format():
    """Valida formato de erro 429."""
    # Fazer requisições até ultrapassar limite
    for _ in range(6):  # Limite é 5/min
        client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://youtube.com/watch?v=test"}
        )
    
    response = client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "https://youtube.com/watch?v=test"}
    )
    
    if response.status_code == 429:
        error = response.json()["detail"]
        assert "error" in error
        assert "retry_after_seconds" in error.get("details", {})


@pytest.mark.parametrize("endpoint,expected_fields", [
    ("/health", ["status", "version", "whisper_model"]),
    ("/health/ready", ["status", "checks"]),
])
def test_system_endpoints_schema(endpoint, expected_fields):
    """Valida schemas de endpoints de sistema."""
    response = client.get(endpoint)
    assert response.status_code == 200
    
    data = response.json()
    for field in expected_fields:
        assert field in data, f"Campo '{field}' ausente em {endpoint}"
```

**Comandos de teste:**
```bash
# Rodar testes
pytest tests/integration/test_openapi_compliance.py -v

# Validar OpenAPI schema
curl http://localhost:8000/openapi.json > openapi.json
npx @redocly/cli lint openapi.json
```

---

## 📊 PROGRESSO TRACKING

### Status por Fase

| Fase | Tasks | Status | Tempo Estimado | Tempo Real |
|------|-------|--------|----------------|------------|
| 1 - Críticas | 2 | ⏳ Pendente | 3h | - |
| 2 - Médias | 4 | ⏳ Pendente | 3h | - |
| 3 - Baixas | 2 | ⏳ Pendente | 2h | - |
| **TOTAL** | **8** | **⏳** | **8h** | **-** |

### Checklist Geral

#### Fase 1 - Críticas
- [ ] 1.1 - VideoInfoResponseDTO criado
- [ ] 1.2 - ErrorResponseDTO padronizado

#### Fase 2 - Médias
- [ ] 2.1 - ReadinessCheckDTO criado
- [ ] 2.2 - Headers documentados
- [ ] 2.3 - Rate limits documentados
- [ ] 2.4 - Nomenclatura logs padronizada

#### Fase 3 - Baixas
- [ ] 3.1 - API Contract criado
- [ ] 3.2 - Testes de conformidade implementados

#### Validação Final
- [ ] Todos endpoints têm `response_model`
- [ ] Todos erros seguem `ErrorResponseDTO`
- [ ] OpenAPI `/docs` mostra schemas corretos
- [ ] Testes de integração passam
- [ ] CHANGELOG atualizado
- [ ] PR criado e revisado

---

## 🚀 Como Executar Este Plano

### Passo 1: Preparação
```bash
# 1. Criar branch
git checkout -b fix/openapi-inconsistencies

# 2. Instalar dependências de teste
pip install pytest pytest-cov redocly

# 3. Rodar testes atuais (baseline)
pytest tests/ -v
```

### Passo 2: Implementação
```bash
# Executar tasks na ordem:
# - Fase 1 completa (críticas)
# - Testar e validar
# - Fase 2 completa (médias)
# - Testar e validar
# - Fase 3 completa (baixas)
# - Validação final
```

### Passo 3: Validação
```bash
# 1. Rodar testes de conformidade
pytest tests/integration/test_openapi_compliance.py -v

# 2. Validar OpenAPI schema
curl http://localhost:8000/openapi.json > openapi.json
npx @redocly/cli lint openapi.json

# 3. Testar manualmente em /docs
# Abrir http://localhost:8000/docs
# Verificar schemas de cada endpoint

# 4. Gerar coverage report
pytest tests/ --cov=src --cov-report=html
```

### Passo 4: Commit e PR
```bash
# 1. Commit
git add .
git commit -m "fix: resolve OpenAPI documentation inconsistencies

- Add VideoInfoResponseDTO with complete schema
- Standardize ErrorResponseDTO across all endpoints
- Document custom headers (X-Request-ID, X-Process-Time)
- Document rate limits in endpoint descriptions
- Add ReadinessCheckDTO for /health/ready
- Create API contract documentation
- Add OpenAPI compliance tests

Fixes #XX (issue number)
"

# 2. Push e criar PR
git push origin fix/openapi-inconsistencies

# 3. Criar PR no GitHub com descrição completa
```

---

## 📚 Referências

- [Análise Completa (OPENAPI-INCONSISTENCIES-ANALYSIS.md)](./OPENAPI-INCONSISTENCIES-ANALYSIS.md)
- [FastAPI Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [OpenAPI 3.0 Spec](https://swagger.io/specification/)
- [Pydantic Models](https://docs.pydantic.dev/)

---

## 🏁 Critérios de Aceitação Final

### ✅ Definição de Pronto

- [ ] Todos os 7 problemas identificados resolvidos
- [ ] Todos endpoints têm `response_model` definido
- [ ] Todos erros HTTP seguem `ErrorResponseDTO`
- [ ] OpenAPI `/docs` exibe schemas corretos
- [ ] Testes de conformidade implementados e passando
- [ ] Documentação `API-CONTRACT.md` criada
- [ ] CHANGELOG.md atualizado
- [ ] PR revisado e aprovado
- [ ] Merge para `main` concluído

### 🧪 Comandos de Validação Final

```bash
# Rodar TUDO
pytest tests/ -v --cov=src
npx @redocly/cli lint openapi.json
curl http://localhost:8000/docs  # Verificar manualmente
```

---

**Documento criado:** 2024  
**Autor:** GitHub Copilot  
**Status:** ✅ PRONTO PARA EXECUÇÃO  
**Próximo passo:** Começar Task 1.1
