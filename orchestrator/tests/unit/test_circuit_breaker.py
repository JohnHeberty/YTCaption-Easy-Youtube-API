"""
Testes unitários para Circuit Breaker.
"""
import asyncio
from datetime import datetime, timedelta

import pytest

from infrastructure.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError
from common.datetime_utils import now_brazil


class TestCircuitBreaker:
    """Testes para CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_starts_closed(self):
        """Circuit breaker deve iniciar em estado CLOSED."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.get_state() == "closed"

    @pytest.mark.asyncio
    async def test_allows_calls_when_closed(self):
        """Deve permitir calls quando CLOSED."""
        cb = CircuitBreaker()

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        """Deve abrir após threshold de falhas."""
        cb = CircuitBreaker(failure_threshold=3)

        async def failure_func():
            raise ValueError("test error")

        # 3 falhas consecutivas
        for _ in range(3):
            try:
                await cb.call(failure_func)
            except ValueError:
                pass

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self):
        """Deve rejeitar calls quando OPEN."""
        cb = CircuitBreaker(failure_threshold=1)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = now_brazil()

        async def success_func():
            return "success"

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(success_func)

    @pytest.mark.asyncio
    async def test_closes_on_success(self):
        """Deve fechar após sucesso."""
        cb = CircuitBreaker(failure_threshold=5)
        cb._state = CircuitState.OPEN

        async def success_func():
            return "success"

        # Força transição para HALF_OPEN via timeout
        cb._last_failure_time = now_brazil() - timedelta(seconds=100)

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_resets_failure_count_on_success(self):
        """Deve resetar contador de falhas após sucesso."""
        cb = CircuitBreaker(failure_threshold=5)
        cb._failure_count = 2

        async def success_func():
            return "success"

        await cb.call(success_func)
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_transitions(self):
        """Deve transicionar para HALF_OPEN após timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

        async def failure_func():
            raise ValueError("error")

        # Abre circuito
        try:
            await cb.call(failure_func)
        except ValueError:
            pass

        assert cb.state == CircuitState.OPEN

        # Aguarda timeout
        await asyncio.sleep(1.1)

        # Deve estar em HALF_OPEN (permitindo call)
        async def success_func():
            return "success"

        # Força last_failure_time para passar _should_attempt_reset
        cb._last_failure_time = now_brazil() - timedelta(seconds=2)

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_propagates_exception(self):
        """Deve propagar exceções da função chamada."""
        cb = CircuitBreaker()

        async def failure_func():
            raise RuntimeError("custom error")

        with pytest.raises(RuntimeError, match="custom error"):
            await cb.call(failure_func)

    @pytest.mark.asyncio
    async def test_name_in_error(self):
        """Erro deve conter nome do circuit breaker."""
        cb = CircuitBreaker(name="test-service", failure_threshold=1)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = now_brazil()

        async def success_func():
            return "success"

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call(success_func)
        assert "test-service" in str(exc_info.value)

    def test_manual_reset(self):
        """Reset manual deve funcionar."""
        cb = CircuitBreaker(failure_threshold=1)
        cb._state = CircuitState.OPEN
        cb._failure_count = 5

        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
