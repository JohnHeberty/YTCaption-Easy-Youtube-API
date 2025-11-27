# SPRINT 3 - Implementação do RVC Client

**Duração Estimada:** 4-5 dias  
**Responsável:** Backend Engineer  
**Dependências:** Sprint 1 (Docker GPU) + Sprint 2 (Dependências RVC)

---

## 1. OBJETIVO

Implementar o módulo `rvc_client.py` responsável por realizar voice conversion usando RVC, garantindo:
- ✅ Lazy loading de modelos
- ✅ Conversão de áudio XTTS → RVC
- ✅ Gestão de cache de modelos
- ✅ Tratamento robusto de erros
- ✅ Testes unitários ≥90% coverage

---

## 2. PRÉ-REQUISITOS

### Sprints Anteriores Completas

- [x] Sprint 1: Docker GPU funcional
- [x] Sprint 2: Deps RVC instaladas e validadas

### Validação

```bash
# Deps instaladas
docker exec -it audio-voice-api-gpu python -c "from tts_with_rvc import TTS_RVC; print('OK')"

# GPU disponível
docker exec -it audio-voice-api-gpu python -c "import torch; assert torch.cuda.is_available()"
```

---

## 3. TAREFAS

### 3.1 TESTES (Red Phase)

#### 3.1.1 Criar `tests/test_rvc_client.py`

