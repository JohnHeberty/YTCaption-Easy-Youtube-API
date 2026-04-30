"""
Exceções específicas para o serviço de normalização de áudio.

Segue o princípio de ser específico ao invés de capturar Exception genérico.
"""
from fastapi import status


class AudioNormalizationError(Exception):
    """Base exception para todos os erros do serviço."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "AUDIO_NORMALIZATION_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "detail": self.message,
            "error_code": self.error_code,
            "status_code": self.status_code,
        }


class InvalidAudioFormat(AudioNormalizationError):
    """Formato de áudio inválido ou não suportado."""

    def __init__(self, message: str = "Formato de áudio inválido"):
        super().__init__(
            message,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code="INVALID_AUDIO_FORMAT",
        )


class FileTooLarge(AudioNormalizationError):
    """Arquivo excede tamanho máximo permitido."""

    def __init__(self, size_mb: float, max_size_mb: int):
        super().__init__(
            f"Arquivo muito grande ({size_mb:.2f}MB). Máximo permitido: {max_size_mb}MB",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="FILE_TOO_LARGE",
        )


class ProcessingError(AudioNormalizationError):
    """Erro durante processamento de áudio."""

    def __init__(self, message: str = "Erro no processamento de áudio"):
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROCESSING_ERROR",
        )


class RedisError(AudioNormalizationError):
    """Erro de conexão ou operação no Redis."""

    def __init__(self, message: str = "Erro no Redis"):
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="REDIS_ERROR",
        )


class JobNotFoundError(AudioNormalizationError):
    """Job não encontrado."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job não encontrado: {job_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
        )


class JobExpiredError(AudioNormalizationError):
    """Job expirou."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job expirado: {job_id}",
            status_code=status.HTTP_410_GONE,
            error_code="JOB_EXPIRED",
        )


class StorageError(AudioNormalizationError):
    """Erro de armazenamento (disco, etc)."""

    def __init__(self, message: str = "Erro de armazenamento"):
        super().__init__(
            message,
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            error_code="STORAGE_ERROR",
        )


class ValidationError(AudioNormalizationError):
    """Erro de validação de entrada."""

    def __init__(self, message: str = "Erro de validação"):
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
        )


class CeleryTaskError(AudioNormalizationError):
    """Erro ao enviar tarefa para Celery."""

    def __init__(self, message: str = "Erro ao enviar tarefa para processamento"):
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="CELERY_TASK_ERROR",
        )


class FileValidationError(AudioNormalizationError):
    """Falha na validação do arquivo de entrada."""

    def __init__(self, message: str = "Falha na validação do arquivo"):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="FILE_VALIDATION_ERROR",
        )


class ResourceNotFoundError(AudioNormalizationError):
    """Recurso solicitado não encontrado."""

    def __init__(self, resource_id: str = ""):
        super().__init__(
            f"Recurso não encontrado: {resource_id}" if resource_id else "Recurso não encontrado",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
        )


class ProcessingTimeoutError(AudioNormalizationError):
    """Processamento excedeu o limite de tempo."""

    def __init__(self, message: str = "Processamento excedeu o limite de tempo"):
        super().__init__(
            message,
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            error_code="PROCESSING_TIMEOUT",
        )


class ResourceError(AudioNormalizationError):
    """Falha de recurso/infraestrutura."""

    def __init__(self, message: str = "Recurso indisponível"):
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="RESOURCE_ERROR",
        )


# Backward compatibility alias
AudioNormalizationException = AudioNormalizationError
