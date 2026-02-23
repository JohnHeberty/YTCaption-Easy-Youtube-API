# 🧪 Tests - Make Video Service

Estrutura profissional de testes com 100% seguindo padrão de produção.

## 📁 Estrutura

```
tests/
├── 📖 README.md                           # Este arquivo
├── 📋 RELATORIO_EXECUCAO.md               # Relatório de execução dos testes
├── ⚙️ conftest.py                         # Fixtures compartilhadas (pytest)
├── ⚙️ pytest.ini                          # Configuração do pytest
│
├── 📦 assets/                             # Arquivos de teste (áudio/vídeo)
│   └── TEST-.ogg                          # Áudio real (75KB) - fala em português
│
├── 🏗️ fixtures/                           # Fixtures customizadas
│
├── 🔬 unit/                               # Testes unitários (isolados, rápidos)
│   ├── core/                              # Config, settings
│   ├── domain/                            # Entidades de domínio
│   ├── infrastructure/                    # Circuit breaker, checkpoint
│   ├── services/                          # VideoBuilder, SubtitleGenerator
│   ├── shared/                            # Exceptions, validation
│   ├── subtitle_processing/               # ASS, classificador
│   ├── utils/                             # Audio utils, VAD, timeout
│   └── video_processing/                  # OCR, frame extractor
│
├── 🔗 integration/                        # Testes de integração (componentes juntos)
│   ├── domain/                            # Domain entities + services
│   ├── infrastructure/                    # Infrastructure + external deps
│   ├── pipeline/                          # Pipeline completo (interno)
│   ├── services/                          # Services + dependencies
│   ├── subtitle_processing/               # Subtitle pipeline
│   ├── video_processing/                  # Video processing pipeline
│   │
│   └── 🌐 real/                           # ⚠️ TESTES REAIS (APIs/Serviços externos)
│       ├── README.md                      # Documentação de testes reais
│       ├── test_real_audio_transcription.py   # API real: audio-transcriber
│       └── test_real_pipeline_complete.py     # Pipeline completo end-to-end
│
├── 🚀 e2e/                                # Testes end-to-end (sistema completo)
│   ├── test_complete_integration.py       # Integração completa
│   └── test_main_application.py           # Aplicação principal
│
└── ✅ test_setup_validation.py            # Validação de setup (rodar primeiro)
```

## 🎯 Tipos de Teste

### 1. 🔬 Unit Tests (`unit/`)

**Testes isolados, rápidos, sem dependências externas**

```python
# Exemplo: Testar função isolada
def test_format_timestamp():
    result = format_timestamp(65.5)
    assert result == "00:01:05,500"
```

**Características**:
- ✅ Rápidos (< 1s cada)
- ✅ Sem I/O (sem disco/rede/banco)
- ✅ Mocks para dependências externas
- ✅ Focados em 1 função/método

**Executar**:
```bash
pytest tests/unit/ -v
```

---

### 2. 🔗 Integration Tests (`integration/`)

**Testes com múltiplos componentes, podem ter I/O local**

```python
# Exemplo: SubtitleGenerator + VideoBuilder
async def test_subtitle_burn_in():
    srt = generate_srt(segments)
    video = burn_subtitles(video_path, srt)
    assert video.exists()
```

**Características**:
- ⚡ Médios (1-5s cada)
- 💾 Podem usar disco temporário
- 🔧 Mocks para APIs externas
- 📦 Testam integração de 2+ componentes

**Executar**:
```bash
pytest tests/integration/ -v --ignore=tests/integration/real
```

---

### 3. 🌐 Real Integration Tests (`integration/real/`)

**⚠️ TESTES COM SERVIÇOS REAIS (NÃO MOCKS)**

```python
# Exemplo: Chama API real
@pytest.mark.asyncio
@pytest.mark.external
async def test_real_transcription():
    segments = await api.transcribe_audio(TEST_OGG)  # API REAL!
    assert len(segments) > 0
```

**Características**:
- 🐌 Lentos (30-90s cada)
- 🌐 Chamam APIs/serviços em produção
- ❌ Se serviço está DOWN, teste FALHA (correto!)
- 🎯 Refletem exatamente o que vai acontecer em produção

**Por que não usar mocks?**:
- Mocks podem mentir
- Se API muda formato, mock passa mas produção falha
- Detecta problemas ANTES do deploy

**APIs chamadas**:
- `https://yttranscriber.loadstask.com` (audio-transcriber)
- FFmpeg local
- SubtitleGenerator real
- VideoBuilder real

**Executar**:
```bash
# Requer conectividade com APIs
pytest tests/integration/real/ -v
```

**Documentação completa**: [integration/real/README.md](integration/real/README.md)

---

### 4. 🚀 E2E Tests (`e2e/`)

**Testes do sistema completo (ponta a ponta)**

```python
# Exemplo: Job completo (download → transcrição → vídeo)
async def test_complete_pipeline():
    job = create_job(video_id="abc123")
    await process_job(job)
    assert job.status == "completed"
    assert output_video.exists()
```

**Características**:
- 🐢 Muito lentos (5-15min cada)
- 🌐 Podem chamar APIs reais
- 📦 Testam fluxo completo de usuário
- 🎬 Incluem download, transcrição, processamento

**Executar**:
```bash
pytest tests/e2e/ -v --timeout=900
```

---

## 🚀 Como Executar

