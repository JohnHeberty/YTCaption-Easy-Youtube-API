"""
Unit tests for Circuit Breaker

Tests circuit breaker states and transitions.
"""

import pytest
import time
import sys
import os

# Adicionar o caminho do app ao sys.path
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

# Import direto do módulo para evitar app/__init__.py
from infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerException
)


def test_circuit_breaker_initial_state():
    """Circuit breaker deve iniciar no estado CLOSED"""
    cb = CircuitBreaker()
    assert cb.get_state("test_service") == CircuitBreakerState.CLOSED
    assert cb.get_failures("test_service") == 0


def test_circuit_breaker_is_closed():
    """Circuit breaker CLOSED deve permitir chamadas"""
    cb = CircuitBreaker(failure_threshold=3)
    assert not cb.is_open("test_service")


def test_circuit_breaker_opens_after_threshold():
    """Circuit breaker deve abrir após threshold de falhas"""
    cb = CircuitBreaker(failure_threshold=3)
    
    # Registra falhas até threshold
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.CLOSED
    
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.CLOSED
    
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN
    assert cb.is_open("test_service")


def test_circuit_breaker_blocks_when_open():
    """Circuit breaker OPEN deve bloquear chamadas"""
    cb = CircuitBreaker(failure_threshold=2)
    
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    
    assert cb.is_open("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN


def test_circuit_breaker_transitions_to_half_open():
    """Circuit breaker deve transicionar OPEN -> HALF_OPEN após timeout"""
    cb = CircuitBreaker(failure_threshold=2, timeout=1)
    
    # Abre circuito
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN
    
    # Aguarda timeout
    time.sleep(1.1)
    
    # Próxima verificação deve transicionar para HALF_OPEN
    assert not cb.is_open("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.HALF_OPEN


def test_circuit_breaker_closes_after_success_in_half_open():
    """Circuit breaker HALF_OPEN deve fechar após sucesso"""
    cb = CircuitBreaker(failure_threshold=2, timeout=1)
    
    # Abre circuito
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    
    # Aguarda timeout e transiciona para HALF_OPEN
    time.sleep(1.1)
    cb.is_open("test_service")
    
    # Sucesso fecha o circuito
    cb.record_success("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.CLOSED


def test_circuit_breaker_reopens_after_failure_in_half_open():
    """Circuit breaker HALF_OPEN deve reabrir após falha"""
    cb = CircuitBreaker(failure_threshold=2, timeout=1, half_open_max_calls=1)
    
    # Abre circuito
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    
    # Aguarda timeout e transiciona para HALF_OPEN
    time.sleep(1.1)
    cb.is_open("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.HALF_OPEN
    
    # Falha reabre o circuito
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN


def test_circuit_breaker_resets_failures_on_success():
    """Circuit breaker deve resetar contadores em sucesso"""
    cb = CircuitBreaker(failure_threshold=3)
    
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    assert cb.get_failures("test_service") == 2
    
    cb.record_success("test_service")
    assert cb.get_failures("test_service") == 0


def test_circuit_breaker_reset():
    """Circuit breaker reset deve limpar todos os estados"""
    cb = CircuitBreaker(failure_threshold=2)
    
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN
    
    cb.reset("test_service")
    assert cb.get_state("test_service") == CircuitBreakerState.CLOSED
    assert cb.get_failures("test_service") == 0


def test_circuit_breaker_call_success():
    """Circuit breaker call() deve executar função e registrar sucesso"""
    cb = CircuitBreaker()
    
    def successful_func():
        return "success"
    
    result = cb.call("test_service", successful_func)
    assert result == "success"
    assert cb.get_failures("test_service") == 0


def test_circuit_breaker_call_failure():
    """Circuit breaker call() deve registrar falha e re-lançar exceção"""
    cb = CircuitBreaker(failure_threshold=2)
    
    def failing_func():
        raise ValueError("test error")
    
    # Primeira falha
    with pytest.raises(ValueError):
        cb.call("test_service", failing_func)
    assert cb.get_failures("test_service") == 1
    
    # Segunda falha (abre circuito)
    with pytest.raises(ValueError):
        cb.call("test_service", failing_func)
    assert cb.get_state("test_service") == CircuitBreakerState.OPEN


def test_circuit_breaker_call_blocked_when_open():
    """Circuit breaker call() deve bloquear quando OPEN"""
    cb = CircuitBreaker(failure_threshold=1)
    
    def failing_func():
        raise ValueError("test error")
    
    # Abre circuito
    with pytest.raises(ValueError):
        cb.call("test_service", failing_func)
    
    # Próxima chamada deve ser bloqueada
    with pytest.raises(CircuitBreakerException):
        cb.call("test_service", lambda: "won't execute")


def test_circuit_breaker_half_open_max_calls():
    """Circuit breaker HALF_OPEN deve limitar número de chamadas"""
    cb = CircuitBreaker(failure_threshold=2, timeout=1, half_open_max_calls=2)
    
    # Abre circuito
    cb.record_failure("test_service")
    cb.record_failure("test_service")
    
    # Aguarda timeout
    time.sleep(1.1)
    
    # 2 chamadas permitidas em HALF_OPEN
    assert not cb.is_open("test_service")
    assert not cb.is_open("test_service")
    
    # 3ª chamada bloqueada
    assert cb.is_open("test_service")


def test_circuit_breaker_multiple_services():
    """Circuit breaker deve manter estados independentes por serviço"""
    cb = CircuitBreaker(failure_threshold=2)
    
    # Service A falha
    cb.record_failure("service_a")
    cb.record_failure("service_a")
    
    # Service B não falha
    cb.record_success("service_b")
    
    assert cb.get_state("service_a") == CircuitBreakerState.OPEN
    assert cb.get_state("service_b") == CircuitBreakerState.CLOSED

