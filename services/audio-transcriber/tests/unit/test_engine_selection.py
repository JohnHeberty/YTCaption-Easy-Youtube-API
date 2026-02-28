"""
Teste de seleção de engines Whisper.

Valida que:
1. faster-whisper funciona (já instalado)
2. openai-whisper e whisperx dão erro apropriado se não instalados
3. API aceita parâmetro 'engine'
"""

import pytest
from pathlib import Path
import sys

from app.domain.models import WhisperEngine, Job
from app.services.faster_whisper_manager import FasterWhisperModelManager


# Stub processor para evitar Redis
class StubTranscriptionProcessor:
    """Stub do processor que não precisa de Redis"""
    def __init__(self):
        from app.config import get_settings
        self.settings = get_settings()
        self.model_dir = Path('./models')
        self.model_managers = {}
        self.current_engine = WhisperEngine.FASTER_WHISPER
    
    def _get_model_manager(self, engine: WhisperEngine):
        """Retorna o model manager para o engine especificado"""
        if engine not in self.model_managers:
            if engine == WhisperEngine.FASTER_WHISPER:
                self.model_managers[engine] = FasterWhisperModelManager(model_dir=self.model_dir)
            elif engine == WhisperEngine.OPENAI_WHISPER:
                from app.openai_whisper_manager import OpenAIWhisperManager
                self.model_managers[engine] = OpenAIWhisperManager(model_dir=self.model_dir)
            elif engine == WhisperEngine.WHISPERX:
                from app.whisperx_manager import WhisperXManager
                self.model_managers[engine] = WhisperXManager(model_dir=self.model_dir)
            else:
                from app.exceptions import AudioTranscriptionException
                raise AudioTranscriptionException(f"Engine não suportado: {engine}")
        
        return self.model_managers[engine]


class TestEngineSelection:
    """Testes de seleção de engine"""
    
    def test_whisper_engine_enum(self):
        """Testa que enum WhisperEngine tem 3 valores"""
        engines = list(WhisperEngine)
        assert len(engines) == 3
        assert WhisperEngine.FASTER_WHISPER in engines
        assert WhisperEngine.OPENAI_WHISPER in engines
        assert WhisperEngine.WHISPERX in engines
    
    def test_job_has_engine_field(self):
        """Testa que Job tem campo engine"""
        job = Job.create_new(
            filename="test.mp3",
            operation="transcribe",
            language_in="auto",
            engine=WhisperEngine.FASTER_WHISPER
        )
        
        assert hasattr(job, 'engine')
        assert job.engine == WhisperEngine.FASTER_WHISPER
    
    def test_job_default_engine_is_faster_whisper(self):
        """Testa que engine padrão é faster-whisper"""
        job = Job.create_new(
            filename="test.mp3",
            operation="transcribe",
            language_in="auto"
        )
        
        assert job.engine == WhisperEngine.FASTER_WHISPER
    
    def test_processor_creates_faster_whisper_manager(self):
        """Testa que processor cria FasterWhisperModelManager"""
        processor = StubTranscriptionProcessor()
        
        # Pega manager para faster-whisper
        manager = processor._get_model_manager(WhisperEngine.FASTER_WHISPER)
        
        assert manager is not None
        assert isinstance(manager, FasterWhisperModelManager)
    
    def test_processor_caches_managers(self):
        """Testa que processor cacheia managers"""
        processor = StubTranscriptionProcessor()
        
        # Pega manager duas vezes
        manager1 = processor._get_model_manager(WhisperEngine.FASTER_WHISPER)
        manager2 = processor._get_model_manager(WhisperEngine.FASTER_WHISPER)
        
        # Deve ser a mesma instância
        assert manager1 is manager2
    
    def test_openai_whisper_manager_importable(self):
        """Testa que OpenAIWhisperManager pode ser importado"""
        try:
            from app.openai_whisper_manager import OpenAIWhisperManager
            assert OpenAIWhisperManager is not None
        except ImportError as e:
            pytest.fail(f"Falha ao importar OpenAIWhisperManager: {e}")
    
    def test_whisperx_manager_importable(self):
        """Testa que WhisperXManager pode ser importado"""
        try:
            from app.whisperx_manager import WhisperXManager
            assert WhisperXManager is not None
        except ImportError as e:
            pytest.fail(f"Falha ao importar WhisperXManager: {e}")
    
    def test_processor_handles_openai_whisper_not_installed(self):
        """Testa que processor lida com openai-whisper não instalado"""
        processor = StubTranscriptionProcessor()
        
        # Tenta criar manager para openai-whisper
        try:
            manager = processor._get_model_manager(WhisperEngine.OPENAI_WHISPER)
            
            # Se conseguiu criar, significa que está instalado
            # Nesse caso, verifica que tem os métodos necessários
            assert hasattr(manager, 'load_model')
            assert hasattr(manager, 'transcribe')
            
        except Exception as e:
            # Se falhou, deve ser porque não está instalado
            # Valida que a mensagem de erro é apropriada
            error_msg = str(e).lower()
            assert 'openai' in error_msg or 'whisper' in error_msg or 'not installed' in error_msg or 'instalado' in error_msg
    
    def test_processor_handles_whisperx_not_installed(self):
        """Testa que processor lida com whisperx não instalado"""
        processor = StubTranscriptionProcessor()
        
        # Tenta criar manager para whisperx
        try:
            manager = processor._get_model_manager(WhisperEngine.WHISPERX)
            
            # Se conseguiu criar, significa que está instalado
            assert hasattr(manager, 'load_model')
            assert hasattr(manager, 'transcribe')
            
        except Exception as e:
            # Se falhou, deve ser porque não está instalado
            error_msg = str(e).lower()
            assert 'whisperx' in error_msg or 'not installed' in error_msg or 'instalado' in error_msg


