"""
Exceções específicas do orquestrador.

Hierarquia de exceções customizadas para melhor tratamento de erros.
"""
from typing import Optional


class OrchestratorError(Exception):
    """Base exception para erros do orquestrador."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class PipelineError(OrchestratorError):
    """Erro na execução do pipeline."""

    def __init__(self, stage: str, message: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.stage = stage
        self.original = original

    def __str__(self) -> str:
        if self.original:
            return f"Pipeline failed at stage '{self.stage}': {self.original}"
        return f"Pipeline failed at stage '{self.stage}': {self.message}"


class PipelineStageError(OrchestratorError):
    """Erro em estágio específico do pipeline."""

    def __init__(
        self,
        stage: str,
        message: str,
        original: Optional[Exception] = None,
        service_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.original = original
        self.service_name = service_name

    def __str__(self) -> str:
        service = f"[{self.service_name}] " if self.service_name else ""
        if self.original:
            return f"{service}Stage '{self.stage}' failed: {self.original}"
        return f"{service}Stage '{self.stage}' failed: {self.message}"


class CircuitBreakerOpenError(OrchestratorError):
    """Circuit breaker está aberto."""

    def __init__(self, service_name: str, message: Optional[str] = None):
        msg = message or f"Circuit breaker is OPEN for service '{service_name}'"
        super().__init__(msg)
        self.service_name = service_name


class JobNotFoundError(OrchestratorError):
    """Job não encontrado."""

    def __init__(self, job_id: str):
        super().__init__(f"Job '{job_id}' not found")
        self.job_id = job_id


class ValidationError(OrchestratorError):
    """Erro de validação."""

    pass


class ServiceUnavailableError(OrchestratorError):
    """Serviço indisponível."""

    def __init__(self, service_name: str, message: Optional[str] = None):
        msg = message or f"Service '{service_name}' is unavailable"
        super().__init__(msg)
        self.service_name = service_name


class DownloadError(PipelineStageError):
    """Erro no download de arquivo."""

    def __init__(self, message: str, original: Optional[Exception] = None):
        super().__init__("download", message, original, "video-downloader")


class NormalizationError(PipelineStageError):
    """Erro na normalização de áudio."""

    def __init__(self, message: str, original: Optional[Exception] = None):
        super().__init__("normalization", message, original, "audio-normalization")


class TranscriptionError(PipelineStageError):
    """Erro na transcrição."""

    def __init__(self, message: str, original: Optional[Exception] = None):
        super().__init__("transcription", message, original, "audio-transcriber")
