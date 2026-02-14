"""
Enhanced Exception Hierarchy - Enterprise Pattern

Baseado em padrões de grandes empresas (Google, AWS, Microsoft).
Exceções ricas em contexto com error codes, tracking e serialização.

Pattern: Exception Hierarchy + Error Codes
"""

from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import traceback
import json


class ErrorCode(Enum):
    """
    Códigos de erro padronizados
    
    Organizados por categoria (prefixo numérico):
    - 1xxx: Audio Errors
    - 2xxx: Video Errors
    - 3xxx: Processing Errors
    - 4xxx: External Service Errors
    - 5xxx: System Errors
    """
    # Audio Errors (1xxx)
    AUDIO_NOT_FOUND = 1001
    AUDIO_FILE_NOT_FOUND = 1001  # Alias
    AUDIO_TOO_SHORT = 1002
    AUDIO_TOO_LONG = 1003
    AUDIO_CORRUPTED = 1004
    AUDIO_INVALID_FORMAT = 1005
    AUDIO_UPLOAD_FAILED = 1006
    AUDIO_PROCESSING_FAILED = 1007
    TRANSCRIPTION_FAILED = 1008
    
    # Video Errors (2xxx)
    VIDEO_NOT_FOUND = 2001
    VIDEO_FILE_NOT_FOUND = 2001  # Alias
    VIDEO_DOWNLOAD_FAILED = 2002
    VIDEO_VALIDATION_FAILED = 2003
    VIDEO_HAS_SUBTITLES = 2004
    VIDEO_CORRUPTED = 2005
    VIDEO_TOO_SHORT = 2006
    VIDEO_TOO_LONG = 2007
    VIDEO_INVALID_RESOLUTION = 2008
    VIDEO_ENCODING_FAILED = 2009
    
    # Processing Errors (3xxx)
    NO_SHORTS_FOUND = 3001
    INSUFFICIENT_SHORTS = 3002
    NO_VALID_SHORTS = 3002  # Alias
    CONCATENATION_FAILED = 3003
    SUBTITLE_GENERATION_FAILED = 3004
    SUBTITLE_FILE_NOT_FOUND = 3005
    OCR_DETECTION_FAILED = 3006
    BLACKLIST_CHECK_FAILED = 3007
    CACHE_WRITE_FAILED = 3008
    TEMP_FILE_ERROR = 3009
    INSUFFICIENT_DURATION = 3010
    INVALID_QUERY = 3011
    INVALID_TRIM_CONFIG = 3012
    PROCESSING_STAGE_FAILED = 3013
    PROCESSING_FAILED = 3014
    
    # External Service Errors (4xxx)
    YOUTUBE_SEARCH_UNAVAILABLE = 4001
    VIDEO_DOWNLOADER_UNAVAILABLE = 4002
    AUDIO_TRANSCRIBER_UNAVAILABLE = 4003
    TRANSCRIBER_TIMEOUT = 4004
    API_RATE_LIMIT_EXCEEDED = 4005
    API_AUTHENTICATION_FAILED = 4006
    API_INVALID_RESPONSE = 4007
    
    # System Errors (5xxx)
    DISK_FULL = 5001
    OUT_OF_MEMORY = 5002
    REDIS_UNAVAILABLE = 5003
    REDIS_TIMEOUT = 5004
    DATABASE_ERROR = 5005
    CONFIGURATION_ERROR = 5006
    UNKNOWN_ERROR = 5999


class EnhancedMakeVideoException(Exception):
    """
    Base exception aprimorada para Make-Video service
    
    Features:
    - Error codes padronizados
    - Contexto rico (details dict)
    - Causa raiz (exception chaining)
    - Serialização para API/logs
    - Timestamp automático
    - Stack trace preservation
    
    Pattern: Rich Exception Hierarchy
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        job_id: Optional[str] = None,
        recoverable: bool = False
    ):
        """
        Args:
            message: Mensagem descritiva do erro
            error_code: Código de erro padronizado
            details: Detalhes adicionais (dados, valores, paths)
            cause: Exceção original (root cause)
            job_id: ID do job afetado (para tracking)
            recoverable: Se o erro permite retry/recovery
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.job_id = job_id
        self.recoverable = recoverable
        self.timestamp = datetime.utcnow()
        
        # Preservar stack trace da exceção original
        if cause:
            self.cause_traceback = ''.join(
                traceback.format_exception(
                    type(cause), cause, cause.__traceback__
                )
            )
        else:
            self.cause_traceback = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serializa exceção para dicionário (API responses, logs)
        
        Returns:
            Dict com estrutura padronizada
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "error_code_name": self.error_code.name,
            "details": self.details,
            "job_id": self.job_id,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
            "cause_type": type(self.cause).__name__ if self.cause else None
        }
    
    def to_json(self) -> str:
        """Serializa para JSON"""
        return json.dumps(self.to_dict(), default=str)
    
    def __str__(self) -> str:
        """String representation com código e mensagem"""
        base = f"[{self.error_code.name}] {self.message}"
        if self.job_id:
            base = f"[Job: {self.job_id}] {base}"
        return base
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.error_code.name}, "
            f"message='{self.message[:50]}...', "
            f"job_id={self.job_id})"
        )