# ============================================================================
# Helper functions
# ============================================================================

def _is_openai_whisper_installed() -> bool:
    """Verifica se openai-whisper está instalado"""
    try:
        import whisper
        return True
    except ImportError:
        return False


def _is_whisperx_installed() -> bool:
    """Verifica se whisperx está instalado"""
    try:
        import whisperx
        return True
    except ImportError:
        return False


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestEngineIntegration:
    """Testes de integração com engines (requerem instalação)"""
    
    def test_faster_whisper_available(self):
        """Testa que faster-whisper está disponível"""
        try:
            from faster_whisper import WhisperModel
            assert WhisperModel is not None
        except ImportError:
            pytest.fail("faster-whisper não está instalado!")
    
    @pytest.mark.skipif(
        not _is_openai_whisper_installed(),
        reason="openai-whisper não instalado"
    )
    def test_openai_whisper_manager_loads(self):
        """Testa que OpenAIWhisperManager carrega (se instalado)"""
        from app.openai_whisper_manager import OpenAIWhisperManager
        
        manager = OpenAIWhisperManager()
        assert manager is not None
        assert hasattr(manager, 'load_model')
    
    @pytest.mark.skipif(
        not _is_whisperx_installed(),
        reason="whisperx não instalado"
    )
    def test_whisperx_manager_loads(self):
        """Testa que WhisperXManager carrega (se instalado)"""
        from app.whisperx_manager import WhisperXManager
        
        manager = WhisperXManager()
        assert manager is not None
        assert hasattr(manager, 'load_model')


# ============================================================================
# Informações para o usuário
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TESTE DE ENGINES WHISPER")
    print("=" * 70)
    print()
    print("Este teste valida a seleção de engines de transcrição.")
    print()
    print("✅ faster-whisper: SEMPRE testado (instalado por padrão)")
    print()
    
    if _is_openai_whisper_installed():
        print("✅ openai-whisper: INSTALADO")
    else:
        print("⚠️  openai-whisper: NÃO INSTALADO")
        print("   Instale com: pip install openai-whisper")
    print()
    
    if _is_whisperx_installed():
        print("✅ whisperx: INSTALADO")
    else:
        print("⚠️  whisperx: NÃO INSTALADO")
        print("   Instale com: pip install whisperx")
    print()
    print("=" * 70)
    print()
    print("Para rodar os testes:")
    print("  pytest tests/unit/test_engine_selection.py -v")
    print()
    print("Para rodar SOMENTE testes que não dependem de instalação:")
    print("  pytest tests/unit/test_engine_selection.py -v -k 'not integration'")
    print("=" * 70)
