# SPRINT 4 - Integração XTTS + RVC

**Duração Estimada:** 3-4 dias  
**Responsável:** Backend Engineer  
**Dependências:** Sprint 3 (RVC Client funcional)

---

## 1. OBJETIVO

Integrar RVC Client com XTTS Client e Processor, criando pipeline XTTS → RVC:
- ✅ Modificar `xtts_client.py` para suportar RVC
- ✅ Modificar `processor.py` para pipeline completo
- ✅ Adicionar parâmetros RVC em requests
- ✅ Garantir backward compatibility 100%
- ✅ Testes de integração ≥85% coverage

---

## 2. PRÉ-REQUISITOS

- [x] Sprint 3: RVC Client implementado e testado
- [x] `test_rvc_client.py` 100% green

---

## 3. TAREFAS

### 3.1 TESTES (Red Phase)

#### 3.1.1 Criar `tests/test_xtts_rvc_integration.py`

```python
"""
Testes de integração XTTS + RVC
Sprint 4
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from app.xtts_client import XTTSClient
from app.models import RvcModel, RvcParameters, QualityProfile


@pytest.fixture
def mock_rvc_model(tmp_path):
    import torch
    model_path = tmp_path / "test.pth"
    torch.save({'weight': {}}, model_path)
    return RvcModel.create_new("Test", str(model_path))


class TestXTTSClientRvcIntegration:
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_without_rvc(self):
        """Deve funcionar sem RVC (backward compatibility)"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client, 'tts') as mock_tts:
            mock_tts.tts_to_file = Mock()
            
            audio_bytes, duration = await client.generate_dubbing(
                text="Test",
                language="en",
                enable_rvc=False
            )
            
            assert len(audio_bytes) > 0
            assert client.rvc_client is None  # Não carregou RVC
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_with_rvc(self, mock_rvc_model):
        """Deve aplicar RVC quando enable_rvc=True"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client, '_load_rvc_client'):
            client.rvc_client = Mock()
            client.rvc_client.convert_audio = AsyncMock(
                return_value=(np.random.randn(24000), 1.0)
            )
            
            with patch.object(client, 'tts'):
                audio_bytes, duration = await client.generate_dubbing(
                    text="Test",
                    language="en",
                    enable_rvc=True,
                    rvc_model=mock_rvc_model,
                    rvc_params=RvcParameters()
                )
                
                client.rvc_client.convert_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rvc_fallback_on_error(self, mock_rvc_model):
        """Deve fazer fallback para XTTS se RVC falhar"""
        client = XTTSClient(device='cpu')
        
        with patch.object(client, '_load_rvc_client'):
            client.rvc_client = Mock()
            client.rvc_client.convert_audio = AsyncMock(
                side_effect=Exception("RVC error")
            )
            
            with patch.object(client, 'tts'):
                audio_bytes, duration = await client.generate_dubbing(
                    text="Test",
                    language="en",
                    enable_rvc=True,
                    rvc_model=mock_rvc_model
                )
                
                # Não deve lançar exceção, usa XTTS puro
                assert len(audio_bytes) > 0


class TestProcessorRvcIntegration:
    
    @pytest.mark.asyncio
    async def test_process_dubbing_job_with_rvc(self, mock_rvc_model):
        """Processor deve passar parâmetros RVC para XTTS client"""
        from app.processor import VoiceProcessor
        from app.models import Job, JobMode, JobStatus
        
        processor = VoiceProcessor()
        
        job = Job(
            id="test123",
            mode=JobMode.DUBBING,
            status=JobStatus.PENDING,
            text="Test",
            source_language="en",
            enable_rvc=True,
            rvc_model_id=mock_rvc_model.id,
            rvc_pitch=2,
            rvc_index_rate=0.8
        )
        
        with patch.object(processor.engine, 'generate_dubbing') as mock_gen:
            mock_gen.return_value = (b'audio', 1.0)
            
            result = await processor.process_dubbing_job(job)
            
            # Verifica que chamou com parâmetros RVC
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs['enable_rvc'] is True
            assert call_kwargs['rvc_params'].pitch == 2
```

---

### 3.2 IMPLEMENTAÇÃO (Green Phase)

#### 3.2.1 Modificar `app/xtts_client.py`

