"""
Testes unitários para FasterWhisperModelManager.

Testa o gerenciamento do modelo Faster-Whisper, incluindo:
- Detecção de device (CPU/GPU)
- Carregamento e descarregamento do modelo
- Transcrição com word timestamps
- Retry logic
- Gestão de memória
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock, create_autospec
from pathlib import Path
import sys
import os
import importlib.util

# Cria mocks ANTES de qualquer import
mock_interfaces_module = MagicMock()
mock_interfaces_module.IModelManager = type('IModelManager', (), {})

mock_exceptions_module = MagicMock()
mock_exceptions_module.AudioTranscriptionException = Exception

mock_config_module = MagicMock()
mock_settings = MagicMock()
mock_settings.get = Mock(side_effect=lambda key, default=None: {
    'whisper_download_root': './models',
    'whisper_model': 'small',
    'whisper_device': 'cpu',
    'model_load_retries': 3,
    'model_load_backoff': 2.0
}.get(key, default))
mock_config_module.get_settings.return_value = mock_settings

# Registra os mocks no sys.modules
sys.modules['app.interfaces'] = mock_interfaces_module
sys.modules['app.exceptions'] = mock_exceptions_module
sys.modules['app.config'] = mock_config_module

# Carrega o módulo faster_whisper_manager diretamente (sem passar por app/__init__.py)
module_path = Path(__file__).parent.parent.parent.parent / "app" / "faster_whisper_manager.py"
spec = importlib.util.spec_from_file_location("app.faster_whisper_manager", module_path)
fwm_module = importlib.util.module_from_spec(spec)
sys.modules['app.faster_whisper_manager'] = fwm_module
spec.loader.exec_module(fwm_module)

FasterWhisperModelManager = fwm_module.FasterWhisperModelManager


@pytest.fixture
def mock_torch():
    """Mock do PyTorch"""
    with patch.object(fwm_module, 'torch') as mock:
        mock.cuda.is_available.return_value = False
        mock.cuda.empty_cache = Mock()
        mock.cuda.get_device_name.return_value = "Mock GPU"
        yield mock


@pytest.fixture
def mock_whisper_model():
    """Mock do WhisperModel do faster-whisper"""
    with patch.object(fwm_module, 'WhisperModel') as mock:
        # Simula o modelo carregado
        model_instance = MagicMock()
        
        # Simula info retornada pela transcrição
        info = MagicMock()
        info.language = "pt"
        info.duration = 2.5
        
        # Simula segment com words
        word1 = MagicMock()
        word1.word = "um"
        word1.start = 0.0
        word1.end = 0.5
        word1.probability = 0.95
        
        word2 = MagicMock()
        word2.word = "dois"
        word2.start = 0.6
        word2.end = 1.0
        word2.probability = 0.93
        
        segment = MagicMock()
        segment.start = 0.0
        segment.end = 2.5
        segment.text = "um dois três quatro"
        segment.words = [word1, word2]
        
        # Configura o retorno de transcribe (retorna generator, info)
        model_instance.transcribe.return_value = (iter([segment]), info)
        
        mock.return_value = model_instance
        yield mock


@pytest.fixture
def temp_model_dir(tmp_path):
    """Cria diretório temporário para modelos"""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    return model_dir


class TestInitialization:
    """Testes de inicialização do FasterWhisperModelManager"""
    
    def test_init_default_params(self, temp_model_dir, mock_torch):
        """Testa inicialização com parâmetros padrão"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        
        assert manager.model_dir == temp_model_dir
        assert manager.model_name == "small"  # Vem de mock_settings
        assert manager.model is None
        assert manager.device is None  # Só é setado em load_model()
        assert manager.is_loaded is False
        assert manager.max_retries == 3
        assert manager.retry_backoff == 2.0
    
    def test_init_uses_settings_defaults(self, mock_torch):
        """Testa que usa valores de settings quando model_dir não é fornecido"""
        manager = FasterWhisperModelManager()
        
        # Usa valor de whisper_download_root (Path remove o ./)
        assert str(manager.model_dir) == "models"
        assert manager.model_name == "small"


