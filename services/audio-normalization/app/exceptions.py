"""
Sistema robusto de exceções e tratamento de erros
"""
import time
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Níveis de severidade de erro"""
    LOW = "low"           # Degradação mínima
    MEDIUM = "medium"     # Funcionalidade afetada
    HIGH = "high"         # Serviço comprometido
    CRITICAL = "critical" # Sistema inoperante


class ErrorCategory(Enum):
    """Categorias de erro para melhor classificação"""
    VALIDATION = "validation"       # Dados inválidos
    RESOURCE = "resource"          # Recursos insuficientes
    EXTERNAL = "external"          # Dependências externas
    PROCESSING = "processing"      # Falhas no processamento
    SECURITY = "security"          # Questões de segurança
    SYSTEM = "system"              # Erros de sistema


class BaseServiceError(Exception):
    """Exceção base para o serviço"""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        details: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.correlation_id = correlation_id
        self.timestamp = time.time()
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa erro para logging estruturado"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "details": self.details,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp
        }


# ===== EXCEÇÕES DE VALIDAÇÃO =====
class ValidationError(BaseServiceError):
    """Erros de validação de entrada"""
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        details = {"field": field, "invalid_value": str(value)} if field else {}
        super().__init__(
            message,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            details=details,
            **kwargs
        )


class FileValidationError(ValidationError):
    """Erros específicos de validação de arquivo"""
    def __init__(self, message: str, filename: str = None, file_size: int = None, **kwargs):
        details = {"filename": filename, "file_size": file_size}
        super().__init__(message, details={**details, **kwargs.get('details', {})}, **kwargs)


class AudioFormatError(ValidationError):
    """Erro de formato de áudio não suportado"""
    def __init__(self, format_name: str, supported_formats: list = None, **kwargs):
        message = f"Formato de áudio não suportado: {format_name}"
        if supported_formats:
            message += f". Formatos suportados: {', '.join(supported_formats)}"
        
        super().__init__(
            message,
            details={"format": format_name, "supported": supported_formats},
            **kwargs
        )


# ===== EXCEÇÕES DE RECURSOS =====
class ResourceError(BaseServiceError):
    """Erros relacionados a recursos do sistema"""
    def __init__(self, message: str, resource_type: str = None, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.RESOURCE,
            details={"resource_type": resource_type},
            **kwargs
        )


class InsufficientResourcesError(ResourceError):
    """Recursos insuficientes (memória, CPU, disco)"""
    def __init__(self, resource_type: str, required: str = None, available: str = None, **kwargs):
        message = f"Recursos insuficientes: {resource_type}"
        details = {
            "resource_type": resource_type,
            "required": required,
            "available": available
        }
        super().__init__(message, details=details, **kwargs)


class FileTooLargeError(ResourceError):
    """Arquivo excede tamanho máximo permitido"""
    def __init__(self, file_size: int, max_size: int, **kwargs):
        message = f"Arquivo muito grande: {file_size}B (máximo: {max_size}B)"
        super().__init__(
            message,
            resource_type="file_size",
            details={"file_size": file_size, "max_size": max_size},
            **kwargs
        )


class ProcessingTimeoutError(ResourceError):
    """Timeout no processamento"""
    def __init__(self, timeout_seconds: int, operation: str = None, **kwargs):
        message = f"Timeout no processamento: {timeout_seconds}s"
        if operation:
            message += f" ({operation})"
        
        super().__init__(
            message,
            resource_type="processing_time",
            details={"timeout_seconds": timeout_seconds, "operation": operation},
            **kwargs
        )


# ===== EXCEÇÕES EXTERNAS =====
class ExternalServiceError(BaseServiceError):
    """Erros de serviços externos"""
    def __init__(self, service_name: str, message: str = None, **kwargs):
        message = message or f"Falha no serviço externo: {service_name}"
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL,
            details={"service_name": service_name},
            **kwargs
        )


class RedisConnectionError(ExternalServiceError):
    """Falha de conexão com Redis"""
    def __init__(self, redis_url: str = None, **kwargs):
        super().__init__(
            "redis",
            "Falha de conexão com Redis",
            details={"redis_url": redis_url},
            **kwargs
        )


class CeleryWorkerError(ExternalServiceError):
    """Falha nos workers Celery"""
    def __init__(self, worker_name: str = None, **kwargs):
        super().__init__(
            "celery",
            "Worker Celery indisponível",
            details={"worker_name": worker_name},
            **kwargs
        )


# ===== EXCEÇÕES DE PROCESSAMENTO =====
class ProcessingError(BaseServiceError):
    """Erros durante processamento de áudio"""
    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PROCESSING,
            details={"operation": operation},
            **kwargs
        )


class AudioProcessingError(ProcessingError):
    """Falha no processamento de áudio"""
    def __init__(self, operation: str, error_details: str = None, **kwargs):
        message = f"Falha no processamento de áudio: {operation}"
        if error_details:
            message += f" - {error_details}"
        
        super().__init__(
            message,
            operation=operation,
            details={"error_details": error_details},
            **kwargs
        )


class JobNotFoundError(ProcessingError):
    """Job não encontrado"""
    def __init__(self, job_id: str, **kwargs):
        super().__init__(
            f"Job não encontrado: {job_id}",
            severity=ErrorSeverity.LOW,
            details={"job_id": job_id},
            **kwargs
        )


class JobExpiredError(ProcessingError):
    """Job expirado"""
    def __init__(self, job_id: str, expired_at: str = None, **kwargs):
        super().__init__(
            f"Job expirado: {job_id}",
            severity=ErrorSeverity.LOW,
            details={"job_id": job_id, "expired_at": expired_at},
            **kwargs
        )


# ===== EXCEÇÕES DE SEGURANÇA =====
class SecurityError(BaseServiceError):
    """Erros relacionados à segurança"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SECURITY,
            **kwargs
        )


