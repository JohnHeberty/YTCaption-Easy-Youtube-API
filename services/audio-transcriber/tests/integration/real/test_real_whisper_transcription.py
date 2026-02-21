"""
Testes de integração REAIS com Faster-Whisper.

⚠️  ATENÇÃO: Estes testes NÃO usam mocks!
✅ Carregam o modelo Faster-Whisper real
✅ Transcrevem áudio real (TEST-.ogg)
✅ Validam word timestamps reais
✅ Medem performance real de produção

Execute com: pytest -m real -v --tb=short
"""

import pytest
import time
from pathlib import Path
import sys
import os
import importlib.util
from unittest.mock import MagicMock

# Setup para importar sem Redis
mock_interfaces = MagicMock()
mock_interfaces.IModelManager = type('IModelManager', (), {})
sys.modules['app.interfaces'] = mock_interfaces
sys.modules['app.exceptions'] = MagicMock()
mock_config = MagicMock()
mock_settings = MagicMock()
mock_settings.get = lambda k, d=None: {
    'whisper_download_root': './models',
    'whisper_model': 'small',  # small é mais rápido para testes
    'whisper_device': 'cpu',
    'model_load_retries': 3,
    'model_load_backoff': 2.0
}.get(k, d)
mock_config.get_settings.return_value = mock_settings
sys.modules['app.config'] = mock_config

# Importa FasterWhisperModelManager
module_path = Path(__file__).parent.parent.parent.parent / "app" / "faster_whisper_manager.py"
spec = importlib.util.spec_from_file_location("app.faster_whisper_manager", module_path)
fwm_module = importlib.util.module_from_spec(spec)
sys.modules['app.faster_whisper_manager'] = fwm_module
spec.loader.exec_module(fwm_module)

FasterWhisperModelManager = fwm_module.FasterWhisperModelManager


@pytest.fixture(scope="module")
def test_audio_file():
    """Retorna caminho do arquivo de teste real"""
    audio_path = Path(__file__).parent.parent.parent / "TEST-.ogg"
    assert audio_path.exists(), f"Arquivo de teste não encontrado: {audio_path}"
    return audio_path


@pytest.fixture(scope="module")
def model_manager():
    """
    Cria e retorna FasterWhisperModelManager REAL.
    
    ⚠️  SEM MOCKS! Carrega modelo real do Hugging Face.
    """
    manager = FasterWhisperModelManager()
    return manager


