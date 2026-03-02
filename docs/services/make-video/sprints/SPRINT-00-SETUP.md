# 🛠️ SPRINT 0 - CONFIGURAÇÃO DO AMBIENTE DE TESTES

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 2-3 horas  
**Pré-requisitos**: Nenhum (primeira sprint)

---

## 🎯 OBJETIVOS

Esta sprint é **pré-requisito obrigatório** para todas as outras. Você irá:

1. ✅ Configurar estrutura de diretórios de teste
2. ✅ Criar fixtures globais reutilizáveis
3. ✅ Gerar arquivos de teste reais (vídeos, áudios)
4. ✅ Configurar ambiente de teste (.env.test)
5. ✅ Validar que todos os recursos estão funcionando
6. ✅ Estabelecer baseline de qualidade

> **⚠️ IMPORTANTE**: Sem completar esta sprint, as outras não funcionarão!

---

## 📁 ESTRUTURA A SER CRIADA

```
make-video/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # ⭐ Fixtures globais
│   ├── pytest.ini                     # Configuração do pytest
│   ├── .env.test                      # Variáveis de ambiente de teste
│   │
│   ├── fixtures/                      # Dados de teste reais
│   │   ├── real_videos/
│   │   │   ├── test_sample.mp4       # Vídeo sem legendas (10s)
│   │   │   ├── with_subs.mp4         # Vídeo com legendas (5s)
│   │   │   └── silent.mp4            # Vídeo silencioso (3s)
│   │   ├── real_audio/
│   │   │   ├── test_sample.mp3       # Áudio teste (5s)
│   │   │   ├── silent.wav            # Áudio silencioso (2s)
│   │   │   └── voice.mp3             # Áudio com voz (se possível)
│   │   ├── real_subtitles/
│   │   │   └── sample.ass            # Arquivo .ass válido
│   │   └── config/
│   │       └── test_settings.json    # Configurações extras
│   │
│   ├── unit/                          # Testes unitários (mas reais!)
│   │   └── __init__.py
│   ├── integration/                   # Testes de integração
│   │   └── __init__.py
│   ├── e2e/                          # Testes end-to-end
│   │   └── __init__.py
│   └── data/                         # Dados temporários dos testes
│       ├── raw/
│       ├── transform/
│       ├── validate/
│       ├── approved/
│       └── logs/
```

---

## 🔧 PASSO A PASSO - IMPLEMENTAÇÃO

### **PASSO 1: Criar Estrutura de Diretórios**

```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Criar estrutura
mkdir -p tests/{unit,integration,e2e}
mkdir -p tests/fixtures/{real_videos,real_audio,real_subtitles,config}
mkdir -p tests/data/{raw,transform,validate,approved,logs}

# Criar __init__.py files
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py

echo "✅ Estrutura de diretórios criada"
```

**Validação**:
```bash
tree tests/ -L 2
```

---

### **PASSO 2: Instalar Dependências de Teste**

```bash
# Ativar ambiente virtual (se existir)
source .venv_full/bin/activate || python3 -m venv .venv_test && source .venv_test/bin/activate

# Instalar pytest e plugins
pip install pytest==7.4.3
pip install pytest-cov==4.1.0
pip install pytest-asyncio==0.21.1
pip install pytest-timeout==2.2.0
pip install pytest-xdist==3.5.0
pip install pytest-mock==3.12.0

# Verificar instalação
pytest --version
echo "✅ Dependências instaladas"
```

**Validação**:
```bash
pip list | grep pytest
```

---

### **PASSO 3: Criar conftest.py (Fixtures Globais)**

Crie o arquivo `tests/conftest.py`:

