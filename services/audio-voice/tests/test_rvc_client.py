"""
Testes unitários para RVC Client
Sprint 3: RVC Client Implementation
"""
import pytest
import numpy as np
import torch
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import tempfile
import os

from app.models import RvcModel, RvcParameters
from app.exceptions import RvcConversionException, RvcModelException, RvcDeviceException


@pytest.fixture
def sample_audio():
    """Fixture de áudio sintético (3s, 24kHz)"""
    sample_rate = 24000
    duration = 3.0
    samples = int(sample_rate * duration)
    audio = np.random.randn(samples).astype(np.float32) * 0.1
    return audio, sample_rate


@pytest.fixture
def mock_rvc_model(tmp_path):
    """Fixture de modelo RVC mock"""
    model_path = tmp_path / "test_model.pth"
    
    # Cria modelo PyTorch fake
    checkpoint = {
        'weight': {'generator': {}},
        'config': {'sample_rate': 24000, 'version': 'v2'},
        'info': 'test_model'
    }
    torch.save(checkpoint, model_path)
    
    index_path = tmp_path / "test_model.index"
    index_path.write_text("fake_index_data")
    
    return RvcModel.create_new(
        name="Test Model",
        model_path=str(model_path),
        index_path=str(index_path),
        description="Test model for unit tests"
    )


@pytest.fixture
def default_rvc_params():
    """Fixture de parâmetros RVC padrão"""
    return RvcParameters()


class TestRvcClientInitialization:
    """Testes de inicialização do RvcClient"""
    
    def test_init_default_device(self):
        """Deve auto-detectar device (cuda ou cpu)"""
        from app.rvc_client import RvcClient
        client = RvcClient()
        assert client.device in ['cuda', 'cpu']
    
    def test_init_explicit_cuda(self):
        """Deve aceitar device='cuda' se disponível"""
        from app.rvc_client import RvcClient
        if torch.cuda.is_available():
            client = RvcClient(device='cuda')
            assert client.device == 'cuda'
    
    def test_init_explicit_cpu(self):
        """Deve aceitar device='cpu' sempre"""
        from app.rvc_client import RvcClient
        client = RvcClient(device='cpu')
        assert client.device == 'cpu'
    
    def test_init_cuda_fallback_to_cpu(self):
        """Deve fazer fallback para CPU se CUDA não disponível"""
        from app.rvc_client import RvcClient
        with patch('torch.cuda.is_available', return_value=False):
            client = RvcClient(device='cuda', fallback_to_cpu=True)
            assert client.device == 'cpu'
    
    def test_init_cuda_no_fallback_raises(self):
        """Deve lançar erro se CUDA não disponível e fallback desabilitado"""
        from app.rvc_client import RvcClient
        with patch('torch.cuda.is_available', return_value=False):
            with pytest.raises(RvcDeviceException, match="CUDA requested but not available"):
                RvcClient(device='cuda', fallback_to_cpu=False)
    
    def test_init_creates_models_dir(self, tmp_path):
        """Deve criar diretório de modelos se não existir"""
        from app.rvc_client import RvcClient
        models_dir = tmp_path / "rvc_models"
        assert not models_dir.exists()
        
        client = RvcClient(models_dir=str(models_dir))
        assert models_dir.exists()
    
    def test_lazy_load_vc_initially_none(self):
        """VC module deve ser None inicialmente (lazy load)"""
        from app.rvc_client import RvcClient
        client = RvcClient()
        assert client._vc is None


class TestRvcClientLazyLoading:
    """Testes de lazy loading do módulo VC"""
    
    def test_load_vc_module(self):
        """Deve carregar módulo VC sob demanda"""
        from app.rvc_client import RvcClient
        client = RvcClient()
        assert client._vc is None
        
        client._load_vc()
        
        assert client._vc is not None
    
    def test_load_vc_only_once(self):
        """Deve carregar VC apenas uma vez (idempotente)"""
        from app.rvc_client import RvcClient
        client = RvcClient()
        
        client._load_vc()
        vc_first = client._vc
        
        client._load_vc()
        vc_second = client._vc
        
        assert vc_first is vc_second