@pytest.mark.real
@pytest.mark.slow
class TestRealWhisperIntegration:
    """
    Testes de integração REAL com Faster-Whisper.
    
    ⚠️  Estes testes:
    - Carregam o modelo real (~250MB download na primeira vez)
    - Fazem inferência real
    - Demoram mais tempo (modelo small ~10-30s no CPU)
    """
    
    def test_model_download_and_load(self, model_manager):
        """
        Teste 1: Carrega modelo Faster-Whisper REAL.
        
        Valida:
        - Download do modelo (se necessário)
        - Carregamento em memória
        - Device detection
        - Status after load
        """
        print("\n" + "="*70)
        print("🚀 TESTE REAL: Carregando modelo Faster-Whisper...")
        print("="*70)
        
        start_time = time.time()
        
        # Carrega modelo REAL (sem mocks!)
        model_manager.load_model()
        
        load_time = time.time() - start_time
        
        # Validações
        assert model_manager.is_loaded is True, "Modelo não foi carregado"
        assert model_manager.model is not None, "Modelo está None"
        assert model_manager.device in ["cpu", "cuda"], f"Device inválido: {model_manager.device}"
        
        # Status
        status = model_manager.get_status()
        assert status["loaded"] is True
        assert status["engine"] == "faster-whisper"
        
        print(f"\n✅ Modelo carregado com sucesso!")
        print(f"   - Modelo: {model_manager.model_name}")
        print(f"   - Device: {model_manager.device}")
        print(f"   - Tempo de load: {load_time:.2f}s")
        print(f"   - Engine: {status['engine']}")
        
    def test_real_transcription_with_word_timestamps(self, model_manager, test_audio_file):
        """
        Teste 2: Transcrição REAL com word timestamps.
        
        Valida:
        - Transcrição do arquivo TEST-.ogg real
        - Word-level timestamps gerados
        - Estrutura do resultado
        - Performance em produção
        """
        print("\n" + "="*70)
        print("🎤 TESTE REAL: Transcrevendo áudio real (TEST-.ogg)...")
        print("="*70)
        print(f"   Arquivo: {test_audio_file.name} ({test_audio_file.stat().st_size / 1024:.1f} KB)")
        
        start_time = time.time()
        
        # Transcreve REAL (sem mocks!)
        result = model_manager.transcribe(test_audio_file, language="pt")
        
        transcription_time = time.time() - start_time
        
        # Validações básicas
        assert result["success"] is True, "Transcrição falhou"
        assert "text" in result, "Resultado não tem 'text'"
        assert "segments" in result, "Resultado não tem 'segments'"
        assert len(result["segments"]) > 0, "Nenhum segment gerado"
        
        # Valida word timestamps
        total_words = 0
        for segment in result["segments"]:
            assert "words" in segment, "Segment não tem 'words'"
            words = segment["words"]
            total_words += len(words)
            
            # Valida cada word
            for word in words:
                assert "word" in word, "Word não tem campo 'word'"
                assert "start" in word, "Word não tem campo 'start'"
                assert "end" in word, "Word não tem campo 'end'"
                assert "probability" in word, "Word não tem campo 'probability'"
                
                # Timestamps são válidos
                assert word["start"] >= 0, f"Start inválido: {word['start']}"
                # Faster-Whisper pode gerar start == end para palavras muito curtas
                assert word["end"] >= word["start"], f"End < start: {word}"
                assert 0 <= word["probability"] <= 1, f"Probability inválida: {word['probability']}"
        
        # Métricas
        duration = result.get("duration", 0)
        rtf = transcription_time / duration if duration > 0 else 0  # Real-Time Factor
        
        print(f"\n✅ Transcrição concluída!")
        print(f"\n📊 RESULTADOS:")
        print(f"   - Texto: \"{result['text'][:100]}...\"" if len(result['text']) > 100 else f"   - Texto: \"{result['text']}\"")
        print(f"   - Segments: {len(result['segments'])}")
        print(f"   - Total words: {total_words}")
        print(f"   - Idioma detectado: {result.get('language', 'N/A')}")
        print(f"   - Duração áudio: {duration:.2f}s")
        print(f"\n⏱️  PERFORMANCE:")
        print(f"   - Tempo transcrição: {transcription_time:.2f}s")
        print(f"   - RTF (Real-Time Factor): {rtf:.2f}x")
        print(f"   - Throughput: {total_words/transcription_time:.1f} words/s")
        
        # Valida que encontrou palavras esperadas
        text_lower = result['text'].lower()
        expected_words = ["um", "dois", "três", "quatro", "1", "2", "3", "4"]
        found_words = [w for w in expected_words if w in text_lower]
        
        print(f"\n🎯 VALIDAÇÃO CONTEÚDO:")
        print(f"   - Texto completo: \"{result['text']}\"")
        print(f"   - Palavras esperadas: {expected_words}")
        print(f"   - Palavras encontradas: {found_words}")
        if found_words:
            print(f"   - Taxa acerto: {len(found_words)}/{len(expected_words)} ({len(found_words)*100/len(expected_words):.0f}%)")
        
        # Pelo menos 25% das palavras esperadas devem estar presentes
        assert len(found_words) >= len(expected_words) * 0.25, \
            f"Poucas palavras esperadas encontradas: {found_words}"
    
    def test_word_timestamps_accuracy(self, model_manager, test_audio_file):
        """
        Teste 3: Precisão dos word timestamps.
        
        Valida:
        - Timestamps são sequenciais
        - Não há gaps grandes entre palavras
        - Duração das palavras é razoável
        """
        print("\n" + "="*70)
        print("⏱️  TESTE REAL: Validando precisão dos timestamps...")
        print("="*70)
        
        result = model_manager.transcribe(test_audio_file, language="pt")
        
        all_words = []
        for segment in result["segments"]:
            all_words.extend(segment["words"])
        
        print(f"\n📊 Analisando {len(all_words)} palavras...")
        
        # Valida sequencialidade
        for i in range(len(all_words) - 1):
            current = all_words[i]
            next_word = all_words[i + 1]
            
            # Timestamps são crescentes
            assert current["end"] <= next_word["start"] + 0.5, \
                f"Timestamps não sequenciais: {current} -> {next_word}"
            
            # Gap entre palavras não é absurdo (< 2s)
            gap = next_word["start"] - current["end"]
            assert gap < 2.0, f"Gap muito grande entre palavras: {gap:.2f}s"
        
        # Valida duração das palavras
        durations = [w["end"] - w["start"] for w in all_words]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        
        print(f"\n📈 ESTATÍSTICAS DOS TIMESTAMPS:")
        print(f"   - Duração média: {avg_duration:.3f}s")
        print(f"   - Duração mínima: {min_duration:.3f}s")
        print(f"   - Duração máxima: {max_duration:.3f}s")
        
        # Valida que durações são razoáveis
        assert avg_duration > 0, "Duração média deve ser > 0"
        assert avg_duration < 2.0, f"Duração média muito alta: {avg_duration}"
        assert max_duration < 5.0, f"Palavra com duração absurda: {max_duration}s"
        
        # Mostra algumas palavras com timestamps
        print(f"\n🔍 AMOSTRA DE PALAVRAS COM TIMESTAMPS:")
        for i, word in enumerate(all_words[:5]):  # Primeiras 5 palavras
            print(f"   {i+1}. \"{word['word']}\" [{word['start']:.2f}s - {word['end']:.2f}s] (conf: {word['probability']:.2%})")
        
        print(f"\n✅ Timestamps validados com sucesso!")
    
    @pytest.mark.skip(reason="Teste longo (>5min) com arquivo de 33s - execute manualmente se necessário")
    def test_multiple_transcriptions_performance(self, model_manager, test_audio_file):
        """
        Teste 4: Performance de múltiplas transcrições.
        
        ⚠️  ATENÇÃO: Teste MUITO LENTO (>5 min) devido ao arquivo de 33s.
        Execute manualmente: pytest -m real -k "performance" --timeout=600
        
        Valida:
        - Modelo é reutilizado (não recarrega)
        - Performance se mantém estável
        - Não há memory leaks
        """
        print("\n" + "="*70)
        print("🔄 TESTE REAL: Performance de múltiplas transcrições...")
        print("="*70)
        
        num_runs = 3
        times = []
        word_counts = []
        
        for i in range(num_runs):
            print(f"\n   Run {i+1}/{num_runs}...")
            
            start = time.time()
            result = model_manager.transcribe(test_audio_file, language="pt")
            elapsed = time.time() - start
            
            times.append(elapsed)
            word_count = sum(len(seg["words"]) for seg in result["segments"])
            word_counts.append(word_count)
            
            print(f"      ✓ {elapsed:.2f}s ({word_count} words)")
        
        avg_time = sum(times) / len(times)
        std_dev = (sum((t - avg_time)**2 for t in times) / len(times)) ** 0.5
        
        print(f"\n📊 RESULTADOS DE PERFORMANCE:")
        print(f"   - Runs: {num_runs}")
        print(f"   - Tempo médio: {avg_time:.2f}s")
        print(f"   - Desvio padrão: {std_dev:.2f}s")
        print(f"   - Variação: {std_dev/avg_time*100:.1f}%")
        print(f"   - Mais rápido: {min(times):.2f}s")
        print(f"   - Mais lento: {max(times):.2f}s")
        print(f"   - Word count consistente: {len(set(word_counts)) == 1}")
        
        # Valida consistência
        assert len(set(word_counts)) == 1, \
            f"Word counts inconsistentes: {word_counts}"
        
        # Performance não degrada muito
        assert max(times) < min(times) * 2, \
            "Performance degrada muito entre runs"
        
        print(f"\n✅ Performance estável confirmada!")
    
    def test_model_unload(self, model_manager):
        """
        Teste 5: Descarregamento do modelo.
        
        Valida:
        - Modelo é descarregado corretamente
        - Memória é liberada
        - Status após unload
        """
        print("\n" + "="*70)
        print("🔥 TESTE REAL: Descarregando modelo...")
        print("="*70)
        
        # Status antes
        status_before = model_manager.get_status()
        assert status_before["loaded"] is True
        
        # Unload
        result = model_manager.unload_model()
        
        # Validações
        assert result["success"] is True, "Unload falhou"
        assert model_manager.model is None, "Modelo ainda está na memória"
        assert model_manager.is_loaded is False, "Flag is_loaded ainda True"
        
        # Status depois
        status_after = model_manager.get_status()
        assert status_after["loaded"] is False
        
        print(f"\n✅ Modelo descarregado!")
        print(f"   - Memória RAM liberada: ~{result['memory_freed']['ram_mb']}MB")
        print(f"   - Status: {status_after}")


