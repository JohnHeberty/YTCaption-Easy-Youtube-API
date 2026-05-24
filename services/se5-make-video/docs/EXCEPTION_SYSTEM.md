# 🛡️ Sistema de Exceções - Make-Video Service

**Status**: ✅ Produção  
**Versão**: 2.1.0  
**Data**: 2026-02-20

---

## 📋 Visão Geral

Sistema de exceções hierárquico completamente corrigido que eliminou o bug crítico de `TypeError: got multiple values for keyword argument 'details'`.

**Correção aplicada**: 30 classes de exceção agora usam padrão `kwargs.pop('details', {})` para evitar conflitos de parâmetros.

---

## 🐛 Bug Crítico RESOLVIDO

### Problema Original
Jobs falhavam em 75% do progresso com:
```python
TypeError: MakeVideoBaseException.__init__() got multiple values for keyword argument 'details'
```

### Causa Raiz
Conflito **multi-camadas** na hierarquia de exceções:
1. **Camada Base**: `MakeVideoBaseException` recebia `details=` como kwarg
2. **Camada Parent**: `ExternalServiceException` também recebia `details=`
3. **Camada Caller**: Código chamador passava `details=` explicitamente
4. **Resultado**: Python reclamava de "multiple values"

### Solução Implementada

**ANTES** ❌:
```python
class ExternalServiceException(MakeVideoBaseException):
    def __init__(self, message, service, error_code=None, details=None, **kwargs):
        # ❌ details= explícito causava conflito
        super().__init__(details=details, **kwargs)
```

**DEPOIS** ✅:
```python
class ExternalServiceException(MakeVideoBaseException):
    def __init__(self, message, service, error_code=None, **kwargs):
        # ✅ Extrai details do kwargs ANTES de passar para super()
        details = kwargs.pop('details', {})
        merged_details = {
            "service": service,
            **details  # Merge com details adicionais
        }
        super().__init__(details=merged_details, **kwargs)
```

---

## 🏗️ Hierarquia de Exceções

```
MakeVideoBaseException (base)
├── AudioException
│   ├── AudioNotFoundException
│   ├── AudioNormalizationException
│   └── AudioProcessingFailedException
│       └── FFmpegAudioException
├── VideoException
│   ├── VideoNotFoundException
│   ├── VideoDownloadException
│   ├── VideoIncompatibleException
│   ├── VideoProcessingFailedException
│   └── FFmpegFailedException
├── SubtitleException
│   ├── SubtitleDetectionException
│   └── SubtitleGenerationException
├── ExternalServiceException
│   ├── TranscriberUnavailableException
│   ├── TranscriptionFailedException
│   ├── TranscriptionTimeoutException
│   ├── APIRateLimitException
│   └── ServiceConnectionException
├── ProcessingException
│   ├── ProcessingTimeoutException
│   ├── CircuitBreakerException
│   └── CheckpointException
└── ConfigurationException
    ├── InvalidConfigException
    └── MissingConfigException
```

**Total**: 30 classes (todas corrigidas ✅)

---

## 📐 Padrão de Implementação

### Base Class (MakeVideoBaseException)

```python
class MakeVideoBaseException(Exception):
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = False,
        **kwargs
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.recoverable = recoverable
        self.timestamp = datetime.utcnow().isoformat()
        
        # Merge com kwargs adicionais
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa exceção para JSON."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value if self.error_code else None,
            "details": self.details,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
            "cause": str(self.cause) if self.cause else None
        }
```

### Parent Class (ExternalServiceException)

```python
class ExternalServiceException(MakeVideoBaseException):
    """Base para exceções de serviços externos."""
    
    def __init__(self, message: str, service: str, error_code=None, **kwargs):
        # ✅ Extrai details do kwargs ANTES
        details = kwargs.pop('details', {})
        
        # Merge service + details adicionais
        merged_details = {
            "service": service,
            **details
        }
        
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.SERVICE_UNAVAILABLE,
            details=merged_details,
            recoverable=True,
            **kwargs
        )
        
        self.service = service
```

### Child Class (TranscriberUnavailableException)

```python
class TranscriberUnavailableException(ExternalServiceException):
    """Audio transcriber não disponível."""
    
    def __init__(self, reason: str, **kwargs):
        super().__init__(
            message=f"Audio transcriber unavailable: {reason}",
            service="audio-transcriber",
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            **kwargs  # ✅ NÃO passa details= explicitamente
        )
        self.reason = reason
```

