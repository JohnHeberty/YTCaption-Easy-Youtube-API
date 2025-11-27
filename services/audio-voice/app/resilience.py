"""
Utilitários de resiliência: retry, circuit breaker, timeouts
"""
import asyncio
import functools
import logging
from typing import Callable, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker pattern para evitar cascade failures
    
    Estados:
    - CLOSED: Normal, permite requests
    - OPEN: Muitas falhas, bloqueia requests
    - HALF_OPEN: Testa se serviço recuperou
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executa função com circuit breaker"""
        
        # Se OPEN, verifica se passou timeout
        if self.state == "OPEN":
            if self.last_failure_time and datetime.now() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker HALF_OPEN (testing recovery)")
            else:
                raise Exception("Circuit breaker OPEN (too many failures)")
        
        try:
            result = func(*args, **kwargs)
            
            # Sucesso: reseta contador
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                logger.info("Circuit breaker CLOSED (service recovered)")
            
            self.failure_count = 0
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error("Circuit breaker OPEN (failures: %d)", self.failure_count)
            
            raise


def retry_async(
    max_attempts: int = 3,
    delay_seconds: int = 5,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator para retry automático de funções async
    
    Args:
        max_attempts: Máximo de tentativas
        delay_seconds: Delay inicial entre tentativas
        backoff_multiplier: Multiplicador para exponential backoff
        exceptions: Tupla de exceções que devem causar retry
    
    Example:
        @retry_async(max_attempts=3, delay_seconds=5)
        async def generate_audio(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = delay_seconds
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error("%s failed after %d attempts: %s", 
                                   func.__name__, max_attempts, e)
                        raise
                    
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %ds...",
                        func.__name__, attempt, max_attempts, e, delay
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_multiplier
        
        return wrapper
    return decorator


async def with_timeout(coro, timeout_seconds: int):
    """
    Executa corrotina com timeout
    
    Args:
        coro: Corrotina async
        timeout_seconds: Timeout em segundos
    
    Raises:
        asyncio.TimeoutError: Se timeout excedido
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error("Operation timed out after %ds", timeout_seconds)
        raise
