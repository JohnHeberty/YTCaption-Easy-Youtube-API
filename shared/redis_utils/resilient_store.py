from __future__ import annotations

"""
Resilient Redis store with connection pooling and circuit breaker
"""
import inspect
import socket
import logging
import time
from typing import Any
from datetime import datetime
from redis import Redis
from redis.connection import ConnectionPool

from common.datetime_utils import now_brazil

logger = logging.getLogger(__name__)


class RedisCircuitBreaker:
    """
    Circuit breaker pattern para operações Redis.
    
    Estados:
    - CLOSED: Normal operation
    - OPEN: Falhas detectadas, reject calls
    - HALF_OPEN: Testing recovery
    """
    
    def __init__(
        self,
        max_failures: int = 5,
        timeout_seconds: int = 60,
        half_open_max_requests: int = 3,
    ) -> None:
        self.max_failures = max_failures
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests
        
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.half_open_attempts = 0
    
    def is_open(self) -> bool:
        """Verifica se circuit está aberto"""
        if self.state == "CLOSED":
            return False
        
        if self.state == "OPEN":
            # Verifica se passou tempo de recovery
            if self.last_failure_time:
                elapsed = (now_brazil() - self.last_failure_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    logger.info(f"Circuit breaker transitioning OPEN → HALF_OPEN")
                    self.state = "HALF_OPEN"
                    self.half_open_attempts = 0
                    return False
            return True
        
        # HALF_OPEN state
        if self.half_open_attempts >= self.half_open_max_requests:
            logger.warning(f"Circuit breaker HALF_OPEN limit reached, reopening")
            self.state = "OPEN"
            self.last_failure_time = now_brazil()
            return True
        
        return False
    
    def record_success(self) -> None:
        """Registra sucesso - fecha circuit completamente"""
        previous_state = self.state
        if previous_state != "CLOSED":
            logger.info(f"Circuit breaker {previous_state} → CLOSED - recovered")
        
        self.state = "CLOSED"
        self.failure_count = 0
        self.half_open_attempts = 0
        self.last_failure_time = None
    
    def record_failure(self) -> None:
        """Registra falha - pode abrir circuit"""
        self.last_failure_time = now_brazil()
        
        if self.state == "HALF_OPEN":
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_max_requests:
                self.state = "OPEN"
                logger.error(f"Circuit breaker HALF_OPEN → OPEN - recovery failed")
            return
        
        if self.state == "CLOSED":
            self.failure_count += 1
            logger.warning(f"Circuit breaker failure {self.failure_count}/{self.max_failures}")
            
            if self.failure_count >= self.max_failures:
                self.state = "OPEN"
                logger.error(
                    f"Circuit breaker CLOSED → OPEN after {self.failure_count} failures"
                )
    
    def call(self, func, *args, **kwargs) -> Any:
        """Executa função com circuit breaker (sync)."""
        if self.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is {self.state} - Redis unavailable"
            )
        
        if self.state == "HALF_OPEN":
            self.half_open_attempts += 1
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    async def acall(self, func, *args, **kwargs) -> Any:
        """Executa função async com circuit breaker."""
        if self.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is {self.state} - Redis unavailable"
            )
        
        if self.state == "HALF_OPEN":
            self.half_open_attempts += 1
        
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


class CircuitBreakerOpenError(Exception):
    """Exceção quando circuit breaker está aberto"""
    pass


