"""
Exceções customizadas para a aplicação.
Segue boas práticas de tratamento de erros.

v2.1: Exceções granulares para melhor debugging.
"""


class DomainException(Exception):
    """Exceção base para erros de domínio."""


class VideoDownloadError(DomainException):
    """Erro ao baixar vídeo."""


class TranscriptionError(DomainException):
    """Erro ao transcrever áudio."""


class StorageError(DomainException):
    """Erro de armazenamento."""


class ValidationError(DomainException):
    """Erro de validação."""


class ResourceNotFoundError(DomainException):
    """Recurso não encontrado."""


class ServiceUnavailableError(DomainException):
    """Serviço indisponível."""


# ============= EXCEÇÕES GRANULARES v2.1 =============

class AudioTooLongError(ValidationError):
    """Áudio excede duração máxima permitida."""
    
    def __init__(self, duration: float, max_duration: float):
        self.duration = duration
        self.max_duration = max_duration
        super().__init__(
            f"Audio duration {duration:.0f}s exceeds maximum allowed {max_duration:.0f}s"
        )


class AudioCorruptedError(ValidationError):
    """Arquivo de áudio corrompido ou ilegível."""
    
    def __init__(self, file_path: str, reason: str = "Unknown"):
        self.file_path = file_path
        self.reason = reason
        super().__init__(
            f"Audio file '{file_path}' is corrupted: {reason}"
        )


class ModelLoadError(TranscriptionError):
    """Erro ao carregar modelo Whisper."""
    
    def __init__(self, model_name: str, reason: str):
        self.model_name = model_name
        self.reason = reason
        super().__init__(
            f"Failed to load Whisper model '{model_name}': {reason}"
        )


class CacheError(DomainException):
    """Erro no sistema de cache."""
    
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"Cache operation '{operation}' failed: {reason}"
        )


class WorkerPoolError(TranscriptionError):
    """Erro no pool de workers de transcrição."""
    
    def __init__(self, worker_id: int = None, reason: str = "Unknown"):
        self.worker_id = worker_id
        self.reason = reason
        msg = "Worker pool error"
        if worker_id is not None:
            msg += f" (worker {worker_id})"
        msg += f": {reason}"
        super().__init__(msg)


class FFmpegError(TranscriptionError):
    """Erro ao executar FFmpeg."""
    
    def __init__(self, command: str, stderr: str):
        self.command = command
        self.stderr = stderr
        super().__init__(
            f"FFmpeg command failed: {stderr[:200]}"
        )


class NetworkError(DomainException):
    """Erro de rede ao comunicar com serviços externos."""
    
    def __init__(self, service: str, reason: str):
        self.service = service
        self.reason = reason
        super().__init__(
            f"Network error communicating with {service}: {reason}"
        )


class OperationTimeoutError(DomainException):
    """Operação excedeu tempo limite."""
    
    def __init__(self, operation: str, timeout: float):
        self.operation = operation
        self.timeout = timeout
        super().__init__(
            f"Operation '{operation}' timed out after {timeout}s"
        )


class QuotaExceededError(DomainException):
    """Quota/limite de uso excedido."""
    
    def __init__(self, resource: str, limit: int, current: int):
        self.resource = resource
        self.limit = limit
        self.current = current
        super().__init__(
            f"Quota exceeded for '{resource}': {current}/{limit}"
        )