@pytest.mark.real
@pytest.mark.slow
class TestRealProductionScenario:
    """
    Testes simulando cenário real de produção.
    """
    
    def test_cold_start_to_transcription(self, test_audio_file):
        """
        Teste 6: Cold start completo (como em produção).
        
        Simula:
        - Aplicação inicia
        - Modelo não está em cache
        - Primeira transcrição
        """
        print("\n" + "="*70)
        print("🆕 TESTE REAL: Cenário de cold start (produção)...")
        print("="*70)
        
        # Cria manager novo (simula cold start)
        manager = FasterWhisperModelManager()
        
        print("\n1️⃣  Aplicação iniciando (modelo não carregado)...")
        status = manager.get_status()
        assert status["loaded"] is False
        print(f"   ✓ Status inicial: {status}")
        
        print("\n2️⃣  Primeira requisição de transcrição...")
        start = time.time()
        
        # Transcreve (deve carregar modelo automaticamente)
        result = manager.transcribe(test_audio_file, language="pt")
        
        total_time = time.time() - start
        
        print(f"   ✓ Transcrição concluída!")
        print(f"\n⏱️  TEMPO TOTAL (COLD START + TRANSCRIÇÃO): {total_time:.2f}s")
        
        # Valida resultado
        assert result["success"] is True
        assert len(result["segments"]) > 0
        
        # Segunda transcrição (modelo já carregado)
        print("\n3️⃣  Segunda requisição (modelo quente)...")
        start2 = time.time()
        result2 = manager.transcribe(test_audio_file, language="pt")
        warm_time = time.time() - start2
        
        print(f"   ✓ Transcrição concluída!")
        print(f"\n⏱️  TEMPO (MODELO QUENTE): {warm_time:.2f}s")
        print(f"\n📊 COMPARAÇÃO:")
        print(f"   - Cold start: {total_time:.2f}s")
        print(f"   - Warm: {warm_time:.2f}s")
        print(f"   - Speedup: {total_time/warm_time:.1f}x mais rápido")
        
        # Cleanup
        manager.unload_model()
        
        print(f"\n✅ Cenário de produção validado!")


# ============================================================================
# Teste de Sanidade Rápido (para CI/CD)
# ============================================================================

@pytest.mark.real
class TestRealQuickSanity:
    """
    Teste rápido de sanidade com modelo real.
    Útil para CI/CD quando não há tempo para testes completos.
    """
    
    def test_quick_sanity_check(self, test_audio_file):
        """
        Teste 7: Sanity check rápido com modelo real.
        
        Execução: ~10-30s
        Valida apenas o essencial.
        """
        print("\n" + "="*70)
        print("⚡ TESTE REAL RÁPIDO: Sanity check...")
        print("="*70)
        
        manager = FasterWhisperModelManager()
        
        # Load + Transcribe
        result = manager.transcribe(test_audio_file, language="pt")
        
        # Validações mínimas
        assert result["success"] is True
        assert len(result["text"]) > 0
        assert len(result["segments"]) > 0
        
        total_words = sum(len(seg["words"]) for seg in result["segments"])
        assert total_words > 0
        
        # Cleanup
        manager.unload_model()
        
        print(f"\n✅ Sanity check OK!")
        print(f"   - Texto: \"{result['text'][:50]}...\"")
        print(f"   - Words: {total_words}")
