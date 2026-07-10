"""
Teste de Transcrição REAL - SEM MOCKS

❌ NÃO usa MagicMock
❌ NÃO mocka interfaces
✅ Usa arquivo de áudio REAL (TEST-.ogg)
✅ Carrega modelo Faster-Whisper REAL
✅ Valida transcrição completa end-to-end

Execute com: pytest tests/resilience/test_transcription_real.py -v -s
"""
import ctypes
import ctypes.util
import pytest
import time
from pathlib import Path


def _cuda_available() -> bool:
    """Check if CUDA libraries (libcublas) are available."""
    return ctypes.util.find_library("cublas") is not None


# Marca este módulo como "real" e "slow"
pytestmark = [
    pytest.mark.real,
    pytest.mark.slow,
    pytest.mark.skipif(not _cuda_available(), reason="CUDA libraries (libcublas) not available"),
]


class TestRealTranscription:
    """
    Suite de testes REAIS de transcrição sem mocks.
    
    ⚠️  ATENÇÃO:
    - Baixa modelo real (~250MB na primeira execução)
    - Executa inferência real (10-30s no CPU)
    - Requer espaço em disco
    """
    
    def test_audio_file_exists_and_valid(self, test_audio_real):
        """
        Teste 0: Valida que arquivo TEST-.ogg existe e é válido.
        
        Garante que:
        - Arquivo existe
        - Tem tamanho razoável (> 10KB)
        - É formato OGG válido
        """
        print(f"\n{'='*70}")
        print(f"📁 Validando arquivo de teste: {test_audio_real.name}")
        print(f"{'='*70}")
        
        # Existe
        assert test_audio_real.exists(), f"Arquivo não encontrado: {test_audio_real}"
        
        # Tamanho razoável
        size_bytes = test_audio_real.stat().st_size
        size_kb = size_bytes / 1024
        print(f"   ✓ Arquivo encontrado: {size_kb:.1f} KB")
        assert size_bytes > 10_000, f"Arquivo muito pequeno: {size_kb:.1f}KB"
        
        # Header OGG válido
        with open(test_audio_real, 'rb') as f:
            header = f.read(4)
            assert header == b'OggS', f"Header inválido: {header} (esperado b'OggS')"
        
        print(f"   ✓ Formato OGG válido")
        print(f"   ✓ Arquivo pronto para transcrição\n")
    
    def test_model_loading_without_mocks(self, temp_work_dir):
        """
        Teste 1: Carrega modelo Faster-Whisper REAL (sem mocks).
        
        Valida:
        - Import sem mocks
        - Model loading real
        - Device detection
        - Circuit breaker funcionando
        """
        print(f"\n{'='*70}")
        print("🚀 TESTE REAL: Carregando Faster-Whisper (SEM MOCKS)")
        print(f"{'='*70}")
        
        # Import REAL (sem patches)
        from app.services.faster_whisper_manager import FasterWhisperModelManager
        from app.infrastructure import get_circuit_breaker
        
        print("   ✓ Imports realizados com sucesso")
        
        # Garante que circuit breaker está disponível
        cb = get_circuit_breaker()
        assert cb is not None, "Circuit breaker não disponível"
        print("   ✓ Circuit breaker disponível")
        
        # Cria manager REAL
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        print("   ✓ Manager criado")
        
        # Carrega modelo REAL
        start_time = time.time()
        manager.load_model()
        load_time = time.time() - start_time
        
        # Validações
        assert manager.is_loaded is True, "Modelo não foi carregado"
        assert manager.model is not None, "Modelo é None"
        assert manager.device in ["cpu", "cuda"], f"Device inválido: {manager.device}"
        
        print(f"\n   ✅ Modelo carregado com sucesso!")
        print(f"      - Nome: {manager.model_name}")
        print(f"      - Device: {manager.device.upper()}")
        print(f"      - Tempo: {load_time:.2f}s")
        
        # Cleanup
        manager.unload_model()
        print(f"   ✓ Modelo descarregado\n")
    
    def test_full_transcription_real_audio(self, test_audio_real, temp_work_dir):
        """
        Teste 2: Transcrição COMPLETA do arquivo TEST-.ogg REAL.
        
        Este é o teste MAIS IMPORTANTE - valida pipeline completo:
        - Carregamento de modelo REAL
        - Leitura de arquivo REAL
        - Transcrição REAL (inferência)
        - Word-level timestamps
        - Segments gerados
        - Circuit breaker registrando sucesso
        
        ⚠️  Sem mocks! Todas as operações são reais.
        """
        print(f"\n{'='*70}")
        print("🎤 TESTE REAL: Transcrição Completa (SEM MOCKS)")
        print(f"{'='*70}")
        print(f"   Arquivo: {test_audio_real.name}")
        print(f"   Tamanho: {test_audio_real.stat().st_size / 1024:.1f} KB\n")
        
        # Import REAL
        from app.services.faster_whisper_manager import FasterWhisperModelManager
        
        # Manager REAL
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        
        # Carrega modelo
        print("   Carregando modelo Faster-Whisper...")
        manager.load_model()
        print(f"   ✓ Modelo carregado no {manager.device.upper()}\n")
        
        # Transcreve REAL
        print("   Transcrevendo áudio...")
        start_time = time.time()
        
        result = manager.transcribe(
            audio_path=test_audio_real,
            language="auto",  # Detecta idioma automaticamente
            task="transcribe"
        )
        
        transcription_time = time.time() - start_time
        
        # ========================================
        # VALIDAÇÕES DO RESULTADO
        # ========================================
        
        print(f"\n{'='*70}")
        print("📊 VALIDANDO RESULTADO")
        print(f"{'='*70}")
        
        # 1. Estrutura básica
        assert result is not None, "Resultado é None"
        assert isinstance(result, dict), f"Resultado não é dict: {type(result)}"
        print("   ✓ Estrutura básica válida")
        
        # 2. Success flag
        assert result.get("success") is True, "Transcrição não foi bem-sucedida"
        print("   ✓ Success = True")
        
        # 3. Texto transcrito
        assert "text" in result, "Falta campo 'text'"
        assert isinstance(result["text"], str), "Texto não é string"
        assert len(result["text"]) > 0, "Texto está vazio"
        print(f"   ✓ Texto transcrito: {len(result['text'])} caracteres")
        
        # 4. Segments
        assert "segments" in result, "Falta campo 'segments'"
        assert isinstance(result["segments"], list), "Segments não é lista"
        assert len(result["segments"]) > 0, "Nenhum segment gerado"
        print(f"   ✓ Segments: {len(result['segments'])} encontrados")
        
        # 5. Valida estrutura de cada segment
        total_words = 0
        for i, segment in enumerate(result["segments"]):
            assert "start" in segment, f"Segment {i} sem 'start'"
            assert "end" in segment, f"Segment {i} sem 'end'"
            assert "text" in segment, f"Segment {i} sem 'text'"
            assert "words" in segment, f"Segment {i} sem 'words'"
            
            # Valida timestamps
            assert isinstance(segment["start"], (int, float)), "start não é numérico"
            assert isinstance(segment["end"], (int, float)), "end não é numérico"
            assert segment["end"] >= segment["start"], "end < start"
            
            # Conta words
            total_words += len(segment["words"])
            
            # Valida word-level timestamps
            for word_data in segment["words"]:
                assert "word" in word_data, "Word sem 'word'"
                assert "start" in word_data, "Word sem 'start'"
                assert "end" in word_data, "Word sem 'end'"
        
        print(f"   ✓ Word-level timestamps: {total_words} palavras")
        
        # 6. Idioma detectado
        if "language" in result:
            print(f"   ✓ Idioma detectado: {result['language']}")
        
        # 7. Duração
        if "duration" in result:
            print(f"   ✓ Duração do áudio: {result['duration']:.2f}s")
        
        # ========================================
        # SUMÁRIO FINAL
        # ========================================
        
        print(f"\n{'='*70}")
        print("✅ TRANSCRIÇÃO REAL COMPLETA COM SUCESSO")
        print(f"{'='*70}")
        print(f"   Tempo de transcrição: {transcription_time:.2f}s")
        print(f"   Segments gerados: {len(result['segments'])}")
        print(f"   Total de palavras: {total_words}")
        print(f"   Comprimento do texto: {len(result['text'])} chars")
        print(f"   Idioma: {result.get('language', 'N/A')}")
        print(f"   Duração áudio: {result.get('duration', 0):.2f}s")
        print(f"\n   📝 Prévia do texto transcrito:")
        print(f"   \"{result['text'][:200]}...\"")
        print(f"{'='*70}\n")
        
        # Cleanup
        manager.unload_model()
    
    def test_circuit_breaker_records_success(self, test_audio_real, temp_work_dir):
        """
        Teste 3: Valida que circuit breaker registra sucessos corretamente.
        
        Após transcrição bem-sucedida, circuit breaker deve:
        - Estar em estado CLOSED
        - Ter 0 falhas registradas
        - Permitir novas chamadas
        """
        print(f"\n{'='*70}")
        print("🔌 TESTE: Circuit Breaker - Registro de Sucessos")
        print(f"{'='*70}")
        
        from app.services.faster_whisper_manager import FasterWhisperModelManager
        from app.infrastructure import get_circuit_breaker, CircuitBreakerState
        
        # Get circuit breaker
        cb = get_circuit_breaker()
        
        # Manager e transcrição
        manager = FasterWhisperModelManager(model_dir=temp_work_dir / "models")
        manager.load_model()
        
        service_name = f"faster_whisper_transcribe_{manager.model_name}"
        
        # Transcreve
        result = manager.transcribe(test_audio_real, language="auto")
        assert result["success"] is True
        
        # Valida circuit breaker
        state = cb.state.get(service_name, CircuitBreakerState.CLOSED)
        failures = cb.failures.get(service_name, 0)
        
        print(f"   ✓ Estado do circuit: {state}")
        print(f"   ✓ Falhas registradas: {failures}")
        
        assert state == CircuitBreakerState.CLOSED, f"Circuit não está CLOSED: {state}"
        assert failures == 0, f"Falhas registradas: {failures}"
        assert not cb.is_open(service_name), "Circuit está aberto após sucesso"
        
        print(f"\n   ✅ Circuit breaker funcionando corretamente\n")
        
        # Cleanup
        manager.unload_model()


if __name__ == "__main__":
    """
    Permite executar diretamente: python test_transcription_real.py
    """
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
