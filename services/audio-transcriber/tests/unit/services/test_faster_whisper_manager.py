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
from unittest.mock import Mock, patch, MagicMock, PropertyMock,create_autospec
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
mock_settings.MODEL_NAME = "small"
mock_settings.MODEL_DIR = "/tmp/models"
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
        yield mock


@pytest.fixture
def mock_whisper_model():
    """Mock do WhisperModel do faster-whisper"""
    with patch.object(fwm_module, 'WhisperModel') as mock:
        # Simula o modelo carregado
        model_instance = MagicMock()
        
        # Simula segments retornados pela transcrição
        segment1 = MagicMock()
        segment1.start = 0.0
        segment1.end = 2.5
        segment1.text = "um dois três quatro"
        segment1.words = [
            MagicMock(start=0.0, end=0.5, word="um", probability=0.95),
            MagicMock(start=0.6, end=1.0, word="dois", probability=0.93),
            MagicMock(start=1.1, end=1.5, word="três", probability=0.94),
            MagicMock(start=1.6, end=2.5, word="quatro", probability=0.96),
        ]
        
        # Simula info retornada pela transcrição
        info = MagicMock()
        info.language = "pt"
        info.language_probability = 0.98
        info.duration = 2.5
        
        # Configura o retorno de transcribe
        model_instance.transcribe.return_value = ([segment1], info)
        
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
        assert manager.model_name == "small"
        assert manager.model is None
        assert manager.device in ["cpu", "cuda"]
        assert manager.compute_type in ["int8", "float16", "float32"]
    
    def test_init_custom_params(self, temp_model_dir, mock_torch):
        """Testa inicialização com parâmetros customizados"""
        manager = FasterWhisperModelManager(
            model_dir=temp_model_dir,
            model_name="base",
            device="cpu",
            compute_type="int8",
            num_workers=2
        )
        
        assert manager.model_name == "base"
        assert manager.device == "cpu"
        assert manager.compute_type == "int8"
        assert manager.num_workers == 2


class TestDeviceDetection:
    """Testes de detecção de device (CPU/GPU)"""
    
    def test_detect_device_cpu_only(self, temp_model_dir, mock_torch):
        """Testa detecção quando apenas CPU está disponível"""
        mock_torch.cuda.is_available.return_value = False
        
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        
        assert manager.device == "cpu"
        assert manager.compute_type == "int8"
    
    def test_detect_device_cuda_available(self, temp_model_dir, mock_torch):
        """Testa detecção quando GPU está disponível"""
        mock_torch.cuda.is_available.return_value = True
        
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        
        assert manager.device == "cuda"
        assert manager.compute_type == "float16"


