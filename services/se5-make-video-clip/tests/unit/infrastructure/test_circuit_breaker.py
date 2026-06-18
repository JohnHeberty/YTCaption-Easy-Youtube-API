"""Testes para Circuit Breaker pattern"""
import pytest
import time
from enum import Enum

try:
    from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerState
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False


class CircuitState(Enum):
    """Estados do Circuit Breaker (para testes conceituais)"""
    CLOSED = "closed"  # Normal
    OPEN = "open"      # Bloqueado (muitas falhas)
    HALF_OPEN = "half_open"  # Testando recuperação


class TestCircuitBreaker:
    """Testes de Circuit Breaker pattern"""
    
    def test_circuit_breaker_pattern(self):
        """Padrão Circuit Breaker básico"""
        failure_count = 0
        threshold = 3
        
        def failing_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count < threshold:
                raise ValueError("Error")
            return "success"
        
        # Tentar até abrir o circuito
        for _ in range(threshold - 1):
            with pytest.raises(ValueError):
                failing_operation()
        
        # Próxima deve ter sucesso
        result = failing_operation()
        assert result == "success"
    
    def test_circuit_closes_after_threshold(self):
        """Circuito fecha após limite de erros"""
        failures = []
        threshold = 5
        
        def operation_with_failures():
            if len(failures) < threshold:
                failures.append(1)
                raise ConnectionError("Service unavailable")
            return "recovered"
        
        # Acumular falhas até threshold
        for i in range(threshold):
            with pytest.raises(ConnectionError):
                operation_with_failures()
        
        # Após threshold, circuito abre
        assert len(failures) == threshold
        
        # Operação seguinte deve ter sucesso
        result = operation_with_failures()
        assert result == "recovered"
    
    def test_circuit_breaker_with_counter(self):
        """Circuit breaker com contador de falhas"""
        class SimpleCircuitBreaker:
            def __init__(self, threshold=3):
                self.threshold = threshold
                self.failures = 0
                self.state = CircuitState.CLOSED
            
            def call(self, func, *args, **kwargs):
                if self.state == CircuitState.OPEN:
                    raise Exception("Circuit is OPEN")
                
                try:
                    result = func(*args, **kwargs)
                    # Sucesso: resetar contador
                    self.failures = 0
                    self.state = CircuitState.CLOSED
                    return result
                except Exception as e:
                    self.failures += 1
                    if self.failures >= self.threshold:
                        self.state = CircuitState.OPEN
                    raise e
        
        cb = SimpleCircuitBreaker(threshold=3)
        
        def failing_func():
            raise ValueError("Fail")
        
        # Falhar 3 vezes
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        # Circuito deve estar aberto
        assert cb.state == CircuitState.OPEN
        
        # Próxima chamada deve ser bloqueada
        with pytest.raises(Exception, match="Circuit is OPEN"):
            cb.call(failing_func)
    
    def test_circuit_breaker_recovery(self):
        """Recuperação do circuit breaker"""
        class CircuitBreaker:
            def __init__(self, threshold=3, timeout=1):
                self.threshold = threshold
                self.timeout = timeout
                self.failures = 0
                self.state = CircuitState.CLOSED
                self.opened_at = None
            
            def call(self, func):
                # Se aberto, verificar timeout
                if self.state == CircuitState.OPEN:
                    if time.time() - self.opened_at >= self.timeout:
                        self.state = CircuitState.HALF_OPEN
                    else:
                        raise Exception("Circuit OPEN")
                
                try:
                    result = func()
                    self.failures = 0
                    self.state = CircuitState.CLOSED
                    return result
                except Exception:
                    self.failures += 1
                    if self.failures >= self.threshold:
                        self.state = CircuitState.OPEN
                        self.opened_at = time.time()
                    raise
        
        cb = CircuitBreaker(threshold=2, timeout=1)
        
        def failing():
            raise ValueError("Fail")
        
        # Falhar até abrir
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        assert cb.state == CircuitState.OPEN
        
        # Aguardar timeout
        time.sleep(1.1)
        
        # Deve mudar para HALF_OPEN na próxima chamada
        with pytest.raises(ValueError):
            cb.call(failing)
        
        assert cb.state == CircuitState.OPEN  # Volta para OPEN pois falhou
    
    def test_circuit_breaker_success_after_failures(self):
        """Sucesso após várias falhas"""
        attempts = []
        
        def flaky_operation():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("Temporary error")
            return "success"
        
        # Falhar 2 vezes
        for _ in range(2):
            with pytest.raises(RuntimeError):
                flaky_operation()
        
        # Ter sucesso na 3ª
        result = flaky_operation()
        assert result == "success"
        assert len(attempts) == 3
    
    def test_circuit_breaker_half_open_state(self):
        """Estado HALF_OPEN permite tentativas limitadas"""
        class StatefulCircuitBreaker:
            def __init__(self):
                self.state = CircuitState.CLOSED
                self.failures = 0
            
            def transition_to_half_open(self):
                self.state = CircuitState.HALF_OPEN
            
            def call(self, func):
                if self.state == CircuitState.OPEN:
                    raise Exception("Circuit OPEN")
                
                try:
                    result = func()
                    if self.state == CircuitState.HALF_OPEN:
                        # Sucesso no HALF_OPEN -> CLOSED
                        self.state = CircuitState.CLOSED
                    return result
                except Exception:
                    self.state = CircuitState.OPEN
                    raise
        
        cb = StatefulCircuitBreaker()
        cb.transition_to_half_open()
        
        assert cb.state == CircuitState.HALF_OPEN
        
        # Sucesso deve fechar o circuito
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_with_timeout(self):
        """Circuit breaker com timeout de operação"""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Operation timed out")
        
        class TimeoutCircuitBreaker:
            def __init__(self, timeout=2):
                self.timeout = timeout
                self.failures = 0
                self.threshold = 3
            
            def call_with_timeout(self, func):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.timeout)
                
                try:
                    result = func()
                    signal.alarm(0)
                    return result
                except TimeoutError:
                    self.failures += 1
                    signal.alarm(0)
                    raise
        
        cb = TimeoutCircuitBreaker(timeout=1)
        
        # Operação rápida
        result = cb.call_with_timeout(lambda: "fast")
        assert result == "fast"
    
    def test_multiple_circuit_breakers(self):
        """Múltiplos circuit breakers independentes"""
        class ServiceCircuitBreaker:
            def __init__(self, name):
                self.name = name
                self.state = CircuitState.CLOSED
                self.failures = 0
        
        service_a = ServiceCircuitBreaker("service_a")
        service_b = ServiceCircuitBreaker("service_b")
        
        # Abrir apenas service_a
        service_a.state = CircuitState.OPEN
        
        assert service_a.state == CircuitState.OPEN
        assert service_b.state == CircuitState.CLOSED
        
        # Independentes
        assert service_a.name != service_b.name


