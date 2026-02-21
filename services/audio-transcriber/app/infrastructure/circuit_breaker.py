"""
Circuit Breaker Pattern for Audio Transcriber Service

Protege serviços externos (HuggingFace model downloads, GPU operations)
de falhas em cascata. Adaptado do padrão make-video.
"""

from typing import Callable, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CircuitBreakerState:
    """Estados do Circuit Breaker"""
    CLOSED = "closed"  # Normal: permite chamadas
    OPEN = "open"  # Aberto: bloqueia chamadas (serviço com problemas)
    HALF_OPEN = "half_open"  # Meio-aberto: testando recuperação


class CircuitBreakerException(Exception):
    """Exceção lançada quando circuit breaker está aberto"""
    pass


class CircuitBreaker:
    """
    Circuit Breaker Pattern para proteger operações de transcrição.
    
    Estados:
    - CLOSED: Normal, permite todas as chamadas
    - OPEN: Serviço com problemas, bloqueia chamadas por timeout
    - HALF_OPEN: Testando recuperação, permite chamadas limitadas
    
    Transições:
    - CLOSED → OPEN: Após failure_threshold falhas consecutivas
    - OPEN → HALF_OPEN: Após timeout segundos
    - HALF_OPEN → CLOSED: Se chamada de teste bem-sucedida
    - HALF_OPEN → OPEN: Se chamada de teste falhar
    
    Use cases para audio-transcriber:
    - Model download failures (HuggingFace)
    - GPU out of memory
    - Audio file corruption
    - Whisper engine crashes
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Args:
            failure_threshold: Número de falhas para abrir circuito
            timeout: Tempo em segundos até tentar recuperação (OPEN → HALF_OPEN)
            half_open_max_calls: Máximo de chamadas em HALF_OPEN antes de fechar
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        # Estado por serviço (ex: "faster_whisper_load", "openai_whisper_transcribe")
        self.failures = {}  # {service: count}
        self.state = {}  # {service: CircuitBreakerState}
        self.last_failure_time = {}  # {service: timestamp}
        self.half_open_calls = {}  # {service: count}
        
        logger.info(
            f"✅ CircuitBreaker initialized "
            f"(threshold={failure_threshold}, timeout={timeout}s)"
        )
    
    def is_open(self, service: str) -> bool:
        """
        Verifica se circuito está aberto para um serviço.
        
        Args:
            service: Nome do serviço (ex: "faster_whisper_load", "whisperx_transcribe")
        
        Returns:
            True se circuito está aberto (bloqueia chamadas)
        """
        current_state = self.state.get(service, CircuitBreakerState.CLOSED)
        
        # Se CLOSED, permite
        if current_state == CircuitBreakerState.CLOSED:
            return False
        
        # Se HALF_OPEN, permite chamadas limitadas
        if current_state == CircuitBreakerState.HALF_OPEN:
            calls = self.half_open_calls.get(service, 0)
            if calls < self.half_open_max_calls:
                self.half_open_calls[service] = calls + 1
                return False
            # Excedeu limite de half-open, bloqueia
            return True
        
        # Se OPEN, verifica se timeout passou
        if current_state == CircuitBreakerState.OPEN:
            last_failure = self.last_failure_time.get(service, 0)
            elapsed = datetime.now().timestamp() - last_failure
            
            if elapsed > self.timeout:
                # Transição OPEN → HALF_OPEN
                logger.info(
                    f"🟡 Circuit breaker HALF_OPEN for {service} "
                    f"(elapsed={elapsed:.1f}s, timeout={self.timeout}s)"
                )
                self.state[service] = CircuitBreakerState.HALF_OPEN
                self.half_open_calls[service] = 1  # Primeira chamada de teste
                return False
            
            # Ainda em timeout, bloqueia
            return True
        
        return False
    
    def record_success(self, service: str):
        """
        Registra sucesso em uma chamada.
        
        Fecha o circuito se estava em HALF_OPEN.
        Reset contadores de falha.
        """
        current_state = self.state.get(service, CircuitBreakerState.CLOSED)
        
        # Reset failures
        self.failures[service] = 0
        
        # Se estava HALF_OPEN, fecha circuito
        if current_state == CircuitBreakerState.HALF_OPEN:
            logger.info(f"🟢 Circuit breaker CLOSED for {service} (recovered)")
            self.state[service] = CircuitBreakerState.CLOSED
            self.half_open_calls[service] = 0
    
    def record_failure(self, service: str):
        """
        Registra falha em uma chamada.
        
        Abre o circuito se atingir failure_threshold.
        """
        current_state = self.state.get(service, CircuitBreakerState.CLOSED)
        
        # Incrementar falhas
        self.failures[service] = self.failures.get(service, 0) + 1
        self.last_failure_time[service] = datetime.now().timestamp()
        
        failure_count = self.failures[service]
        
        # Se em HALF_OPEN e falhou, volta para OPEN
        if current_state == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                f"🔴 Circuit breaker OPEN for {service} "
                f"(failed during recovery test)"
            )
            self.state[service] = CircuitBreakerState.OPEN
            self.half_open_calls[service] = 0
            return
        
        # Se em CLOSED e atingiu threshold, abre circuito
        if current_state == CircuitBreakerState.CLOSED:
            if failure_count >= self.failure_threshold:
                logger.error(
                    f"🔴 Circuit breaker OPEN for {service} "
                    f"(failures={failure_count}, threshold={self.failure_threshold})"
                )
                self.state[service] = CircuitBreakerState.OPEN
    
    def get_state(self, service: str) -> str:
        """Retorna estado atual do circuito para um serviço"""
        return self.state.get(service, CircuitBreakerState.CLOSED)
    
    def get_failures(self, service: str) -> int:
        """Retorna contagem de falhas para um serviço"""
        return self.failures.get(service, 0)
    
    def reset(self, service: str):
        """Reset completo do circuito para um serviço"""
        self.failures.pop(service, None)
        self.state.pop(service, None)
        self.last_failure_time.pop(service, None)
        self.half_open_calls.pop(service, None)
        logger.info(f"🔄 Circuit breaker RESET for {service}")
    
    def call(self, service: str, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Executa função protegida por circuit breaker.
        
        Args:
            service: Nome do serviço
            func: Função a executar
            *args, **kwargs: Argumentos da função
        
        Returns:
            Resultado da função
        
        Raises:
            CircuitBreakerException: Se circuito estiver aberto
        """
        if self.is_open(service):
            raise CircuitBreakerException(
                f"Circuit breaker is OPEN for {service}. "
                f"Service temporarily unavailable."
            )
        
        try:
            result = func(*args, **kwargs)
            self.record_success(service)
            return result
        except Exception as e:
            self.record_failure(service)
            raise


# Singleton global
_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=60,
    half_open_max_calls=3
)


def get_circuit_breaker() -> CircuitBreaker:
    """Retorna instância singleton do CircuitBreaker"""
    return _circuit_breaker
