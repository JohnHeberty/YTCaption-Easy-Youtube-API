"""
Implementação do Circuit Breaker pattern.

Protege contra falhas em cascata quando serviços estão instáveis.

O Circuit Breaker monitora chamadas a serviços externos e,
após um número configurado de falhas consecutivas,
"abre o circuito" impedindo novas chamadas por um período,
protegendo o sistema contra sobrecarga.

Example:
    >>> from infrastructure.circuit_breaker import CircuitBreaker
    >>> cb = CircuitBreaker(
    ...     failure_threshold=5,
    ...     recovery_timeout=60,
    ...     name="my_service"
    ... )
    >>> try:
    ...     result = await cb.call(my_async_function, arg1, arg2)
    ... except CircuitBreakerOpenError:
    ...     print("Service unavailable - circuit breaker is open")
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from common.log_utils import get_logger
from common.datetime_utils import now_brazil
from domain.interfaces import CircuitBreakerInterface
from infrastructure.exceptions import CircuitBreakerOpenError

logger = get_logger(__name__)


class CircuitState(Enum):
    """Estados possíveis do circuit breaker.
    
    Attributes:
        CLOSED: Operação normal - todas as requisições passam
        OPEN: Circuito aberto - requisições bloqueadas
        HALF_OPEN: Período de teste - permite requisições limitadas
    """

    CLOSED = "closed"  # Normal - permite requests
    OPEN = "open"  # Falhas detectadas - bloqueia requests
    HALF_OPEN = "half_open"  # Testando se serviço recuperou


class CircuitBreaker(CircuitBreakerInterface):
    """Circuit Breaker para proteção contra falhas em cascata.
    
    Implementa o padrão Circuit Breaker que monitora falhas em 
    chamadas a serviços externos e bloqueia temporariamente novas
    chamadas quando detecta instabilidade.
    
    Estados:
        - CLOSED: Funcionamento normal, requests passam
        - OPEN: Muitas falhas, requests bloqueados
        - HALF_OPEN: Período de teste após timeout
    
    Attributes:
        failure_threshold: Número de falhas consecutivas para abrir circuito
        recovery_timeout: Tempo em segundos até tentar reabrir
        half_open_max_calls: Máximo de calls permitidas em estado HALF_OPEN
        name: Identificador do circuit breaker para logging
        state: Estado atual do circuit breaker
    
    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        >>> try:
        ...     result = await cb.call(some_async_function, arg1, arg2)
        ... except CircuitBreakerOpenError:
        ...     print("Service unavailable")
        ... except Exception as e:
        ...     print(f"Function failed: {e}")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        name: str = "default",
    ):
        """Inicializa Circuit Breaker.

        Args:
            failure_threshold: Falhas consecutivas para abrir circuito
            recovery_timeout: Segundos até tentar reabrir
            half_open_max_calls: Máximo de calls em estado HALF_OPEN
            name: Nome identificador para logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self._failure_count: int = 0
        self._last_failure_time: Optional[datetime] = None
        self._state: CircuitState = CircuitState.CLOSED
        self._half_open_calls: int = 0

    @property
    def state(self) -> CircuitState:
        """Retorna estado atual.
        
        Returns:
            CircuitState atual (CLOSED, OPEN, ou HALF_OPEN)
        """
        return self._state

    def get_state(self) -> str:
        """Retorna estado como string.
        
        Returns:
            String representando o estado atual ('closed', 'open', ou 'half_open')
        """
        return self._state.value

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Executa função com proteção do circuit breaker.

        Executa a função assíncrona fornecida, aplicando as regras
de estado do circuit breaker. Se o circuito estiver OPEN,
lança CircuitBreakerOpenError imediatamente. Se estiver HALF_OPEN,
permite execução limitada para testar se o serviço recuperou.

        Args:
            func: Função assíncrona a ser executada
            *args: Argumentos posicionais para a função
            **kwargs: Argumentos nomeados para a função

        Returns:
            Resultado da função executada

        Raises:
            CircuitBreakerOpenError: Se circuito estiver aberto
            Exception: Qualquer exceção lançada pela função
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"[{self.name}] Circuit breaker OPEN → HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar reabrir após timeout.
        
        Compara o tempo desde a última falha com o recovery_timeout
        configurado para determinar se deve transicionar para HALF_OPEN.
        
        Returns:
            True se deve tentar reset, False caso contrário
        """
        if not self._last_failure_time:
            return True
        elapsed = now_brazil() - self._last_failure_time
        return elapsed > timedelta(seconds=self.recovery_timeout)

    def _on_success(self) -> None:
        """Registra sucesso - fecha circuito.
        
        Transiciona o estado para CLOSED, reseta contadores de falha
        e registra no log se houve mudança de estado.
        """
        previous = self._state
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0
        self._last_failure_time = None
        if previous != CircuitState.CLOSED:
            logger.info(f"[{self.name}] Circuit breaker {previous.value} → CLOSED")

    def _on_failure(self) -> None:
        """Registra falha - pode abrir circuito.
        
        Incrementa contador de falhas. Se em estado HALF_OPEN,
verifica se atingiu o limite de tentativas. Se em CLOSED,
verifica se atingiu o threshold de falhas.
        """
        self._failure_count += 1
        self._last_failure_time = now_brazil()

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                logger.warning(
                    f"[{self.name}] Circuit breaker HALF_OPEN → OPEN "
                    f"({self._half_open_calls} failed attempts)"
                )
                self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            logger.critical(
                f"[{self.name}] Circuit breaker CLOSED → OPEN "
                f"({self._failure_count} failures)"
            )
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Força reset manual para estado CLOSED.
        
        Útil para testes ou recuperação manual após incidente.
        Reseta todos os contadores e muda estado para CLOSED.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        logger.info(f"[{self.name}] Circuit breaker manually reset to CLOSED")
