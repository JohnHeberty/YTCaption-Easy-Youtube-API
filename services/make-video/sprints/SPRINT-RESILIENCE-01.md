# SPRINT-01: Resiliência de Processos (P1)

**Duração:** 2 semanas (10 dias úteis)  
**Prioridade:** P1 (Alta Instabilidade)  
**Story Points:** 29  
**Impacto Esperado:** -60% instabilidade, -15% falhas tardias  
**Data de Criação:** 18/02/2026  
**Status:** 🟡 PENDENTE (aguarda Quick Wins)

---

## 📋 Objetivos da Sprint

Implementar correções de **instabilidade moderada** que causam falhas não-críticas mas impactam UX e recuperação de jobs. Foco em **validação antecipada** e **compatibilidade**.

### Métricas de Sucesso
- ✅ Redução de 60% nas falhas de concatenação
- ✅ Redução de 80% no tempo de diagnóstico de erros
- ✅ Zero falhas por incompatibilidade de codec/FPS
- ✅ Drift áudio-legenda <500ms em 99% dos casos
- ✅ Recuperação de 80% dos jobs após crash

---

## 🎯 Riscos Corrigidos

Esta sprint corrige os seguintes riscos do Risk Register:

- **R-006:** Exceções Genéricas Perdem Contexto
- **R-007:** Sincronização Áudio-Legenda Sem Validação de Drift
- **R-008:** Download de Shorts Sem Verificação Completa de Integridade
- **R-009:** Concatenação Sem Validação de Codec/FPS Compatível
- **R-013:** Checkpoint Granular Não Usado Consistentemente

---

## 📝 Tasks Detalhadas

### Task 1: Criar Hierarquia de Exceções Específicas (R-006)

**Story Points:** 8  
**Prioridade:** P1  
**Impacto:** +100% debugabilidade

#### Descrição
Criar hierarquia de exceções específicas por categoria de erro, eliminando `except Exception` genérico.

#### Sub-tasks

##### 1.1: Definir Hierarquia de Exceções

**Arquivo:** `app/shared/exceptions.py`

