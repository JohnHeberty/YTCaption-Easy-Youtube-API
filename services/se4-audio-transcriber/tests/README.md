# 🧪 Tests - Audio Transcriber Service

Estrutura profissional de testes com cobertura completa seguindo padrão de produção.

## 📁 Estrutura

```
tests/
├── 📖 README.md                           # Este arquivo
├── ⚙️ conftest.py                         # Fixtures compartilhadas (pytest)
├── ⚙️ pytest.ini                          # Configuração do pytest
├── 🎵 TEST-.ogg                           # Áudio de teste (75KB)
│
├── 📦 assets/                             # Arquivos de teste
│   └── audio_samples/                     # Samples de áudio
│
├── 🏗️ fixtures/                           # Fixtures customizadas
│   ├── __init__.py
│   ├── audio_fixtures.py                  # Fixtures de áudio
│   ├── api_fixtures.py                    # Fixtures de API
│   └── mock_fixtures.py                   # Mocks customizados
│
├── 🔬 unit/                               # Testes unitários (isolados, rápidos)
│   ├── __init__.py
│   ├── core/                              # Config, settings
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   └── test_settings.py
│   ├── domain/                            # Modelos de domínio
│   │   ├── __init__.py
│   │   └── test_models.py
│   ├── services/                          # Serviços de negócio
│   │   ├── __init__.py
│   │   ├── test_processor.py
│   │   ├── test_faster_whisper_manager.py
│   │   └── test_audio_preprocessor.py
│   └── utils/                             # Utilitários
│       ├── __init__.py
│       └── test_audio_utils.py
│
├── 🔗 integration/                        # Testes de integração
│   ├── __init__.py
│   ├── api/                               # Testes de API
│   │   ├── __init__.py
│   │   └── test_api_endpoints.py
│   ├── pipeline/                          # Pipeline completo
│   │   ├── __init__.py
│   │   └── test_transcription_pipeline.py
│   ├── storage/                           # Redis, filesystem
│   │   ├── __init__.py
│   │   ├── test_redis_store.py
│   │   └── test_file_operations.py
│   │
│   └── 🌐 real/                           # ⚠️ TESTES REAIS (APIs externas)
│       ├── __init__.py
│       ├── README.md
│       └── test_real_whisper_api.py
│
├── 🚀 e2e/                                # Testes end-to-end
│   ├── __init__.py
│   ├── test_complete_workflow.py          # Workflow completo
│   └── test_celery_tasks.py               # Tarefas Celery
│
├── 📊 performance/                        # Testes de performance
│   ├── __init__.py
│   └── test_transcription_speed.py
│
├── 🔒 security/                           # Testes de segurança
│   ├── __init__.py
│   └── test_input_validation.py
│
└── ✅ test_setup_validation.py            # Validação de setup

```

## 🎯 Tipos de Teste

### 1. 🔬 Unit Tests (`unit/`)

**Testes isolados, rápidos, sem dependências externas**

```python
# Exemplo: Testar processador de áudio
def test_audio_format_conversion(audio_processor):
    result = audio_processor.convert_to_wav("test.mp3")
    assert result.format == "wav"
    assert result.sample_rate == 16000
```

**Características**:
- ✅ Rápidos (< 1s cada)
- ✅ Sem I/O externo (sem rede/banco)
- ✅ Mocks para dependências
- ✅ Focados em 1 função/método

**Executar**:
```bash
pytest tests/unit/ -v
```

---

### 2. 🔗 Integration Tests (`integration/`)

**Testes com múltiplos componentes**

```python
# Exemplo: API + Processor + Storage
async def test_transcription_endpoint():
    response = await client.post("/transcribe", files={"audio": audio_file})
    assert response.status_code == 200
    assert "segments" in response.json()
```

**Características**:
- ⚡ Médios (1-5s cada)
- 💾 Podem usar disco/Redis de teste
- 🔧 Mocks para APIs externas
- 📦 Testam integração de 2+ componentes

**Executar**:
```bash
pytest tests/integration/ -v --ignore=tests/integration/real
```

---

### 3. 🌐 Real Integration Tests (`integration/real/`)

**⚠️ TESTES REAIS - Usam APIs/Serviços externos**

```python
# Exemplo: Whisper API real
@pytest.mark.real
async def test_real_whisper_transcription():
    model = WhisperModel("base")
    result = model.transcribe("test_audio.wav")
    assert len(result.segments) > 0
```

