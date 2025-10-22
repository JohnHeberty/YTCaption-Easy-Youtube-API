# Análise de Inconsistências: OpenAPI (/docs) vs. Logs Reais

## 📊 Executive Summary

Este documento apresenta uma análise completa das inconsistências encontradas entre a documentação OpenAPI (`/docs`) e o comportamento real da aplicação conforme registrado nos logs.

**Status da Análise:** ✅ CONCLUÍDO  
**Data:** 2024  
**Versão da API:** v2.2  
**Criticidade:** 🟡 MÉDIA (afeta documentação e contratos de API)

---

## 🔍 Metodologia de Análise

1. **Análise de DTOs** - Revisar schemas definidos em `transcription_dtos.py`
2. **Análise de Rotas** - Comparar response_model com retornos reais
3. **Análise de Logs** - Examinar campos logados vs. campos no response
4. **Análise de Middlewares** - Verificar transformações intermediárias
5. **Análise de Exceções** - Comparar ErrorResponseDTO com erros reais

---

## ❌ INCONSISTÊNCIAS CRÍTICAS

### 1. **Endpoint `/api/v1/video/info` - AUSÊNCIA DE `response_model`**

**Severidade:** 🔴 CRÍTICA  
**Arquivo:** `src/presentation/api/routes/video_info.py`  
**Linha:** 28-41

#### Problema
```python
@router.post(
    "/info",
    # ❌ FALTA response_model - OpenAPI não sabe o schema da resposta
    status_code=200,
    summary="Get video information without downloading",
    ...
)
```

#### Resposta Real (código)
```python
response = {
    "video_id": info.get('video_id'),
    "title": info.get('title'),
    "duration_seconds": duration,
    "duration_formatted": duration_formatted,
    "uploader": info.get('uploader'),
    "upload_date": info.get('upload_date'),
    "view_count": info.get('view_count'),
    "description_preview": (info.get('description', '')[:200] + "..."),
    "language_detection": info.get('language_detection', {}),
    "subtitles": {
        "available": info.get('available_subtitles', []),
        "manual_languages": info.get('subtitle_languages', []),
        "auto_languages": info.get('auto_caption_languages', []),
        "total": len(info.get('available_subtitles', []))
    },
    "whisper_recommendation": info.get('whisper_recommendation', {}),
    "warnings": []
}
```

#### OpenAPI `/docs`
```json
{
  "schema": {} // ❌ VAZIO! OpenAPI não documenta a estrutura
}
```

#### Impacto
- ❌ Clientes não sabem quais campos esperar
- ❌ Validação automática de response não ocorre
- ❌ Geradores de código (OpenAPI Generator) falham
- ❌ Testes automatizados não podem validar schema

#### Solução Necessária
Criar `VideoInfoResponseDTO` em `transcription_dtos.py` e adicionar `response_model`.

---

### 2. **Erro HTTP: `detail` como Dict vs. String**

**Severidade:** 🟡 MÉDIA  
**Arquivos:** Todos os endpoints  
**Padrão:** RFC 7807 vs. Custom

#### Problema
FastAPI permite `detail` como `str` ou `dict`, mas a documentação OpenAPI assume apenas `str`.

#### Código Real (transcription.py, linha ~135)
```python
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={  # ❌ DICT
        "error": "AudioTooLongError",
        "message": str(e),
        "request_id": request_id,
        "details": {
            "duration": e.duration,
            "max_duration": e.max_duration
        }
    }
)
```

#### OpenAPI `/docs` (schema padrão HTTPException)
```json
{
  "detail": "string"  // ❌ Documenta como STRING, mas retorna DICT
}
```

#### Resposta Real
```json
{
  "detail": {
    "error": "AudioTooLongError",
    "message": "Audio duration (7250s) exceeds maximum allowed (7200s)",
    "request_id": "abc123",
    "details": {
      "duration": 7250,
      "max_duration": 7200
    }
  }
}
```

#### Impacto
- ❌ Cliente espera `string`, recebe `object`
- ❌ Parsing falha em linguagens fortemente tipadas
- ❌ Contratos de API quebrados