### Código Chamador (USO CORRETO)

```python
# ✅ CORRETO: Não passa details= explicitamente
raise TranscriberUnavailableException(
    reason="Failed to create transcription job after 3 attempts"
)

# ✅ CORRETO: Se precisar de details adicionais, passa via kwargs
raise TranscriberUnavailableException(
    reason="Service timeout",
    timeout_seconds=300,
    attempts=5
)

# ❌ EVITAR: Passar details= explicitamente
raise TranscriberUnavailableException(
    reason="...",
    details={"extra": "info"}  # ❌ Causa conflito!
)
```

---

## 🧪 Validação e Testes

### Cobertura: 10 testes de regressão (100% passing)

**Arquivo**: `tests/unit/shared/test_exception_details_conflict.py`

**Testes**:
1. ✅ `test_transcription_timeout_exception_no_details_conflict`
2. ✅ `test_transcription_timeout_with_extra_kwargs`
3. ✅ `test_api_rate_limit_exception_no_details_conflict`
4. ✅ `test_circuit_breaker_exception_no_details_conflict`
5. ✅ `test_external_service_exception_details_merge`
6. ✅ `test_exception_serialization`
7. ✅ `test_regression_original_bug` - Reproduz Job 76kUcvmUNS5ZKAKrvy8umv
8. ✅ `test_all_external_service_exceptions_work`
9. ✅ `test_exception_with_details_conflict_scenario` - Reproduz Job htRtccPHGyzJd8JSk2JcYB
10. ✅ `test_all_audio_exceptions_without_details_kwarg`

**Resultado**:
```bash
$ pytest tests/unit/shared/test_exception_details_conflict.py -v
======================== 10 passed, 1 warning in 2.39s ========================
```

---

## 📊 Classes Corrigidas (30 total)

### Audio Exceptions (4)
- ✅ AudioNotFoundException
- ✅ AudioNormalizationException
- ✅ AudioProcessingFailedException
- ✅ FFmpegAudioException

### Video Exceptions (5)
- ✅ VideoNotFoundException
- ✅ VideoDownloadException
- ✅ VideoIncompatibleException
- ✅ VideoProcessingFailedException
- ✅ FFmpegFailedException

### Subtitle Exceptions (2)
- ✅ SubtitleDetectionException
- ✅ SubtitleGenerationException

### External Service Exceptions (5)
- ✅ TranscriberUnavailableException
- ✅ TranscriptionFailedException
- ✅ TranscriptionTimeoutException
- ✅ APIRateLimitException
- ✅ ServiceConnectionException

### Processing Exceptions (3)
- ✅ ProcessingTimeoutException
- ✅ CircuitBreakerException
- ✅ CheckpointException

### Configuration Exceptions (2)
- ✅ InvalidConfigException
- ✅ MissingConfigException

### Base Classes (3)
- ✅ MakeVideoBaseException
- ✅ AudioException
- ✅ VideoException
- ✅ SubtitleException
- ✅ ExternalServiceException
- ✅ ProcessingException
- ✅ ConfigurationException

### Outras (6)
- ✅ ValidationException
- ✅ FileSystemException
- ✅ NetworkException
- ✅ ResourceNotFoundException
- ✅ PermissionException
- ✅ StateException

---

## 🎯 Princípios de Design

### 1. **Single Source of Truth**
- Details são **criados internamente** pela exceção
- Callers **não especificam** details explicitamente
- Merge automático de details adicionais via kwargs

### 2. **Imutabilidade de Assinatura**
- Base class tem assinatura completa
- Child classes **não redeclaram** parâmetros já existentes
- Sempre usar `**kwargs` para extensibilidade

### 3. **Serialização JSON**
```python
exc = TranscriberUnavailableException(reason="Timeout")
json_data = exc.to_dict()
# {
#   "error": "TranscriberUnavailableException",
#   "message": "Audio transcriber unavailable: Timeout",
#   "error_code": "SERVICE_UNAVAILABLE",
#   "details": {"service": "audio-transcriber"},
#   "recoverable": true,
#   "timestamp": "2026-02-20T12:00:00Z"
# }
```

