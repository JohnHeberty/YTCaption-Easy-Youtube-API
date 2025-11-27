"""
Testes de integração XTTS + RVC
Sprint 4 - Red Phase (TDD)
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import numpy as np
import torch
import tempfile
from pathlib import Path

from app.xtts_client import XTTSClient
from app.models import RvcModel, RvcParameters, QualityProfile, Job, JobMode, JobStatus


@pytest.fixture
def mock_rvc_model(tmp_path):
    """Cria modelo RVC falso para testes"""
    model_path = tmp_path / "test.pth"
    torch.save({'weight': {}}, model_path)
    
    index_path = tmp_path / "test.index"
    index_path.write_text("fake index")
    
    return RvcModel.create_new(
        name="Test Voice",
        model_path=str(model_path),
        index_path=str(index_path),
        description="Test model"
    )


@pytest.fixture
def default_rvc_params():
    """Parâmetros RVC padrão para testes"""
    return RvcParameters(
        pitch=0,
        index_rate=0.75,
        f0_method='rmvpe',
        protect=0.33
    )


@pytest.fixture
def sample_audio():
    """Áudio sintético para testes (3 segundos, 24kHz)"""
    sample_rate = 24000
    duration = 3.0
    samples = int(sample_rate * duration)
    
    # Onda senoidal
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t) * 0.3
    
    return audio.astype(np.float32), sample_rate


class TestXTTSClientRvcIntegration:
    """Testes de integração XTTS + RVC no XTTSClient"""
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_without_rvc(self):
        """Deve funcionar sem RVC (backward compatibility)"""
        client = XTTSClient(device='cpu')
        
        # Mock do método tts_to_file
        with patch.object(client.tts, 'tts_to_file') as mock_tts:
            # Cria arquivo temporário fake
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                import soundfile as sf
                sf.write(tmp.name, np.random.randn(24000), 24000)
                tmp_path = tmp.name
            
            mock_tts.return_value = None  # tts_to_file retorna None, grava no arquivo
            
            # Mock sf.read para retornar áudio
            with patch('soundfile.read') as mock_read:
                mock_read.return_value = (np.random.randn(24000), 24000)
                
                audio_bytes, duration = await client.generate_dubbing(
                    text="Test without RVC",
                    language="en",
                    enable_rvc=False
                )
                
                assert len(audio_bytes) > 0
                assert duration > 0
                assert client.rvc_client is None  # Não deve ter carregado RVC
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_with_rvc_enabled(self, mock_rvc_model, default_rvc_params, sample_audio):
        """Deve aplicar RVC quando enable_rvc=True"""
        client = XTTSClient(device='cpu')
        
        audio_data, sr = sample_audio
        
        # Mock RVC client
        with patch.object(client, '_load_rvc_client') as mock_load:
            client.rvc_client = Mock()
            client.rvc_client.convert_audio = AsyncMock(
                return_value=(np.random.randn(24000), 1.0)
            )
            
            # Mock XTTS generation
            with patch.object(client.tts, 'tts_to_file'):
                with patch('soundfile.read') as mock_read:
                    mock_read.return_value = (audio_data, sr)
                    
                    audio_bytes, duration = await client.generate_dubbing(
                        text="Test with RVC",
                        language="en",
                        enable_rvc=True,
                        rvc_model=mock_rvc_model,
                        rvc_params=default_rvc_params
                    )
                    
                    # Deve ter chamado RVC
                    mock_load.assert_called_once()
                    client.rvc_client.convert_audio.assert_called_once()
                    
                    # Verifica argumentos da chamada RVC
                    call_args = client.rvc_client.convert_audio.call_args
                    assert np.array_equal(call_args[0][0], audio_data)  # audio_data
                    assert call_args[0][1] == sr  # sample_rate
                    assert call_args[0][2] == mock_rvc_model  # rvc_model
                    assert call_args[0][3] == default_rvc_params  # rvc_params
    
    @pytest.mark.asyncio
    async def test_rvc_fallback_on_error(self, mock_rvc_model, default_rvc_params, sample_audio):
        """Deve fazer fallback para XTTS se RVC falhar"""
        client = XTTSClient(device='cpu')
        
        audio_data, sr = sample_audio
        
        with patch.object(client, '_load_rvc_client'):
            client.rvc_client = Mock()
            # RVC lança erro
            client.rvc_client.convert_audio = AsyncMock(
                side_effect=Exception("RVC conversion failed")
            )
            
            with patch.object(client.tts, 'tts_to_file'):
                with patch('soundfile.read') as mock_read:
                    mock_read.return_value = (audio_data, sr)
                    
                    # Não deve lançar exceção
                    audio_bytes, duration = await client.generate_dubbing(
                        text="Test fallback",
                        language="en",
                        enable_rvc=True,
                        rvc_model=mock_rvc_model,
                        rvc_params=default_rvc_params
                    )
                    
                    # Deve ter retornado áudio XTTS puro
                    assert len(audio_bytes) > 0
                    assert duration > 0
    
    @pytest.mark.asyncio
    async def test_rvc_lazy_loading(self, mock_rvc_model, default_rvc_params):
        """RVC client deve ser carregado apenas quando necessário (lazy)"""
        client = XTTSClient(device='cpu')
        
        assert client.rvc_client is None
        
        with patch('app.xtts_client.RvcClient') as MockRvcClient:
            mock_instance = Mock()
            MockRvcClient.return_value = mock_instance
            
            client._load_rvc_client()
            
            assert client.rvc_client is not None
            MockRvcClient.assert_called_once_with(
                device='cpu',
                fallback_to_cpu=True
            )
    
    @pytest.mark.asyncio
    async def test_rvc_idempotent_loading(self):
        """Carregar RVC múltiplas vezes não deve recriar instância"""
        client = XTTSClient(device='cpu')
        
        with patch('app.xtts_client.RvcClient') as MockRvcClient:
            mock_instance = Mock()
            MockRvcClient.return_value = mock_instance
            
            client._load_rvc_client()
            first_instance = client.rvc_client
            
            client._load_rvc_client()
            second_instance = client.rvc_client
            
            assert first_instance is second_instance
            assert MockRvcClient.call_count == 1  # Só criou uma vez
    
    @pytest.mark.asyncio
    async def test_rvc_without_model_raises_warning(self, default_rvc_params):
        """Se enable_rvc=True mas sem rvc_model, deve logar warning e usar XTTS puro"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client.tts, 'tts_to_file'):
            with patch('soundfile.read') as mock_read:
                mock_read.return_value = (np.random.randn(24000), 24000)
                
                with patch('app.xtts_client.logger') as mock_logger:
                    audio_bytes, duration = await client.generate_dubbing(
                        text="Test",
                        language="en",
                        enable_rvc=True,
                        rvc_model=None,  # SEM modelo
                        rvc_params=default_rvc_params
                    )
                    
                    # Deve ter logado warning
                    mock_logger.warning.assert_called()
                    assert "RVC enabled but no model provided" in str(mock_logger.warning.call_args)
                    
                    # Não deve ter carregado RVC
                    assert client.rvc_client is None


