"""
Exceções específicas do orquestrador.

Hierarquia única de exceções — todas herdam de OrchestratorError
para permitir captura genérica quando necessário.
"""
from typing import Optional


class OrchestratorError(Exception):
    """Base para todas as exceções do orquestrador.

    Attributes:
        message: Mensagem de erro
        error_code: Código de erro para identificação
        details: Dicionário com detalhes adicionais
    """

    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "ORCHESTRATOR_ERROR"
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ValidationError(OrchestratorError):
    """Erro de validação de dados de entrada."""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class JobCreationError(OrchestratorError):
    """Erro ao criar job."""

    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(message, "JOB_CREATION_ERROR")


class RedisConnectionError(OrchestratorError):
    """Erro de conexão com Redis."""

    def __init__(self, message: str, redis_url: str = None):
        self.redis_url = redis_url
        super().__init__(message, "REDIS_CONNECTION_ERROR")


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
        super().__init__(msg, "CIRCUIT_BREAKER_OPEN")
        self.service_name = service_name