---

### 3. **ErrorResponseDTO Não Utilizado nas Exceptions**

**Severidade:** 🟡 MÉDIA  
**Arquivo:** `src/application/dtos/transcription_dtos.py` (linhas 87-103)

#### Problema
Existe um `ErrorResponseDTO` definido, mas **NENHUMA exception o utiliza** como response_model.

#### DTO Definido (não usado)
```python
class ErrorResponseDTO(BaseModel):
    """DTO para respostas de erro."""
    error: str = Field(..., description="Tipo de erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[dict] = Field(None, description="Detalhes adicionais")
```

#### Exception Real (não usa DTO)
```python
raise HTTPException(
    status_code=400,
    detail={  # ❌ NÃO É ErrorResponseDTO
        "error": "AudioTooLongError",
        "message": str(e),
        "request_id": request_id,  # ❌ CAMPO EXTRA não no DTO
        "details": {...}
    }
)
```

#### Diferenças
| Campo | ErrorResponseDTO | Exception Real | Status |
|-------|-----------------|----------------|--------|
| `error` | ✅ Sim | ✅ Sim | ✅ Match |
| `message` | ✅ Sim | ✅ Sim | ✅ Match |
| `details` | ✅ Sim | ✅ Sim | ✅ Match |
| `request_id` | ❌ NÃO | ✅ SIM | ❌ **INCONSISTÊNCIA** |

#### Impacto
- ❌ OpenAPI não documenta `request_id` em erros
- ❌ DTO inutilizado (código morto)
- ❌ Clientes não sabem que `request_id` existe

---

## ⚠️ INCONSISTÊNCIAS MÉDIAS

### 4. **Logs vs. Response: Nomes de Campos Diferentes**

**Severidade:** 🟡 MÉDIA  
**Arquivos:** Múltiplos

#### Exemplo 1: Transcription Endpoint

**Log (linha 111-119):**
```python
logger.info(
    "✅ Transcription successful",
    extra={
        "request_id": request_id,
        "transcription_id": response.transcription_id,  # ✅ Correto
        "segments_count": response.total_segments,      # ⚠️ DIFERENTE
        "processing_time": response.processing_time     # ✅ Correto
    }
)
```

**Response DTO:**
```python
class TranscribeResponseDTO:
    transcription_id: str
    total_segments: int     # ❌ Log usa "segments_count"
    processing_time: float
```

**Impacto:**
- ⚠️ Logs e responses usam nomenclaturas diferentes
- ⚠️ Correlação manual necessária
- ⚠️ Ferramentas de APM podem não correlacionar

---

### 5. **Health Check: Response Inconsistente**

**Severidade:** 🟡 MÉDIA  
**Arquivo:** `src/presentation/api/routes/system.py`

#### GET `/health` (linha ~47)
```python
@router.get(
    "/health",
    response_model=HealthCheckDTO,  # ✅ TEM response_model
    ...
)
async def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        # ...
    }
```
✅ **Correto** - usa DTO

#### GET `/health/ready` (linha ~82)
```python
@router.get(
    "/health/ready",
    # ❌ NÃO TEM response_model definido
    status_code=200,
    ...
)
async def readiness_check():
    return {
        "status": "ready",
        "checks": {...},
        # ...
    }
```
❌ **Inconsistente** - não usa DTO, schema não documentado

---

### 6. **Middleware: Headers Customizados Não Documentados**

**Severidade:** 🟢 BAIXA  
**Arquivo:** `src/presentation/api/main.py` (linha ~420)

#### Headers Adicionados
```python
response.headers["X-Request-ID"] = request_id     # ❌ Não documentado
response.headers["X-Process-Time"] = f"{...}"     # ❌ Não documentado
```

#### OpenAPI `/docs`
```yaml
responses:
  200:
    headers: {}  # ❌ VAZIO - não menciona X-Request-ID nem X-Process-Time
```

#### Impacto
- ⚠️ Clientes não sabem que podem usar `X-Request-ID` para tracking
- ⚠️ APM tools podem não capturar `X-Process-Time`