```python
"""
Fixtures globais para todos os testes
Estas fixtures criam recursos REAIS (sem mocks)
"""
import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Dict
import os
import sys

# Adicionar app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings


# ============================================================================
# CONFIGURAÇÃO E SETTINGS
# ============================================================================

@pytest.fixture(scope="session")
def test_settings():
    """
    Settings reais para testes
    Usa configurações do .env.test se existir
    """
    # Carregar .env.test se existir
    env_test = Path(__file__).parent / ".env.test"
    if env_test.exists():
        from dotenv import load_dotenv
        load_dotenv(env_test)
    
    return get_settings()


@pytest.fixture(scope="session")
def test_redis_url():
    """URL do Redis de teste (database 15)"""
    return os.getenv("REDIS_URL", "redis://localhost:6379/15")


# ============================================================================
# DIRETÓRIOS TEMPORÁRIOS
# ============================================================================

@pytest.fixture(scope="function")
def temp_data_dirs(tmp_path):
    """
    Cria estrutura completa de diretórios temporários
    Simula estrutura real do pipeline
    """
    base = tmp_path / "pipeline_data"
    
    dirs = {
        'base': base,
        'raw': base / 'data/raw/shorts',
        'raw_audio': base / 'data/raw/audio',
        'transform': base / 'data/transform/videos',
        'validate': base / 'data/validate/in_progress',
        'approved': base / 'data/approved/videos',
        'output': base / 'data/approved/output',
        'logs': base / 'logs',
        'database': base / 'data/database',
    }
    
    # Criar todos os diretórios
    for name, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)
    
    yield dirs
    
    # Cleanup automático pelo pytest (tmp_path)


@pytest.fixture(scope="function")
def clean_temp_dir(tmp_path):
    """Diretório temporário limpo para uso geral"""
    return tmp_path


# ============================================================================
# VÍDEOS DE TESTE REAIS
# ============================================================================

@pytest.fixture(scope="session")
def real_test_video():
    """
    Vídeo de teste REAL (1080x1920, 10s, sem legendas)
    Gerado uma vez por sessão
    """
    video_path = Path("tests/fixtures/real_videos/test_sample.mp4")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not video_path.exists():
        print("\n🎬 Gerando vídeo de teste real...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=10:size=1080x1920:rate=30",
            "-vf", "drawtext=text='TEST VIDEO':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(video_path)
        ], check=True, capture_output=True)
        print(f"✅ Vídeo criado: {video_path}")
    
    return video_path


@pytest.fixture(scope="session")
def video_with_subtitles():
    """
    Vídeo de teste REAL com legendas simuladas (5s)
    Texto branco na parte inferior (simula legenda)
    """
    video_path = Path("tests/fixtures/real_videos/with_subs.mp4")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not video_path.exists():
        print("\n📝 Gerando vídeo com legendas...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1080x1920:d=5",
            "-vf", "drawtext=text='SUBTITLE TEXT':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.5:boxborderw=10",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(video_path)
        ], check=True, capture_output=True)
        print(f"✅ Vídeo com legendas criado: {video_path}")
    
    return video_path


@pytest.fixture(scope="session")
def silent_video():
    """Vídeo silencioso REAL (3s, sem áudio)"""
    video_path = Path("tests/fixtures/real_videos/silent.mp4")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not video_path.exists():
        print("\n🔇 Gerando vídeo silencioso...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=blue:s=1080x1920:d=3",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(video_path)
        ], check=True, capture_output=True)
        print(f"✅ Vídeo silencioso criado: {video_path}")
    
    return video_path


# ============================================================================
# ÁUDIOS DE TESTE REAIS
# ============================================================================

@pytest.fixture(scope="session")
def real_test_audio():
    """
    Áudio de teste REAL (5s, tom de 440Hz)
    """
    audio_path = Path("tests/fixtures/real_audio/test_sample.mp3")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not audio_path.exists():
        print("\n🎵 Gerando áudio de teste real...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=5",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(audio_path)
        ], check=True, capture_output=True)
        print(f"✅ Áudio criado: {audio_path}")
    
    return audio_path


@pytest.fixture(scope="session")
def silent_audio():
    """Áudio silencioso REAL (2s)"""
    audio_path = Path("tests/fixtures/real_audio/silent.wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not audio_path.exists():
        print("\n🔇 Gerando áudio silencioso...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=duration=2",
            "-c:a", "pcm_s16le",
            str(audio_path)
        ], check=True, capture_output=True)
        print(f"✅ Áudio silencioso criado: {audio_path}")
    
    return audio_path


# ============================================================================
# ARQUIVOS DE LEGENDA REAIS
# ============================================================================

@pytest.fixture(scope="session")
def sample_ass_file():
    """Arquivo .ass válido para testes"""
    ass_path = Path("tests/fixtures/real_subtitles/sample.ass")
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not ass_path.exists():
        content = """[Script Info]
Title: Test Subtitle
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,22,&H00FFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,10,10,10,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Hello World
Dialogue: 0,0:00:02.50,0:00:04.50,Default,,0,0,0,,Testing Subtitles
Dialogue: 0,0:00:05.00,0:00:07: 00,Default,,0,0,0,,Final Test
"""
        ass_path.write_text(content)
        print(f"✅ Arquivo .ass criado: {ass_path}")
    
    return ass_path


# ============================================================================
# HELPERS
# ============================================================================

@pytest.fixture
def ffmpeg_available():
    """Verifica se FFmpeg está disponível"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível")
        return False


@pytest.fixture
def redis_available(test_redis_url):
    """Verifica se Redis está disponível"""
    try:
        import redis
        r = redis.from_url(test_redis_url)
        r.ping()
        return True
    except Exception:
        pytest.skip("Redis não disponível")
        return False


# ============================================================================
# CLEANUP HELPERS
# ============================================================================

@pytest.fixture
def cleanup_test_db():
    """Limpa database SQLite de teste após o teste"""
    db_files = []
    
    def register(db_path: Path):
        db_files.append(db_path)
    
    yield register
    
    # Cleanup
    for db_file in db_files:
        if db_file.exists():
            db_file.unlink()


# ============================================================================
# MARKERS
# ============================================================================

def pytest_configure(config):
    """Registrar markers customizados"""
    config.addinivalue_line("markers", "unit: Testes unitários (mas reais)")
    config.addinivalue_line("markers", "integration: Testes de integração")
    config.addinivalue_line("markers", "e2e: Testes end-to-end")
    config.addinivalue_line("markers", "slow: Testes lentos (>5s)")
    config.addinivalue_line("markers", "requires_video: Requer vídeo real")
    config.addinivalue_line("markers", "requires_audio: Requer áudio real")
    config.addinivalue_line("markers", "requires_redis: Requer Redis ativo")
    config.addinivalue_line("markers", "requires_ffmpeg: Requer FFmpeg instalado")
```

