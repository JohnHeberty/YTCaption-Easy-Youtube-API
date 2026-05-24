"""
Testes de Circuit Breaker Pattern

Valida comportamento do circuit breaker em cenários de falha:
- Abertura após threshold de falhas
- Timeout e transição para HALF_OPEN
- Recuperação e fechamento
- Bloqueio de chamadas quando OPEN

✅ SEM MOCKS - testa comportamento real
"""
import pytest
import time
from pathlib import Path


pytestmark = [pytest.mark.resilience, pytest.mark.circuit_breaker]


class TestCircuitBreakerBehavior:
    """
    Testes focados no comportamento do Circuit Breaker.
    """
    
    def test_circuit_breaker_initialization(self):
        """
        Teste 1: Circuit breaker inicializa corretamente.
        """
        print(f"\n{'='*70}")
        print("🔌 TESTE: Inicialização do Circuit Breaker")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        
        assert cb is not None, "Circuit breaker é None"
        assert hasattr(cb, 'failure_threshold'), "Falta failure_threshold"
        assert hasattr(cb, 'timeout'), "Falta timeout"
        assert hasattr(cb, 'state'), "Falta state dict"
        assert hasattr(cb, 'failures'), "Falta failures dict"
        
        print(f"   ✓ Failure threshold: {cb.failure_threshold}")
        print(f"   ✓ Timeout: {cb.timeout}s")
        print(f"   ✓ Half-open max calls: {cb.half_open_max_calls}")
        print(f"\n   ✅ Circuit breaker inicializado corretamente\n")
    
    def test_circuit_starts_closed(self):
        """
        Teste 2: Circuit breaker começa em estado CLOSED.
        """
        print(f"\n{'='*70}")
        print("🟢 TESTE: Estado Inicial CLOSED")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        test_service = "test_service_initial"
        
        # Serviço novo deve estar CLOSED
        state = cb.state.get(test_service, CircuitBreakerState.CLOSED)
        is_open = cb.is_open(test_service)
        
        print(f"   ✓ Estado: {state}")
        print(f"   ✓ Is open: {is_open}")
        
        assert state == CircuitBreakerState.CLOSED, f"Estado inicial não é CLOSED: {state}"
        assert not is_open, "Circuit está aberto inicialmente"
        
        print(f"\n   ✅ Circuit inicia CLOSED conforme esperado\n")
    
    def test_circuit_opens_after_failures(self):
        """
        Teste 3: Circuit abre após atingir threshold de falhas.
        
        Simula múltiplas falhas e valida:
        - Falhas são contadas corretamente
        - Circuit abre após threshold
        - Chamadas são bloqueadas quando OPEN
        """
        print(f"\n{'='*70}")
        print("🔴 TESTE: Abertura Após Falhas")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        test_service = "test_service_failures"
        
        # Limpa estado anterior
        cb.state[test_service] = CircuitBreakerState.CLOSED
        cb.failures[test_service] = 0
        
        print(f"   Failure threshold: {cb.failure_threshold}")
        print(f"   Simulando falhas...\n")
        
        # Simula falhas até threshold
        for i in range(1, cb.failure_threshold + 1):
            cb.record_failure(test_service)
            failures = cb.failures[test_service]
            state = cb.state.get(test_service, CircuitBreakerState.CLOSED)
            
            print(f"   Falha {i}/{cb.failure_threshold} - Falhas: {failures}, Estado: {state}")
        
        # Valida que abriu
        state = cb.state.get(test_service)
        is_open = cb.is_open(test_service)
        
        print(f"\n   ✓ Estado final: {state}")
        print(f"   ✓ Is open: {is_open}")
        
        assert state == CircuitBreakerState.OPEN, f"Circuit não abriu: {state}"
        assert is_open, "Circuit não está bloqueando chamadas"
        
        print(f"\n   ✅ Circuit ABRIU após {cb.failure_threshold} falhas\n")
    
    def test_circuit_blocks_calls_when_open(self):
        """
        Teste 4: Circuit bloqueia chamadas quando OPEN.
        """
        print(f"\n{'='*70}")
        print("🚫 TESTE: Bloqueio de Chamadas (OPEN)")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState, CircuitBreakerException
        
        cb = get_circuit_breaker()
        test_service = "test_service_block"
        
        # Força estado OPEN
        cb.state[test_service] = CircuitBreakerState.OPEN
        cb.failures[test_service] = cb.failure_threshold
        cb.last_failure_time[test_service] = time.time()
        
        print(f"   ✓ Circuit forçado para OPEN")
        
        # Tenta executar com circuit OPEN
        def dummy_operation():
            return "should not execute"
        
        with pytest.raises(CircuitBreakerException) as exc_info:
            cb.call(test_service, dummy_operation)
        
        print(f"   ✓ CircuitBreakerException lançada")
        print(f"   ✓ Mensagem: {str(exc_info.value)}")
        
        assert "OPEN" in str(exc_info.value), "Mensagem não menciona OPEN"
        assert test_service in str(exc_info.value), "Mensagem não menciona serviço"
        
        print(f"\n   ✅ Circuit bloqueou chamada corretamente\n")
    
    def test_circuit_transitions_to_half_open(self):
        """
        Teste 5: Circuit transiciona para HALF_OPEN após timeout.
        
        Simula:
        - Circuit em estado OPEN
        - Espera timeout
        - Valida transição para HALF_OPEN
        """
        print(f"\n{'='*70}")
        print("🟡 TESTE: Transição OPEN → HALF_OPEN")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        test_service = "test_service_half_open"
        
        # Configura timeout curto para teste (usa o padrão se muito longo)
        original_timeout = cb.timeout
        test_timeout = 2  # 2 segundos para teste rápido
        cb.timeout = test_timeout
        
        # Força estado OPEN com timestamp antigo
        cb.state[test_service] = CircuitBreakerState.OPEN
        cb.failures[test_service] = cb.failure_threshold
        cb.last_failure_time[test_service] = time.time() - (test_timeout + 1)  # Já passou timeout
        
        print(f"   ✓ Circuit configurado: OPEN")
        print(f"   ✓ Timeout configurado: {test_timeout}s")
        print(f"   ✓ Tempo decorrido: > {test_timeout}s\n")
        
        # Verifica se circuit está aberto (deve transicionar para HALF_OPEN)
        is_open = cb.is_open(test_service)
        state = cb.state.get(test_service)
        
        print(f"   ✓ Estado após timeout: {state}")
        print(f"   ✓ Is open: {is_open}")
        
        assert state == CircuitBreakerState.HALF_OPEN, f"Não transicionou para HALF_OPEN: {state}"
        assert not is_open, "Circuit ainda está bloqueando após timeout"
        
        print(f"\n   ✅ Transição OPEN → HALF_OPEN ocorreu\n")
        
        # Restaura timeout original
        cb.timeout = original_timeout
    
    def test_circuit_closes_on_success_from_half_open(self):
        """
        Teste 6: Circuit fecha após sucesso em estado HALF_OPEN.
        """
        print(f"\n{'='*70}")
        print("🟢 TESTE: Recuperação HALF_OPEN → CLOSED")
        print(f"{'='*70}")
        
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        test_service = "test_service_recovery"
        
        # Força estado HALF_OPEN
        cb.state[test_service] = CircuitBreakerState.HALF_OPEN
        cb.failures[test_service] = 3
        cb.half_open_calls[test_service] = 0
        
        print(f"   ✓ Circuit configurado: HALF_OPEN")
        print(f"   ✓ Falhas anteriores: {cb.failures[test_service]}")
        
        # Registra sucesso
        cb.record_success(test_service)
        
        state = cb.state.get(test_service)
        failures = cb.failures[test_service]
        
        print(f"\n   ✓ Estado após sucesso: {state}")
        print(f"   ✓ Falhas resetadas: {failures}")
        
        assert state == CircuitBreakerState.CLOSED, f"Não fechou: {state}"
        assert failures == 0, f"Falhas não foram resetadas: {failures}"
        
        print(f"\n   ✅ Circuit RECUPEROU (CLOSED)\n")
    
    def test_circuit_breaker_with_real_model_loading(self, temp_work_dir):
        """
        Teste 7: Circuit breaker integrado com model loading REAL.
        
        Valida:
        - Circuit breaker funciona em operação real
        - Sucessos são registrados
        - Estado permanece CLOSED após sucesso
        """
        print(f"\n{'='*70}")
        print("🔌 TESTE: Circuit Breaker + Model Loading Real")
        print(f"{'='*70}")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        cb = get_circuit_breaker()
        
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        service_name = f"faster_whisper_load_{manager.model_name}"
        
        # Limpa estado anterior
        if service_name in cb.state:
            cb.state[service_name] = CircuitBreakerState.CLOSED
            cb.failures[service_name] = 0
        
        print(f"   Service: {service_name}")
        print(f"   Carregando modelo...\n")
        
        # Carrega modelo (opera através do circuit breaker)
        manager.load_model()
        
        # Valida circuit breaker
        state = cb.state.get(service_name, CircuitBreakerState.CLOSED)
        failures = cb.failures.get(service_name, 0)
        is_open = cb.is_open(service_name)
        
        print(f"   ✓ Modelo carregado: {manager.is_loaded}")
        print(f"   ✓ Circuit state: {state}")
        print(f"   ✓ Failures: {failures}")
        print(f"   ✓ Is open: {is_open}")
        
        assert manager.is_loaded, "Modelo não carregou"
        assert state == CircuitBreakerState.CLOSED, f"Circuit não está CLOSED: {state}"
        assert failures == 0, f"Falhas registradas: {failures}"
        assert not is_open, "Circuit está aberto após sucesso"
        
        print(f"\n   ✅ Circuit breaker integrado funciona corretamente\n")
        
        # Cleanup
        manager.unload_model()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