class TestRvcClientConversion:
    """Testes de conversão de áudio"""
    
    @pytest.mark.asyncio
    async def test_convert_audio_basic(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve converter áudio básico com sucesso"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        # Mock do vc.vc_single
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.get_vc = Mock()
            client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            converted_audio, duration = await client.convert_audio(
                audio_data=audio_data,
                sample_rate=sample_rate,
                rvc_model=mock_rvc_model,
                params=default_rvc_params
            )
            
            assert isinstance(converted_audio, np.ndarray)
            assert duration > 0
            assert duration == pytest.approx(3.0, abs=0.1)
    
    @pytest.mark.asyncio
    async def test_convert_audio_loads_vc_if_needed(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve carregar VC automaticamente se não carregado"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        assert client._vc is None
        
        # Mock
        with patch.object(client, '_load_vc') as mock_load:
            client._vc = Mock()
            client._vc.get_vc = Mock()
            client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
            
            # Deve ter chamado _load_vc
            mock_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_convert_audio_validates_empty_audio(self, mock_rvc_model, default_rvc_params):
        """Deve lançar erro para áudio vazio"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        empty_audio = np.array([])
        
        with pytest.raises(RvcConversionException, match="Audio data is empty"):
            await client.convert_audio(empty_audio, 24000, mock_rvc_model, default_rvc_params)
    
    @pytest.mark.asyncio
    async def test_convert_audio_handles_extreme_pitch(self, sample_audio, mock_rvc_model):
        """Deve aceitar valores extremos de pitch (+12, -12)"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.get_vc = Mock()
            client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            # Pitch +12
            params_high = RvcParameters(pitch=12)
            result = await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params_high)
            assert result is not None
            
            # Pitch -12
            params_low = RvcParameters(pitch=-12)
            result = await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params_low)
            assert result is not None


class TestRvcClientModelCaching:
    """Testes de caching de modelos"""
    
    @pytest.mark.asyncio
    async def test_model_caching_on_first_use(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve cachear modelo na primeira conversão"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            mock_get_vc = Mock()
            client._vc.get_vc = mock_get_vc
            client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            # Primeira conversão
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
            
            # get_vc deve ter sido chamado para carregar modelo
            assert mock_get_vc.call_count == 1
    
    @pytest.mark.asyncio
    async def test_model_cache_reuse(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve reutilizar modelo cacheado em conversões subsequentes"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            mock_get_vc = Mock()
            client._vc.get_vc = mock_get_vc
            client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            # Primeira conversão
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
            
            # Segunda conversão com mesmo modelo
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
            
            # get_vc deve ter sido chamado apenas 1 vez (cache hit na segunda)
            assert mock_get_vc.call_count == 1


class TestRvcClientCleanup:
    """Testes de limpeza de recursos"""
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve limpar arquivo temporário após conversão bem-sucedida"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        temp_file_path = None
        
        def mock_write(path, data, sr):
            nonlocal temp_file_path
            temp_file_path = path
            # Cria arquivo real
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("fake audio data")
        
        with patch('soundfile.write', side_effect=mock_write):
            with patch.object(client, '_load_vc'):
                client._vc = Mock()
                client._vc.get_vc = Mock()
                client._vc.vc_single = Mock(return_value=(sample_rate, audio_data))
                
                await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
        
        # Arquivo temp deve ter sido deletado
        if temp_file_path:
            assert not Path(temp_file_path).exists()
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_error(self, sample_audio, mock_rvc_model, default_rvc_params):
        """Deve limpar arquivo temporário mesmo em caso de erro"""
        from app.rvc_client import RvcClient
        
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        temp_file_path = None
        
        def mock_write(path, data, sr):
            nonlocal temp_file_path
            temp_file_path = path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("fake audio data")
        
        with patch('soundfile.write', side_effect=mock_write):
            with patch.object(client, '_load_vc'):
                client._vc = Mock()
                client._vc.get_vc = Mock()
                # Simula erro na conversão
                client._vc.vc_single = Mock(side_effect=Exception("Conversion failed"))
                
                with pytest.raises(RvcConversionException):
                    await client.convert_audio(audio_data, sample_rate, mock_rvc_model, default_rvc_params)
        
        # Arquivo temp deve ter sido deletado mesmo com erro
        if temp_file_path:
            assert not Path(temp_file_path).exists()