```python
"""
Hierarchical exception system for Make-Video Service
"""
from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    """Error codes for structured error reporting"""
    
    # FFmpeg/Subprocess errors (1xxx)
    SUBPROCESS_TIMEOUT = "1001"
    SUBPROCESS_FAILED = "1002"
    SUBPROCESS_ORPHAN = "1003"
    
    # Video processing errors (2xxx)
    VIDEO_CORRUPTED = "2001"
    VIDEO_INVALID_CODEC = "2002"
    VIDEO_INVALID_FPS = "2003"
    VIDEO_INVALID_RESOLUTION = "2004"
    VIDEO_CONVERSION_FAILED = "2005"
    VIDEO_CONVERSION_TIMEOUT = "2006"
    VIDEO_CONCAT_INCOMPATIBLE = "2007"
    VIDEO_CONCAT_FAILED = "2008"
    VIDEO_TRIM_FAILED = "2009"
    VIDEO_CROP_FAILED = "2010"
    VIDEO_SUBTITLE_OVERLAY_FAILED = "2011"
    
    # Audio processing errors (3xxx)
    AUDIO_EXTRACTION_FAILED = "3001"
    AUDIO_INVALID_FORMAT = "3002"
    AUDIO_INVALID_DURATION = "3003"
    
    # Transcription errors (4xxx)
    TRANSCRIPTION_FAILED = "4001"
    TRANSCRIPTION_TIMEOUT = "4002"
    TRANSCRIPTION_QUOTA_EXCEEDED = "4003"
    TRANSCRIPTION_INVALID_RESPONSE = "4004"
    
    # External API errors (5xxx)
    API_TIMEOUT = "5001"
    API_RATE_LIMIT = "5002"
    API_INVALID_RESPONSE = "5003"
    API_UNAVAILABLE = "5004"
    YOUTUBE_SEARCH_FAILED = "5101"
    VIDEO_DOWNLOADER_FAILED = "5102"
    
    # Validation errors (6xxx)
    VALIDATION_INTEGRITY_FAILED = "6001"
    VALIDATION_SUBTITLE_DETECTED = "6002"
    VALIDATION_CODEC_INCOMPATIBLE = "6003"
    VALIDATION_FPS_INCOMPATIBLE = "6004"
    VALIDATION_DRIFT_EXCEEDED = "6005"
    
    # Resource errors (7xxx)
    RESOURCE_DISK_FULL = "7001"
    RESOURCE_MEMORY_EXCEEDED = "7002"
    RESOURCE_CONCURRENT_LIMIT = "7003"
    
    # Job/State errors (8xxx)
    JOB_NOT_FOUND = "8001"
    JOB_CANCELLED = "8002"
    JOB_EXPIRED = "8003"
    CHECKPOINT_LOAD_FAILED = "8004"


class MakeVideoBaseException(Exception):
    """Base exception for all Make-Video errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/API responses"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None
        }


# === Subprocess/FFmpeg Exceptions ===

class SubprocessException(MakeVideoBaseException):
    """Base for subprocess-related errors"""
    pass


class SubprocessTimeoutException(SubprocessException):
    """Subprocess exceeded timeout"""
    def __init__(self, message: str, command: str, timeout: float, **kwargs):
        super().__init__(
            message,
            ErrorCode.SUBPROCESS_TIMEOUT,
            details={"command": command, "timeout": timeout, **kwargs}
        )


class SubprocessFailedException(SubprocessException):
    """Subprocess returned non-zero exit code"""
    def __init__(self, message: str, command: str, returncode: int, stderr: str = "", **kwargs):
        super().__init__(
            message,
            ErrorCode.SUBPROCESS_FAILED,
            details={
                "command": command,
                "returncode": returncode,
                "stderr": stderr,
                **kwargs
            }
        )


# === Video Processing Exceptions ===

class VideoProcessingException(MakeVideoBaseException):
    """Base for video processing errors"""
    pass


class VideoCorruptedException(VideoProcessingException):
    """Video file is corrupted or unreadable"""
    def __init__(self, message: str, video_path: str, **kwargs):
        super().__init__(
            message,
            ErrorCode.VIDEO_CORRUPTED,
            details={"video_path": video_path, **kwargs}
        )


class VideoIncompatibleException(VideoProcessingException):
    """Video has incompatible codec/FPS/resolution"""
    def __init__(
        self,
        message: str,
        video_path: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        incompatibility_type: str = "codec"
    ):
        error_codes = {
            "codec": ErrorCode.VIDEO_INVALID_CODEC,
            "fps": ErrorCode.VIDEO_INVALID_FPS,
            "resolution": ErrorCode.VIDEO_INVALID_RESOLUTION
        }
        
        super().__init__(
            message,
            error_codes.get(incompatibility_type, ErrorCode.VIDEO_CONCAT_INCOMPATIBLE),
            details={
                "video_path": video_path,
                "expected": expected,
                "actual": actual,
                "incompatibility_type": incompatibility_type
            }
        )


class VideoConcatenationException(VideoProcessingException):
    """Video concatenation failed"""
    def __init__(
        self,
        message: str,
        input_files: list,
        expected_duration: float,
        actual_duration: float = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.VIDEO_CONCAT_FAILED,
            details={
                "input_count": len(input_files),
                "expected_duration": expected_duration,
                "actual_duration": actual_duration,
                **kwargs
            }
        )


class VideoSyncDriftException(VideoProcessingException):
    """Audio-video sync drift exceeded tolerance"""
    def __init__(
        self,
        message: str,
        audio_duration: float,
        video_duration: float,
        drift: float,
        tolerance: float = 0.5
    ):
        super().__init__(
            message,
            ErrorCode.VALIDATION_DRIFT_EXCEEDED,
            details={
                "audio_duration": audio_duration,
                "video_duration": video_duration,
                "drift": drift,
                "tolerance": tolerance,
                "drift_percentage": (drift / audio_duration * 100) if audio_duration > 0 else 0
            }
        )


# === Audio Processing Exceptions ===

class AudioProcessingException(MakeVideoBaseException):
    """Base for audio processing errors"""
    pass


class AudioExtractionException(AudioProcessingException):
    """Audio extraction from video failed"""
    def __init__(self, message: str, video_path: str, **kwargs):
        super().__init__(
            message,
            ErrorCode.AUDIO_EXTRACTION_FAILED,
            details={"video_path": video_path, **kwargs}
        )


# === Transcription Exceptions ===

class TranscriptionException(MakeVideoBaseException):
    """Base for transcription errors"""
    pass


class TranscriptionFailedException(TranscriptionException):
    """Transcription failed after retries"""
    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: str = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.TRANSCRIPTION_FAILED,
            details={
                "attempts": attempts,
                "last_error": last_error,
                **kwargs
            }
        )


class TranscriptionTimeoutException(TranscriptionException):
    """Transcription request timed out"""
    def __init__(self, message: str, timeout: float, **kwargs):
        super().__init__(
            message,
            ErrorCode.TRANSCRIPTION_TIMEOUT,
            details={"timeout": timeout, **kwargs}
        )


# === External API Exceptions ===

class MicroserviceException(MakeVideoBaseException):
    """Base for external microservice errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        service_name: str,
        details: Optional[Dict] = None
    ):
        super().__init__(
            message,
            error_code,
            details={"service": service_name, **(details or {})}
        )
        self.service_name = service_name


class APITimeoutException(MicroserviceException):
    """External API timed out"""
    def __init__(self, service_name: str, timeout: float, endpoint: str = None):
        super().__init__(
            f"{service_name} API timeout after {timeout}s",
            ErrorCode.API_TIMEOUT,
            service_name,
            details={"timeout": timeout, "endpoint": endpoint}
        )


class APIRateLimitException(MicroserviceException):
    """External API rate limit exceeded"""
    def __init__(self, service_name: str, retry_after: int = None):
        super().__init__(
            f"{service_name} API rate limit exceeded",
            ErrorCode.API_RATE_LIMIT,
            service_name,
            details={"retry_after": retry_after}
        )


# === Validation Exceptions ===

class ValidationException(MakeVideoBaseException):
    """Base for validation errors"""
    pass


class IntegrityValidationException(ValidationException):
    """File integrity validation failed"""
    def __init__(self, message: str, file_path: str, **kwargs):
        super().__init__(
            message,
            ErrorCode.VALIDATION_INTEGRITY_FAILED,
            details={"file_path": file_path, **kwargs}
        )


# === Resource Exceptions ===

class ResourceException(MakeVideoBaseException):
    """Base for resource constraint errors"""
    pass


class DiskFullException(ResourceException):
    """Disk space exhausted"""
    def __init__(self, message: str, available_gb: float, required_gb: float):
        super().__init__(
            message,
            ErrorCode.RESOURCE_DISK_FULL,
            details={
                "available_gb": available_gb,
                "required_gb": required_gb
            }
        )
```