---

### 7. **Rate Limiting: Erro 429 Não Documentado**

**Severidade:** 🟡 MÉDIA  
**Arquivos:** Todos os endpoints com `@limiter.limit()`

#### Decorador Aplicado
```python
@limiter.limit("5/minute")  # ❌ OpenAPI não sabe deste limite
@router.post("/transcribe", ...)
```

#### OpenAPI `/docs`
```yaml
responses:
  429:
    description: "Too Many Requests"  # ✅ Mencionado
    content:
      application/json:
        schema: {}  # ❌ VAZIO - não documenta estrutura do erro
```

#### Resposta Real (slowapi)
```json
{
  "error": "Rate limit exceeded",
  "message": "5 per 1 minute"
}
```

#### Problema
- ❌ Schema do erro 429 não documentado
- ❌ Limite (`5/minute`) não visível no `/docs`

---

## ✅ ASPECTOS CORRETOS (Para Referência)

### 1. **POST `/api/v1/transcribe` - Response Modelo Correto**
```python
@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,  # ✅ CORRETO
    status_code=200,
    ...
)
```
✅ Schema documentado corretamente no OpenAPI

### 2. **GET `/health` - Response Modelo Correto**
```python
@router.get(
    "/health",
    response_model=HealthCheckDTO,  # ✅ CORRETO
    ...
)
```
✅ Schema documentado corretamente

### 3. **Logs Estruturados com `extra={}`**
```python
logger.info(
    "Message",
    extra={  # ✅ CORRETO - formato estruturado
        "request_id": request_id,
        "field": value
    }
)
```
✅ Padrão consistente em toda aplicação

---

## 📋 TABELA RESUMO DE INCONSISTÊNCIAS

| # | Inconsistência | Severidade | Arquivo(s) | Impacto | Esforço Fix |
|---|---------------|------------|------------|---------|-------------|
| 1 | `/api/v1/video/info` sem `response_model` | 🔴 CRÍTICA | video_info.py | Alto - Clientes não sabem schema | 1h |
| 2 | HTTPException `detail` como dict vs string | 🟡 MÉDIA | Todos endpoints | Médio - Parsing falha | 2h |
| 3 | `ErrorResponseDTO` não usado | 🟡 MÉDIA | transcription_dtos.py | Médio - `request_id` não documentado | 2h |
| 4 | Logs vs Response: nomes diferentes | 🟡 MÉDIA | transcription.py | Baixo - Correlação manual | 0.5h |
| 5 | `/health/ready` sem `response_model` | 🟡 MÉDIA | system.py | Médio - Schema não validado | 0.5h |
| 6 | Headers customizados não documentados | 🟢 BAIXA | main.py | Baixo - Discovery manual | 1h |
| 7 | Rate limit 429 sem schema | 🟡 MÉDIA | Todos + main.py | Médio - Erro não tipado | 1h |

**Total Esforço Estimado:** ~8 horas

---

## 🛠️ PLANO DE CORREÇÃO DETALHADO

### **FASE 1: Correções Críticas (Prioridade ALTA)** - 3h

#### 1.1. Criar DTO para `/api/v1/video/info` (1h)

**Arquivo:** `src/application/dtos/transcription_dtos.py`