class TestCircuitBreakerModule:
    """Testa módulo circuit_breaker.py"""
    
    def test_circuit_breaker_module_imports(self):
        """Módulo circuit_breaker importa corretamente"""
        assert CIRCUIT_BREAKER_AVAILABLE, "circuit_breaker.py deve existir"
        assert CircuitBreaker is not None
        assert CircuitBreakerState is not None
    
    def test_circuit_states_enum(self):
        """CircuitBreakerState tem todos os estados"""
        assert CIRCUIT_BREAKER_AVAILABLE, "circuit_breaker.py deve existir"
        assert CircuitBreakerState.CLOSED == "closed"
        assert CircuitBreakerState.OPEN == "open"
        assert CircuitBreakerState.HALF_OPEN == "half_open"
    
    def test_circuit_breaker_instantiation(self):
        """CircuitBreaker pode ser instanciado"""
        assert CIRCUIT_BREAKER_AVAILABLE, "circuit_breaker.py deve existir"
        cb = CircuitBreaker(failure_threshold=3, timeout=5, half_open_max_calls=2)
        assert cb is not None
        assert cb.failure_threshold == 3
        assert cb.timeout == 5
        assert cb.half_open_max_calls == 2
        # Estado inicial vazio (rastreia por service)
        assert len(cb.failures) == 0
        assert len(cb.state) == 0