##### 1.2: Criar Exception Handler Global

**Arquivo:** `app/shared/exception_handler.py` (NOVO)

```python
"""
Global exception handler with structured logging
"""
import logging
import traceback
from typing import Optional
from app.shared.exceptions import MakeVideoBaseException, ErrorCode

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """Centralized exception handling with structured logging"""
    
    @staticmethod
    def log_exception(
        exc: Exception,
        context: Optional[dict] = None,
        log_level: str = "error"
    ):
        """
        Log exception com contexto estruturado
        
        Args:
            exc: Exception a logar
            context: Contexto adicional (job_id, stage, etc)
            log_level: Nível do log (error, warning, critical)
        """
        context = context or {}
        
        # Se é exceção customizada, usar to_dict()
        if isinstance(exc, MakeVideoBaseException):
            log_data = {
                **exc.to_dict(),
                **context,
                "stacktrace": traceback.format_exc()
            }
        else:
            # Exceção genérica
            log_data = {
                "error_type": type(exc).__name__,
                "error_code": "UNKNOWN",
                "message": str(exc),
                **context,
                "stacktrace": traceback.format_exc()
            }
        
        # Logar com nível apropriado
        log_func = getattr(logger, log_level, logger.error)
        log_func(
            f"Exception: {log_data['error_type']}",
            extra=log_data
        )
        
        return log_data
    
    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        """
        Determina se exceção é retryable
        
        Returns:
            True se deve fazer retry (erro temporário)
        """
        from app.shared.exceptions import (
            APITimeoutException,
            APIRateLimitException,
            TranscriptionTimeoutException
        )
        
        retryable_exceptions = (
            APITimeoutException,
            APIRateLimitException,
            TranscriptionTimeoutException,
            ConnectionError,
            TimeoutError
        )
        
        return isinstance(exc, retryable_exceptions)
    
    @staticmethod
    def should_alert(exc: Exception) -> bool:
        """
        Determina se exceção requer alerta (PagerDuty, etc)
        
        Returns:
            True se é erro crítico que requer atenção imediata
        """
        from app.shared.exceptions import (
            ResourceException,
            SubprocessException
        )
        
        critical_exceptions = (
            ResourceException,  # Disk full, OOM
            SystemError,
            MemoryError
        )
        
        return isinstance(exc, critical_exceptions)
```