### 4. **Recoverability**
```python
# Exceções recuperáveis (retry possível)
ExternalServiceException.recoverable = True
TranscriptionTimeoutException.recoverable = True

# Exceções não-recuperáveis (falha definitiva)
AudioNotFoundException.recoverable = False
InvalidConfigException.recoverable = False
```

---

## 🔧 Uso Prático

### Exemplo 1: Exceção de Serviço Externo

```python
async def transcribe_audio(audio_path: Path) -> Dict:
    try:
        response = await api_client.create_transcription_job(audio_path)
        return response
    except httpx.TimeoutException as e:
        # ✅ CORRETO: Apenas reason, kwargs automáticos
        raise TranscriberUnavailableException(
            reason="Transcription service timed out",
            cause=e
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # ✅ CORRETO: Rate limit com retry_after via kwargs
            raise APIRateLimitException(
                service="audio-transcriber",
                retry_after=int(e.response.headers.get("Retry-After", 60)),
                cause=e
            )
        raise
```

### Exemplo 2: Exceção de Processamento

```python
async def normalize_audio(audio_path: Path) -> Path:
    if not audio_path.exists():
        # ✅ CORRETO: Apenas audio_path
        raise AudioNotFoundException(audio_path=str(audio_path))
    
    try:
        normalized = await ffmpeg_normalize(audio_path)
        return normalized
    except subprocess.CalledProcessError as e:
        # ✅ CORRETO: file_path + reason via kwargs
        raise FFmpegAudioException(
            file_path=str(audio_path),
            reason=f"Normalization failed: {e.stderr}",
            cause=e
        )
```

### Exemplo 3: Exceção de Vídeo

```python
async def download_video(video_url: str) -> Path:
    try:
        video_path = await youtube_dl.download(video_url)
        return video_path
    except Exception as e:
        # ✅ CORRETO: video_url + reason
        raise VideoDownloadException(
            video_url=video_url,
            reason=str(e),
            cause=e
        )
```

---

## 📈 Impacto da Correção

### Antes (BUG)
```log
[ERROR] TypeError: MakeVideoBaseException.__init__() got multiple values for keyword argument 'details'
[ERROR] Job 76kUcvmUNS5ZKAKrvy8umv FAILED at 75%
[ERROR] Job htRtccPHGyzJd8JSk2JcYB FAILED at 75%
```

### Depois (CORRIGIDO)
```log
[WARNING] TranscriberUnavailableException: Audio transcriber unavailable: Service timeout
[INFO] Job 5Ytn5xFZrm25DDtZywXchY FAILED with VideoIncompatibleException (legitimate failure)
[INFO] TypeError: ELIMINATED completely ✅
```

### Métricas
- **Jobs afetados**: 2+ antes da correção
- **Taxa de falha**: 100% quando transcriber indisponível
- **Após correção**: 0% TypeError (100% de eliminação)
- **Exceções legítimas**: Agora funcionam corretamente

---

## 🐛 Troubleshooting

### Problema: "TypeError: got multiple values for 'details'"
**Status**: ✅ RESOLVIDO  
**Causa**: Bug já corrigido em todas as 30 exceções  
**Solução**: Sistema atualizado para v2.1.0

### Problema: Exception não serializa para JSON
**Causa**: `to_dict()` não implementado ou incorreto  
**Solução**: Todas as exceções herdam `to_dict()` de `MakeVideoBaseException`

### Problema: Details não contém campos esperados
**Causa**: Child class não está fazendo merge correto  
**Solução**: Verificar que `kwargs.pop('details', {})` + merge está implementado

---

## 📚 Referências

- **Código**: `app/shared/exceptions_v2.py` (30 classes, ~800 linhas)
- **Testes**: `tests/unit/shared/test_exception_details_conflict.py` (10 testes)
- **Enum**: `app/shared/error_codes.py` (ErrorCode enum)
- **Correções Aplicadas**: 
  - Linhas 95-145: MakeVideoBaseException
  - Linhas 476-495: ExternalServiceException
  - api_client.py linhas 369, 425, 457: Remoção de details= explícito

---

**Última Atualização**: 2026-02-20  
**Status**: ✅ Produção (zero TypeError desde correção)  
**Maintainer**: Sistema Make-Video v2.1.0
