# 🧪 Guia de Testes

Este documento descreve a estrutura de testes do projeto.

## 📁 Estrutura de Testes

```
tests/
├── conftest.py                    # Fixtures e configurações compartilhadas
├── unit/                          # Testes unitários (isolados, rápidos)
│   ├── domain/                    # Testes de Domain Layer
│   │   ├── entities/              # Testes de entidades
│   │   │   ├── test_transcription.py
│   │   │   └── test_video_file.py
│   │   └── value_objects/         # Testes de Value Objects
│   │       ├── test_youtube_url.py
│   │       └── test_transcription_segment.py
│   ├── infrastructure/            # Testes de Infrastructure Layer
│   │   ├── test_circuit_breaker.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_storage.py
│   │   └── test_cache.py
│   └── application/               # Testes de Application Layer
│       └── test_transcribe_use_case.py
├── integration/                   # Testes de integração (múltiplos componentes)
│   └── test_real_youtube_download.py
└── e2e/                          # Testes end-to-end (fluxo completo)
    └── test_api_transcribe.py
```

## 🚀 Executando Testes

### Todos os testes
```bash
python run_tests.py
```

### Apenas testes unitários
```bash
python run_tests.py --unit
```

### Apenas testes de integração
```bash
python run_tests.py --integration
```

### Com cobertura de código
```bash
python run_tests.py --coverage
```

### Testes rápidos (pular lentos)
```bash
python run_tests.py --fast
```

### Sem testes que requerem rede
```bash
python run_tests.py --no-network
```

### Usando pytest diretamente
```bash
# Todos os testes
pytest tests/

# Testes específicos
pytest tests/unit/infrastructure/test_circuit_breaker.py

# Teste específico
pytest tests/unit/infrastructure/test_circuit_breaker.py::TestCircuitBreakerAsync::test_acall_async_function_success

# Com verbose
pytest -v tests/

# Com cobertura
pytest --cov=src --cov-report=html tests/
```

## 📊 Relatórios de Cobertura

Após executar com `--coverage`, abra o relatório HTML:

```bash
# Windows
start htmlcov/index.html

# Linux/Mac
open htmlcov/index.html
```

## 🏷️ Markers

Os testes podem ser marcados com:

- `@pytest.mark.integration` - Testes de integração
- `@pytest.mark.slow` - Testes lentos
- `@pytest.mark.requires_network` - Requer acesso à internet
- `@pytest.mark.requires_ffmpeg` - Requer FFmpeg instalado

### Exemplos

```python
import pytest

@pytest.mark.slow
@pytest.mark.requires_network
async def test_download_real_video():
    # Este teste é lento e requer internet
    pass
```

## 🧪 Escrevendo Novos Testes

### Teste Unitário

```python
import pytest
from src.domain.entities.transcription import Transcription

class TestTranscription:
    def test_create_transcription(self):
        t = Transcription(video_id="test", language="en", model_name="base")
        assert t.video_id == "test"
```

### Teste Async

```python
import pytest

class TestAsyncFunction:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        result = await some_async_function()
        assert result is not None
```

### Teste com Mocks

```python
from unittest.mock import Mock, AsyncMock

class TestWithMocks:
    def test_with_mock(self):
        mock_service = Mock()
        mock_service.method.return_value = "mocked"
        
        result = some_function(mock_service)
        
        mock_service.method.assert_called_once()
        assert result == "mocked"
```

### Usando Fixtures

```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

class TestWithFixture:
    def test_uses_fixture(self, sample_data):
        assert sample_data["key"] == "value"
```

## 📈 Objetivo de Cobertura

Meta: **80%+ de cobertura** em:
- Domain Layer: 90%+
- Application Layer: 85%+
- Infrastructure Layer: 75%+

## 🔍 Debugging Testes

### Ver output detalhado
```bash
pytest -s tests/  # Mostra prints
```

### Parar no primeiro erro
```bash
pytest -x tests/
```

### Executar último teste que falhou
```bash
pytest --lf tests/
```

### Debug com pdb
```python
def test_with_debug():
    import pdb; pdb.set_trace()
    # Código do teste
```

## ✅ Checklist para Pull Requests

Antes de fazer PR, garanta que:

- [ ] Todos os testes passam (`pytest tests/`)
- [ ] Cobertura está acima de 80% (`pytest --cov=src tests/`)
- [ ] Novos recursos têm testes
- [ ] Testes estão documentados
- [ ] Sem warnings do pytest
