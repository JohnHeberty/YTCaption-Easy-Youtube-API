"""
Sistema de exceções customizadas e circuit breaker para Audio Transcriber
Implementação de padrões de resiliência para tratamento de erros
"""
import asyncio
import time
from typing import Optional, Dict, Any, Type, Callable
from enum import Enum
from functools import wraps

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class ErrorSeverity(str, Enum):
    """Níveis de severidade de erro"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categorias de erro"""
    VALIDATION = "validation"
    TRANSCRIPTION = "transcription"
    RESOURCE = "resource"
    NETWORK = "network"
    SECURITY = "security"
    CONFIGURATION = "configuration"


class BaseTranscriberError(Exception):
    """Classe base para erros do transcriber"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.TRANSCRIPTION,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.timestamp = time.time()


class ValidationError(BaseTranscriberError):
    """Erros de validação de entrada"""
    
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )


class TranscriptionError(BaseTranscriberError):
    """Erros específicos de transcrição"""
    
    def __init__(self, message: str, error_code: str = "TRANSCRIPTION_ERROR", **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.TRANSCRIPTION,
            **kwargs
        )


class ModelLoadError(TranscriptionError):
    """Erro ao carregar modelo Whisper"""
    
    def __init__(self, model_name: str, **kwargs):
        super().__init__(
            message=f"Failed to load Whisper model: {model_name}",
            error_code="MODEL_LOAD_ERROR",
            severity=ErrorSeverity.CRITICAL,
            context={"model_name": model_name},
            **kwargs
        )


class AudioProcessingError(TranscriptionError):
    """Erro no processamento de áudio"""
    
    def __init__(self, message: str, file_path: str = None, **kwargs):
        context = {"file_path": file_path} if file_path else {}
        super().__init__(
            message=message,
            error_code="AUDIO_PROCESSING_ERROR",
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs
        )


class ResourceError(BaseTranscriberError):
    """Erros relacionados a recursos (memória, CPU, disco)"""
    
    def __init__(self, message: str, error_code: str = "RESOURCE_ERROR", **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.RESOURCE,
            **kwargs
        )


class SecurityError(BaseTranscriberError):
    """Erros de segurança"""
    
    def __init__(self, message: str, error_code: str = "SECURITY_ERROR", **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.SECURITY,
            **kwargs
        )


class NetworkError(BaseTranscriberError):
    """Erros de rede/conectividade"""
    
    def __init__(self, message: str, error_code: str = "NETWORK_ERROR", **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            **kwargs
        )


class CircuitBreakerState(str, Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker pattern para prevenção de falhas em cascata
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.expected_exception = expected_exception
        
        # State
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitBreakerState.CLOSED
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise NetworkError(
                        "Circuit breaker is OPEN - service unavailable",
                        error_code="CIRCUIT_BREAKER_OPEN"
                    )
            
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _on_success(self):
        """Chamado quando operação é bem-sucedida"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """Chamado quando operação falha"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitBreakerState.HALF_OPEN


# Circuit breakers pré-configurados
whisper_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    reset_timeout=30.0,
    expected_exception=TranscriptionError
)

redis_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    reset_timeout=60.0,
    expected_exception=NetworkError
)

file_processing_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    reset_timeout=45.0,
    expected_exception=AudioProcessingError
)


# Decorators de retry
def retry_transcription(max_attempts: int = 3):
    """Retry decorator para operações de transcrição"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((TranscriptionError, AudioProcessingError)),
        reraise=True
    )


def retry_network(max_attempts: int = 3):
    """Retry decorator para operações de rede"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type(NetworkError),
        reraise=True
    )


def retry_resource(max_attempts: int = 2):
    """Retry decorator para operações que podem falhar por recursos"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=5, max=15),
        retry=retry_if_exception_type(ResourceError),
        reraise=True
    )


class ErrorHandler:
    """Manipulador centralizado de erros"""
    
    @staticmethod
    def handle_whisper_error(exception: Exception, model_name: str = None) -> BaseTranscriberError:
        """Converte exceções do Whisper em erros tipados"""
        if "CUDA" in str(exception) or "GPU" in str(exception):
            return ResourceError(
                f"GPU/CUDA error in Whisper: {exception}",
                error_code="WHISPER_GPU_ERROR",
                context={"model_name": model_name}
            )
        
        if "memory" in str(exception).lower():
            return ResourceError(
                f"Memory error in Whisper: {exception}",
                error_code="WHISPER_MEMORY_ERROR",
                context={"model_name": model_name}
            )
        
        if "model" in str(exception).lower():
            return ModelLoadError(model_name or "unknown")
        
        return TranscriptionError(
            f"Whisper transcription failed: {exception}",
            error_code="WHISPER_GENERAL_ERROR",
            context={"model_name": model_name}
        )
    
    @staticmethod
    def handle_file_error(exception: Exception, file_path: str = None) -> BaseTranscriberError:
        """Converte exceções de arquivo em erros tipados"""
        if isinstance(exception, FileNotFoundError):
            return ValidationError(
                f"Audio file not found: {file_path}",
                error_code="FILE_NOT_FOUND",
                context={"file_path": file_path}
            )
        
        if isinstance(exception, PermissionError):
            return ResourceError(
                f"Permission denied accessing file: {file_path}",
                error_code="FILE_PERMISSION_ERROR",
                context={"file_path": file_path}
            )
        
        if "codec" in str(exception).lower() or "format" in str(exception).lower():
            return AudioProcessingError(
                f"Unsupported audio format: {exception}",
                file_path=file_path
            )
        
        return AudioProcessingError(
            f"Audio file processing failed: {exception}",
            file_path=file_path
        )
    
    @staticmethod
    def handle_redis_error(exception: Exception) -> BaseTranscriberError:
        """Converte exceções do Redis em erros tipados"""
        if "Connection" in str(exception) or "timeout" in str(exception).lower():
            return NetworkError(
                f"Redis connection failed: {exception}",
                error_code="REDIS_CONNECTION_ERROR"
            )
        
        if "memory" in str(exception).lower() or "OOM" in str(exception):
            return ResourceError(
                f"Redis memory error: {exception}",
                error_code="REDIS_MEMORY_ERROR"
            )
        
        return NetworkError(
            f"Redis operation failed: {exception}",
            error_code="REDIS_GENERAL_ERROR"
        )


# Context manager para captura e conversão de exceções
class ErrorCapture:
    """Context manager para captura automática de erros"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False  # No exception
        
        # Se já é um erro customizado, não converte
        if isinstance(exc_val, BaseTranscriberError):
            return False
        
        # Converte exceção genérica em erro tipado
        if "whisper" in self.operation_name.lower():
            converted_error = ErrorHandler.handle_whisper_error(exc_val)
        elif "file" in self.operation_name.lower() or "audio" in self.operation_name.lower():
            converted_error = ErrorHandler.handle_file_error(exc_val)
        elif "redis" in self.operation_name.lower():
            converted_error = ErrorHandler.handle_redis_error(exc_val)
        else:
            converted_error = BaseTranscriberError(
                f"Operation '{self.operation_name}' failed: {exc_val}",
                error_code="GENERAL_ERROR",
                severity=ErrorSeverity.MEDIUM
            )
        
        # Re-raise como erro convertido
        raise converted_error from exc_val