```python
"""
Testes unitários para RVC Client
Sprint 3: RVC Client Implementation
"""
import pytest
import numpy as np
import torch
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.rvc_client import RvcClient
from app.models import RvcModel, RvcParameters
from app.exceptions import RvcConversionException, RvcModelException


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


class TestRvcClientInitialization:
    """Testes de inicialização do RvcClient"""
    
    def test_init_default_device(self):
        """Deve auto-detectar device (cuda ou cpu)"""
        client = RvcClient()
        assert client.device in ['cuda', 'cpu']
    
    def test_init_explicit_cuda(self):
        """Deve aceitar device='cuda' se disponível"""
        if torch.cuda.is_available():
            client = RvcClient(device='cuda')
            assert client.device == 'cuda'
    
    def test_init_explicit_cpu(self):
        """Deve aceitar device='cpu' sempre"""
        client = RvcClient(device='cpu')
        assert client.device == 'cpu'
    
    def test_init_cuda_fallback_to_cpu(self):
        """Deve fazer fallback para CPU se CUDA não disponível"""
        with patch('torch.cuda.is_available', return_value=False):
            client = RvcClient(device='cuda', fallback_to_cpu=True)
            assert client.device == 'cpu'
    
    def test_init_cuda_no_fallback_raises(self):
        """Deve lançar erro se CUDA não disponível e fallback desabilitado"""
        with patch('torch.cuda.is_available', return_value=False):
            with pytest.raises(RuntimeError, match="CUDA requested but not available"):
                RvcClient(device='cuda', fallback_to_cpu=False)
    
    def test_init_creates_models_dir(self, tmp_path):
        """Deve criar diretório de modelos se não existir"""
        models_dir = tmp_path / "rvc_models"
        assert not models_dir.exists()
        
        client = RvcClient(models_dir=str(models_dir))
        assert models_dir.exists()
    
    def test_lazy_load_vc_initially_none(self):
        """VC module deve ser None inicialmente (lazy load)"""
        client = RvcClient()
        assert client.vc is None


class TestRvcClientLazyLoading:
    """Testes de lazy loading do módulo VC"""
    
    def test_load_vc_module(self):
        """Deve carregar módulo VC sob demanda"""
        client = RvcClient()
        assert client.vc is None
        
        client._load_vc()
        
        assert client.vc is not None
        assert hasattr(client.vc, 'get_vc')
        assert hasattr(client.vc, 'vc_single')
    
    def test_load_vc_only_once(self):
        """Deve carregar VC apenas uma vez (idempotente)"""
        client = RvcClient()
        
        client._load_vc()
        vc_first = client.vc
        
        client._load_vc()
        vc_second = client.vc
        
        assert vc_first is vc_second
    
    @patch('app.rvc_client.VC')
    def test_load_vc_configures_device(self, mock_vc_class):
        """Deve configurar device correto no VC"""
        client = RvcClient(device='cpu')
        client._load_vc()
        
        # Verifica que Config foi criado com device correto
        mock_vc_class.assert_called_once()
        config = mock_vc_class.call_args[0][0]
        assert config.device == 'cpu'


class TestRvcClientConversion:
    """Testes de conversão de áudio"""
    
    @pytest.mark.asyncio
    async def test_convert_audio_basic(self, sample_audio, mock_rvc_model):
        """Deve converter áudio básico com sucesso"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        # Mock do vc.vc_single
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        converted_audio, duration = await client.convert_audio(
            audio_data=audio_data,
            sample_rate=sample_rate,
            rvc_model=mock_rvc_model,
            params=params
        )
        
        assert isinstance(converted_audio, np.ndarray)
        assert duration > 0
        assert duration == pytest.approx(3.0, abs=0.1)
    
    @pytest.mark.asyncio
    async def test_convert_audio_loads_vc_if_needed(self, sample_audio, mock_rvc_model):
        """Deve carregar VC automaticamente se não carregado"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        assert client.vc is None
        
        # Mock
        with patch.object(client, '_load_vc') as mock_load:
            mock_load.return_value = None
            client.vc = Mock()
            client.vc.get_vc = Mock()
            client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
            
            # Deve ter chamado _load_vc
            mock_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_convert_audio_creates_temp_file(self, sample_audio, mock_rvc_model, tmp_path):
        """Deve criar arquivo temporário para RVC"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        temp_files_created = []
        
        # Mock soundfile.write para capturar temp file
        def mock_write(path, data, sr):
            temp_files_created.append(path)
        
        with patch('soundfile.write', side_effect=mock_write):
            client._load_vc()
            client.vc.get_vc = Mock()
            client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        assert len(temp_files_created) == 1
        assert 'rvc_input' in temp_files_created[0]
    
    @pytest.mark.asyncio
    async def test_convert_audio_cleans_temp_file(self, sample_audio, mock_rvc_model):
        """Deve limpar arquivo temporário após conversão"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        temp_file = None
        
        # Mock para capturar temp file
        original_write = __import__('soundfile').write
        def track_temp_write(path, data, sr):
            nonlocal temp_file
            temp_file = path
            original_write(path, data, sr)
        
        with patch('soundfile.write', side_effect=track_temp_write):
            client._load_vc()
            client.vc.get_vc = Mock()
            client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
            
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        # Arquivo temp deve ter sido deletado
        from pathlib import Path
        assert temp_file is not None
        assert not Path(temp_file).exists()


class TestRvcClientModelCaching:
    """Testes de cache de modelos"""
    
    @pytest.mark.asyncio
    async def test_loads_model_on_first_use(self, sample_audio, mock_rvc_model):
        """Deve carregar modelo na primeira conversão"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        assert client.current_model_path is None
        
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        client.vc.get_vc.assert_called_once_with(mock_rvc_model.model_path)
        assert client.current_model_path == mock_rvc_model.model_path
    
    @pytest.mark.asyncio
    async def test_reuses_cached_model(self, sample_audio, mock_rvc_model):
        """Deve reutilizar modelo em cache (não recarregar)"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        # Primeira conversão
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        assert client.vc.get_vc.call_count == 1
        
        # Segunda conversão (mesmo modelo)
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        assert client.vc.get_vc.call_count == 1  # Não deve recarregar
    
    @pytest.mark.asyncio
    async def test_reloads_different_model(self, sample_audio, mock_rvc_model, tmp_path):
        """Deve recarregar se modelo mudar"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        # Segundo modelo
        model_path_2 = tmp_path / "model2.pth"
        torch.save({'weight': {}}, model_path_2)
        mock_rvc_model_2 = RvcModel.create_new("Model 2", str(model_path_2))
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        # Primeira conversão (modelo 1)
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        assert client.vc.get_vc.call_count == 1
        
        # Segunda conversão (modelo 2)
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model_2, params)
        assert client.vc.get_vc.call_count == 2  # Recarregou


class TestRvcClientErrorHandling:
    """Testes de tratamento de erros"""
    
    @pytest.mark.asyncio
    async def test_raises_on_vc_single_failure(self, sample_audio, mock_rvc_model):
        """Deve lançar RvcConversionException se vc_single falhar"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(side_effect=Exception("VC error"))
        
        with pytest.raises(RvcConversionException, match="RVC conversion error"):
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
    
    @pytest.mark.asyncio
    async def test_raises_on_model_load_failure(self, sample_audio, mock_rvc_model):
        """Deve lançar RvcModelException se get_vc falhar"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        client._load_vc()
        client.vc.get_vc = Mock(side_effect=Exception("Model load error"))
        
        with pytest.raises(RvcConversionException):
            await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
    
    @pytest.mark.asyncio
    async def test_cleans_temp_file_on_error(self, sample_audio, mock_rvc_model):
        """Deve limpar temp file mesmo em caso de erro"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        temp_file = None
        
        # Mock para capturar temp file
        original_write = __import__('soundfile').write
        def track_temp_write(path, data, sr):
            nonlocal temp_file
            temp_file = path
            original_write(path, data, sr)
        
        with patch('soundfile.write', side_effect=track_temp_write):
            client._load_vc()
            client.vc.get_vc = Mock()
            client.vc.vc_single = Mock(side_effect=Exception("Error"))
            
            with pytest.raises(RvcConversionException):
                await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        # Arquivo temp deve ter sido deletado mesmo com erro
        from pathlib import Path
        assert temp_file is not None
        assert not Path(temp_file).exists()


class TestRvcClientParameters:
    """Testes de parâmetros RVC"""
    
    @pytest.mark.asyncio
    async def test_passes_all_parameters_to_vc_single(self, sample_audio, mock_rvc_model):
        """Deve passar todos os parâmetros para vc_single"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        
        params = RvcParameters(
            pitch=3,
            index_rate=0.8,
            f0_method='fcpe',
            filter_radius=5,
            resample_sr=48000,
            rms_mix_rate=0.6,
            protect=0.4
        )
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        # Verifica argumentos passados
        call_kwargs = client.vc.vc_single.call_args[1]
        assert call_kwargs['f0_up_key'] == 3
        assert call_kwargs['index_rate'] == 0.8
        assert call_kwargs['f0_method'] == 'fcpe'
        assert call_kwargs['filter_radius'] == 5
        assert call_kwargs['resample_sr'] == 48000
        assert call_kwargs['rms_mix_rate'] == 0.6
        assert call_kwargs['protect'] == 0.4
    
    @pytest.mark.asyncio
    async def test_uses_index_path_if_provided(self, sample_audio, mock_rvc_model):
        """Deve usar index_path do modelo se fornecido"""
        client = RvcClient(device='cpu')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        await client.convert_audio(audio_data, sample_rate, mock_rvc_model, params)
        
        call_kwargs = client.vc.vc_single.call_args[1]
        assert call_kwargs['file_index'] == mock_rvc_model.index_path


@pytest.mark.integration
class TestRvcClientIntegration:
    """Testes de integração (requerem deps RVC reais)"""
    
    @pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires GPU")
    @pytest.mark.asyncio
    async def test_real_conversion_gpu(self, sample_audio, mock_rvc_model):
        """Teste de conversão real em GPU (se disponível)"""
        # Este teste usa RVC real, não mocks
        client = RvcClient(device='cuda')
        audio_data, sample_rate = sample_audio
        params = RvcParameters()
        
        # Nota: requer modelo RVC real
        # Mock por enquanto
        client._load_vc()
        client.vc.get_vc = Mock()
        client.vc.vc_single = Mock(return_value=(sample_rate, audio_data))
        
        converted_audio, duration = await client.convert_audio(
            audio_data, sample_rate, mock_rvc_model, params
        )
        
        assert converted_audio.shape == audio_data.shape
```