**Salvar arquivo**:
```bash
# O arquivo já está criado acima
echo "✅ conftest.py criado"
```

---

### **PASSO 4: Criar pytest.ini**

Crie o arquivo `pytest.ini` na raiz do projeto:

```ini
[pytest]
# Diretório de testes
testpaths = tests

# Padrões de nomes
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Opções padrão
addopts = 
    -v
    --strict-markers
    --tb=short
    --disable-warnings
    --maxfail=5
    --ff
    -ra

# Markers customizados
markers =
    unit: Testes unitários (mas com dados reais)
    integration: Testes de integração
    e2e: Testes end-to-end completos
    slow: Testes lentos que demoram mais de 5 segundos
    requires_video: Testes que requerem vídeos reais
    requires_audio: Testes que requerem áudios reais
    requires_redis: Testes que requerem Redis ativo
    requires_ffmpeg: Testes que requerem FFmpeg instalado

# Timeout padrão (evitar testes travados)
timeout = 300

# Output
console_output_style = progress

# Coverage (se ativado)
[coverage:run]
source = app
omit = 
    */tests/*
    */__pycache__/*
    */migrations/*
    */.venv*/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

**Salvar arquivo**:
```bash
cat > pytest.ini << 'EOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --tb=short --disable-warnings --maxfail=5 --ff -ra
markers =
    unit: Testes unitários
    integration: Testes de integração
    e2e: Testes end-to-end
    slow: Testes lentos (>5s)
    requires_video: Requer vídeos reais
    requires_audio: Requer áudios reais
    requires_redis: Requer Redis
    requires_ffmpeg: Requer FFmpeg
EOF

echo "✅ pytest.ini criado"
```

---

### **PASSO 5: Criar .env.test**

Crie o arquivo `tests/.env.test`:

```bash
# Redis (usar database 15 para testes)
REDIS_URL=redis://localhost:6379/15

# Diretórios (temporários para testes)
AUDIO_UPLOAD_DIR=./tests/data/raw/audio
SHORTS_CACHE_DIR=./tests/data/raw/shorts
OUTPUT_DIR=./tests/data/approved/output
LOG_DIR=./tests/data/logs

# Database
VIDEO_STATUS_DB_PATH=./tests/data/database/video_status.db

