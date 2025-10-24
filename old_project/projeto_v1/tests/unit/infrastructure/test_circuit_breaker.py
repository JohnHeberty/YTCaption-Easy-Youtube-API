"""
Testes unitários para CircuitBreaker.

CRÍTICO: Estes testes vão validar se acall() funciona corretamente
com funções assíncronas e identificar o bug do TypeError.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from src.infrastructure.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


class TestCircuitBreakerSync:
    """Testes para método call() síncrono (backward compatibility)."""
    
    def test_call_sync_function_success(self):
        """call() deve executar função síncrona com sucesso."""
        cb = CircuitBreaker(name="test_sync", failure_threshold=3, timeout_seconds=1)
        
        def sync_func(x, y):
            return x + y
        
        result = cb.call(sync_func, 2, 3)
        assert result == 5
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_call_sync_function_with_exception(self):
        """call() deve registrar falha quando função síncrona lança exceção."""
        cb = CircuitBreaker(name="test_sync_fail", failure_threshold=2, timeout_seconds=1)
        
        def failing_func():
            raise ValueError("Test error")
        
        # Primeira falha
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
        
        # Segunda falha - deve abrir o circuit breaker
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.failure_count == 2
        assert cb.state == CircuitState.OPEN
    
    def test_call_sync_circuit_breaker_open(self):
        """call() deve lançar CircuitBreakerOpenError quando aberto."""
        cb = CircuitBreaker(name="test_open", failure_threshold=1, timeout_seconds=60)
        
        def failing_func():
            raise ValueError("Error")
        
        # Causar falha para abrir circuit breaker
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Tentar chamar novamente deve lançar CircuitBreakerOpenError
        def another_func():
            return "success"
        
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(another_func)


class TestCircuitBreakerAsync:
    """Testes para método acall() assíncrono (CRÍTICO para encontrar o bug!)."""
    
    @pytest.mark.asyncio
    async def test_acall_async_function_success(self):
        """acall() deve executar função assíncrona com sucesso."""
        cb = CircuitBreaker(name="test_async", failure_threshold=3, timeout_seconds=1)
        
        async def async_func(x, y):
            await asyncio.sleep(0.01)
            return x * y
        
        result = await cb.acall(async_func, 3, 4)
        assert result == 12
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_acall_async_function_with_kwargs(self):
        """acall() deve passar kwargs corretamente."""
        cb = CircuitBreaker(name="test_kwargs", failure_threshold=3, timeout_seconds=1)
        
        async def async_func(name, age=None, city=None):
            await asyncio.sleep(0.01)
            return f"{name}, {age}, {city}"
        
        result = await cb.acall(async_func, "John", age=30, city="NY")
        assert result == "John, 30, NY"
    
    @pytest.mark.asyncio
    async def test_acall_async_function_with_exception(self):
        """acall() deve registrar falha quando função async lança exceção."""
        cb = CircuitBreaker(name="test_async_fail", failure_threshold=2, timeout_seconds=1)
        
        async def failing_async():
            await asyncio.sleep(0.01)
            raise ConnectionError("Network error")
        
        # Primeira falha
        with pytest.raises(ConnectionError):
            await cb.acall(failing_async)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
        
        # Segunda falha - deve abrir circuit breaker
        with pytest.raises(ConnectionError):
            await cb.acall(failing_async)
        
        assert cb.failure_count == 2
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_acall_circuit_breaker_open(self):
        """acall() deve lançar CircuitBreakerOpenError quando aberto."""
        cb = CircuitBreaker(name="test_async_open", failure_threshold=1, timeout_seconds=60)
        
        async def failing_func():
            raise ValueError("Error")
        
        # Causar falha para abrir circuit breaker
        with pytest.raises(ValueError):
            await cb.acall(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Tentar chamar novamente deve lançar CircuitBreakerOpenError
        async def another_func():
            return "success"
        
        with pytest.raises(CircuitBreakerOpenError):
            await cb.acall(another_func)
    
    @pytest.mark.asyncio
    async def test_acall_with_none_return(self):
        """
        TESTE CRÍTICO: acall() deve lidar corretamente com funções que retornam None.
        
        Este é o caso que pode estar causando o bug!
        Se a função retorna None, acall() deve retornar None (não tentar await None).
        """
        cb = CircuitBreaker(name="test_none_return", failure_threshold=3, timeout_seconds=1)
        
        async def async_func_returns_none():
            await asyncio.sleep(0.01)
            return None
        
        # Este teste vai FALHAR se acall() tentar fazer await em None!
        result = await cb.acall(async_func_returns_none)
        assert result is None
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_acall_multiple_concurrent_calls(self):
        """acall() deve suportar múltiplas chamadas concorrentes."""
        cb = CircuitBreaker(name="test_concurrent", failure_threshold=5, timeout_seconds=1)
        
        async def async_task(task_id):
            await asyncio.sleep(0.05)
            return f"Task {task_id} done"
        
        # Executar 3 tarefas concorrentemente
        results = await asyncio.gather(
            cb.acall(async_task, 1),
            cb.acall(async_task, 2),
            cb.acall(async_task, 3)
        )
        
        assert len(results) == 3
        assert "Task 1 done" in results
        assert "Task 2 done" in results
        assert "Task 3 done" in results
    
    @pytest.mark.asyncio
    async def test_acall_half_open_recovery(self):
        """acall() deve permitir recuperação quando circuit breaker passa para half-open."""
        cb = CircuitBreaker(name="test_recovery", failure_threshold=2, timeout_seconds=0.1)
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            
            # Falha nas primeiras 2 chamadas
            if call_count <= 2:
                raise ConnectionError("Temporary failure")
            
            # Sucesso na terceira chamada
            return "success"
        
        # Causar 2 falhas para abrir circuit breaker
        with pytest.raises(ConnectionError):
            await cb.acall(flaky_func)
        
        with pytest.raises(ConnectionError):
            await cb.acall(flaky_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Aguardar timeout para passar para half-open
        await asyncio.sleep(0.15)
        
        # Próxima chamada deve tentar novamente (half-open)
        result = await cb.acall(flaky_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerEdgeCases:
    """Testes de casos extremos e situações especiais."""
    
    @pytest.mark.asyncio
    async def test_acall_with_async_generator(self):
        """acall() não deve ser usado com async generators (deve falhar graciosamente)."""
        cb = CircuitBreaker(name="test_generator", failure_threshold=3, timeout_seconds=1)
        
        async def async_generator():
            for i in range(3):
                yield i
        
        # Este teste documenta comportamento esperado
        # (async generators não são suportados, mas não devem causar TypeError)
        result = await cb.acall(async_generator)
        assert result is not None  # Retorna o generator object
    
    @pytest.mark.asyncio
    async def test_acall_preserves_exception_type(self):
        """acall() deve preservar o tipo original da exceção."""
        cb = CircuitBreaker(name="test_exception_type", failure_threshold=5, timeout_seconds=1)
        
        class CustomError(Exception):
            pass
        
        async def raises_custom_error():
            raise CustomError("Custom message")
        
        with pytest.raises(CustomError) as exc_info:
            await cb.acall(raises_custom_error)
        
        assert str(exc_info.value) == "Custom message"
    
    def test_circuit_breaker_metrics(self):
        """Circuit breaker deve expor métricas corretas."""
        cb = CircuitBreaker(name="test_metrics", failure_threshold=3, timeout_seconds=1)
        
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_threshold == 3
        assert cb.timeout == 1
        
        # Após falha
        def failing():
            raise ValueError()
        
        with pytest.raises(ValueError):
            cb.call(failing)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED  # Ainda fechado (threshold é 3)


class TestCircuitBreakerIntegration:
    """Testes de integração simulando uso real com YouTube downloader."""
    
    @pytest.mark.asyncio
    async def test_youtube_downloader_pattern(self):
        """
        TESTE CRÍTICO: Simula exatamente o padrão usado em YouTubeDownloader.
        
        Este teste reproduz:
        await _youtube_circuit_breaker.acall(self._download_internal, url, ...)
        """
        youtube_cb = CircuitBreaker(
            name="youtube_api",
            failure_threshold=5,
            timeout_seconds=300
        )
        
        # Simula _download_internal
        async def _download_internal(url, output_path, validate=True, max_duration=None):
            await asyncio.sleep(0.01)  # Simula download
            return {"video_id": url, "path": output_path, "duration": 120}
        
        # Simula chamada do YouTubeDownloader.download()
        result = await youtube_cb.acall(
            _download_internal,
            "test_video_id",
            "/tmp/output.mp4",
            validate=True,
            max_duration=600
        )
        
        assert result["video_id"] == "test_video_id"
        assert result["path"] == "/tmp/output.mp4"
        assert youtube_cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_rate_limiter_with_circuit_breaker(self):
        """Testa integração entre rate limiter e circuit breaker."""
        cb = CircuitBreaker(name="test_rate_limit", failure_threshold=3, timeout_seconds=1)
        
        call_times = []
        
        async def rate_limited_func():
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)  # Simula rate limiting
            return "success"
        
        # Executar 3 chamadas
        results = []
        for _ in range(3):
            result = await cb.acall(rate_limited_func)
            results.append(result)
        
        assert len(results) == 3
        assert all(r == "success" for r in results)
        
        # Verificar que houve delay entre chamadas
        if len(call_times) >= 2:
            time_diff = call_times[1] - call_times[0]
            assert time_diff >= 0.05  # Pelo menos 50ms de delay