##### 1.3: Refatorar Código para Usar Exceções Específicas

**Locais a refatorar:**

1. **video_builder.py** - Substituir `Exception` por `VideoProcessingException`, `SubprocessFailedException`
2. **api_client.py** - Usar `MicroserviceException`, `APITimeoutException`
3. **celery_tasks.py** - Usar `TranscriptionFailedException`, `VideoConcatenationException`
4. **video_validator.py** - Usar `ValidationException`, `VideoCorruptedException`

**Exemplo de refatoração:**

```python
# ANTES:
try:
    result = await process_video(input_path)
except Exception as e:
    logger.error(f"Error: {e}")
    raise

# DEPOIS:
from app.shared.exceptions import VideoProcessingException, VideoCorruptedException
from app.shared.exception_handler import ExceptionHandler

try:
    result = await process_video(input_path)
except VideoCorruptedException as e:
    # Exceção esperada - logar e propagar
    ExceptionHandler.log_exception(e, context={"job_id": job_id}, log_level="warning")
    raise
except VideoProcessingException as e:
    # Erro de processamento genérico
    ExceptionHandler.log_exception(e, context={"job_id": job_id})
    raise
except Exception as e:
    # Exceção INESPERADA - crítica!
    ExceptionHandler.log_exception(e, context={"job_id": job_id}, log_level="critical")
    if ExceptionHandler.should_alert(e):
        # Disparar alerta
        pass
    raise
```

**Critério de Aceite:**
- ✅ Hierarquia completa de 30+ exceções específicas
- ✅ 90% dos `except Exception` substituídos
- ✅ Todos os logs incluem error_code e stacktrace
- ✅ Exceptions retryable identificadas automaticamente

---

### Task 2: Validação de Drift Áudio-Legenda (R-007)

**Story Points:** 5  
**Prioridade:** P1  
**Impacto:** Melhor UX (sync perfeito)

#### Descrição
Adicionar validação de drift entre áudio e vídeo final, com correção automática se necessário.

#### Sub-tasks

##### 2.1: Implementar Validador de Drift

**Arquivo:** `app/services/sync_validator.py` (NOVO)