class TestProcessorRvcIntegration:
    """Testes de integração RVC no VoiceProcessor"""
    
    @pytest.mark.asyncio
    async def test_process_dubbing_job_with_rvc(self, mock_rvc_model, default_rvc_params):
        """Processor deve passar parâmetros RVC para XTTS client"""
        from app.processor import VoiceProcessor
        
        processor = VoiceProcessor(lazy_load=True)
        processor._load_engine()  # Força carregar engine
        
        job = Job(
            id="test_rvc_123",
            mode=JobMode.DUBBING,
            status=JobStatus.PENDING,
            text="Test with RVC",
            source_language="en",
            # Parâmetros RVC
            enable_rvc=True,
            rvc_model_id=mock_rvc_model.id,
            rvc_pitch=2,
            rvc_index_rate=0.8,
            rvc_f0_method='rmvpe',
            rvc_protect=0.35
        )
        
        with patch.object(processor.engine, 'generate_dubbing') as mock_gen:
            mock_gen.return_value = (b'fake_audio_data', 1.5)
            
            result = await processor.process_dubbing_job(job)
            
            # Verifica que chamou com parâmetros RVC
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args[1]
            
            assert call_kwargs['enable_rvc'] is True
            assert call_kwargs['rvc_model'].id == mock_rvc_model.id
            assert call_kwargs['rvc_params'].pitch == 2
            assert call_kwargs['rvc_params'].index_rate == 0.8
            assert call_kwargs['rvc_params'].f0_method == 'rmvpe'
            assert call_kwargs['rvc_params'].protect == 0.35
    
    @pytest.mark.asyncio
    async def test_process_dubbing_job_without_rvc_backward_compat(self):
        """Jobs antigos sem RVC devem funcionar (backward compatibility)"""
        from app.processor import VoiceProcessor
        
        processor = VoiceProcessor(lazy_load=True)
        processor._load_engine()
        
        job = Job(
            id="test_legacy_456",
            mode=JobMode.DUBBING,
            status=JobStatus.PENDING,
            text="Test legacy",
            source_language="en"
            # SEM parâmetros RVC
        )
        
        with patch.object(processor.engine, 'generate_dubbing') as mock_gen:
            mock_gen.return_value = (b'fake_audio', 1.0)
            
            result = await processor.process_dubbing_job(job)
            
            # Deve ter chamado sem RVC
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs.get('enable_rvc', False) is False
            assert call_kwargs.get('rvc_model') is None
    
    @pytest.mark.asyncio
    async def test_processor_loads_rvc_model_from_id(self, mock_rvc_model):
        """Processor deve carregar modelo RVC a partir do rvc_model_id"""
        from app.processor import VoiceProcessor
        
        processor = VoiceProcessor(lazy_load=True)
        processor._load_engine()
        
        # Mock model store
        processor.rvc_model_store = Mock()
        processor.rvc_model_store.get_model.return_value = mock_rvc_model
        
        job = Job(
            id="test789",
            mode=JobMode.DUBBING,
            status=JobStatus.PENDING,
            text="Test",
            source_language="en",
            enable_rvc=True,
            rvc_model_id=mock_rvc_model.id
        )
        
        with patch.object(processor.engine, 'generate_dubbing') as mock_gen:
            mock_gen.return_value = (b'audio', 1.0)
            
            result = await processor.process_dubbing_job(job)
            
            # Deve ter buscado modelo pelo ID
            processor.rvc_model_store.get_model.assert_called_once_with(mock_rvc_model.id)
            
            # Deve ter passado modelo carregado
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs['rvc_model'] == mock_rvc_model


class TestBackwardCompatibility:
    """Testes de compatibilidade retroativa"""
    
    @pytest.mark.asyncio
    async def test_old_code_still_works(self):
        """Código antigo sem RVC deve continuar funcionando"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client.tts, 'tts_to_file'):
            with patch('soundfile.read') as mock_read:
                mock_read.return_value = (np.random.randn(24000), 24000)
                
                # Chamada antiga (sem parâmetros RVC)
                audio_bytes, duration = await client.generate_dubbing(
                    text="Legacy call",
                    language="en"
                )
                
                assert len(audio_bytes) > 0
                assert client.rvc_client is None
    
    @pytest.mark.asyncio
    async def test_parameters_optional(self):
        """Todos parâmetros RVC devem ser opcionais"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client.tts, 'tts_to_file'):
            with patch('soundfile.read') as mock_read:
                mock_read.return_value = (np.random.randn(24000), 24000)
                
                # Deve aceitar enable_rvc sem outros parâmetros
                audio_bytes, duration = await client.generate_dubbing(
                    text="Test",
                    language="en",
                    enable_rvc=False  # Explicitamente desabilitado
                )
                
                assert len(audio_bytes) > 0
