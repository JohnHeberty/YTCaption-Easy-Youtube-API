"""
Sistema de tratamento de erros e resiliência para Video Downloader Service
Circuit breakers, retry policies e error handling específicos para download de vídeos
"""
import asyncio
import time
import random
from typing import Any, Callable, Dict, List, Optional, Type, Union
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class DownloadErrorType(str, Enum):
    """Tipos de erro de download"""
    NETWORK_ERROR = "network_error"
    VIDEO_NOT_FOUND = "video_not_found"
    ACCESS_DENIED = "access_denied"
    FORMAT_ERROR = "format_error"
    SIZE_LIMIT_EXCEEDED = "size_limit_exceeded"
    TIMEOUT_ERROR = "timeout_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    USER_AGENT_BLOCKED = "user_agent_blocked"
    REGION_BLOCKED = "region_blocked"
    COPYRIGHT_CLAIM = "copyright_claim"
    PRIVATE_VIDEO = "private_video"
    DELETED_VIDEO = "deleted_video"
    LIVE_STREAM = "live_stream_error"
    EXTRACTION_ERROR = "extraction_error"
    FILESYSTEM_ERROR = "filesystem_error"


# Exceções customizadas para download de vídeos
class VideoDownloadError(Exception):
    """Exceção base para erros de download de vídeo"""
    
    def __init__(
        self, 
        message: str, 
        error_type: DownloadErrorType = DownloadErrorType.NETWORK_ERROR,
        retryable: bool = True,
        user_agent: Optional[str] = None,
        video_id: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.error_type = error_type
        self.retryable = retryable
        self.user_agent = user_agent
        self.video_id = video_id
        self.original_exception = original_exception
        super().__init__(message)
    
    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.message}"


class NetworkError(VideoDownloadError):
    """Erros de rede durante download"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message, 
            error_type=DownloadErrorType.NETWORK_ERROR,
            retryable=True,
            **kwargs
        )


class VideoNotFoundError(VideoDownloadError):
    """Vídeo não encontrado"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.VIDEO_NOT_FOUND,
            retryable=False,
            **kwargs
        )


class AccessDeniedError(VideoDownloadError):
    """Acesso negado ao vídeo"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.ACCESS_DENIED,
            retryable=False,
            **kwargs
        )


class RateLimitError(VideoDownloadError):
    """Rate limit atingido"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.RATE_LIMITED,
            retryable=True,
            **kwargs
        )


class UserAgentBlockedError(VideoDownloadError):
    """User-Agent bloqueado"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.USER_AGENT_BLOCKED,
            retryable=True,
            **kwargs
        )


class SizeLimitError(VideoDownloadError):
    """Arquivo muito grande"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.SIZE_LIMIT_EXCEEDED,
            retryable=False,
            **kwargs
        )