class AudioProcessingException(EnhancedMakeVideoException):
    """
    Erro no processamento de áudio
    
    Usar para:
    - Arquivo não encontrado
    - Formato inválido
    - Duração inadequada
    - Corrupção
    - Upload/download failures
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        audio_path: Optional[str] = None,
        **kwargs
    ):
        if audio_path:
            if 'details' not in kwargs:
                kwargs['details'] = {}
            kwargs['details']['audio_path'] = audio_path
        
        super().__init__(message, error_code, **kwargs)


class VideoProcessingException(EnhancedMakeVideoException):
    """
    Erro no processamento de vídeo
    
    Usar para:
    - Download failures
    - Validação (OCR detection)
    - Encoding/concatenation errors
    - Formato/resolução inválida
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        video_id: Optional[str] = None,
        video_path: Optional[str] = None,
        **kwargs
    ):
        if 'details' not in kwargs:
            kwargs['details'] = {}
        
        if video_id:
            kwargs['details']['video_id'] = video_id
        if video_path:
            kwargs['details']['video_path'] = video_path
        
        super().__init__(message, error_code, **kwargs)


class MicroserviceException(EnhancedMakeVideoException):
    """
    Erro em comunicação com microserviços externos
    
    Usar para:
    - youtube-search timeout
    - video-downloader unavailable
    - audio-transcriber errors
    - API rate limiting
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        service_name: str,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        if 'details' not in kwargs:
            kwargs['details'] = {}
        
        kwargs['details']['service'] = service_name
        if endpoint:
            kwargs['details']['endpoint'] = endpoint
        if status_code:
            kwargs['details']['http_status'] = status_code
        
        # Microservice errors são frequentemente recuperáveis (retry)
        if 'recoverable' not in kwargs:
            kwargs['recoverable'] = True
        
        super().__init__(message, error_code, **kwargs)


class SystemException(EnhancedMakeVideoException):
    """
    Erro de sistema/infraestrutura
    
    Usar para:
    - Disco cheio
    - Memória insuficiente
    - Redis/DB unavailable
    - Config errors
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        component: Optional[str] = None,
        **kwargs
    ):
        if component:
            if 'details' not in kwargs:
                kwargs['details'] = {}
            kwargs['details']['component'] = component
        
        # System errors raramente são recuperáveis
        if 'recoverable' not in kwargs:
            kwargs['recoverable'] = False
        
        super().__init__(message, error_code, **kwargs)


# ============================================================================
# Helper Functions
# ============================================================================

def create_audio_error(
    message: str,
    error_code: ErrorCode,
    audio_path: str,
    job_id: Optional[str] = None,
    cause: Optional[Exception] = None
) -> AudioProcessingException:
    """Helper para criar AudioProcessingException com contexto padrão"""
    return AudioProcessingException(
        message=message,
        error_code=error_code,
        audio_path=audio_path,
        job_id=job_id,
        cause=cause,
        recoverable=False
    )


def create_video_error(
    message: str,
    error_code: ErrorCode,
    video_id: Optional[str] = None,
    video_path: Optional[str] = None,
    job_id: Optional[str] = None,
    cause: Optional[Exception] = None
) -> VideoProcessingException:
    """Helper para criar VideoProcessingException com contexto padrão"""
    return VideoProcessingException(
        message=message,
        error_code=error_code,
        video_id=video_id,
        video_path=video_path,
        job_id=job_id,
        cause=cause,
        recoverable=error_code in [
            ErrorCode.VIDEO_DOWNLOAD_FAILED,
            ErrorCode.VIDEO_VALIDATION_FAILED
        ]
    )


def create_api_error(
    message: str,
    service_name: str,
    error_code: ErrorCode = ErrorCode.API_INVALID_RESPONSE,
    endpoint: Optional[str] = None,
    status_code: Optional[int] = None,
    job_id: Optional[str] = None,
    cause: Optional[Exception] = None
) -> MicroserviceException:
    """Helper para criar MicroserviceException com contexto padrão"""
    return MicroserviceException(
        message=message,
        error_code=error_code,
        service_name=service_name,
        endpoint=endpoint,
        status_code=status_code,
        job_id=job_id,
        cause=cause,
        recoverable=True
    )


# ============================================================================
# Backward Compatibility (Mantém compatibilidade com código existente)
# ============================================================================

class MakeVideoException(EnhancedMakeVideoException):
    """
    Backward compatible exception class
    
    Aceita tanto o novo formato (com error_code) quanto o antigo (apenas message)
    """
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        job_id: Optional[str] = None,
        recoverable: bool = False
    ):
        """
        Args:
            message: Mensagem de erro (obrigatória)
            error_code: Código de erro (opcional, padrão UNKNOWN_ERROR)
            details: Detalhes adicionais (opcional)
            cause: Exceção original (opcional)
            job_id: ID do job (opcional)
            recoverable: Se permite retry (opcional)
        """
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            cause=cause,
            job_id=job_id,
            recoverable=recoverable
        )