class TestModelLoading:
    """Testes de carregamento do modelo"""
    
    def test_load_model_success(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa carregamento bem-sucedido do modelo"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        
        # Verifica que o modelo foi carregado
        assert manager.model is not None
        mock_whisper_model.assert_called_once_with(
            manager.model_name,
            device=manager.device,
            compute_type=manager.compute_type,
            download_root=str(temp_model_dir),
            num_workers=manager.num_workers
        )
    
    def test_load_model_already_loaded(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa que não recarrega modelo se já estiver carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        manager.load_model()  # Segunda chamada
        
        # Verifica que foi carregado apenas uma vez
        assert mock_whisper_model.call_count == 1


class TestModelUnloading:
    """Testes de descarregamento do modelo"""
    
    def test_unload_model_success(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa descarregamento bem-sucedido do modelo"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        manager.unload_model()
        
        # Verifica que o modelo foi descarregado
        assert manager.model is None
        mock_torch.cuda.empty_cache.assert_called_once()
    
    def test_unload_model_not_loaded(self, temp_model_dir, mock_torch):
        """Testa descarregamento quando modelo não está carregado"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.unload_model()  # Não deve dar erro
        
        assert manager.model is None


class TestTranscription:
    """Testes de transcrição de áudio"""
    
    def test_transcribe_success(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa transcrição bem-sucedida com word timestamps"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        
        # Executa transcrição
        segments, info = manager.transcribe(str(temp_model_dir / "test.ogg"))
        
        # Verifica que transcribe foi chamado com parâmetros corretos
        manager.model.transcribe.assert_called_once()
        call_kwargs = manager.model.transcribe.call_args[1]
        assert call_kwargs["word_timestamps"] is True
        assert call_kwargs["language"] == "pt"
        
        # Verifica resultados
        segments_list = list(segments)
        assert len(segments_list) == 1
        assert segments_list[0].text == "um dois três quatro"
        assert len(segments_list[0].words) == 4
        assert info.language == "pt"
    
    def test_transcribe_without_loading_model(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa que transcribe carrega o modelo automaticamente se necessário"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        # Não carrega o modelo explicitamente
        
        segments, info = manager.transcribe(str(temp_model_dir / "test.ogg"))
        
        # Verifica que o modelo foi carregado automaticamente
        assert manager.model is not None
        mock_whisper_model.assert_called_once()
    
    def test_transcribe_word_timestamps_detail(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa detalhes dos word timestamps"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        segments, info = manager.transcribe(str(temp_model_dir / "test.ogg"))
        
        segment = list(segments)[0]
        words = segment.words
        
        # Verifica cada palavra
        assert words[0].word == "um"
        assert words[0].start == 0.0
        assert words[0].end == 0.5
        assert words[0].probability >= 0.9
        
        assert words[1].word == "dois"
        assert words[2].word == "três"
        assert words[3].word == "quatro"


class TestErrorHandling:
    """Testes de tratamento de erros"""
    
    def test_load_model_failure(self, temp_model_dir, mock_torch):
        """Testa falha no carregamento do modelo"""
        with patch.object(fwm_module, 'WhisperModel', side_effect=Exception("Model not found")):
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            
            with pytest.raises(Exception, match="Model not found"):
                manager.load_model()
    
    def test_transcribe_failure(self, temp_model_dir, mock_torch):
        """Testa falha na transcrição"""
        with patch.object(fwm_module, 'WhisperModel') as mock:
            model_instance = MagicMock()
            model_instance.transcribe.side_effect = Exception("Transcription failed")
            mock.return_value = model_instance
            
            manager = FasterWhisperModelManager(model_dir=temp_model_dir)
            
            with pytest.raises(Exception, match="Transcription failed"):
                manager.transcribe("test.ogg")


class TestMemoryManagement:
    """Testes de gestão de memória"""
    
    def test_cuda_cache_cleared_on_unload(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa que o cache CUDA é limpo ao descarregar o modelo"""
        mock_torch.cuda.is_available.return_value = True
        
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        manager.load_model()
        manager.unload_model()
        
        # Verifica que empty_cache foi chamado
        mock_torch.cuda.empty_cache.assert_called()


class TestConfiguration:
    """Testes de configuração do manager"""
    
    def test_model_name_variations(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa diferentes nomes de modelo"""
        for model_name in ["tiny", "base", "small", "medium", "large-v2"]:
            manager = FasterWhisperModelManager(
                model_dir=temp_model_dir,
                model_name=model_name
            )
            manager.load_model()
            
            assert manager.model_name == model_name
    
    def test_compute_type_variations(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa diferentes compute types"""
        for compute_type in ["int8", "float16", "float32"]:
            manager = FasterWhisperModelManager(
                model_dir=temp_model_dir,
                compute_type=compute_type
            )
            
            assert manager.compute_type == compute_type


# ============================================================================
# Testes de Integração Leve (com mocks mínimos)
# ============================================================================

@pytest.mark.integration
class TestIntegrationLight:
    """Testes de integração leve (com mocks mínimos)"""
    
    def test_full_workflow(self, temp_model_dir, mock_torch, mock_whisper_model):
        """Testa workflow completo: init → load → transcribe → unload"""
        manager = FasterWhisperModelManager(model_dir=temp_model_dir)
        
        # Load
        manager.load_model()
        assert manager.model is not None
        
        # Transcribe
        segments, info = manager.transcribe("test.ogg")
        assert info.language == "pt"
        
        # Unload
        manager.unload_model()
        assert manager.model is None
