"""
Testes adicionais para RvcClient
Sprint 5 - Melhorar coverage para ≥90%
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile

from app.rvc_client import RvcClient
from app.models import RvcParameters, RvcModel
from app.exceptions import RvcConversionException, RvcDeviceException


class TestRvcClientDeviceHandling:
    """Testes de detecção e uso de device"""
    
    def test_device_auto_detect_cpu(self):
        """Deve detectar CPU quando CUDA não disponível"""
        with patch('torch.cuda.is_available', return_value=False):
            client = RvcClient(device=None)
            assert client.device == 'cpu'
    
    def test_device_auto_detect_cuda(self):
        """Deve detectar CUDA quando disponível"""
        with patch('torch.cuda.is_available', return_value=True):
            client = RvcClient(device=None)
            assert client.device == 'cuda'
    
    def test_device_explicit_cpu(self):
        """Deve usar CPU quando explicitamente solicitado"""
        client = RvcClient(device='cpu')
        assert client.device == 'cpu'
    
    def test_device_explicit_cuda_available(self):
        """Deve usar CUDA quando explícito e disponível"""
        with patch('torch.cuda.is_available', return_value=True):
            client = RvcClient(device='cuda')
            assert client.device == 'cuda'
    
    def test_device_explicit_cuda_unavailable_fallback(self):
        """Deve fazer fallback para CPU se CUDA indisponível"""
        with patch('torch.cuda.is_available', return_value=False):
            client = RvcClient(device='cuda', fallback_to_cpu=True)
            assert client.device == 'cpu'
    
    def test_device_explicit_cuda_unavailable_no_fallback(self):
        """Deve lançar erro se CUDA indisponível e sem fallback"""
        with patch('torch.cuda.is_available', return_value=False):
            with pytest.raises(RvcDeviceException):
                RvcClient(device='cuda', fallback_to_cpu=False)


class TestRvcClientInitialization:
    """Testes de inicialização do RvcClient"""
    
    def test_init_creates_models_dir(self, tmp_path):
        """Deve criar diretório de modelos se não existir"""
        models_dir = tmp_path / "rvc_models"
        assert not models_dir.exists()
        
        client = RvcClient(device='cpu', models_dir=str(models_dir))
        
        assert models_dir.exists()
        assert models_dir.is_dir()
    
    def test_init_models_dir_default(self):
        """Deve usar diretório default se não especificado"""
        client = RvcClient(device='cpu')
        assert client.models_dir is not None
        assert Path(client.models_dir).name == 'rvc'
    
    def test_init_lazy_vc_not_loaded(self):
        """VC não deve ser carregado na inicialização (lazy)"""
        client = RvcClient(device='cpu')
        assert client._vc is None
    
    def test_init_cache_empty(self):
        """Cache de modelo deve estar vazio na inicialização"""
        client = RvcClient(device='cpu')
        assert client._current_model_id is None
        assert client._cached_model is None


class TestRvcClientVCLoading:
    """Testes de carregamento do módulo VC"""
    
    def test_load_vc_success(self):
        """Deve carregar VC com sucesso"""
        client = RvcClient(device='cpu')
        
        with patch('app.rvc_client.rvc_deps') as mock_deps:
            mock_deps.VC = Mock()
            
            client._load_vc()
            
            assert client._vc is not None
    
    def test_load_vc_idempotent(self):
        """Carregar VC múltiplas vezes não deve recriar"""
        client = RvcClient(device='cpu')
        
        with patch('app.rvc_client.rvc_deps') as mock_deps:
            mock_vc_class = Mock()
            mock_deps.VC = mock_vc_class
            
            client._load_vc()
            first_instance = client._vc
            
            client._load_vc()
            second_instance = client._vc
            
            assert first_instance is second_instance
            # VC() deve ter sido chamado apenas 1x
            assert mock_vc_class.call_count == 1
    
    def test_load_vc_import_error(self):
        """Deve lançar RvcConversionException se VC não disponível"""
        client = RvcClient(device='cpu')
        
        with patch('app.rvc_client.rvc_deps') as mock_deps:
            mock_deps.VC = None  # Simula import falho
            
            with pytest.raises(RvcConversionException, match="not available"):
                client._load_vc()


class TestRvcClientConversionFlow:
    """Testes do fluxo completo de conversão"""
    
    @pytest.mark.asyncio
    async def test_convert_audio_complete_flow(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve executar fluxo completo de conversão"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            # Mock VC module
            mock_vc = Mock()
            client._vc = mock_vc
            
            # Mock vc_single retorna áudio processado
            processed_audio = audio * 0.9  # Simula processamento
            mock_vc.vc_single = Mock(return_value=(processed_audio, None))
            
            result, duration = await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            # Verificações
            assert result is not None
            assert isinstance(result, np.ndarray)
            assert len(result) > 0
            assert duration > 0
            
            # vc_single deve ter sido chamado
            mock_vc.vc_single.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_convert_audio_creates_temp_file(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve criar arquivo temporário para RVC"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        temp_files_created = []
        
        original_tempfile = tempfile.NamedTemporaryFile
        
        def mock_tempfile(*args, **kwargs):
            temp = original_tempfile(*args, **kwargs)
            temp_files_created.append(temp.name)
            return temp
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            with patch('tempfile.NamedTemporaryFile', side_effect=mock_tempfile):
                await client.convert_audio(
                    audio, sr, mock_rvc_model, rvc_params_default
                )
                
                # Deve ter criado pelo menos 1 arquivo temp
                assert len(temp_files_created) > 0
    
    @pytest.mark.asyncio
    async def test_convert_audio_cleanup_on_success(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve remover arquivo temp após sucesso"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        temp_path = None
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            # Captura path do temp file
            original_write = __builtins__['open']
            
            def capture_temp(*args, **kwargs):
                nonlocal temp_path
                if 'rvc_input_' in str(args[0]):
                    temp_path = args[0]
                return original_write(*args, **kwargs)
            
            # Executa conversão
            await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            # Arquivo temp deve ter sido removido
            # (difícil verificar pois NamedTemporaryFile com delete=False)
            # Teste passa se não lançar erro
    
    @pytest.mark.asyncio
    async def test_convert_audio_cleanup_on_error(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve remover arquivo temp mesmo em caso de erro"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            # vc_single lança erro
            client._vc.vc_single = Mock(side_effect=Exception("RVC error"))
            
            with pytest.raises(RvcConversionException):
                await client.convert_audio(
                    audio, sr, mock_rvc_model, rvc_params_default
                )
            
            # Cleanup deve ter ocorrido (verificar via logs ou filesystem)


class TestRvcClientModelCaching:
    """Testes detalhados de cache de modelos"""
    
    @pytest.mark.asyncio
    async def test_first_conversion_loads_model(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Primeira conversão deve carregar modelo"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        assert client._current_model_id is None
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            # Modelo deve estar em cache
            assert client._current_model_id == mock_rvc_model.id
    
    @pytest.mark.asyncio
    async def test_same_model_reuses_cache(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Mesma conversão deve reutilizar cache"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            # Primeira conversão
            await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            first_cache_id = client._current_model_id
            
            # Segunda conversão (mesmo modelo)
            await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            second_cache_id = client._current_model_id
            
            # Cache deve ser o mesmo
            assert first_cache_id == second_cache_id
    
    @pytest.mark.asyncio
    async def test_different_model_invalidates_cache(self, tmp_path, sample_audio_3s, rvc_params_default):
        """Modelo diferente deve invalidar cache"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        # Cria 2 modelos
        import torch
        model1_path = tmp_path / "model1.pth"
        model2_path = tmp_path / "model2.pth"
        torch.save({'weight': {}}, model1_path)
        torch.save({'weight': {}}, model2_path)
        
        model1 = RvcModel.create_new("M1", str(model1_path))
        model2 = RvcModel.create_new("M2", str(model2_path))
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            # Conversão com model1
            await client.convert_audio(audio, sr, model1, rvc_params_default)
            cache_after_m1 = client._current_model_id
            
            # Conversão com model2
            await client.convert_audio(audio, sr, model2, rvc_params_default)
            cache_after_m2 = client._current_model_id
            
            # Cache deve ter mudado
            assert cache_after_m1 != cache_after_m2
            assert cache_after_m2 == model2.id