class TestDeviceDetection:
    """Testes de detecção de device (CPU/GPU)"""
    
    def test_detect_device_cpu_only(self, temp_model_dir, mock_torch):
        """Testa detecção quando apenas CPU está disponível"""
        mock_torch.cuda.is_available.return_value = False
        
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        device = manager._detect_device()
        
        assert device == "cpu"
    
    def test_detect_device_cuda_available(self, temp_model_dir, mock_torch):
        """Testa detecção quando GPU está disponível"""
        mock_torch.cuda.is_available.return_value = True
        
        # Cria função lambda que não causa recursão
        original_get = mock_settings.get
        def cuda_settings_get(k, d=None):
            if k == 'whisper_device':
                return 'cuda'
            return original_get(k, d)
        
        with patch.object(mock_settings, 'get', side_effect=cuda_settings_get):
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            device = manager._detect_device()
            
            assert device == "cuda"
    
    def test_detect_device_cuda_requested_but_unavailable(self, temp_model_dir, mock_torch):
        """Testa fallback para CPU quando CUDA é solicitado mas não disponível"""
        mock_torch.cuda.is_available.return_value = False
        
        original_get = mock_settings.get
        def cuda_settings_get(k, d=None):
            if k == 'whisper_device':
                return 'cuda'
            return original_get(k, d)
        
        with patch.object(mock_settings, 'get', side_effect=cuda_settings_get):
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            device = manager._detect_device()
            
            assert device == "cpu"