```python
"""
Audio-Video Synchronization Validator
"""
import logging
from typing import Tuple, Dict, Any
from app.shared.exceptions import VideoSyncDriftException

logger = logging.getLogger(__name__)


class SyncValidator:
    """Valida sincronização áudio-vídeo"""
    
    def __init__(self, tolerance_seconds: float = 0.5):
        """
        Args:
            tolerance_seconds: Tolerância máxima de drift (default: 500ms)
        """
        self.tolerance = tolerance_seconds
    
    async def validate_sync(
        self,
        video_path: str,
        audio_path: str,
        video_builder  # VideoBuilder instance
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Valida sincronização entre áudio e vídeo.
        
        Args:
            video_path: Path do vídeo final com legendas
            audio_path: Path do áudio original
            video_builder: Instância do VideoBuilder para get_video_info
        
        Returns:
            (is_valid, drift, metadata)
        
        Raises:
            VideoSyncDriftException: Se drift exceder tolerância
        """
        logger.info(f"Validating A/V sync: video={video_path}, audio={audio_path}")
        
        # Obter durações
        video_info = await video_builder.get_video_info(video_path)
        video_duration = video_info['duration']
        
        from app.utils.audio_utils import get_audio_duration
        audio_duration = await get_audio_duration(audio_path)
        
        # Calcular drift
        drift = abs(video_duration - audio_duration)
        drift_percentage = (drift / audio_duration * 100) if audio_duration > 0 else 0
        
        is_valid = drift <= self.tolerance
        
        metadata = {
            "audio_duration": audio_duration,
            "video_duration": video_duration,
            "drift": drift,
            "drift_percentage": drift_percentage,
            "tolerance": self.tolerance,
            "is_valid": is_valid
        }
        
        logger.info(
            f"A/V sync validation: drift={drift:.3f}s ({drift_percentage:.2f}%)",
            extra=metadata
        )
        
        if not is_valid:
            raise VideoSyncDriftException(
                f"Audio-video drift ({drift:.3f}s) exceeds tolerance ({self.tolerance}s)",
                audio_duration=audio_duration,
                video_duration=video_duration,
                drift=drift,
                tolerance=self.tolerance
            )
        
        return is_valid, drift, metadata
    
    def calculate_subtitle_correction(
        self,
        drift: float,
        audio_duration: float,
        video_duration: float
    ) -> Dict[str, float]:
        """
        Calcula correção linear para timestamps de legendas.
        
        Se vídeo é mais longo que áudio:
        - Stretch subtitle timing (multiplicar timestamps)
        
        Se vídeo é mais curto:
        - Compress subtitle timing (dividir timestamps)
        
        Args:
            drift: Diferença absoluta em segundos
            audio_duration: Duração do áudio
            video_duration: Duração do vídeo
        
        Returns:
            {
                "scale_factor": float,  # Multiplicador para timestamps
                "offset": float          # Offset inicial
            }
        """
        scale_factor = video_duration / audio_duration if audio_duration > 0 else 1.0
        
        logger.info(
            f"Subtitle correction: scale_factor={scale_factor:.4f}",
            extra={
                "audio_duration": audio_duration,
                "video_duration": video_duration,
                "drift": drift
            }
        )
        
        return {
            "scale_factor": scale_factor,
            "offset": 0.0  # Pode ajustar se precisar
        }
    
    async def apply_subtitle_correction(
        self,
        srt_path: str,
        scale_factor: float,
        offset: float = 0.0
    ) -> str:
        """
        Aplica correção temporal a arquivo SRT.
        
        Args:
            srt_path: Path do arquivo SRT original
            scale_factor: Fator de escala para timestamps
            offset: Offset a adicionar (segundos)
        
        Returns:
            Path do SRT corrigido
        """
        import pysrt
        from pathlib import Path
        
        logger.info(f"Applying subtitle correction: scale={scale_factor:.4f}, offset={offset:.3f}s")
        
        # Carregar SRT
        subs = pysrt.open(srt_path)
        
        # Aplicar correção
        for sub in subs:
            # Start time
            start_ms = (sub.start.ordinal / 1000.0)  # Converter para segundos
            new_start_ms = (start_ms * scale_factor + offset) * 1000
            sub.start.ordinal = int(new_start_ms)
            
            # End time
            end_ms = (sub.end.ordinal / 1000.0)
            new_end_ms = (end_ms * scale_factor + offset) * 1000
            sub.end.ordinal = int(new_end_ms)
        
        # Salvar SRT corrigido
        corrected_path = str(Path(srt_path).with_suffix('.corrected.srt'))
        subs.save(corrected_path, encoding='utf-8')
        
        logger.info(f"✅ Subtitle correction applied: {corrected_path}")
        
        return corrected_path
```

##### 2.2: Integrar no Pipeline

**Arquivo:** `app/infrastructure/celery_tasks.py`

Adicionar após overlay de legendas:

```python
# Após add_subtitles_to_video
final_video_path = await video_builder.add_subtitles_to_video(...)

logger.info(f"📏 [7.5/7] Validating A/V sync...")

# Validar sync
from app.services.sync_validator import SyncValidator
sync_validator = SyncValidator(tolerance_seconds=0.5)

try:
    is_valid, drift, sync_metadata = await sync_validator.validate_sync(
        video_path=final_video_path,
        audio_path=str(audio_path),
        video_builder=video_builder
    )
    
    logger.info(
        f"✅ A/V sync validation passed: drift={drift:.3f}s",
        extra=sync_metadata
    )
    
    # Salvar metadata no job
    await update_job_status(
        job_id,
        JobStatus.ADDING_SUBTITLES,
        progress=95.0,
        stage_updates={
            "adding_subtitles": {
                "metadata": {
                    "sync_validation": sync_metadata
                }
            }
        }
    )

except VideoSyncDriftException as e:
    logger.warning(
        f"⚠️ A/V sync drift detected: {e.details['drift']:.3f}s, attempting correction..."
    )
    
    # Calcular correção
    correction = sync_validator.calculate_subtitle_correction(
        drift=e.details['drift'],
        audio_duration=e.details['audio_duration'],
        video_duration=e.details['video_duration']
    )
    
    # Aplicar correção ao SRT
    corrected_srt_path = await sync_validator.apply_subtitle_correction(
        srt_path=srt_path,
        scale_factor=correction['scale_factor'],
        offset=correction['offset']
    )
    
    # Refazer overlay com SRT corrigido
    logger.info("🔄 Re-applying subtitles with corrected timestamps...")
    
    final_video_path = await video_builder.add_subtitles_to_video(
        video_path=temp_video_path,
        audio_path=str(audio_path),
        srt_path=corrected_srt_path,
        output_path=str(output_path),
        subtitle_style=subtitle_style
    )
    
    # Validar novamente
    _, new_drift, _ = await sync_validator.validate_sync(
        video_path=final_video_path,
        audio_path=str(audio_path),
        video_builder=video_builder
    )
    
    logger.info(f"✅ Subtitle correction successful: drift reduced to {new_drift:.3f}s")
```