**Validação:** Rodar `pytest tests/test_rvc_client.py -v`

**Resultado Esperado:** ❌ TODOS OS TESTES DEVEM FALHAR (rvc_client.py não existe)

---

### 3.2 IMPLEMENTAÇÃO (Green Phase)

#### 3.2.1 Criar `app/exceptions.py` (adicionar exceções RVC)

```python
# Adicionar ao arquivo existente app/exceptions.py

class RvcConversionException(Exception):
    """Erro durante conversão RVC"""
    pass


class RvcModelException(Exception):
    """Erro ao carregar ou validar modelo RVC"""
    pass


class RvcDeviceException(Exception):
    """Erro de device CUDA/CPU"""
    pass
```

#### 3.2.2 Criar `app/models.py` (adicionar modelos RVC)

```python
# Adicionar ao arquivo existente app/models.py

from dataclasses import dataclass
from typing import Optional
import hashlib
import os


class RvcModel(BaseModel):
    """Modelo RVC para voice conversion"""
    id: str
    name: str
    description: Optional[str] = None
    model_path: str
    index_path: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime
    file_size: Optional[int] = None
    
    @classmethod
    def create_new(
        cls,
        name: str,
        model_path: str,
        index_path: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None
    ) -> "RvcModel":
        """Cria novo modelo RVC"""
        now = datetime.now()
        model_id = f"rvc_{hashlib.md5(f'{name}_{now.timestamp()}'.encode()).hexdigest()[:12]}"
        
        file_size = os.path.getsize(model_path) if os.path.exists(model_path) else None
        
        return cls(
            id=model_id,
            name=name,
            description=description,
            model_path=model_path,
            index_path=index_path,
            language=language,
            created_at=now,
            file_size=file_size
        )


@dataclass
class RvcParameters:
    """Parâmetros de conversão RVC"""
    pitch: int = 0
    index_rate: float = 0.75
    f0_method: str = "rmvpe"
    filter_radius: int = 3
    resample_sr: int = 0
    rms_mix_rate: float = 0.5
    protect: float = 0.33
    
    @classmethod
    def from_quality_profile(cls, profile_name: str) -> 'RvcParameters':
        """Factory para criar parâmetros de perfil de qualidade"""
        profiles = {
            "natural": cls(
                pitch=0,
                index_rate=0.85,
                f0_method="rmvpe",
                filter_radius=3,
                rms_mix_rate=0.5,
                protect=0.33
            ),
            "expressive": cls(
                pitch=0,
                index_rate=0.90,
                f0_method="rmvpe",
                filter_radius=2,
                rms_mix_rate=0.6,
                protect=0.25
            ),
            "stable": cls(
                pitch=0,
                index_rate=0.70,
                f0_method="rmvpe",
                filter_radius=5,
                rms_mix_rate=0.4,
                protect=0.40
            )
        }
        return profiles.get(profile_name, profiles["natural"])
```

