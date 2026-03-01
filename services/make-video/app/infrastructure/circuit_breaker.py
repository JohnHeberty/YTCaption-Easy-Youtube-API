"""
Intelligent Retry & Circuit Breaker - Sprint-04

Sistema de retry exponencial com circuit breaker para proteger serviços externos.
"""

from typing import Callable, Any, Optional
from datetime import datetime
import asyncio
import logging
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

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
    Circuit Breaker Pattern para proteger serviços externos.
    
    Estados:
    - CLOSED: Normal, permite todas as chamadas
    - OPEN: Serviço com problemas, bloqueia chamadas por timeout
    - HALF_OPEN: Testando recuperação, permite chamadas limitadas
    
    Transições:
    - CLOSED → OPEN: Após failure_threshold falhas consecutivas
    - OPEN → HALF_OPEN: Após timeout segundos
    - HALF_OPEN → CLOSED: Se chamada de teste bem-sucedida
    - HALF_OPEN → OPEN: Se chamada de teste falhar
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
        
        # Estado por serviço
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
            service: Nome do serviço
        
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
            elapsed = now_brazil().timestamp() - last_failure
            
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
        self.last_failure_time[service] = now_brazil().timestamp()
        
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


# Singleton global
_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=60,
    half_open_max_calls=3
)


def get_circuit_breaker() -> CircuitBreaker:
    """Retorna instância singleton do CircuitBreaker"""
    return _circuit_breaker


def with_retry_and_circuit_breaker(
    service_name: str,
    max_attempts: int = 5,
    min_wait: int = 2,
    max_wait: int = 60,
    exception_types: tuple = (Exception,)
):
    """
    Decorador que adiciona retry exponencial + circuit breaker.
    
    Args:
        service_name: Nome do serviço (para circuit breaker)
        max_attempts: Máximo de tentativas
        min_wait: Tempo mínimo de espera entre tentativas (segundos)
        max_wait: Tempo máximo de espera entre tentativas (segundos)
        exception_types: Tupla de exceções que devem causar retry
    
    Backoff exponencial: 2s, 4s, 8s, 16s, 32s, 60s (max)
    
    Usage:
        @with_retry_and_circuit_breaker("video-downloader")
        async def download_video(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exception_types),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        async def wrapper(*args, **kwargs) -> Any:
            # Verificar circuit breaker
            circuit_breaker = get_circuit_breaker()
            
            if circuit_breaker.is_open(service_name):
                error_msg = f"Circuit breaker OPEN for {service_name}"
                logger.error(f"🔴 {error_msg}")
                raise CircuitBreakerException(error_msg)
            
            try:
                # Executar função
                result = await func(*args, **kwargs)
                
                # Registrar sucesso
                circuit_breaker.record_success(service_name)
                
                return result
            
            except Exception as e:
                # Registrar falha
                circuit_breaker.record_failure(service_name)
                
                # Re-lançar exceção para retry do tenacity
                raise
        
        return wrapper
    return decorator


async def call_with_protection(
    service_name: str,
    api_call_func: Callable,
    *args,
    max_attempts: int = 5,
    **kwargs
) -> Any:
    """
    Chama API com retry exponencial e circuit breaker (versão funcional).
    
    Args:
        service_name: Nome do serviço
        api_call_func: Função async a ser chamada
        *args: Argumentos posicionais para api_call_func
        max_attempts: Máximo de tentativas
        **kwargs: Argumentos nomeados para api_call_func
    
    Returns:
        Resultado da chamada
    
    Raises:
        CircuitBreakerException: Se circuito está aberto
        Exception: Última exceção após esgotar tentativas
    
    Usage:
        result = await call_with_protection(
            "video-downloader",
            api_client.download_video,
            video_id="abc123"
        )
    """
    circuit_breaker = get_circuit_breaker()
    
    for attempt in range(1, max_attempts + 1):
        # Verificar circuit breaker
        if circuit_breaker.is_open(service_name):
            error_msg = f"Circuit breaker OPEN for {service_name}"
            logger.error(f"🔴 {error_msg}")
            raise CircuitBreakerException(error_msg)
        
        try:
            # Executar chamada
            result = await api_call_func(*args, **kwargs)
            
            # Sucesso: registrar e retornar
            circuit_breaker.record_success(service_name)
            return result
        
        except Exception as e:
            # Registrar falha
            circuit_breaker.record_failure(service_name)
            
            # Se é a última tentativa, re-lançar
            if attempt == max_attempts:
                logger.error(
                    f"❌ Failed after {max_attempts} attempts: {service_name}"
                )
                raise
            
            # Calcular backoff exponencial
            wait_time = min(2 ** attempt, 60)  # 2s, 4s, 8s, 16s, 32s, 60s (max)
            
            logger.warning(
                f"⚠️  Attempt {attempt}/{max_attempts} failed for {service_name}. "
                f"Retrying in {wait_time}s... Error: {str(e)}"
            )
            
            await asyncio.sleep(wait_time)
    
    # Nunca deve chegar aqui, mas por garantia
    raise Exception(f"Failed after {max_attempts} attempts: {service_name}")