class RateLimitExceededError(SecurityError):
    """Rate limit excedido"""
    def __init__(self, client_id: str, limit: int, window: int, **kwargs):
        message = f"Rate limit excedido para {client_id}: {limit}/{window}s"
        super().__init__(
            message,
            details={"client_id": client_id, "limit": limit, "window": window},
            **kwargs
        )


class SuspiciousFileError(SecurityError):
    """Arquivo suspeito detectado"""
    def __init__(self, reason: str, filename: str = None, **kwargs):
        message = f"Arquivo suspeito detectado: {reason}"
        super().__init__(
            message,
            details={"reason": reason, "filename": filename},
            **kwargs
        )


# ===== CIRCUIT BREAKER =====
class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"      # Funcionamento normal
    OPEN = "open"          # Falhas excessivas - rejeita requests
    HALF_OPEN = "half_open"  # Teste de recuperação


class CircuitBreaker:
    """
    Implementação de Circuit Breaker para proteger contra falhas em cascata
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar circuit breaker"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self._call(func, *args, **kwargs)
        return wrapper
    
    def _call(self, func: Callable, *args, **kwargs):
        """Executa função com proteção do circuit breaker"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise ExternalServiceError(
                    "circuit_breaker",
                    "Circuit breaker aberto - serviço indisponível",
                    details={
                        "state": self.state.value,
                        "failure_count": self.failure_count,
                        "last_failure": self.last_failure_time
                    }
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker"""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Callback para sucesso"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """Callback para falha"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


# ===== DECORATORS ÚTEIS =====
def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator para retry automático com backoff exponencial
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    logger.warning(
                        f"Tentativa {attempt + 1}/{max_attempts} falhou: {e}. "
                        f"Tentando novamente em {current_delay}s..."
                    )
                    
                    if asyncio.iscoroutinefunction(func):
                        await asyncio.sleep(current_delay)
                    else:
                        time.sleep(current_delay)
                    
                    current_delay *= backoff
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    logger.warning(
                        f"Tentativa {attempt + 1}/{max_attempts} falhou: {e}. "
                        f"Tentando novamente em {current_delay}s..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


@contextmanager
def error_context(operation: str, **context_data):
    """
    Context manager para capturar e enriquecer erros com contexto
    """
    try:
        yield
    except BaseServiceError as e:
        # Enriquece erro existente com contexto
        e.details.update({"operation": operation, **context_data})
        raise
    except Exception as e:
        # Converte exceção genérica em erro de serviço
        raise ProcessingError(
            f"Erro na operação '{operation}': {str(e)}",
            operation=operation,
            details={"original_error": str(e), **context_data}
        ) from e


def log_errors(func: Callable) -> Callable:
    """
    Decorator para logging automático de erros
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseServiceError as e:
            logger.error(
                f"Erro em {func.__name__}: {e.message}",
                extra={
                    "error_data": e.to_dict(),
                    "function": func.__name__,
                    "args": str(args)[:100],  # Limita tamanho do log
                }
            )
            raise
        except Exception as e:
            logger.exception(
                f"Erro não tratado em {func.__name__}: {str(e)}",
                extra={
                    "function": func.__name__,
                    "args": str(args)[:100],
                }
            )
            raise
    
    return wrapper


# ===== HELPER FUNCTIONS =====
def handle_external_service_error(service_name: str, error: Exception) -> BaseServiceError:
    """
    Converte erros de serviços externos em erros padronizados
    """
    error_mappings = {
        "redis": RedisConnectionError,
        "celery": CeleryWorkerError,
    }
    
    error_class = error_mappings.get(service_name, ExternalServiceError)
    
    return error_class(
        service_name=service_name,
        message=str(error),
        details={"original_error": str(error)}
    )


def create_error_response(error: BaseServiceError) -> Dict[str, Any]:
    """
    Cria resposta HTTP padronizada para erros
    """
    return {
        "error": True,
        "error_code": error.error_code,
        "message": error.message,
        "severity": error.severity.value,
        "correlation_id": error.correlation_id,
        "timestamp": error.timestamp
    }