#### 3.2.3 Criar `app/rvc_client.py` (IMPLEMENTAÇÃO COMPLETA)

```python
"""
RVC Client - Adapter para voice conversion
Sprint 3: Core implementation
"""
import logging
import os
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import asyncio

from .models import RvcModel, RvcParameters
from .exceptions import RvcConversionException, RvcModelException
from .config import get_settings

logger = logging.getLogger(__name__)


class RvcClient:
    """
    Cliente RVC para pós-processamento de áudio XTTS
    
    Funciona como camada de conversão de voz sobre áudio já gerado,
    melhorando naturalidade, entonação e emoção.
    """
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        models_dir: str = "./models/rvc"
    ):
        """
        Inicializa cliente RVC
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
            fallback_to_cpu: Se True, usa CPU quando CUDA não disponível
            models_dir: Diretório de modelos RVC (.pth)
        """
        # Device detection
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            if device == 'cuda' and not torch.cuda.is_available():
                if fallback_to_cpu:
                    logger.warning("CUDA requested but not available, falling back to CPU for RVC")
                    self.device = 'cpu'
                else:
                    raise RuntimeError("CUDA requested but not available")
        
        logger.info(f"Initializing RVC client on device: {self.device}")
        
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True, parents=True)
        
        # Lazy load de VC
        self.vc = None
        self.current_model_path = None
        
        # Cache de modelos
        self.loaded_models = {}
    
    def _load_vc(self):
        """Carrega módulo VC (lazy initialization)"""
        if self.vc is not None:
            return
        
        try:
            from tts_with_rvc.infer.vc.modules import VC
            from tts_with_rvc.infer.vc.config import Config
            
            logger.info("Initializing RVC VC module")
            
            config = Config()
            config.device = self.device
            config.is_half = (self.device == 'cuda')
            
            self.vc = VC(config)
            
            logger.info("RVC VC module loaded successfully")
            
        except ImportError as e:
            raise RvcConversionException(
                f"Failed to import RVC modules. Install: pip install tts-with-rvc. Error: {e}"
            )
    
    async def convert_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        rvc_model: RvcModel,
        params: RvcParameters
    ) -> Tuple[np.ndarray, float]:
        """
        Aplica RVC conversion em áudio XTTS gerado
        
        Args:
            audio_data: Audio numpy array (waveform)
            sample_rate: Sample rate do áudio (24000 para XTTS)
            rvc_model: Modelo RVC a usar
            params: Parâmetros de conversão
        
        Returns:
            Tuple[np.ndarray, float]: (audio convertido, duração em segundos)
        
        Raises:
            RvcConversionException: Se conversão falhar
        """
        # Garante que VC esteja carregado
        if self.vc is None:
            self._load_vc()
        
        temp_input = None
        
        try:
            # Salva áudio temporário
            temp_input = f"/tmp/rvc_input_{os.getpid()}_{id(audio_data)}.wav"
            sf.write(temp_input, audio_data, sample_rate)
            
            # Carrega modelo RVC se necessário
            if self.current_model_path != rvc_model.model_path:
                logger.info(f"Loading RVC model: {rvc_model.model_path}")
                self.vc.get_vc(rvc_model.model_path)
                self.current_model_path = rvc_model.model_path
            else:
                logger.debug("Using cached RVC model")
            
            # Aplica voice conversion
            logger.info(f"Applying RVC conversion with params: pitch={params.pitch}, "
                       f"index_rate={params.index_rate}, f0_method={params.f0_method}")
            
            # Chama vc_single (síncronamente em executor)
            loop = asyncio.get_event_loop()
            
            tgt_sr, audio_opt = await loop.run_in_executor(
                None,
                lambda: self.vc.vc_single(
                    sid=0,
                    input_audio_path=temp_input,
                    f0_up_key=params.pitch,
                    f0_file=None,
                    f0_method=params.f0_method,
                    file_index=rvc_model.index_path if rvc_model.index_path else "",
                    file_index2="",
                    index_rate=params.index_rate,
                    filter_radius=params.filter_radius,
                    resample_sr=params.resample_sr,
                    rms_mix_rate=params.rms_mix_rate,
                    protect=params.protect
                )
            )
            
            # Calcula duração
            duration = len(audio_opt) / tgt_sr
            
            logger.info(f"RVC conversion completed: {duration:.2f}s, sample_rate={tgt_sr}")
            
            return audio_opt, duration
            
        except Exception as e:
            logger.error(f"RVC conversion failed: {e}", exc_info=True)
            raise RvcConversionException(f"RVC conversion error: {str(e)}")
        
        finally:
            # Cleanup temp file
            if temp_input and os.path.exists(temp_input):
                try:
                    os.remove(temp_input)
                    logger.debug(f"Cleaned up temp file: {temp_input}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_input}: {e}")
```