**Características**:
- 🐌 Lentos (5-60s cada)
- 🌐 Usam APIs reais (Whisper)
- 💰 Podem ter custo
- 🔐 Requerem credenciais reais

**Executar**:
```bash
pytest tests/integration/real/ -v -m real
```

---

### 4. 🚀 End-to-End Tests (`e2e/`)

**Testes do sistema completo**

```python
# Exemplo: Upload → Transcrição → Download
async def test_complete_transcription_workflow():
    job_id = await upload_audio("test.mp3")
    result = await poll_until_complete(job_id)
    transcription = await download_result(job_id)
    assert "text" in transcription
```

**Características**:
- 🐢 Muito lentos (10-120s)
- 🏗️ Testam sistema completo
- 📊 Simulam uso real
- 🔄 Incluem Celery tasks

**Executar**:
```bash
pytest tests/e2e/ -v
```

---

## 🚀 Executando Testes

### Todos os testes (exceto reais)
```bash
make test
# ou
pytest tests/ -v --ignore=tests/integration/real
```

### Por categoria
```bash
# Unit tests (rápidos)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v --ignore=tests/integration/real

# End-to-end tests
pytest tests/e2e/ -v

# Performance tests
pytest tests/performance/ -v

# Security tests
pytest tests/security/ -v
```

### Testes reais (APIs externas)
```bash
# ⚠️ Requer serviços rodando
pytest tests/integration/real/ -v -m real
```

### Com cobertura
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### Específico
```bash
# Um arquivo
pytest tests/unit/services/test_processor.py -v

# Uma função
pytest tests/unit/services/test_processor.py::test_process_audio -v

# Por marker
pytest -m "not slow" -v
```

---

## 📊 Markers

```python
@pytest.mark.unit          # Teste unitário
@pytest.mark.integration   # Teste de integração
@pytest.mark.e2e           # Teste end-to-end
@pytest.mark.real          # Usa APIs reais
@pytest.mark.slow          # Demora > 5s
@pytest.mark.gpu           # Requer GPU
@pytest.mark.celery        # Requer Celery
```

---

## 🎯 Cobertura de Testes

**Meta: > 80% de cobertura**

### Áreas críticas (100% cobertura):
- ✅ `app/processor.py` - Lógica principal
- ✅ `app/faster_whisper_manager.py` - Gerenciamento de modelo
- ✅ `app/models.py` - Modelos de dados
- ✅ `app/config.py` - Configurações

### Áreas importantes (> 80%):
- ⚡ `app/main.py` - Endpoints FastAPI
- ⚡ `app/celery_tasks.py` - Tarefas assíncronas
- ⚡ `app/redis_store.py` - Armazenamento

---

## 🔧 Ferramentas

```bash
# Instalar dependências de teste
pip install -r requirements-test.txt

# Rodar com pytest-watch (auto-reload)
ptw -- -v

# Rodar em paralelo (mais rápido)
pytest -n auto

# Gerar relatório HTML
pytest --html=report.html --self-contained-html
```

---

## 📝 Escrevendo Testes

### Estrutura de teste (AAA pattern)
```python
def test_transcribe_audio():
    # 1. ARRANGE - Preparar
    audio_file = create_test_audio()
    processor = TranscriptionProcessor()
    
    # 2. ACT - Executar
    result = processor.transcribe(audio_file)
    
    # 3. ASSERT - Verificar
    assert result.success is True
    assert len(result.segments) > 0
    assert result.segments[0].text != ""
```

### Boas práticas
- ✅ Um conceito por teste
- ✅ Nomes descritivos: `test_should_return_error_when_audio_is_corrupted`
- ✅ Testes independentes (sem ordem)
- ✅ Use fixtures para setup
- ✅ Cleanup automático
- ✅ Asserts claros
- ❌ Evite lógica complexa nos testes
- ❌ Não teste implementação, teste comportamento

---

## 🐛 Debugging

```bash
# Modo verbose
pytest -vv

# Com print statements
pytest -s

# Parar no primeiro erro
pytest -x

# Debugger no erro
pytest --pdb

# Específico com debug
pytest tests/unit/test_processor.py::test_process_audio -vv -s --pdb
```

---

## 📈 CI/CD

Testes executados automaticamente em:
- ✅ Push para branch
- ✅ Pull Request
- ✅ Merge para main

Pipeline:
1. Unit tests (obrigatório ✅)
2. Integration tests (obrigatório ✅)
3. E2E tests (opcional ⚠️)
4. Coverage report (> 80% ✅)

---

## 📚 Referências

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)
