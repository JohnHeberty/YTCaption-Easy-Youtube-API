"""
Circuit Breaker Pattern - Protege sistema de falhas em cascata.

Implementa o padrão Circuit Breaker para proteger a aplicação de 
falhas repetidas em serviços externos (YouTube API, etc).

Estados:
- CLOSED: Normal, todas chamadas passam
- OPEN: Bloqueado, rejeita chamadas sem tentar
- HALF_OPEN: Testando recuperação, permite chamadas limitadas

v2.2: Implementação inicial.
"""
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
from collections import deque
import threading
from loguru import logger

from src.domain.exceptions import ServiceUnavailableError


class CircuitState(Enum):
    """Estados do Circuit Breaker."""
    CLOSED = "closed"        # Operação normal
    OPEN = "open"            # Bloqueado (muitas falhas)
    HALF_OPEN = "half_open"  # Testando recuperação


class CircuitBreakerOpenError(ServiceUnavailableError):
    """Exceção lançada quando circuit breaker está OPEN."""
    
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            service_name,
            f"Circuit breaker OPEN. Service unavailable. Retry after {retry_after:.0f}s"
        )


class CircuitBreaker:
    """
    Circuit Breaker para proteger serviços externos.
    
    Monitora falhas e automaticamente bloqueia chamadas quando
    um serviço está falhando consistentemente.
    
    Example:
        ```python
        breaker = CircuitBreaker(
            name="youtube_api",
            failure_threshold=5,
            timeout_seconds=60
        )
        
        @breaker.call
        async def download_video(url):
            return await youtube_downloader.download(url)
        ```
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        window_size: int = 10
    ):
        """
        Inicializa Circuit Breaker.
        
        Args:
            name: Nome do serviço protegido
            failure_threshold: Número de falhas consecutivas para abrir circuito
            timeout_seconds: Tempo em OPEN antes de tentar HALF_OPEN
            half_open_max_calls: Máximo de chamadas em HALF_OPEN
            success_threshold: Sucessos necessários em HALF_OPEN para fechar
            window_size: Tamanho da janela de monitoramento
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.window_size = window_size
        
        # Estado
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        # Janela deslizante de resultados
        self.call_history: deque = deque(maxlen=window_size)
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Estatísticas
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.state_changes = 0
        
        logger.info(
            f"Circuit Breaker initialized: {name}",
            extra={
                "failure_threshold": failure_threshold,
                "timeout_seconds": timeout_seconds,
                "half_open_max_calls": half_open_max_calls
            }
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa função protegida por circuit breaker.
        
        Args:
            func: Função a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
            
        Raises:
            CircuitBreakerOpenError: Se circuito estiver OPEN
            Exception: Exceções da função original
        """
        with self.lock:
            self.total_calls += 1
            
            # Estado OPEN: Bloquear chamadas
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    retry_after = self._time_until_retry()
                    logger.warning(
                        f"Circuit breaker OPEN: {self.name}",
                        extra={
                            "retry_after": retry_after,
                            "failure_count": self.failure_count,
                            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
                        }
                    )
                    raise CircuitBreakerOpenError(self.name, retry_after)
            
            # Estado HALF_OPEN: Limitar chamadas
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    logger.warning(
                        f"Circuit breaker HALF_OPEN limit reached: {self.name}",
                        extra={
                            "half_open_calls": self.half_open_calls,
                            "max_calls": self.half_open_max_calls
                        }
                    )
                    raise CircuitBreakerOpenError(self.name, self.timeout.total_seconds())
                
                self.half_open_calls += 1
        
        # Executar função
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar reset (OPEN → HALF_OPEN)."""
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure >= self.timeout
    
    def _time_until_retry(self) -> float:
        """Calcula tempo restante até próxima tentativa."""
        if not self.last_failure_time:
            return 0.0
        
        elapsed = datetime.now() - self.last_failure_time
        remaining = self.timeout - elapsed
        return max(0.0, remaining.total_seconds())
    
    def _on_success(self):
        """Callback de sucesso."""
        with self.lock:
            self.total_successes += 1
            self.call_history.append(True)
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                logger.debug(
                    f"Circuit breaker HALF_OPEN success: {self.name}",
                    extra={
                        "success_count": self.success_count,
                        "threshold": self.success_threshold
                    }
                )
                
                # Sucessos suficientes → Fechar circuito
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            
            elif self.state == CircuitState.CLOSED:
                # Reset failure count em caso de sucesso
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit breaker: resetting failure count after success: {self.name}",
                        extra={"previous_failure_count": self.failure_count}
                    )
                    self.failure_count = 0
    
    def _on_failure(self, exception: Exception):
        """Callback de falha."""
        with self.lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            self.call_history.append(False)
            
            logger.warning(
                f"Circuit breaker failure: {self.name}",
                extra={
                    "failure_count": self.failure_count,
                    "threshold": self.failure_threshold,
                    "state": self.state.value,
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception)[:200]
                }
            )
            
            # Estado HALF_OPEN: Falha → Abrir novamente
            if self.state == CircuitState.HALF_OPEN:
                logger.error(
                    f"Circuit breaker: HALF_OPEN → OPEN (failure during test): {self.name}"
                )
                self._transition_to_open()
            
            # Estado CLOSED: Muitas falhas → Abrir
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()
    
    def _transition_to_open(self):
        """Transição para estado OPEN."""
        self.state = CircuitState.OPEN
        self.state_changes += 1
        self.half_open_calls = 0
        self.success_count = 0
        
        logger.error(
            f"⚠️  Circuit breaker OPENED: {self.name}",
            extra={
                "failure_count": self.failure_count,
                "timeout_seconds": self.timeout.total_seconds(),
                "state_changes": self.state_changes
            }
        )
    
    def _transition_to_half_open(self):
        """Transição para estado HALF_OPEN."""
        self.state = CircuitState.HALF_OPEN
        self.state_changes += 1
        self.half_open_calls = 0
        self.success_count = 0
        
        logger.info(
            f"🔄 Circuit breaker: OPEN → HALF_OPEN (testing recovery): {self.name}",
            extra={
                "max_test_calls": self.half_open_max_calls,
                "success_threshold": self.success_threshold
            }
        )
    
    def _transition_to_closed(self):
        """Transição para estado CLOSED."""
        self.state = CircuitState.CLOSED
        self.state_changes += 1
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        
        logger.info(
            f"✅ Circuit breaker CLOSED: {self.name} (service recovered)",
            extra={
                "state_changes": self.state_changes
            }
        )
    
    def reset(self):
        """Reset manual do circuit breaker."""
        with self.lock:
            logger.info(f"Circuit breaker manually reset: {self.name}")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            self.last_failure_time = None
            self.call_history.clear()
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do circuit breaker.
        
        Returns:
            Dict com estatísticas
        """
        with self.lock:
            # Calcular taxa de falha da janela
            if len(self.call_history) > 0:
                failures_in_window = sum(1 for result in self.call_history if not result)
                failure_rate = (failures_in_window / len(self.call_history)) * 100
            else:
                failure_rate = 0.0
            
            return {
                "name": self.name,
                "state": self.state.value,
                "total_calls": self.total_calls,
                "total_successes": self.total_successes,
                "total_failures": self.total_failures,
                "current_failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
                "state_changes": self.state_changes,
                "window_size": len(self.call_history),
                "failure_rate_percent": round(failure_rate, 2),
                "half_open_calls": self.half_open_calls if self.state == CircuitState.HALF_OPEN else 0
            }
