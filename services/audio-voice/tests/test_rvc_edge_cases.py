"""
Testes de edge cases RVC
Sprint 5 - Unit Tests Suite
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, AsyncMock

from app.rvc_client import RvcClient
from app.models import RvcParameters, RvcModel
from app.exceptions import RvcConversionException, RvcModelException


class TestRvcClientEdgeCases:
    """Testes de casos extremos no RvcClient"""
    
    @pytest.mark.asyncio
    async def test_empty_audio(self, mock_rvc_model, rvc_params_default):
        """Deve rejeitar áudio vazio"""
        client = RvcClient(device='cpu')
        empty_audio = np.array([], dtype=np.float32)
        
        with pytest.raises(RvcConversionException, match="empty"):
            await client.convert_audio(
                empty_audio, 24000, mock_rvc_model, rvc_params_default
            )
    
    @pytest.mark.asyncio
    async def test_very_short_audio(self, mock_rvc_model, rvc_params_default):
        """Deve processar áudio muito curto (0.1s)"""
        client = RvcClient(device='cpu')
        short_audio = np.random.randn(2400).astype(np.float32)  # 0.1s @ 24kHz
        
        # Mock VC para evitar erro
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(short_audio, None))
            
            result, duration = await client.convert_audio(
                short_audio, 24000, mock_rvc_model, rvc_params_default
            )
            
            assert result is not None
            assert duration > 0
    
    @pytest.mark.asyncio
    async def test_extreme_pitch_positive(self, sample_audio_3s, mock_rvc_model):
        """Deve aceitar pitch máximo (+12)"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        params = RvcParameters(pitch=12)  # Máximo
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            result, _ = await client.convert_audio(
                audio, sr, mock_rvc_model, params
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_extreme_pitch_negative(self, sample_audio_3s, mock_rvc_model):
        """Deve aceitar pitch mínimo (-12)"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        params = RvcParameters(pitch=-12)  # Mínimo
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            result, _ = await client.convert_audio(
                audio, sr, mock_rvc_model, params
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_model_file_not_found(self, tmp_path, rvc_params_default):
        """Deve falhar se arquivo .pth não existir"""
        client = RvcClient(device='cpu')
        
        # Modelo com path inexistente
        fake_model = RvcModel.create_new(
            name="Nonexistent",
            model_path="/tmp/nonexistent_model.pth",
            index_path=None
        )
        
        audio = np.random.randn(24000).astype(np.float32)
        
        with pytest.raises(RvcModelException, match="not found"):
            await client.convert_audio(
                audio, 24000, fake_model, rvc_params_default
            )
    
    @pytest.mark.asyncio
    async def test_model_without_index(self, mock_rvc_model_no_index, sample_audio_3s, rvc_params_default):
        """Deve funcionar sem arquivo .index (index_path=None)"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        # Deve processar sem erro (index é opcional)
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            result, _ = await client.convert_audio(
                audio, sr, mock_rvc_model_no_index, rvc_params_default
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_zero_sample_rate(self, mock_rvc_model, rvc_params_default):
        """Deve rejeitar sample rate inválido"""
        client = RvcClient(device='cpu')
        audio = np.random.randn(24000).astype(np.float32)
        
        # Sample rate zero é inválido
        with pytest.raises(Exception):  # Tipo de erro depende de implementação
            await client.convert_audio(
                audio, 0, mock_rvc_model, rvc_params_default
            )
    
    @pytest.mark.asyncio
    async def test_very_high_sample_rate(self, mock_rvc_model, rvc_params_default):
        """Deve processar sample rate muito alto (96kHz)"""
        client = RvcClient(device='cpu')
        
        sr = 96000
        duration = 1.0
        samples = int(sr * duration)
        audio = np.random.randn(samples).astype(np.float32) * 0.1
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            result, _ = await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_nan_values_in_audio(self, mock_rvc_model, rvc_params_default):
        """Deve tratar NaN no áudio"""
        client = RvcClient(device='cpu')
        
        audio = np.array([0.1, np.nan, 0.3, 0.4], dtype=np.float32)
        
        # Pode rejeitar ou limpar NaN dependendo de implementação
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            # Simula que RVC limpa NaN
            clean_audio = np.nan_to_num(audio)
            client._vc.vc_single = Mock(return_value=(clean_audio, None))
            
            result, _ = await client.convert_audio(
                audio, 24000, mock_rvc_model, rvc_params_default
            )
            
            assert not np.isnan(result).any()
    
    @pytest.mark.asyncio
    async def test_inf_values_in_audio(self, mock_rvc_model, rvc_params_default):
        """Deve tratar valores infinitos no áudio"""
        client = RvcClient(device='cpu')
        
        audio = np.array([0.1, np.inf, 0.3, -np.inf], dtype=np.float32)
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            clean_audio = np.clip(audio, -1.0, 1.0)
            client._vc.vc_single = Mock(return_value=(clean_audio, None))
            
            result, _ = await client.convert_audio(
                audio, 24000, mock_rvc_model, rvc_params_default
            )
            
            assert np.isfinite(result).all()


class TestRvcParametersEdgeCases:
    """Testes de edge cases nos RvcParameters"""
    
    def test_pitch_validation_min(self):
        """Deve aceitar pitch mínimo (-12)"""
        params = RvcParameters(pitch=-12)
        assert params.pitch == -12
    
    def test_pitch_validation_max(self):
        """Deve aceitar pitch máximo (+12)"""
        params = RvcParameters(pitch=12)
        assert params.pitch == 12
    
    def test_pitch_validation_out_of_range_positive(self):
        """Deve rejeitar pitch > 12"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            RvcParameters(pitch=13)
    
    def test_pitch_validation_out_of_range_negative(self):
        """Deve rejeitar pitch < -12"""
        with pytest.raises(Exception):
            RvcParameters(pitch=-13)
    
    def test_index_rate_zero(self):
        """Deve aceitar index_rate=0"""
        params = RvcParameters(index_rate=0.0)
        assert params.index_rate == 0.0
    
    def test_index_rate_one(self):
        """Deve aceitar index_rate=1"""
        params = RvcParameters(index_rate=1.0)
        assert params.index_rate == 1.0
    
    def test_index_rate_out_of_range(self):
        """Deve rejeitar index_rate > 1"""
        with pytest.raises(Exception):
            RvcParameters(index_rate=1.5)
    
    def test_protect_max(self):
        """Deve aceitar protect=0.5 (máximo)"""
        params = RvcParameters(protect=0.5)
        assert params.protect == 0.5
    
    def test_protect_out_of_range(self):
        """Deve rejeitar protect > 0.5"""
        with pytest.raises(Exception):
            RvcParameters(protect=0.6)
    
    def test_filter_radius_max(self):
        """Deve aceitar filter_radius=7 (máximo)"""
        params = RvcParameters(filter_radius=7)
        assert params.filter_radius == 7
    
    def test_filter_radius_out_of_range(self):
        """Deve rejeitar filter_radius > 7"""
        with pytest.raises(Exception):
            RvcParameters(filter_radius=8)
    
    def test_all_extreme_values(self, rvc_params_extreme):
        """Deve aceitar todos parâmetros nos limites"""
        assert rvc_params_extreme.pitch == 12
        assert rvc_params_extreme.index_rate == 1.0
        assert rvc_params_extreme.protect == 0.5
        assert rvc_params_extreme.rms_mix_rate == 1.0
        assert rvc_params_extreme.filter_radius == 7


class TestRvcClientCaching:
    """Testes de cache de modelos RVC"""
    
    @pytest.mark.asyncio
    async def test_model_cache_hit(self, mock_rvc_model, sample_audio_3s, rvc_params_default):
        """Deve reutilizar modelo em cache"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            # Primeira conversão
            await client.convert_audio(audio, sr, mock_rvc_model, rvc_params_default)
            
            # Segunda conversão com MESMO modelo
            await client.convert_audio(audio, sr, mock_rvc_model, rvc_params_default)
            
            # VC deve ser chamado 2x, mas modelo carregado 1x
            # (verificar via _current_model_id)
            assert client._current_model_id == mock_rvc_model.id
    
    @pytest.mark.asyncio
    async def test_model_cache_miss(self, tmp_path, sample_audio_3s, rvc_params_default):
        """Deve recarregar quando modelo diferente"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        # Cria dois modelos diferentes
        model1_path = tmp_path / "model1.pth"
        model2_path = tmp_path / "model2.pth"
        import torch
        torch.save({'weight': {}}, model1_path)
        torch.save({'weight': {}}, model2_path)
        
        model1 = RvcModel.create_new("Model1", str(model1_path))
        model2 = RvcModel.create_new("Model2", str(model2_path))
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            # Conversão com model1
            await client.convert_audio(audio, sr, model1, rvc_params_default)
            first_id = client._current_model_id
            
            # Conversão com model2 (cache miss)
            await client.convert_audio(audio, sr, model2, rvc_params_default)
            second_id = client._current_model_id
            
            assert first_id != second_id
    
    def test_clear_cache(self, mock_rvc_model):
        """Deve limpar cache de modelo"""
        client = RvcClient(device='cpu')
        
        client._current_model_id = mock_rvc_model.id
        client._cached_model = "fake_model"
        
        client.clear_cache()
        
        assert client._current_model_id is None
        assert client._cached_model is None
    
    def test_unload_releases_memory(self):
        """Deve liberar memória ao descarregar"""
        client = RvcClient(device='cpu')
        
        # Simula VC carregado
        client._vc = Mock()
        client._current_model_id = "test123"
        
        client.unload()
        
        assert client._vc is None
        assert client._current_model_id is None


@pytest.mark.slow
class TestRvcClientPerformance:
    """Testes de performance (marcados como slow)"""
    
    @pytest.mark.asyncio
    async def test_large_audio_processing(self, mock_rvc_model, rvc_params_default):
        """Deve processar áudio longo (60s)"""
        client = RvcClient(device='cpu')
        
        # 60s @ 24kHz
        sr = 24000
        duration = 60.0
        samples = int(sr * duration)
        audio = np.random.randn(samples).astype(np.float32) * 0.1
        
        with patch.object(client, '_load_vc'):
            client._vc = Mock()
            client._vc.vc_single = Mock(return_value=(audio, None))
            
            import time
            start = time.time()
            
            result, _ = await client.convert_audio(
                audio, sr, mock_rvc_model, rvc_params_default
            )
            
            elapsed = time.time() - start
            
            assert result is not None
            # Performance check (mock deve ser rápido)
            assert elapsed < 5.0  # Mock não deve demorar


@pytest.mark.integration
class TestRvcXttsIntegrationEdgeCases:
    """Edge cases na integração XTTS + RVC"""
    
    @pytest.mark.asyncio
    async def test_xtts_generates_silence_then_rvc(self, mock_rvc_model, rvc_params_default):
        """RVC deve processar silêncio gerado por XTTS"""
        from app.xtts_client import XTTSClient
        
        client = XTTSClient(device='cpu')
        
        # Simula XTTS gerando silêncio
        silence = np.zeros(24000, dtype=np.float32)
        
        with patch.object(client, '_load_rvc_client'):
            client.rvc_client = Mock()
            client.rvc_client.convert_audio = AsyncMock(
                return_value=(silence, 1.0)
            )
            
            with patch.object(client.tts, 'tts_to_file'):
                with patch('soundfile.read') as mock_read:
                    mock_read.return_value = (silence, 24000)
                    
                    audio_bytes, duration = await client.generate_dubbing(
                        text="Test",
                        language="en",
                        enable_rvc=True,
                        rvc_model=mock_rvc_model,
                        rvc_params=rvc_params_default
                    )
                    
                    assert len(audio_bytes) > 0