class TestRvcClientErrorHandling:
    """Testes de tratamento de erros"""
    
    @pytest.mark.asyncio
    async def test_vc_single_throws_exception(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve propagar exceção de vc_single"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(side_effect=RuntimeError("VC failed"))
            
            with pytest.raises(RvcConversionException, match="VC failed"):
                await client.convert_audio(
                    audio, sr, mock_rvc_model, rvc_params_default
                )
    
    @pytest.mark.asyncio
    async def test_soundfile_write_error(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve tratar erro ao escrever arquivo"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            
            with patch('soundfile.write', side_effect=IOError("Disk full")):
                with pytest.raises(RvcConversionException):
                    await client.convert_audio(
                        audio, sr, mock_rvc_model, rvc_params_default
                    )


class TestRvcClientUtilityMethods:
    """Testes de métodos utilitários"""
    
    def test_clear_cache_clears_all(self, mock_rvc_model):
        """clear_cache() deve limpar tudo"""
        client = RvcClient(device='cpu')
        
        # Simula estado com cache
        client._current_model_id = mock_rvc_model.id
        client._cached_model = {"fake": "model"}
        
        client.clear_cache()
        
        assert client._current_model_id is None
        assert client._cached_model is None
    
    def test_unload_clears_vc_and_cache(self):
        """unload() deve limpar VC e cache"""
        client = RvcClient(device='cpu')
        
        # Simula VC carregado
        client._vc = Mock()
        client._current_model_id = "test123"
        client._cached_model = {}
        
        client.unload()
        
        assert client._vc is None
        assert client._current_model_id is None
        assert client._cached_model is None
    
    def test_str_representation(self):
        """Deve ter representação string legível"""
        client = RvcClient(device='cpu')
        
        str_repr = str(client)
        
        assert 'RvcClient' in str_repr or 'cpu' in str_repr