```python
# Adicionar ao XTTSClient existente

from .rvc_client import RvcClient
from .models import RvcModel, RvcParameters

class XTTSClient:
    def __init__(...):
        # ... código existente ...
        
        # RVC client (lazy load)
        self.rvc_client = None
    
    def _load_rvc_client(self):
        """Carrega RVC client (lazy)"""
        if self.rvc_client is not None:
            return
        
        logger.info("Initializing RVC client")
        self.rvc_client = RvcClient(
            device=self.device,
            fallback_to_cpu=True
        )
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        quality_profile: QualityProfile = QualityProfile.BALANCED,
        temperature: Optional[float] = None,
        speed: Optional[float] = None,
        # NOVOS PARÂMETROS RVC
        enable_rvc: bool = False,
        rvc_model: Optional[RvcModel] = None,
        rvc_params: Optional[RvcParameters] = None
    ) -> Tuple[bytes, float]:
        # ... código XTTS existente ...
        
        # Lê áudio gerado
        audio_data, sr = sf.read(output_path)
        
        # === PONTO DE INSERÇÃO RVC ===
        if enable_rvc and rvc_model is not None:
            try:
                logger.info("Applying RVC post-processing")
                
                if self.rvc_client is None:
                    self._load_rvc_client()
                
                if rvc_params is None:
                    rvc_params = RvcParameters.from_quality_profile("natural")
                
                audio_data, duration = await self.rvc_client.convert_audio(
                    audio_data=audio_data,
                    sample_rate=sr,
                    rvc_model=rvc_model,
                    params=rvc_params
                )
                
                logger.info(f"RVC post-processing completed: {duration:.2f}s")
                
            except Exception as e:
                logger.error(f"RVC conversion failed, using XTTS output: {e}")
                # Fallback: continua com áudio XTTS
        
        # Converte para bytes
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, sr, format='WAV')
        audio_bytes = buffer.getvalue()
        
        # ... resto do código ...
```

#### 3.2.2 Modificar `app/processor.py`

```python
# Adicionar ao VoiceProcessor

async def process_dubbing_job(self, job: Job, voice_profile: Optional[VoiceProfile] = None) -> Job:
    try:
        # ... código existente ...
        
        # Obtém modelo RVC se habilitado
        rvc_model = None
        rvc_params = None
        
        if job.enable_rvc:
            if job.rvc_model_id:
                rvc_model = self.job_store.get_rvc_model(job.rvc_model_id)
                
                if rvc_model is None:
                    logger.warning(f"RVC model {job.rvc_model_id} not found, skipping RVC")
                else:
                    rvc_params = RvcParameters(
                        pitch=job.rvc_pitch or 0,
                        index_rate=job.rvc_index_rate or 0.75,
                        protect=job.rvc_protect or 0.33
                    )
        
        # Gera áudio
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=job.text,
            language=job.source_language or job.target_language or 'en',
            voice_preset=job.voice_preset,
            voice_profile=voice_profile,
            quality_profile=job.quality_profile,
            speed=1.0,
            enable_rvc=job.enable_rvc,
            rvc_model=rvc_model,
            rvc_params=rvc_params
        )
        
        # ... resto do código ...
```

#### 3.2.3 Modificar `app/models.py` (adicionar campos RVC em Job)

```python
class Job(BaseModel):
    # ... campos existentes ...
    
    # RVC fields
    enable_rvc: bool = False
    rvc_model_id: Optional[str] = None
    rvc_pitch: Optional[int] = Field(None, ge=-12, le=12)
    rvc_index_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    rvc_protect: Optional[float] = Field(None, ge=0.0, le=1.0)
```

---

### 3.3 REFATORAÇÃO

- Adicionar métricas de timing (XTTS vs RVC vs total)
- Otimizar pipeline (evitar I/O desnecessário)
- Documentar fluxo completo

---

## 4. CRITÉRIOS DE ACEITAÇÃO

- [ ] Pipeline XTTS → RVC funciona ✅
- [ ] Backward compatibility (enable_rvc=False funciona) ✅
- [ ] Fallback em caso de erro RVC ✅
- [ ] Testes integração ≥85% coverage ✅
- [ ] Sem regressões em testes XTTS existentes ✅

---

## 5. ENTREGÁVEIS

```
app/
├── xtts_client.py               🔄 MODIFICADO
├── processor.py                 🔄 MODIFICADO
└── models.py                    🔄 MODIFICADO

tests/
└── test_xtts_rvc_integration.py ✅ NOVO
```

---

**Sprint 4 Completa!** 🎉

Próxima: **Sprint 5 - Suite de Testes Unitários** →