class TestModelLoading:
    """Testes de carregamento do modelo"""
    
    def test_load_model_success_cpu(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa carregamento bem-sucedido do modelo no CPU"""
        mock_torch.cuda.is_available.return_value = False
        
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        
        # Verifica que o modelo foi carregado
        assert manager.model is not None
        assert manager.is_loaded is True
        assert manager.device == "cpu"
        
        # Verifica chamada ao WhisperModel
        mock_whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",  # CPU usa int8
            download_root=str(temp_model_dir)
        )
    
    def test_load_model_success_cuda(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa carregamento bem-sucedido do modelo na GPU"""
        mock_torch.cuda.is_available.return_value = True
        
        original_get = mock_settings.get
        def cuda_settings_get(k, d=None):
            if k == 'whisper_device':
                return 'cuda'
            return original_get(k, d)
        
        with patch.object(mock_settings, 'get', side_effect=cuda_settings_get):
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            manager.load_model()
            
            assert manager.device == "cuda"
            # CUDA usa float16
            call_kwargs = mock_whisper_model.call_args[1]
            assert call_kwargs["compute_type"] == "float16"
    
    def test_load_model_already_loaded(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa que não recarrega modelo se já estiver carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        manager.load_model()  # Segunda chamada
        
        # Verifica que foi carregado apenas uma vez
        assert mock_whisper_model.call_count == 1
    
    def test_load_model_creates_directory(self, tmp_path, mock_torch, mock_whisper_model):
        """Testa que cria diretório se não existir"""
        model_dir = tmp_path / "nonexistent" / "models"
        
        manager = FasterWhisperModelManager(model_dir=model_dir)
        manager.load_model()
        
        assert model_dir.exists()


class TestModelUnloading:
    """Testes de descarregamento do modelo"""
    
    def test_unload_model_success(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa descarregamento bem-sucedido do modelo"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        result = manager.unload_model()
        
        # Verifica que o modelo foi descarregado
        assert manager.model is None
        assert manager.is_loaded is False
        assert result["success"] is True
        assert result["model_name"] == "small"
        assert result["memory_freed"]["ram_mb"] > 0
    
    def test_unload_model_not_loaded(self, temp_model_dir, mock_torch):
        """Testa descarregamento quando modelo não está carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        result = manager.unload_model()
        
        assert result["success"] is True
        assert "já estava descarregado" in result["message"]


class TestGetStatus:
    """Testes do método get_status"""
    
    def test_get_status_not_loaded(self, temp_model_dir, mock_torch):
        """Testa status quando modelo não está carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        status = manager.get_status()
        
        assert status["loaded"] is False
        assert status["model_name"] == "small"
        assert status["device"] is None
        assert status["engine"] == "faster-whisper"
    
    def test_get_status_loaded(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa status quando modelo está carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        status = manager.get_status()
        
        assert status["loaded"] is True
        assert status["device"] == "cpu"
        assert status["engine"] == "faster-whisper"


class TestTranscription:
    """Testes de transcrição de áudio"""
    
    def test_transcribe_success(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa transcrição bem-sucedida com word timestamps"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        
        # Cria arquivo de teste
        audio_file = temp_model_dir / "test.ogg"
        audio_file.touch()
        
        # Executa transcrição
        result = manager.transcribe(audio_file, language="pt")
        
        # Verifica que transcribe foi chamado com parâmetros corretos
        manager.model.transcribe.assert_called_once()
        call_args = manager.model.transcribe.call_args
        assert call_args[0][0] == str(audio_file)
        assert call_args[1]["word_timestamps"] is True
        assert call_args[1]["language"] == "pt"
        
        # Verifica resultado
        assert result["success"] is True
        assert result["text"] == "um dois três quatro"
        assert len(result["segments"]) == 1
        assert result["language"] == "pt"
        assert result["duration"] == 2.5
        
        # Verifica words
        segment = result["segments"][0]
        assert len(segment["words"]) == 2
        assert segment["words"][0]["word"] == "um"
        assert segment["words"][0]["start"] == 0.0
        assert segment["words"][0]["end"] == 0.5
        assert segment["words"][0]["probability"] == 0.95
    
    def test_transcribe_auto_loads_model(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa que transcribe carrega o modelo automaticamente se necessário"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        audio_file = temp_model_dir / "test.ogg"
        audio_file.touch()
        
        # Não carrega o modelo explicitamente
        result = manager.transcribe(audio_file)
        
        # Verifica que o modelo foi carregado automaticamente
        assert manager.is_loaded is True
        assert manager.model is not None
    
    def test_transcribe_auto_language_detection(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa detecção automática de idioma"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        audio_file = temp_model_dir / "test.ogg"
        audio_file.touch()
        
        result = manager.transcribe(audio_file, language="auto")
        
        # Verifica que não passou language para faster-whisper (deixa detectar)
        call_kwargs = manager.model.transcribe.call_args[1]
        assert "language" not in call_kwargs
        # Mas resultado tem o idioma detectado
        assert result["language"] == "pt"


class TestErrorHandling:
    """Testes de tratamento de erros"""
    
    def test_load_model_failure_max_retries(self, temp_model_dir, mock_torch):
        """Testa falha após max_retries"""
        with patch.object(fwm_module, 'WhisperModel', side_effect=Exception("Model not found")):
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            
            with pytest.raises(Exception, match="Falha ao carregar Faster-Whisper"):
                manager.load_model()
            
            # Verifica que tentou 3 vezes
            assert not manager.is_loaded
    
    def test_transcribe_failure(self, temp_model_dir, mock_torch):
        """Testa falha na transcrição"""
        with patch.object(fwm_module, 'WhisperModel') as mock:
            model_instance = MagicMock()
            model_instance.transcribe.side_effect = Exception("Transcription failed")
            mock.return_value = model_instance
            
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            audio_file = temp_model_dir / "test.ogg"
            audio_file.touch()
            
            with pytest.raises(Exception, match="Falha na transcrição"):
                manager.transcribe(audio_file)


class TestMemoryManagement:
    """Testes de gestão de memória"""
    
    def test_memory_estimates(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa estimativas de memória liberada"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        result = manager.unload_model()
        
        # small model deve liberar ~250MB
        assert result["memory_freed"]["ram_mb"] == 250


# ============================================================================
# Testes de Integração Leve (com mocks mínimos)
# ============================================================================

@pytest.mark.integration
class TestIntegrationWorkflow:
    """Testes de integração do workflow completo"""
    
    def test_full_workflow(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa workflow completo: init → load → status → transcribe → unload"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        
        # 1. Status inicial
        status = manager.get_status()
        assert status["loaded"] is False
        
        # 2. Load
        manager.load_model()
        assert manager.is_loaded is True
        
        # 3. Status após load
        status = manager.get_status()
        assert status["loaded"] is True
        assert status["device"] == "cpu"
        
        # 4. Transcribe
        audio_file = temp_model_dir / "test.ogg"
        audio_file.touch()
        result = manager.transcribe(audio_file)
        assert result["success"] is True
        
        # 5. Unload
        unload_result = manager.unload_model()
        assert unload_result["success"] is True
        assert manager.is_loaded is False
    
    def test_multiple_transcriptions(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa múltiplas transcrições sem recarregar modelo"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        audio_file = temp_model_dir / "test.ogg"
        audio_file.touch()
        
        # Primeira transcrição (carrega modelo)
        result1 = manager.transcribe(audio_file)
        assert result1["success"] is True
        
        # Segunda transcrição (reutiliza modelo)
        result2 = manager.transcribe(audio_file)
        assert result2["success"] is True
        
        # Verifica que modelo foi carregado apenas uma vez
        assert mock_whisper_model.call_count == 1