**Critério de Aceite:**
- ✅ Drift detectado e validado
- ✅ Correção automática aplicada se drift >500ms
- ✅ Testes: VFR video → drift <500ms após correção

---

### Task 3: Validação de Integridade em Download (R-008)

**Story Points:** 5  
**Prioridade:** P1  
**Impacto:** -25% falhas tardias

#### Descrição
Adicionar validação de integridade (ffprobe) imediatamente após download de vídeo.

#### Sub-tasks

##### 3.1: Refatorar api_client.download_video

**Arquivo:** `app/api/api_client.py`

```python
async def download_video(self, video_id: str, output_path: str) -> Dict:
    """
    Baixa vídeo E valida integridade.
    
    Raises:
        IntegrityValidationException: Se vídeo corrompido
    """
    logger.info(f"📡 Downloading video: {video_id}")
    
    # ... código de download existente ...
    
    # Baixar arquivo
    video_response = await self.client.get(
        f"{self.video_downloader_url}/jobs/{job_id}/download"
    )
    video_response.raise_for_status()
    
    # Salvar
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(video_response.content)
    
    logger.info(f"💾 File saved: {output_path} ({len(video_response.content)} bytes)")
    
    # ✅ VALIDAR INTEGRIDADE
    from app.video_processing.video_validator import VideoValidator
    from app.shared.exceptions import IntegrityValidationException
    
    try:
        validator = VideoValidator()
        is_valid = validator.validate_video_integrity(output_path, timeout=10)
        
        logger.info(f"✅ Integrity validation passed: {video_id}")
    
    except Exception as e:
        logger.error(
            f"❌ Downloaded video failed integrity check: {video_id}",
            exc_info=True
        )
        
        # Remover arquivo corrompido
        try:
            os.unlink(output_path)
            logger.info(f"🗑️  Removed corrupted file: {output_path}")
        except:
            pass
        
        raise IntegrityValidationException(
            f"Downloaded video is corrupted: {e}",
            file_path=output_path,
            video_id=video_id,
            reason=str(e)
        )
    
    return job.get("metadata", {})
```

**Critério de Aceite:**
- ✅ Todos os downloads validados com ffprobe
- ✅ Arquivo corrompido removido imediatamente
- ✅ Exception clara com detalhes

---

### Task 4: Validação de Compatibilidade em Concatenação (R-009)

**Story Points:** 8  
**Prioridade:** P1  
**Impacto:** -15% falhas de concatenação

#### Descrição
Validar que todos os vídeos têm codec/FPS/resolução compatíveis ANTES de concatenar.

#### Sub-tasks

##### 4.1: Implementar Validador de Compatibilidade

**Arquivo:** `app/services/video_compatibility_validator.py` (NOVO)