# Logs
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# APIs (usar localhost ou dev/staging)
YOUTUBE_SEARCH_URL=http://localhost:8001
VIDEO_DOWNLOADER_URL=http://localhost:8002
AUDIO_TRANSCRIBER_URL=http://localhost:8003

# Configurações rápidas para testes
CLEANUP_TEMP_AFTER_HOURS=1
CLEANUP_OUTPUT_AFTER_HOURS=2
OCR_MAX_FRAMES=30
OCR_FRAMES_PER_SECOND=2
DOWNLOAD_MAX_POLLS=5
TRANSCRIBE_MAX_POLLS=10

# FFmpeg
FFMPEG_PRESET=ultrafast
FFMPEG_CRF=23

# Debug
DEBUG=true
```

**Salvar arquivo**:
```bash
cat > tests/.env.test << 'EOF'
REDIS_URL=redis://localhost:6379/15
AUDIO_UPLOAD_DIR=./tests/data/raw/audio
SHORTS_CACHE_DIR=./tests/data/raw/shorts
OUTPUT_DIR=./tests/data/approved/output
LOG_DIR=./tests/data/logs
VIDEO_STATUS_DB_PATH=./tests/data/database/video_status.db
LOG_LEVEL=DEBUG
DEBUG=true
FFMPEG_PRESET=ultrafast
OCR_MAX_FRAMES=30
EOF

echo "✅ .env.test criado"
```

---

### **PASSO 6: Criar Teste de Validação**

Crie `tests/test_setup_validation.py` para validar o setup:

```python
"""
Testes de validação do setup
Estes testes verificam que o ambiente está configurado corretamente
"""
import pytest
import subprocess
from pathlib import Path


class TestSetupValidation:
    """Valida que o ambiente de testes está OK"""
    
    def test_pytest_is_working(self):
        """Pytest está funcionando"""
        assert True
    
    def test_fixtures_directory_exists(self):
        """Diretório de fixtures existe"""
        fixtures_dir = Path("tests/fixtures")
        assert fixtures_dir.exists()
        assert (fixtures_dir / "real_videos").exists()
        assert (fixtures_dir / "real_audio").exists()
        assert (fixtures_dir / "real_subtitles").exists()
    
    def test_ffmpeg_is_installed(self, ffmpeg_available):
        """FFmpeg está instalado e funcionando"""
        assert ffmpeg_available
    
    def test_redis_is_available(self, redis_available):
        """Redis está rodando e acessível"""
        assert redis_available
    
    def test_test_video_fixture_works(self, real_test_video):
        """Fixture de vídeo real funciona"""
        assert real_test_video.exists()
        assert real_test_video.stat().st_size > 0
        assert real_test_video.suffix == ".mp4"
    
    def test_test_audio_fixture_works(self, real_test_audio):
        """Fixture de áudio real funciona"""
        assert real_test_audio.exists()
        assert real_test_audio.stat().st_size > 0
        assert real_test_audio.suffix == ".mp3"
    
    def test_temp_dirs_fixture_works(self, temp_data_dirs):
        """Fixture de diretórios temporários funciona"""
        assert temp_data_dirs['raw'].exists()
        assert temp_data_dirs['transform'].exists()
        assert temp_data_dirs['validate'].exists()
        assert temp_data_dirs['approved'].exists()
    
    def test_ass_file_fixture_works(self, sample_ass_file):
        """Fixture de arquivo .ass funciona"""
        assert sample_ass_file.exists()
        content = sample_ass_file.read_text()
        assert "[Script Info]" in content
        assert "[Events]" in content
    
    def test_settings_loads(self, test_settings):
        """Settings carregam corretamente"""
        assert test_settings is not None
        assert 'service_name' in test_settings
        assert test_settings['service_name'] == 'make-video'
```

---

### **PASSO 7: Executar Validação**

```bash
# Coletar testes (verificar se pytest encontra tudo)
pytest --collect-only

# Executar teste de validação
pytest tests/test_setup_validation.py -v