```python
class SubtitlesInfoDTO(BaseModel):
    """DTO para informações de legendas disponíveis."""
    available: List[str] = Field(..., description="Todas as legendas disponíveis")
    manual_languages: List[str] = Field(..., description="Idiomas com legendas manuais")
    auto_languages: List[str] = Field(..., description="Idiomas com legendas automáticas")
    total: int = Field(..., description="Total de legendas disponíveis")


class LanguageDetectionDTO(BaseModel):
    """DTO para detecção de idioma."""
    detected_language: str = Field(..., description="Idioma detectado")
    confidence: float = Field(..., description="Confiança da detecção (0-1)")


class WhisperRecommendationDTO(BaseModel):
    """DTO para recomendações do Whisper."""
    should_use_youtube_transcript: bool = Field(..., description="Se deve usar transcrição do YouTube")
    reason: str = Field(..., description="Razão da recomendação")
    estimated_time_whisper: Optional[float] = Field(None, description="Tempo estimado com Whisper (segundos)")
    estimated_time_youtube: Optional[float] = Field(None, description="Tempo estimado com YouTube (segundos)")


class VideoInfoResponseDTO(BaseModel):
    """DTO para resposta de informações do vídeo."""
    video_id: str = Field(..., description="ID do vídeo no YouTube")
    title: str = Field(..., description="Título do vídeo")
    duration_seconds: int = Field(..., description="Duração em segundos")
    duration_formatted: str = Field(..., description="Duração formatada (HH:MM:SS)")
    uploader: str = Field(..., description="Nome do canal/uploader")
    upload_date: Optional[str] = Field(None, description="Data de upload (YYYYMMDD)")
    view_count: Optional[int] = Field(None, description="Número de visualizações")
    description_preview: str = Field(..., description="Prévia da descrição (200 chars)")
    language_detection: LanguageDetectionDTO = Field(..., description="Detecção de idioma")
    subtitles: SubtitlesInfoDTO = Field(..., description="Informações de legendas")
    whisper_recommendation: WhisperRecommendationDTO = Field(..., description="Recomendações Whisper")
    warnings: List[str] = Field(default_factory=list, description="Avisos sobre o vídeo")
    
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
                "description_preview": "The official video for 'Never Gonna Give You Up'...",
                "language_detection": {
                    "detected_language": "en",
                    "confidence": 0.95
                },
                "subtitles": {
                    "available": ["en", "es", "pt"],
                    "manual_languages": ["en"],
                    "auto_languages": ["es", "pt"],
                    "total": 3
                },
                "whisper_recommendation": {
                    "should_use_youtube_transcript": True,
                    "reason": "Manual subtitles available in detected language",
                    "estimated_time_whisper": 45.0,
                    "estimated_time_youtube": 2.0
                },
                "warnings": []
            }
        }
```

**Arquivo:** `src/presentation/api/routes/video_info.py`

```python
@router.post(
    "/info",
    response_model=VideoInfoResponseDTO,  # ✅ ADICIONAR
    status_code=200,
    summary="Get video information without downloading",
    ...
)
```

#### 1.2. Padronizar Erros HTTP com ErrorResponseDTO (2h)

**Arquivo:** `src/application/dtos/transcription_dtos.py`

```python
class ErrorResponseDTO(BaseModel):
    """DTO para respostas de erro padronizadas."""
    error: str = Field(..., description="Tipo de erro")
    message: str = Field(..., description="Mensagem de erro")
    request_id: str = Field(..., description="ID da requisição para tracking")  # ✅ ADICIONAR
    details: Optional[dict] = Field(None, description="Detalhes adicionais do erro")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "AudioTooLongError",
                "message": "Audio duration exceeds maximum allowed",
                "request_id": "abc-123-def",
                "details": {
                    "duration": 7250,
                    "max_duration": 7200
                }
            }
        }
```

**Arquivo:** `src/presentation/api/routes/transcription.py` (exemplo)

```python
# ANTES
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={  # ❌ Dict não tipado
        "error": "AudioTooLongError",
        "message": str(e),
        "request_id": request_id,
        ...
    }
)

# DEPOIS
from fastapi.encoders import jsonable_encoder

error_response = ErrorResponseDTO(  # ✅ Usar DTO
    error="AudioTooLongError",
    message=str(e),
    request_id=request_id,
    details={
        "duration": e.duration,
        "max_duration": e.max_duration
    }
)
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail=jsonable_encoder(error_response)
)
```

**Atualizar decoradores de rotas:**
```python
@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    responses={
        400: {"model": ErrorResponseDTO, "description": "Invalid request"},  # ✅ ADICIONAR
        404: {"model": ErrorResponseDTO, "description": "Video not found"},
        429: {"model": ErrorResponseDTO, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponseDTO, "description": "Internal server error"},
        503: {"model": ErrorResponseDTO, "description": "Service unavailable"}
    },
    ...
)
```