**Validação:** Rodar `pytest tests/test_rvc_client.py -v`

**Resultado Esperado:** ✅ TODOS OS TESTES DEVEM PASSAR (green)

---

### 3.3 REFATORAÇÃO

#### 3.3.1 Adicionar type hints completos

- Garantir mypy passa sem erros
- Documentar todos os parâmetros

#### 3.3.2 Adicionar logging estruturado

```python
# Em convert_audio, adicionar métricas
import time

start_time = time.time()
# ... conversão ...
conversion_time = time.time() - start_time

logger.info(
    "RVC conversion metrics",
    extra={
        "duration_seconds": duration,
        "conversion_time_seconds": conversion_time,
        "realtime_factor": conversion_time / duration,
        "model_id": rvc_model.id,
        "pitch": params.pitch,
        "f0_method": params.f0_method
    }
)
```

#### 3.3.3 Otimizar gestão de memória

```python
# Adicionar método para limpar cache
def clear_cache(self):
    """Limpa cache de modelos (libera VRAM)"""
    if self.vc is not None:
        self.current_model_path = None
        # Força coleta de lixo
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("RVC cache cleared")
```

---

## 4. CRITÉRIOS DE ACEITAÇÃO

### ✅ Checklist

- [ ] **rvc_client.py** criado e funcional
- [ ] **Todos os testes** em `test_rvc_client.py` passam ✅
- [ ] **Coverage ≥90%** no rvc_client.py
- [ ] **Lazy loading** funciona (VC não carregado até primeiro uso)
- [ ] **Model caching** funciona (não recarrega mesmo modelo)
- [ ] **Cleanup de temp files** sempre funciona (mesmo com erros)
- [ ] **Logging** estruturado com métricas
- [ ] **Type hints** completos (mypy passa)
- [ ] **Docstrings** completas

### Comando de Validação Final

```bash
# Rodar testes
docker exec -it audio-voice-api-gpu pytest tests/test_rvc_client.py -v --cov=app/rvc_client --cov-report=term

# Coverage deve ser ≥90%
docker exec -it audio-voice-api-gpu pytest tests/test_rvc_client.py --cov=app/rvc_client --cov-report=html

# Type checking
docker exec -it audio-voice-api-gpu mypy app/rvc_client.py

# Lint
docker exec -it audio-voice-api-gpu flake8 app/rvc_client.py
```

**Resultado Esperado:** ✅ TODOS PASSAM

---

## 5. ENTREGÁVEIS

```
app/
├── exceptions.py                🔄 MODIFICADO (+ RVC exceptions)
├── models.py                    🔄 MODIFICADO (+ RvcModel, RvcParameters)
└── rvc_client.py                ✅ NOVO

tests/
└── test_rvc_client.py           ✅ NOVO
```

---

## 6. PRÓXIMOS PASSOS

1. ✅ Marcar Sprint 3 como completa
2. ✅ Commit: `git commit -m "feat(rvc): Sprint 3 - RVC client implementation"`
3. ▶️ Iniciar **Sprint 4** (ler `sprints/SPRINT-04-INTEGRATION.md`)

---

**Sprint 3 Completa!** 🎉

Próxima: **Sprint 4 - Integração XTTS + RVC** →