# Se tudo passar:
echo "✅ Setup concluído com sucesso!"
```

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

Marque cada item conforme completa:

- [ ] Estrutura de diretórios criada
- [ ] conftest.py implementado
- [ ] pytest.ini configurado
- [ ] .env.test criado
- [ ] Vídeo de teste gerado (test_sample.mp4)
- [ ] Vídeo com legendas gerado (with_subs.mp4)
- [ ] Áudio de teste gerado (test_sample.mp3)
- [ ] Arquivo .ass criado
- [ ] Teste de validação passa 100%
- [ ] FFmpeg verificado e funcionando
- [ ] Redis verificado e funcionando
- [ ] `pytest --collect-only` sem erros
- [ ] `pytest tests/test_setup_validation.py -v` passa

---

## 🐛 TROUBLESHOOTING

### Problema: FFmpeg não encontrado

**Sintoma**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Solução**:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# Verificar
ffmpeg -version
```

---

### Problema: Redis não conecta

**Sintoma**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solução**:
```bash
# Verificar se Redis está rodando
redis-cli ping

# Se não estiver, iniciar
redis-server --daemonize yes

# Ou com Docker
docker run -d -p 6379:6379 redis:alpine

# Testar conexão
redis-cli -n 15 ping  # Database 15 para testes
```

---

### Problema: Vídeos não sendo gerados

**Sintoma**:
```
FileNotFoundError: tests/fixtures/real_videos/test_sample.mp4
```

**Solução**:
```bash
# Criar manualmente
mkdir -p tests/fixtures/real_videos

ffmpeg -f lavfi -i testsrc=duration=10:size=1080x1920:rate=30 \
  -vf "drawtext=text='TEST':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast \
  tests/fixtures/real_videos/test_sample.mp4

# Verificar
ls -lh tests/fixtures/real_videos/
```

---

### Problema: Pytest não encontra módulo app

**Sintoma**:
```
ModuleNotFoundError: No module named 'app'
```

**Solução**:
```bash
# Adicionar ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Ou instalar em modo desenvolvimento
pip install -e .

# Verificar
python -c "from app.core.config import get_settings; print('OK')"
```

---

### Problema: Permissões negadas

**Sintoma**:
```
PermissionError: [Errno 13] Permission denied
```

**Solução**:
```bash
# Dar permissões corretas
chmod -R 755 tests/
chmod -R 777 tests/data/

# Verificar
ls -la tests/
```

---

## 📊 VALIDAÇÃO FINAL

Execute os comandos abaixo e verifique que todos passam:

```bash
# 1. Estrutura OK
ls tests/fixtures/real_videos/
ls tests/fixtures/real_audio/

# 2. FFmpeg OK
ffmpeg -version

# 3. Redis OK
redis-cli ping

# 4. Pytest OK
pytest --version

# 5. Coleta OK
pytest --collect-only

# 6. Validação OK
pytest tests/test_setup_validation.py -v

# 7. Cobertura OK (opcional)
pytest tests/test_setup_validation.py --cov=app --cov-report=term
```

**Output Esperado**:
```
tests/test_setup_validation.py::TestSetupValidation::test_pytest_is_working PASSED
tests/test_setup_validation.py::TestSetupValidation::test_fixtures_directory_exists PASSED
tests/test_setup_validation.py::TestSetupValidation::test_ffmpeg_is_installed PASSED
tests/test_setup_validation.py::TestSetupValidation::test_redis_is_available PASSED
tests/test_setup_validation.py::TestSetupValidation::test_test_video_fixture_works PASSED
tests/test_setup_validation.py::TestSetupValidation::test_test_audio_fixture_works PASSED
tests/test_setup_validation.py::TestSetupValidation::test_temp_dirs_fixture_works PASSED
tests/test_setup_validation.py::TestSetupValidation::test_ass_file_fixture_works PASSED
tests/test_setup_validation.py::TestSetupValidation::test_settings_loads PASSED

======================== 9 passed in X.XXs ========================
```

---

## 📝 PRÓXIMOS PASSOS

Após concluir esta sprint com sucesso:

1. ✅ Marcar como completa no [README.md](README.md)
2. ✅ Fazer commit:
   ```bash
   git add tests/
   git commit -m "test: Sprint 0 - Setup do ambiente de testes completo"
   git tag sprint-00-complete
   ```
3. ✅ Partir para [SPRINT-01-CORE.md](SPRINT-01-CORE.md)

---

**Status**: ⏳ → Atualizar para ✅ quando concluída  
**Data de Conclusão**: ___________  
**Problemas Encontrados**: ___________  
**Tempo Real**: ___________
