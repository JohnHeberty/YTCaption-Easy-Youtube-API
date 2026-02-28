"""
Testes de Handling de Arquivos Corrompidos

Valida comportamento do sistema ao receber:
- Arquivos corrompidos
- Arquivos vazios  
- Arquivos com formato inválido
- Arquivos que não são áudio

✅ SEM MOCKS - usa arquivos reais corrompidos
✅ Valida error handling apropriado
✅ Garante que sistema não trava
"""
import pytest
from pathlib import Path


pytestmark = [pytest.mark.resilience, pytest.mark.error_handling]


class TestCorruptedFileshHandling:
    """
    Testes para validar tratamento de arquivos inválidos/corrompidos.
    """
    
    def test_corrupted_file_raises_appropriate_exception(self, corrupted_audio_file, temp_work_dir):
        """
        Teste 1: Arquivo corrompido gera exceção apropriada.
        
        Sistema deve:
        - Detectar arquivo inválido
        - Lançar exceção específica
        - NÃO travar ou causar crash
        - Registrar erro no log
        """
        print(f"\n{'='*70}")
        print("💥 TESTE: Handling de Arquivo Corrompido")
        print(f"{'='*70}")
        print(f"   Arquivo: {corrupted_audio_file.name}")
        print(f"   Tamanho: {corrupted_audio_file.stat().st_size} bytes\n")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.exceptions import AudioTranscriptionException
        
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        print(f"   ✓ Modelo carregado")
        print(f"   Tentando transcrever arquivo corrompido...\n")
        
        # Deve lançar exceção (não travar!)
        with pytest.raises((AudioTranscriptionException, RuntimeError, OSError)) as exc_info:
            manager.transcribe(corrupted_audio_file, language="auto")
        
        print(f"   ✓ Exceção capturada: {type(exc_info.value).__name__}")
        print(f"   ✓ Mensagem: {str(exc_info.value)[:100]}...")
        
        # Valida que sistema continua funcionando após erro
        status = manager.get_status()
        assert status["loaded"] is True, "Modelo foi descarregado após erro"
        
        print(f"\n   ✅ Sistema tratou arquivo corrompido corretamente")
        print(f"   ✅ Modelo permanece carregado e funcional\n")
        
        # Cleanup
        manager.unload_model()
    
    def test_empty_file_handling(self, empty_audio_file, temp_work_dir):
        """
        Teste 2: Arquivo vazio é tratado apropriadamente.
        """
        print(f"\n{'='*70}")
        print("📭 TESTE: Handling de Arquivo Vazio")
        print(f"{'='*70}")
        print(f"   Arquivo: {empty_audio_file.name}")
        print(f"   Tamanho: {empty_audio_file.stat().st_size} bytes\n")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.exceptions import AudioTranscriptionException
        
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        print(f"   ✓ Modelo carregado")
        print(f"   Tentando transcrever arquivo vazio...\n")
        
        # Deve lançar exceção
        with pytest.raises((AudioTranscriptionException, RuntimeError, OSError, ValueError)) as exc_info:
            manager.transcribe(empty_audio_file, language="auto")
        
        print(f"   ✓ Exceção capturada: {type(exc_info.value).__name__}")
        print(f"   ✓ Sistema não travou\n")
        
        print(f"   ✅ Arquivo vazio tratado corretamente\n")
        
        # Cleanup
        manager.unload_model()
    
    def test_non_audio_file_handling(self, temp_work_dir, tmp_path):
        """
        Teste 3: Arquivo que não é áudio (ex: texto) é rejeitado.
        """
        print(f"\n{'='*70}")
        print("📄 TESTE: Handling de Arquivo Não-Áudio")
        print(f"{'='*70}")
        
        # Cria arquivo de texto fingindo ser OGG
        fake_audio = tmp_path / "fake.ogg"
        fake_audio.write_text("This is not an audio file, it's just text!")
        
        print(f"   Arquivo: {fake_audio.name}")
        print(f"   Conteúdo: texto (não é áudio)\n")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.exceptions import AudioTranscriptionException
        
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        print(f"   ✓ Modelo carregado")
        print(f"   Tentando transcrever arquivo não-áudio...\n")
        
        # Deve lançar exceção
        with pytest.raises((AudioTranscriptionException, RuntimeError, OSError)) as exc_info:
            manager.transcribe(fake_audio, language="auto")
        
        print(f"   ✓ Exceção capturada: {type(exc_info.value).__name__}")
        print(f"   ✅ Arquivo não-áudio rejeitado\n")
        
        # Cleanup
        manager.unload_model()
    
    def test_circuit_breaker_tracks_corrupted_file_failures(self, corrupted_audio_file, temp_work_dir):
        """
        Teste 4: Circuit breaker registra falhas de arquivos corrompidos.
        
        Valida que:
        - Falhas com arquivos corrompidos são registradas
        - Circuit pode abrir após múltiplas falhas
        - Sistema protege contra falhas repetidas
        """
        print(f"\n{'='*70}")
        print("🔌 TESTE: Circuit Breaker + Arquivos Corrompidos")
        print(f"{'='*70}")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        from app.exceptions import AudioTranscriptionException
        
        cb = get_circuit_breaker()
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        service_name = f"faster_whisper_transcribe_{manager.model_name}"
        
        # Limpa estado anterior
        cb.state[service_name] = CircuitBreakerState.CLOSED
        cb.failures[service_name] = 0
        
        print(f"   Service: {service_name}")
        print(f"   Estado inicial: CLOSED")
        print(f"   Failure threshold: {cb.failure_threshold}\n")
        
        # Tenta transcrever arquivo corrompido múltiplas vezes
        failure_count = 0
        for i in range(1, cb.failure_threshold + 2):  # Uma a mais para garantir que abre
            try:
                print(f"   Tentativa {i}...")
                manager.transcribe(corrupted_audio_file, language="auto")
            except (AudioTranscriptionException, RuntimeError, OSError):
                failure_count += 1
                current_failures = cb.failures.get(service_name, 0)
                current_state = cb.state.get(service_name, CircuitBreakerState.CLOSED)
                print(f"      ✓ Falha {failure_count} registrada - Estado: {current_state}")
                
                # Se circuit abriu, para
                if current_state == CircuitBreakerState.OPEN:
                    print(f"\n   ⚠️  Circuit ABRIU após {failure_count} falhas")
                    break
        
        # Valida que falhas foram registradas
        final_failures = cb.failures.get(service_name, 0)
        final_state = cb.state.get(service_name, CircuitBreakerState.CLOSED)
        
        print(f"\n   ✓ Total de falhas: {final_failures}")
        print(f"   ✓ Estado final: {final_state}")
        
        assert final_failures >= cb.failure_threshold or final_state == CircuitBreakerState.OPEN, \
            "Circuit breaker não registrou falhas apropriadamente"
        
        print(f"\n   ✅ Circuit breaker protegendo contra falhas repetidas\n")
        
        # Cleanup
        manager.unload_model()
    
    def test_system_recovers_after_corrupted_file(self, corrupted_audio_file, test_audio_real, temp_work_dir):
        """
        Teste 5: Sistema se recupera após processar arquivo corrompido.
        
        Valida que após falha com arquivo corrompido:
        - Sistema pode processar arquivo válido
        - Modelo permanece funcional
        - Circuit breaker permite chamadas após sucesso
        """
        print(f"\n{'='*70}")
        print("♻️  TESTE: Recuperação Após Arquivo Corrompido")
        print(f"{'='*70}")
        
        from app.faster_whisper_manager import FasterWhisperModelManager
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        from app.exceptions import AudioTranscriptionException
        
        cb = get_circuit_breaker()
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        service_name = f"faster_whisper_transcribe_{manager.model_name}"
        
        # Limpa estado
        cb.state[service_name] = CircuitBreakerState.CLOSED
        cb.failures[service_name] = 0
        
        # 1. Tenta arquivo corrompido (deve falhar)
        print(f"\n   FASE 1: Tentando arquivo corrompido...")
        try:
            manager.transcribe(corrupted_audio_file, language="auto")
            assert False, "Deveria ter falhado com arquivo corrompido"
        except (AudioTranscriptionException, RuntimeError, OSError):
            print(f"   ✓ Falha esperada com arquivo corrompido")
            failures_after_error = cb.failures.get(service_name, 0)
            print(f"   ✓ Falhas registradas: {failures_after_error}")
        
        # 2. Tenta arquivo válido (deve ter sucesso)
        print(f"\n   FASE 2: Tentando arquivo válido...")
        result = manager.transcribe(test_audio_real, language="auto")
        
        assert result["success"] is True, "Falhou com arquivo válido após erro"
        print(f"   ✓ Transcrição bem-sucedida")
        
        # 3. Valida recuperação do circuit breaker
        failures_after_success = cb.failures.get(service_name, 0)
        state_after_success = cb.state.get(service_name, CircuitBreakerState.CLOSED)
        
        print(f"\n   ✓ Falhas após sucesso: {failures_after_success}")
        print(f"   ✓ Estado após sucesso: {state_after_success}")
        
        assert failures_after_success == 0, "Falhas não foram resetadas"
        assert state_after_success == CircuitBreakerState.CLOSED, "Circuit não fechou"
        
        print(f"\n   ✅ Sistema SE RECUPEROU completamente")
        print(f"   ✅ Modelo funcional após erro\n")
        
        # Cleanup
        manager.unload_model()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
