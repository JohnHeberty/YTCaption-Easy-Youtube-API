"""
Resilient Redis store with connection pooling and circuit breaker
"""
import socket
import logging
from typing import Optional, Any
from datetime import datetime, timedelta
from redis import Redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

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
        half_open_max_requests: int = 3
    ):
        self.max_failures = max_failures
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.half_open_attempts = 0
    
    def is_open(self) -> bool:
        """Verifica se circuit está aberto"""
        if self.state == "CLOSED":
            return False
        
        if self.state == "OPEN":
            # Verifica se passou tempo de recovery
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
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
            self.last_failure_time = datetime.now()
            return True
        
        return False
    
    def record_success(self):
        """Registra sucesso - fecha circuit completamente"""
        previous_state = self.state
        if previous_state != "CLOSED":
            logger.info(f"Circuit breaker {previous_state} → CLOSED - recovered")
        
        self.state = "CLOSED"
        self.failure_count = 0
        self.half_open_attempts = 0
        self.last_failure_time = None
    
    def record_failure(self):
        """Registra falha - pode abrir circuit"""
        self.last_failure_time = datetime.now()
        
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
        """
        Executa função com circuit breaker.
        
        Raises:
            CircuitBreakerOpenError: Se circuit está aberto
        """
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
    """
    
    def __init__(
        self,
        redis_url: str,
        max_connections: int = 50,
        socket_keepalive: bool = True,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 10,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
        circuit_breaker_enabled: bool = True,
        circuit_breaker_max_failures: int = 5,
        circuit_breaker_timeout: int = 60
    ):
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
    
    def _test_connection(self):
        """Testa conexão inicial com retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.redis.ping()
                logger.info(f"✅ Redis connected: {self.redis_url}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
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
    
    def ping(self) -> bool:
        """
        Verifica se Redis está acessível.
        
        Returns:
            True se conectado, False caso contrário
        """
        try:
            return self._execute_with_circuit_breaker(self.redis.ping)
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """
        Obtém valor do Redis.
        
        Args:
            key: Chave
        
        Returns:
            Valor ou None se não encontrado/erro
        """
        try:
            return self._execute_with_circuit_breaker(self.redis.get, key)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping GET {key}")
            return None
        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
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
        try:
            result = self._execute_with_circuit_breaker(
                self.redis.set,
                key,
                value,
                ex=ex,
                px=px,
                nx=nx,
                xx=xx
            )
            return bool(result)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping SET {key}")
            return False
        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            return False
    
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
        try:
            result = self._execute_with_circuit_breaker(
                self.redis.setex,
                key,
                time,
                value
            )
            return bool(result)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping SETEX {key}")
            return False
        except Exception as e:
            logger.error(f"Redis SETEX failed for key {key}: {e}")
            return False
    
    def delete(self, *keys: str) -> int:
        """
        Deleta chaves.
        
        Args:
            keys: Chaves para deletar
        
        Returns:
            Número de chaves deletadas
        """
        try:
            return self._execute_with_circuit_breaker(self.redis.delete, *keys)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping DELETE {keys}")
            return 0
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    def exists(self, *keys: str) -> int:
        """
        Verifica existência de chaves.
        
        Args:
            keys: Chaves para verificar
        
        Returns:
            Número de chaves que existem
        """
        try:
            return self._execute_with_circuit_breaker(self.redis.exists, *keys)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping EXISTS {keys}")
            return 0
        except Exception as e:
            logger.error(f"Redis EXISTS failed for keys {keys}: {e}")
            return 0
    
    def keys(self, pattern: str = "*") -> list:
        """
        Lista chaves por pattern.
        
        Args:
            pattern: Pattern de busca
        
        Returns:
            Lista de chaves
        """
        try:
            return self._execute_with_circuit_breaker(self.redis.keys, pattern)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker open, skipping KEYS {pattern}")
            return []
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern {pattern}: {e}")
            return []
    
    def close(self):
        """Fecha conexões do pool"""
        try:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}")