---

### **FASE 2: Correções Médias (Prioridade MÉDIA)** - 3h

#### 2.1. Criar DTO para `/health/ready` (0.5h)

```python
class ReadinessCheckDTO(BaseModel):
    """DTO para verificação de prontidão."""
    status: str = Field(..., description="Status de prontidão")
    checks: Dict[str, bool] = Field(..., description="Verificações realizadas")
    message: Optional[str] = Field(None, description="Mensagem adicional")
```

```python
@router.get(
    "/health/ready",
    response_model=ReadinessCheckDTO,  # ✅ ADICIONAR
    status_code=200,
    ...
)
```

#### 2.2. Documentar Headers Customizados (1h)

**Arquivo:** `src/presentation/api/routes/transcription.py`

```python
from fastapi import Header

@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    responses={
        200: {
            "description": "Transcription successful",
            "headers": {  # ✅ ADICIONAR
                "X-Request-ID": {
                    "description": "Request ID for tracking",
                    "schema": {"type": "string"}
                },
                "X-Process-Time": {
                    "description": "Processing time in seconds",
                    "schema": {"type": "string"}
                }
            }
        },
        ...
    }
)
```

#### 2.3. Documentar Rate Limits (1h)

**Opção 1: Descrição no endpoint**
```python
@router.post(
    "/transcribe",
    response_model=TranscribeResponseDTO,
    summary="Transcribe YouTube video",
    description="""
    Transcribe a YouTube video using Whisper or YouTube's native transcripts.
    
    **Rate Limit:** 5 requests per minute per IP address.
    
    Returns 429 if rate limit is exceeded.
    """,  # ✅ ADICIONAR
    ...
)
```

**Opção 2: Custom Response para 429**
```python
class RateLimitErrorDTO(BaseModel):
    """DTO para erro de rate limit."""
    error: str = Field(default="RateLimitExceeded", description="Tipo de erro")
    message: str = Field(..., description="Mensagem do erro")
    request_id: str = Field(..., description="ID da requisição")
    details: dict = Field(..., description="Detalhes do rate limit")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "RateLimitExceeded",
                "message": "Rate limit exceeded: 5 per 1 minute",
                "request_id": "abc-123",
                "details": {
                    "limit": "5/minute",
                    "retry_after": 60
                }
            }
        }
```

#### 2.4. Padronizar Logs vs. Response (0.5h)

**Opção 1: Alinhar logs com DTOs**
```python
# ANTES
logger.info(
    "✅ Transcription successful",
    extra={
        "segments_count": response.total_segments,  # ❌ Diferente do DTO
    }
)

# DEPOIS
logger.info(
    "✅ Transcription successful",
    extra={
        "total_segments": response.total_segments,  # ✅ Igual ao DTO
    }
)
```

**Opção 2: Criar alias no DTO (menos recomendado)**
```python
class TranscribeResponseDTO(BaseModel):
    total_segments: int = Field(..., alias="segments_count")  # ⚠️ Confuso
```

---

### **FASE 3: Melhorias Baixas (Prioridade BAIXA)** - 2h

#### 3.1. Criar Documentação de Contrato de API (1h)

**Arquivo:** `docs/API-CONTRACT.md`

```markdown
# API Contract v2.2

## Response Headers
- `X-Request-ID`: UUID for request tracking
- `X-Process-Time`: Processing time in seconds (e.g., "1.234s")

## Error Format
All errors follow this structure:
```json
{
  "error": "ErrorType",
  "message": "Human-readable message",
  "request_id": "uuid",
  "details": {}  // Optional
}
```

## Rate Limits
- `/api/v1/transcribe`: 5 req/minute
- `/api/v1/video/info`: 10 req/minute
- `/health`: 30 req/minute
```

#### 3.2. Validação Automática com Tests (1h)

**Arquivo:** `tests/integration/test_openapi_compliance.py`