class ResilientRedisStore:
    """
    Redis store resiliente com:
    - Connection pooling
    - Circuit breaker
    - Retry automático
    - Graceful degradation
    - Dependency injection (accepts external Redis client)
    """
    
    def __init__(
        self,
        redis_url: str = "",
        max_connections: int = 50,
        socket_keepalive: bool = True,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 10,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
        circuit_breaker_enabled: bool = True,
        circuit_breaker_max_failures: int = 5,
        circuit_breaker_timeout: int = 60,
        redis_client: Any = None,
    ) -> None:
        """
        Inicializa Redis store resiliente.
        
        Args:
            redis_url: URL de conexão Redis
            max_connections: Máximo de conexões no pool
            socket_keepalive: Habilita TCP keepalive
            socket_connect_timeout: Timeout de conexão (segundos)
            socket_timeout: Timeout de operações (segundos)
            retry_on_timeout: Retry automático em timeout
            health_check_interval: Intervalo de health check (segundos)
            circuit_breaker_enabled: Habilita circuit breaker
            circuit_breaker_max_failures: Falhas para abrir circuit
            circuit_breaker_timeout: Tempo de recovery do circuit (segundos)
        """
        self.redis_url = redis_url
        
        if redis_client is not None:
            # DI: caller provides the Redis client (useful for testing)
            self.redis = redis_client
            self.pool = getattr(redis_client, 'connection_pool', None)
        else:
            # Configura connection pool
            keepalive_options = {}
            if socket_keepalive:
                keepalive_options = {
                    socket.TCP_KEEPIDLE: 60,
                    socket.TCP_KEEPINTVL: 10,
                    socket.TCP_KEEPCNT: 3
                }
            
            self.pool = ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
                socket_keepalive=socket_keepalive,
                socket_keepalive_options=keepalive_options,
                retry_on_timeout=retry_on_timeout,
                health_check_interval=health_check_interval,
                decode_responses=True
            )
            
            self.redis = Redis(connection_pool=self.pool)
        
        # Circuit breaker
        self.circuit_breaker = None
        if circuit_breaker_enabled:
            self.circuit_breaker = RedisCircuitBreaker(
                max_failures=circuit_breaker_max_failures,
                timeout_seconds=circuit_breaker_timeout
            )
        
        # Testa conexão inicial
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Testa conexão inicial com retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.redis.ping()
                logger.info(f"✅ Redis connected: {self.redis_url}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"⚠️ Redis connection attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to connect to Redis after {max_retries} attempts")
                    raise
    
    def _execute_with_circuit_breaker(self, func, *args, **kwargs) -> Any:
        """Executa operação com circuit breaker se habilitado"""
        if self.circuit_breaker:
            return self.circuit_breaker.call(func, *args, **kwargs)
        else:
            return func(*args, **kwargs)

    def _safe_call(self, operation: str, func: Any, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        """Execute a Redis operation with circuit breaker and error handling.

        Args:
            operation: Name for logging (e.g., "GET", "SET").
            func: The Redis method to call.
            *args: Positional args for the method.
            default: Value to return on error.
            **kwargs: Keyword args for the method.

        Returns:
            Result of the operation, or *default* on error.
        """
        try:
            return self._execute_with_circuit_breaker(func, *args, **kwargs)
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open, skipping %s", operation)
            return default
        except Exception as e:
            logger.error("Redis %s failed: %s", operation, e)
            return default
    
    def ping(self) -> bool:
        """
        Verifica se Redis está acessível.

        Returns:
            True se conectado, False caso contrário
        """
        return self._safe_call("PING", self.redis.ping, default=False)

    def get(self, key: str) -> str | None:
        """
        Obtém valor do Redis.

        Args:
            key: Chave

        Returns:
            Valor ou None se não encontrado/erro
        """
        return self._safe_call(f"GET {key}", self.redis.get, key)

    def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Define valor no Redis.

        Args:
            key: Chave
            value: Valor
            ex: Expiration em segundos
            px: Expiration em milissegundos
            nx: Set only if not exists
            xx: Set only if exists

        Returns:
            True se sucesso, False caso contrário
        """
        result = self._safe_call(
            f"SET {key}",
            self.redis.set,
            key,
            value,
            ex=ex,
            px=px,
            nx=nx,
            xx=xx,
            default=False,
        )
        return bool(result)

    def setex(self, key: str, time: int, value: str) -> bool:
        """
        Define valor com expiração.

        Args:
            key: Chave
            time: TTL em segundos
            value: Valor

        Returns:
            True se sucesso, False caso contrário
        """
        result = self._safe_call(
            f"SETEX {key}", self.redis.setex, key, time, value, default=False
        )
        return bool(result)

    def delete(self, *keys: str) -> int:
        """
        Deleta chaves.

        Args:
            keys: Chaves para deletar

        Returns:
            Número de chaves deletadas
        """
        return self._safe_call(f"DELETE {keys}", self.redis.delete, *keys, default=0)

    def exists(self, *keys: str) -> int:
        """
        Verifica existência de chaves.

        Args:
            keys: Chaves para verificar

        Returns:
            Número de chaves que existem
        """
        return self._safe_call(f"EXISTS {keys}", self.redis.exists, *keys, default=0)

    def keys(self, pattern: str = "*") -> list[str]:
        """
        Lista chaves por pattern.

        Args:
            pattern: Pattern de busca

        Returns:
            Lista de chaves
        """
        return self._safe_call(f"KEYS {pattern}", self.redis.keys, pattern, default=[])
    
    def close(self) -> None:
        """Fecha conexões do pool"""
        try:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}")
