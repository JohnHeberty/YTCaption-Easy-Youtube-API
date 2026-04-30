"""
Testes para o engine Whisper.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from app.infrastructure.whisper_engine import WhisperEngine, ModelManager
from app.domain.interfaces import TranscriptionResult
from app.domain.models import WhisperEngine as WhisperEngineEnum


class TestWhisperEngine:
    """Testes para WhisperEngine."""
    
    def test_init_default(self):
        """Inicialização com defaults."""
        engine = WhisperEngine()
        assert engine.model_size == "base"
        assert engine.device in ["cpu", "cuda"]
        assert engine._model is None
    
    def test_init_custom_params(self):
        """Inicialização com parâmetros customizados."""
        engine = WhisperEngine(
            model_size="small",
            device="cpu",
            compute_type="int8",
            download_root="/custom/path"
        )
        assert engine.model_size == "small"
        assert engine.device == "cpu"
        assert engine.compute_type == "int8"
    
    def test_is_loaded_when_not_loaded(self):
        """is_loaded retorna False quando não carregado."""
        engine = WhisperEngine()
        assert engine.is_loaded() is False
    
    def test_is_loaded_when_loaded(self):
        """is_loaded retorna True quando carregado."""
        engine = WhisperEngine()
        engine._model = MagicMock()
        assert engine.is_loaded() is True
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    def test_load_model_success(self, mock_whisper_class):
        """Carregamento bem-sucedido do modelo."""
        mock_model = MagicMock()
        mock_whisper_class.return_value = mock_model
        
        engine = WhisperEngine(model_size="base", device="cpu")
        engine.load_model()
        
        assert engine.is_loaded() is True
        assert engine._load_count == 1
        mock_whisper_class.assert_called_once()
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    def test_load_model_idempotent(self, mock_whisper_class):
        """load_model é idempotente."""
        mock_model = MagicMock()
        mock_whisper_class.return_value = mock_model
        
        engine = WhisperEngine(device="cpu")
        engine.load_model()
        engine.load_model()  # Segunda chamada
        
        # Deve chamar apenas uma vez
        mock_whisper_class.assert_called_once()
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    async def test_unload_model(self, mock_whisper_class):
        """Descarregamento do modelo."""
        mock_model = MagicMock()
        mock_whisper_class.return_value = mock_model
        
        engine = WhisperEngine(device="cpu")
        engine.load_model()
        assert engine.is_loaded() is True
        
        await engine.unload_model()
        assert engine.is_loaded() is False
    
    async def test_unload_when_not_loaded(self):
        """unload quando não carregado não gera erro."""
        engine = WhisperEngine()
        await engine.unload_model()  # Não deve levantar
        assert engine.is_loaded() is False
    
    def test_get_status_not_loaded(self):
        """Status quando não carregado."""
        engine = WhisperEngine()
        status = engine.get_status()
        
        assert status["loaded"] is False
        assert status["model_size"] == "base"
        assert status["load_count"] == 0
    
    def test_get_status_loaded(self):
        """Status quando carregado."""
        engine = WhisperEngine()
        engine._model = MagicMock()
        engine._loaded_at = MagicMock()
        engine._loaded_at.isoformat.return_value = "2024-01-01T12:00:00"
        
        status = engine.get_status()
        
        assert status["loaded"] is True
        assert status["model_size"] == "base"
        assert "loaded_at" in status
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    async def test_transcribe_success(self, mock_whisper_class):
        """Transcrição bem-sucedida."""
        # Mock do modelo
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_segment.start = 0.0
        mock_segment.end = 2.5
        mock_segment.words = []
        
        mock_info = MagicMock()
        mock_info.language = "en"
        
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_whisper_class.return_value = mock_model
        
        engine = WhisperEngine(device="cpu")
        
        # Cria arquivo temporário
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            temp_path = f.name
        
        try:
            result = await engine.transcribe(temp_path, language="en")
            
            assert isinstance(result, TranscriptionResult)
            assert result.text == "Hello world"
            assert len(result.segments) == 1
            assert result.language == "en"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    async def test_transcribe_file_not_found(self):
        """Transcrição com arquivo inexistente."""
        engine = WhisperEngine()
        
        with pytest.raises(Exception) as exc:
            await engine.transcribe("/nonexistent/file.mp3")
        
        assert "não encontrado" in str(exc.value).lower() or "not found" in str(exc.value).lower()


class TestModelManager:
    """Testes para ModelManager (Singleton)."""
    
    def test_singleton_pattern(self):
        """Garante que é singleton."""
        manager1 = ModelManager()
        manager2 = ModelManager()
        
        assert manager1 is manager2
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    def test_get_or_create_engine_creates_new(self, mock_whisper_class):
        """Cria novo engine quando não existe."""
        # Reset singleton para teste
        ModelManager._instance = None
        ModelManager._engines = {}
        
        manager = ModelManager()
        
        mock_whisper_class.return_value = MagicMock()
        
        engine = manager.get_or_create_engine("base")
        
        assert isinstance(engine, WhisperEngine)
        assert "base_auto" in manager._engines
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    def test_get_or_create_engine_returns_cached(self, mock_whisper_class):
        """Retorna engine cacheado quando existe."""
        # Reset singleton
        ModelManager._instance = None
        ModelManager._engines = {}
        
        manager = ModelManager()
        mock_whisper_class.return_value = MagicMock()
        
        engine1 = manager.get_or_create_engine("base")
        engine2 = manager.get_or_create_engine("base")
        
        assert engine1 is engine2
        mock_whisper_class.assert_called_once()
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    async def test_unload_idle_engines(self, mock_whisper_class):
        """Descarrega engines inativos."""
        # Reset singleton
        ModelManager._instance = None
        ModelManager._engines = {}
        ModelManager._last_accessed = {}
        
        manager = ModelManager()
        mock_whisper_class.return_value = MagicMock()
        
        engine = manager.get_or_create_engine("base")
        engine.load_model()
        
        # Marca como acessado há muito tempo atrás
        from datetime import datetime, timedelta, timezone
        manager._last_accessed["base_auto"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        
        unloaded = await manager.unload_idle_engines(timeout_minutes=1)
        
        assert unloaded == 1
        assert not engine.is_loaded()
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    async def test_unload_all(self, mock_whisper_class):
        """Descarrega todos os engines."""
        # Reset singleton
        ModelManager._instance = None
        ModelManager._engines = {}
        
        manager = ModelManager()
        mock_whisper_class.return_value = MagicMock()
        
        engine = manager.get_or_create_engine("base")
        engine.load_model()
        
        await manager.unload_all()
        
        assert len(manager._engines) == 0
        assert not engine.is_loaded()
    
    @patch("app.infrastructure.whisper_engine.WhisperModel")
    def test_get_loaded_engines(self, mock_whisper_class):
        """Lista engines carregados."""
        # Reset singleton
        ModelManager._instance = None
        ModelManager._engines = {}
        
        manager = ModelManager()
        mock_whisper_class.return_value = MagicMock()
        
        engine = manager.get_or_create_engine("base")
        engine.load_model()
        
        loaded = manager.get_loaded_engines()
        
        assert "base_auto" in loaded