```python
import pytest
from fastapi.testclient import TestClient

def test_video_info_matches_schema(client: TestClient):
    """Testa se /video/info retorna schema correto."""
    response = client.post("/api/v1/video/info", json={
        "youtube_url": "https://youtube.com/watch?v=test"
    })
    
    # Validar schema
    assert "video_id" in response.json()
    assert "duration_seconds" in response.json()
    assert "subtitles" in response.json()
    
    # Validar tipos
    assert isinstance(response.json()["duration_seconds"], int)
    assert isinstance(response.json()["warnings"], list)


def test_error_response_matches_dto(client: TestClient):
    """Testa se erros seguem ErrorResponseDTO."""
    response = client.post("/api/v1/transcribe", json={
        "youtube_url": "invalid"
    })
    
    error = response.json()["detail"]
    
    # Validar campos obrigatórios
    assert "error" in error
    assert "message" in error
    assert "request_id" in error  # ✅ Agora está documentado
```

---

## 📊 CRONOGRAMA DE IMPLEMENTAÇÃO

### Sprint 1 (Semana 1) - Críticas
- **Dia 1-2:** Criar `VideoInfoResponseDTO` e DTOs relacionados
- **Dia 3-4:** Implementar uso de `ErrorResponseDTO` em todas exceptions
- **Dia 5:** Testes e validação

### Sprint 2 (Semana 2) - Médias
- **Dia 1:** Criar `ReadinessCheckDTO` e documentar headers
- **Dia 2-3:** Implementar documentação de rate limits
- **Dia 4:** Padronizar nomenclatura logs vs. response
- **Dia 5:** Testes e validação

### Sprint 3 (Semana 3) - Baixas + Docs
- **Dia 1-2:** Criar `API-CONTRACT.md` e documentação adicional
- **Dia 3-4:** Implementar testes de conformidade OpenAPI
- **Dia 5:** Revisão final e atualização do CHANGELOG

---

## 🎯 CRITÉRIOS DE ACEITAÇÃO

### ✅ Definição de Pronto (DoD)

- [ ] Todos endpoints têm `response_model` definido
- [ ] Todos erros seguem `ErrorResponseDTO`
- [ ] OpenAPI `/docs` mostra schemas corretos para:
  - [ ] `/api/v1/video/info` response
  - [ ] `/health/ready` response
  - [ ] Todos os erros (400, 404, 429, 500, 503)
- [ ] Headers customizados documentados em `responses`
- [ ] Rate limits mencionados nas descrições dos endpoints
- [ ] Testes de integração validam schemas
- [ ] `API-CONTRACT.md` criado e atualizado
- [ ] CHANGELOG.md atualizado com correções

### 🧪 Validação
```bash
# 1. Gerar OpenAPI schema
curl http://localhost:8000/openapi.json > openapi.json

# 2. Validar schema
npx @redocly/cli lint openapi.json

# 3. Testar endpoints
pytest tests/integration/test_openapi_compliance.py -v

# 4. Verificar documentação
# Abrir http://localhost:8000/docs e validar manualmente
```

---

## 📚 REFERÊNCIAS

- [FastAPI Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [OpenAPI Specification 3.0](https://swagger.io/specification/)
- [RFC 7807 - Problem Details](https://tools.ietf.org/html/rfc7807)
- [FastAPI Custom Response](https://fastapi.tiangolo.com/advanced/response-directly/)
- [Pydantic Models](https://docs.pydantic.dev/latest/)

---

## 🏁 CONCLUSÃO

Esta análise identificou **7 inconsistências** (1 crítica, 5 médias, 1 baixa) entre a documentação OpenAPI e o comportamento real da API. O plano de correção totaliza **~8 horas** de esforço e deve ser executado em 3 sprints priorizados.

**Próximos Passos:**
1. Revisar e aprovar este plano
2. Criar issues no GitHub para cada fase
3. Implementar correções seguindo prioridade
4. Validar com testes automatizados
5. Atualizar documentação final

---

**Documento criado:** 2024  
**Autor:** GitHub Copilot  
**Status:** ✅ PRONTO PARA REVISÃO