```python
"""
Video Compatibility Validator

Validates that videos can be safely concatenated
"""
import logging
from typing import List, Dict, Any, Optional
from app.shared.exceptions import VideoIncompatibleException

logger = logging.getLogger(__name__)


class VideoCompatibilityValidator:
    """Valida compatibilidade de vídeos para concatenação"""
    
    @staticmethod
    async def validate_concat_compatibility(
        video_files: List[str],
        video_builder,  # VideoBuilder instance
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        Valida que vídeos são compatíveis para concat.
        
        Args:
            video_files: Lista de paths de vídeos
            video_builder: Instância do VideoBuilder
            strict: Se True, falha em qualquer incompatibilidade
                   Se False, apenas avisa
        
        Returns:
            Metadata com resultado da validação
        
        Raises:
            VideoIncompatibleException: Se incompatibilidade detectada (strict=True)
        """
        logger.info(f"Validating compatibility of {len(video_files)} videos")
        
        if len(video_files) == 0:
            raise ValueError("No video files to validate")
        
        # Obter metadata de todos os vídeos
        videos_metadata = []
        for vf in video_files:
            info = await video_builder.get_video_info(vf)
            videos_metadata.append({
                "path": vf,
                "codec": info.get('video_codec'),
                "fps": info.get('fps'),
                "width": info.get('width'),
                "height": info.get('height'),
                "duration": info.get('duration'),
                "bitrate": info.get('bitrate')
            })
        
        # Usar primeiro vídeo como referência
        reference = videos_metadata[0]
        incompatibilities = []
        
        # Validar cada vídeo contra referência
        for i, video_meta in enumerate(videos_metadata[1:], start=1):
            issues = []
            
            # Validar codec
            if video_meta['codec'] != reference['codec']:
                issues.append({
                    "type": "codec",
                    "expected": reference['codec'],
                    "actual": video_meta['codec']
                })
            
            # Validar FPS (tolerância de 0.1)
            fps_diff = abs(video_meta['fps'] - reference['fps'])
            if fps_diff > 0.1:
                issues.append({
                    "type": "fps",
                    "expected": reference['fps'],
                    "actual": video_meta['fps'],
                    "diff": fps_diff
                })
            
            # Validar resolução
            if (video_meta['width'] != reference['width'] or 
                video_meta['height'] != reference['height']):
                issues.append({
                    "type": "resolution",
                    "expected": f"{reference['width']}x{reference['height']}",
                    "actual": f"{video_meta['width']}x{video_meta['height']}"
                })
            
            if issues:
                incompatibilities.append({
                    "video_index": i,
                    "video_path": video_meta['path'],
                    "issues": issues
                })
        
        # Resultado
        is_compatible = len(incompatibilities) == 0
        
        result = {
            "is_compatible": is_compatible,
            "total_videos": len(video_files),
            "reference_video": reference,
            "incompatibilities": incompatibilities
        }
        
        # Logar resultado
        if is_compatible:
            logger.info(
                f"✅ All videos compatible",
                extra={
                    "video_count": len(video_files),
                    "codec": reference['codec'],
                    "fps": reference['fps'],
                    "resolution": f"{reference['width']}x{reference['height']}"
                }
            )
        else:
            logger.warning(
                f"⚠️ Incompatible videos detected: {len(incompatibilities)} issues",
                extra=result
            )
        
        # Lançar exceção se strict=True
        if strict and not is_compatible:
            # Pegar primeira incompatibilidade para mensagem
            first_incompat = incompatibilities[0]
            first_issue = first_incompat['issues'][0]
            
            raise VideoIncompatibleException(
                f"Video {first_incompat['video_index']} has incompatible {first_issue['type']}",
                video_path=first_incompat['video_path'],
                expected={first_issue['type']: first_issue['expected']},
                actual={first_issue['type']: first_issue['actual']},
                incompatibility_type=first_issue['type']
            )
        
        return result
```

##### 4.2: Integrar no Pipeline

**Arquivo:** `app/services/video_builder.py`

```python
async def concatenate_videos(self, video_files, output_path, ...):
    """Concatena vídeos com validação de compatibilidade"""
    
    logger.info(f"🎬 Concatenating {len(video_files)} videos")
    
    # ✅ VALIDAR COMPATIBILIDADE ANTES
    from app.services.video_compatibility_validator import VideoCompatibilityValidator
    
    compat_result = await VideoCompatibilityValidator.validate_concat_compatibility(
        video_files=video_files,
        video_builder=self,
        strict=True  # Falha se incompatível
    )
    
    logger.info(
        f"✅ Compatibility check passed",
        extra=compat_result
    )
    
    # ... resto do código de concatenação ...
```

**Critério de Aceite:**
- ✅ Validação antes de toda concatenação
- ✅ Incompatibilidade detecta codec/FPS/resolução
- ✅ Teste: FPS diferentes → falha rápido

---