### Validação de Setup (rodar primeiro)

```bash
# Valida que ambiente está configurado corretamente
pytest tests/test_setup_validation.py -v
```

### Testes Rápidos (unit + integration sem real)

```bash
# Todos exceto testes reais e e2e
pytest tests/unit/ tests/integration/ --ignore=tests/integration/real/ -v
```

### Testes Completos (incluindo real, mas sem e2e)

```bash
# Requer APIs online
pytest tests/unit/ tests/integration/ -v
```

### Testes REAIS apenas

```bash
# Testa com APIs/serviços de produção
pytest tests/integration/real/ -v
```

### Tudo (incluindo e2e)

```bash
# ATENÇÃO: Pode levar 30+ minutos
pytest tests/ -v --timeout=900
```

### Com Coverage

```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### Por Markers

```bash
# Apenas testes rápidos
pytest -m "not slow" tests/

# Apenas testes que requerem FFmpeg
pytest -m requires_ffmpeg tests/

# Pular testes externos
pytest -m "not external" tests/
```

---

## 📋 Markers (pytest)

```python
@pytest.mark.unit           # Teste unitário
@pytest.mark.integration    # Teste de integração
@pytest.mark.e2e           # Teste end-to-end
@pytest.mark.slow          # Teste lento (> 5s)
@pytest.mark.requires_ffmpeg   # Requer FFmpeg instalado
@pytest.mark.requires_redis    # Requer Redis rodando
@pytest.mark.external      # Chama serviços externos (pode falhar se DOWN)
```

**Ver markers disponíveis**:
```bash
pytest --markers
```

---

## 🎯 Padrões e Boas Práticas

### ✅ Nomenclatura

```python
# ✅ CORRETO
test_format_timestamp.py
test_video_builder.py
test_real_audio_transcription.py

# ❌ ERRADO (não usar prefixos numéricos)
test_00_setup.py
test_01_video.py
test_001_builder.py
```

### ✅ Estrutura de Classes

```python
class TestVideoBuilder:
    """Testes para VideoBuilder"""
    
    def test_initialization(self):
        """Deve inicializar corretamente"""
        builder = VideoBuilder()
        assert builder is not None
    
    def test_burn_subtitles_with_valid_srt(self):
        """Deve aplicar legendas em vídeo válido"""
        # Arrange
        video = create_test_video()
        srt = create_test_srt()
        
        # Act
        result = builder.burn_subtitles(video, srt)
        
        # Assert
        assert result.exists()
        assert result.size > 0
```

### ✅ Fixtures vs Mocks

```python
# ✅ Use fixtures para setup comum
@pytest.fixture
def sample_video():
    video = create_test_video()
    yield video
    cleanup(video)

# ✅ Use mocks para dependências externas (em unit/integration)
@patch('app.api.transcribe_audio')
def test_transcription_error_handling(mock_transcribe):
    mock_transcribe.side_effect = Exception("API error")
    # Test error handling

# ⚠️ NÃO use mocks em integration/real/
# Testes reais DEVEM chamar APIs reais
```

### ✅ Async Tests

```python
# ✅ Use pytest-asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await process_video_async()
    assert result is not None
```

---

## 🛠️ Ferramentas

- **pytest**: Framework de testes
- **pytest-asyncio**: Suporte para testes assíncronos
- **pytest-cov**: Coverage
- **pytest-timeout**: Timeout automático
- **pytest-xdist**: Execução paralela (`pytest -n auto`)

---

## 📊 Coverage

```bash
# Gerar relatório HTML
pytest --cov=app --cov-report=html tests/

# Abrir relatório
xdg-open htmlcov/index.html
```

**Meta de coverage**: > 80% (ideal > 90%)

---

## ⚠️ Troubleshooting

### Erro: "FFmpeg not found"
```bash
# Instalar FFmpeg
sudo apt-get install ffmpeg

# Verificar
ffmpeg -version
```

### Erro: "Redis connection refused"
```bash
# Iniciar Redis
redis-server

# Em outro terminal
redis-cli ping  # Deve retornar "PONG"
```

### Erro: "Connection timeout" (testes real/)
```bash
# Verificar se API está online
curl https://yttranscriber.loadstask.com/health

# Se retornar 200, API está OK
# Se timeout/erro, API está DOWN (teste vai falhar - correto!)
```

### Testes lentos demais
```bash
# Executar em paralelo
pytest -n auto tests/

# Pular testes lentos
pytest -m "not slow" tests/
```

---

## 📖 Documentação Adicional

- [RELATORIO_EXECUCAO.md](RELATORIO_EXECUCAO.md) - Relatório de execução
- [integration/real/README.md](integration/real/README.md) - Testes com APIs reais
- [conftest.py](conftest.py) - Fixtures disponíveis

---

## 🎯 Próximos Passos

1. ✅ Setup validado: `pytest tests/test_setup_validation.py`
2. ⚡ Testes unitários: `pytest tests/unit/ -v`
3. 🔗 Testes integração: `pytest tests/integration/ -v`
4. 🌐 Testes reais: `pytest tests/integration/real/ -v`
5. 🚀 Testes e2e: `pytest tests/e2e/ -v`
6. 📊 Coverage: `pytest --cov=app tests/`

---

**Desenvolvido com padrão de produção** ✨  
**Sem prefixos numéricos feios (00, 01, etc)** ✅  
**Testes reais refletem produção** 🎯
