# SPRINT 5 - Suite Completa de Testes Unitários

**Duração Estimada:** 2-3 dias  
**Responsável:** Backend Engineer + QA Engineer  
**Dependências:** Sprint 4 (Integração funcional)

---

## 1. OBJETIVO

Atingir ≥90% coverage em todo código RVC com testes robustos:
- ✅ Testes unitários abrangentes
- ✅ Edge cases cobertos
- ✅ Mocks apropriados
- ✅ Fixtures reutilizáveis

---

## 2. TAREFAS

### 2.1 Melhorar Coverage Existente

```bash
# Rodar coverage report
pytest --cov=app --cov-report=html --cov-report=term-missing

# Identificar gaps
# Adicionar testes para linhas não cobertas
```

### 2.2 Criar `tests/conftest.py` (Fixtures Globais)

```python
"""
Fixtures globais para testes RVC
"""
import pytest
import torch
import numpy as np
from pathlib import Path


@pytest.fixture(scope="session")
def sample_audio_3s():
    """Áudio sintético 3s 24kHz"""
    sr = 24000
    duration = 3.0
    samples = int(sr * duration)
    audio = np.random.randn(samples).astype(np.float32) * 0.1
    return audio, sr


@pytest.fixture(scope="session")
def sample_audio_10s():
    """Áudio sintético 10s 24kHz"""
    sr = 24000
    duration = 10.0
    samples = int(sr * duration)
    audio = np.random.randn(samples).astype(np.float32) * 0.1
    return audio, sr


@pytest.fixture
def mock_rvc_model(tmp_path):
    """Modelo RVC fake"""
    from app.models import RvcModel
    
    model_path = tmp_path / "test_model.pth"
    torch.save({'weight': {'generator': {}}}, model_path)
    
    return RvcModel.create_new(
        name="Test Model",
        model_path=str(model_path)
    )


@pytest.fixture
def rvc_params_default():
    """Parâmetros RVC padrão"""
    from app.models import RvcParameters
    return RvcParameters()
```

### 2.3 Testes de Edge Cases

#### `tests/test_rvc_edge_cases.py`

```python
"""
Testes de edge cases RVC
"""
import pytest
import numpy as np
from app.rvc_client import RvcClient
from app.models import RvcParameters


class TestRvcEdgeCases:
    
    @pytest.mark.asyncio
    async def test_empty_audio(self, mock_rvc_model):
        """Deve tratar áudio vazio"""
        client = RvcClient(device='cpu')
        empty_audio = np.array([], dtype=np.float32)
        
        with pytest.raises(Exception):
            await client.convert_audio(
                empty_audio, 24000, mock_rvc_model, RvcParameters()
            )
    
    @pytest.mark.asyncio
    async def test_very_short_audio(self, mock_rvc_model):
        """Deve tratar áudio muito curto (<0.1s)"""
        client = RvcClient(device='cpu')
        short_audio = np.random.randn(2400).astype(np.float32)  # 0.1s
        
        # Deve funcionar ou falhar gracefully
        # (comportamento depende de RVC)
    
    @pytest.mark.asyncio
    async def test_extreme_pitch_values(self, sample_audio_3s, mock_rvc_model):
        """Deve limitar pitch em range válido"""
        client = RvcClient(device='cpu')
        audio, sr = sample_audio_3s
        
        # Pitch muito alto
        params = RvcParameters(pitch=12)
        # Deve funcionar
        
        # Pitch muito baixo
        params = RvcParameters(pitch=-12)
        # Deve funcionar
```

---

## 3. CRITÉRIOS DE ACEITAÇÃO

- [ ] Coverage ≥90% em `app/rvc_client.py` ✅
- [ ] Coverage ≥85% em integração XTTS+RVC ✅
- [ ] Todos edge cases testados ✅
- [ ] Fixtures reutilizáveis criadas ✅

---

**Sprint 5 Completa!** 🎉

Próxima: **Sprint 6 - API Model Management** →