class ExtractionError(VideoDownloadError):
    """Erro na extração de informações do vídeo"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=DownloadErrorType.EXTRACTION_ERROR,
            retryable=True,
            **kwargs
        )


class CircuitBreakerState(str, Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"      # Funcionando normalmente
    OPEN = "open"          # Bloqueando chamadas
    HALF_OPEN = "half_open"  # Testando recuperação


class CircuitBreaker:
    """
    Circuit Breaker para proteger contra falhas em cascata em downloads
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,  # 5 minutos
        expected_exception: Type[Exception] = VideoDownloadError,
        name: str = "download_circuit_breaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # Estado interno
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0
        
        # Estatísticas
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
    def _reset(self):
        """Reset do circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")
    
    def _trip(self):
        """Abre o circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.last_failure_time = time.time()
        logger.warning(
            f"Circuit breaker '{self.name}' tripped to OPEN state "
            f"after {self.failure_count} failures"
        )
    
    def _can_attempt_reset(self) -> bool:
        """Verifica se pode tentar reset"""
        return (
            self.state == CircuitBreakerState.OPEN and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa função com proteção do circuit breaker
        
        Args:
            func: Função para executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
            
        Raises:
            CircuitBreakerOpenError: Se circuit breaker estiver aberto
            Exception: Exceções da função original
        """
        self.total_calls += 1
        
        # Verifica se pode tentar reset
        if self._can_attempt_reset():
            self.state = CircuitBreakerState.HALF_OPEN
            logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
        
        # Se estiver aberto, rejeita chamada
        if self.state == CircuitBreakerState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Next retry in {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
            )
        
        try:
            # Executa função
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Sucesso
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Falha esperada
            self._on_failure()
            raise
        except Exception as e:
            # Falha inesperada - não conta para circuit breaker
            logger.error(f"Unexpected error in circuit breaker '{self.name}': {e}")
            raise
    
    def _on_success(self):
        """Trata sucesso"""
        self.total_successes += 1
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Em half-open, sucesso leva ao reset
            self._reset()
        else:
            # Em closed, reset contador de falhas
            self.failure_count = 0
    
    def _on_failure(self):
        """Trata falha"""
        self.total_failures += 1
        self.failure_count += 1
        
        if self.failure_count >= self.failure_threshold:
            self._trip()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "success_rate": (self.total_successes / self.total_calls * 100) if self.total_calls > 0 else 0,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout
        }


class CircuitBreakerOpenError(Exception):
    """Exceção para circuit breaker aberto"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], tuple] = (VideoDownloadError,)
):
    """
    Decorator para retry com backoff exponencial
    
    Args:
        max_retries: Número máximo de tentativas
        base_delay: Delay inicial em segundos
        backoff_multiplier: Multiplicador do backoff
        max_delay: Delay máximo em segundos
        jitter: Adicionar jitter aleatório
        exceptions: Exceções que devem ser retriadas
    """
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except exceptions as e:
                    last_exception = e
                    
                    # Se não é retryable, falha imediatamente
                    if hasattr(e, 'retryable') and not e.retryable:
                        logger.warning(f"Non-retryable error: {e}")
                        raise
                    
                    # Se é a última tentativa, falha
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                        raise
                    
                    # Calcula delay
                    delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                    
                    # Adiciona jitter se habilitado
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s delay. Error: {e}"
                    )
                    
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    # Exceção não esperada - falha imediatamente
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise
            
            # Nunca deveria chegar aqui
            raise last_exception
        
        @wraps(func) 
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                        
                except exceptions as e:
                    last_exception = e
                    
                    if hasattr(e, 'retryable') and not e.retryable:
                        raise
                    
                    if attempt == max_retries:
                        raise
                    
                    delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                    
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s delay. Error: {e}"
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise
            
            raise last_exception
        
        # Retorna wrapper apropriado baseado no tipo da função
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ErrorHandler:
    """
    Centralizador de tratamento de erros para downloads
    """
    
    def __init__(self):
        self.error_stats = {}
        self.user_agent_errors = {}
    
    def classify_error(self, exception: Exception, context: Dict[str, Any] = None) -> DownloadErrorType:
        """
        Classifica erro baseado na exceção e contexto
        
        Args:
            exception: Exceção capturada
            context: Contexto adicional (URL, user agent, etc.)
            
        Returns:
            Tipo do erro classificado
        """
        error_msg = str(exception).lower()
        
        # Análise baseada na mensagem
        if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
            return DownloadErrorType.NETWORK_ERROR
        
        elif any(keyword in error_msg for keyword in ['not found', '404', 'video unavailable']):
            return DownloadErrorType.VIDEO_NOT_FOUND
        
        elif any(keyword in error_msg for keyword in ['access denied', '403', 'forbidden']):
            return DownloadErrorType.ACCESS_DENIED
        
        elif any(keyword in error_msg for keyword in ['rate limit', '429', 'too many requests']):
            return DownloadErrorType.RATE_LIMITED
        
        elif any(keyword in error_msg for keyword in ['user agent', 'bot detected', 'blocked']):
            return DownloadErrorType.USER_AGENT_BLOCKED
        
        elif any(keyword in error_msg for keyword in ['private', 'restricted']):
            return DownloadErrorType.PRIVATE_VIDEO
        
        elif any(keyword in error_msg for keyword in ['deleted', 'removed']):
            return DownloadErrorType.DELETED_VIDEO
        
        elif any(keyword in error_msg for keyword in ['copyright', 'claim']):
            return DownloadErrorType.COPYRIGHT_CLAIM
        
        elif any(keyword in error_msg for keyword in ['region', 'country', 'geo']):
            return DownloadErrorType.REGION_BLOCKED
        
        elif any(keyword in error_msg for keyword in ['live', 'stream']):
            return DownloadErrorType.LIVE_STREAM
        
        elif any(keyword in error_msg for keyword in ['format', 'codec']):
            return DownloadErrorType.FORMAT_ERROR
        
        elif any(keyword in error_msg for keyword in ['size', 'large', 'limit']):
            return DownloadErrorType.SIZE_LIMIT_EXCEEDED
        
        elif any(keyword in error_msg for keyword in ['quota', 'exceeded']):
            return DownloadErrorType.QUOTA_EXCEEDED
        
        elif any(keyword in error_msg for keyword in ['extract', 'parsing']):
            return DownloadErrorType.EXTRACTION_ERROR
        
        elif any(keyword in error_msg for keyword in ['disk', 'space', 'filesystem']):
            return DownloadErrorType.FILESYSTEM_ERROR
        
        else:
            return DownloadErrorType.NETWORK_ERROR  # Default
    
    def handle_error(
        self, 
        exception: Exception,
        video_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        context: Dict[str, Any] = None
    ) -> VideoDownloadError:
        """
        Trata erro e retorna exceção tipada
        
        Args:
            exception: Exceção original
            video_id: ID do vídeo
            user_agent: User agent usado
            context: Contexto adicional
            
        Returns:
            Exceção de download tipada
        """
        
        # Classifica erro
        error_type = self.classify_error(exception, context)
        
        # Atualiza estatísticas
        self._update_error_stats(error_type, user_agent)
        
        # Determina se é retryable
        retryable_errors = {
            DownloadErrorType.NETWORK_ERROR,
            DownloadErrorType.TIMEOUT_ERROR,
            DownloadErrorType.RATE_LIMITED,
            DownloadErrorType.USER_AGENT_BLOCKED,
            DownloadErrorType.EXTRACTION_ERROR
        }
        
        retryable = error_type in retryable_errors
        
        # Cria exceção específica
        error_classes = {
            DownloadErrorType.VIDEO_NOT_FOUND: VideoNotFoundError,
            DownloadErrorType.ACCESS_DENIED: AccessDeniedError,
            DownloadErrorType.RATE_LIMITED: RateLimitError,
            DownloadErrorType.USER_AGENT_BLOCKED: UserAgentBlockedError,
            DownloadErrorType.SIZE_LIMIT_EXCEEDED: SizeLimitError,
            DownloadErrorType.EXTRACTION_ERROR: ExtractionError,
            DownloadErrorType.NETWORK_ERROR: NetworkError
        }
        
        error_class = error_classes.get(error_type, VideoDownloadError)
        
        return error_class(
            message=str(exception),
            error_type=error_type,
            retryable=retryable,
            user_agent=user_agent,
            video_id=video_id,
            original_exception=exception
        )
    
    def _update_error_stats(self, error_type: DownloadErrorType, user_agent: Optional[str]):
        """Atualiza estatísticas de erro"""
        
        # Estatísticas gerais
        if error_type not in self.error_stats:
            self.error_stats[error_type] = 0
        self.error_stats[error_type] += 1
        
        # Estatísticas por user agent
        if user_agent:
            if user_agent not in self.user_agent_errors:
                self.user_agent_errors[user_agent] = {}
            
            if error_type not in self.user_agent_errors[user_agent]:
                self.user_agent_errors[user_agent][error_type] = 0
            
            self.user_agent_errors[user_agent][error_type] += 1
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de erros"""
        return {
            "error_types": dict(self.error_stats),
            "user_agent_errors": dict(self.user_agent_errors),
            "total_errors": sum(self.error_stats.values())
        }
    
    def get_problematic_user_agents(self, min_errors: int = 5) -> List[str]:
        """
        Retorna user agents com muitos erros
        
        Args:
            min_errors: Mínimo de erros para considerar problemático
            
        Returns:
            Lista de user agents problemáticos
        """
        problematic = []
        
        for user_agent, errors in self.user_agent_errors.items():
            total_errors = sum(errors.values())
            if total_errors >= min_errors:
                problematic.append(user_agent)
        
        return problematic
    
    def reset_user_agent_stats(self, user_agent: str) -> bool:
        """
        Reset estatísticas de um user agent
        
        Args:
            user_agent: User agent para resetar
            
        Returns:
            True se resetado com sucesso
        """
        if user_agent in self.user_agent_errors:
            del self.user_agent_errors[user_agent]
            logger.info(f"Reset error stats for user agent: {user_agent[:50]}...")
            return True
        return False


# Instância global do error handler
error_handler = ErrorHandler()