### Task 5: Checkpoint Granular em Etapas Críticas (R-013)

**Story Points:** 8  
**Prioridade:** P2  
**Impacto:** -50% perda de progresso

#### Descrição
Usar `GranularCheckpointManager` em loops de download e validação.

#### Sub-tasks

##### 5.1: Integrar em Download de Shorts

**Arquivo:** `app/pipeline/video_pipeline.py`

```python
async def download_and_validate_batch(
    self,
    shorts: List[Dict],
    job_id: str,
    aspect_ratio: str = "9:16"
) -> List[str]:
    """Download shorts com checkpoint granular"""
    
    from app.infrastructure.checkpoint_manager import (
        GranularCheckpointManager,
        CheckpointStage
    )
    
    checkpoint_mgr = GranularCheckpointManager(self.status_store.redis_store)
    
    # Verificar se há checkpoint anterior
    checkpoint = await checkpoint_mgr.load_checkpoint(job_id)
    
    if checkpoint and checkpoint.stage == CheckpointStage.DOWNLOADING_SHORTS.value:
        logger.info(
            f"📍 Resuming from checkpoint: {checkpoint.completed_items}/{checkpoint.total_items} shorts"
        )
        
        # Filtrar shorts já baixados
        completed_ids = set(checkpoint.item_ids)
        shorts_to_download = [
            s for s in shorts 
            if s['video_id'] not in completed_ids
        ]
        
        logger.info(f"🔄 Skipping {len(completed_ids)} already downloaded shorts")
    else:
        shorts_to_download = shorts
    
    # Download com checkpoint
    approved_shorts = []
    
    for i, short in enumerate(shorts_to_download):
        video_id = short['video_id']
        
        # Download e validate...
        video_path = await self.download_short(video_id, ...)
        
        if is_approved:
            approved_shorts.append(video_path)
        
        # Salvar checkpoint granular a cada 10 shorts
        total_completed = len(completed_ids) + i + 1
        
        if await checkpoint_mgr.should_save_checkpoint(total_completed, len(shorts)):
            await checkpoint_mgr.save_checkpoint(
                job_id=job_id,
                stage=CheckpointStage.DOWNLOADING_SHORTS,
                completed_items=total_completed,
                total_items=len(shorts),
                item_ids=list(completed_ids) + [s['video_id'] for s in shorts_to_download[:i+1]],
                metadata={
                    "approved_count": len(approved_shorts),
                    "aspect_ratio": aspect_ratio
                }
            )
    
    return approved_shorts
```

**Critério de Aceite:**
- ✅ Checkpoint salvo a cada 10 shorts
- ✅ Recuperação automática após crash
- ✅ Teste: crash em 45/50 → retoma de 40/50

---

## 🧪 Plano de Testes

### Testes Unitários
```bash
pytest tests/test_exceptions.py -v
pytest tests/test_sync_validator.py -v
pytest tests/test_video_compatibility.py -v
pytest tests/test_checkpoint_integration.py -v
```

### Testes de Integração
```bash
pytest tests/integration/test_full_pipeline_with_validation.py -v
pytest tests/integration/test_drift_correction.py -v
```

### Testes de Cenários
```bash
# Vídeo VFR com drift
pytest tests/scenarios/test_vfr_video_drift.py

# Vídeos incompatíveis
pytest tests/scenarios/test_incompatible_videos.py

# Recovery com checkpoint
pytest tests/scenarios/test_checkpoint_recovery.py
```

---

## 📊 Métricas de Validação

Dashboard Grafana: "Sprint-01 Metrics"

- `exception_by_type` - Contagem por tipo de exceção
- `sync_drift_histogram` - Distribuição de drift A/V
- `compatibility_failures` - Falhas de compatibilidade
- `checkpoint_recovery_rate` - Taxa de recuperação com checkpoint

---

## ✅ Definition of Done

- [ ] 5 tasks implementadas
- [ ] Hierarquia de exceções com 30+ tipos
- [ ] Drift A/V <500ms em 99% dos casos
- [ ] Zero falhas por incompatibilidade (detectadas antes)
- [ ] 80% dos jobs recuperados com checkpoint
- [ ] Testes 100% passando
- [ ] Code review aprovado
- [ ] Deployed e validado em staging

---

**Próxima Sprint:** SPRINT-RESILIENCE-02.md (Observabilidade e Fallbacks)
