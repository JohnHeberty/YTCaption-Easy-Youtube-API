# 🎯 SPRINT 1 - CORE (CONFIGURAÇÃO E MODELOS)

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 3-4 horas  
**Pré-requisitos**: Sprint 0 completa

---

## 🎯 OBJETIVOS

Esta sprint é **CRÍTICA** pois contém o **FIX DO BUG DE PRODUÇÃO**:

1. 🔧 **CORRIGIR**: `KeyError: 'transform_dir'` em `get_settings()`
2. ✅ Testar todas as configurações do sistema
3. ✅ Validar carregamento de variáveis de ambiente
4. ✅ Garantir que todos os diretórios são criados
5. ✅ Testar modelos Pydantic
6. ✅ Validar constantes do sistema

> **⚠️ BUG CRÍTICO**: O dicionário retornado por `get_settings()` não inclui as chaves `'transform_dir'`, `'validate_dir'`, e `'approved_dir'` que são usadas em `video_pipeline.py:282`

---

## 📁 ARQUIVOS NO ESCOPO

```
app/core/
├── __init__.py                 # 2 linhas - Exports
├── config.py                   # 205 linhas - ⚠️ CONTÉM O BUG
├── models.py                   # XX linhas - Modelos Pydantic
└── constants.py                # XX linhas - Constantes do sistema
```

### Responsabilidades

| Arquivo | Responsabilidade | Complexidade |
|---------|------------------|--------------|
| `config.py` | Settings, get_settings(), ensure_directories() | 🔴 ALTA |
| `models.py` | Modelos de dados (Pydantic) | 🟡 MÉDIA |
| `constants.py` | Constantes globais | 🟢 BAIXA |
| `__init__.py` | Exports e imports | 🟢 BAIXA |

---

## 🐛 ANÁLISE DO BUG

### Localização do Erro

**Arquivo**: `app/pipeline/video_pipeline.py`  
**Linha**: 282  
**Função**: `cleanup_orphaned_files()`

**Código com erro**:
```python
def cleanup_orphaned_files(self, max_age_minutes: int = 30):
    folders = {
        'shorts': Path(self.settings['shorts_cache_dir']),
        'transform': Path(self.settings['transform_dir']),      # ❌ KeyError aqui!
        'validate': Path(self.settings['validate_dir']) / 'in_progress'  # ❌ E aqui!
    }
```

### Causa Raiz

Em `app/core/config.py`, a função `get_settings()` (linhas 137-200) retorna um dicionário, mas **NÃO INCLUI** as chaves:
- `'transform_dir'`
- `'validate_dir'`
- `'approved_dir'`

### Impacto

- Job CRON `cleanup_orphaned_videos_cron` falha a cada 5 minutos
- Arquivos órfãos não são limpos
- Logs cheios de erros
- Disk space pode encher

---

## 🔧 FIX OBRIGATÓRIO

### Fix #1: Adicionar Chaves Faltantes em `get_settings()`

**Arquivo**: `app/core/config.py`  
**Função**: `get_settings()` (aproximadamente linha 137-200)

**ANTES** (incompleto):
```python
def get_settings() -> Dict[str, Any]:
    """Retorna configurações como dicionário (compatível com padrão)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    
    return {
        "service_name": _settings.service_name,
        "version": _settings.version,
        "port": _settings.port,
        # ... outros campos ...
        "audio_upload_dir": _settings.audio_upload_dir,
        "shorts_cache_dir": _settings.shorts_cache_dir,
        "output_dir": _settings.output_dir,
        # ❌ FALTAM: transform_dir, validate_dir, approved_dir
        "log_level": _settings.log_level,
        # ... resto ...
    }
```

**DEPOIS** (corrigido):
```python
def get_settings() -> Dict[str, Any]:
    """Retorna configurações como dicionário (compatível com padrão)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    
    return {
        "service_name": _settings.service_name,
        "version": _settings.version,
        "port": _settings.port,
        # ... outros campos ...
        "audio_upload_dir": _settings.audio_upload_dir,
        "shorts_cache_dir": _settings.shorts_cache_dir,
        "output_dir": _settings.output_dir,
        
        # 🔧 FIX: Adicionar diretórios do pipeline
        "transform_dir": "./data/transform/videos",
        "validate_dir": "./data/validate",
        "approved_dir": "./data/approved/videos",
        
        "log_level": _settings.log_level,
        # ... resto ...
    }
```

### Fix #2: Atualizar `ensure_directories()`

**ANTES**:
```python
def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    
    dirs = [
        settings["audio_upload_dir"],
        settings["shorts_cache_dir"],
        settings["output_dir"],
        settings["log_dir"],
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
```

**DEPOIS**:
```python
def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    
    dirs = [
        settings["audio_upload_dir"],
        settings["shorts_cache_dir"],
        settings["output_dir"],
        settings["log_dir"],
        settings["transform_dir"],  # 🔧 NOVO
        settings["validate_dir"],   # 🔧 NOVO
        settings["approved_dir"],   # 🔧 NOVO
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
```

---

## 🧪 IMPLEMENTAÇÃO DOS TESTES

### Criar `tests/unit/core/test_config.py`

```python
"""
Testes para app/core/config.py
Foco: Validar que o BUG foi corrigido e settings estão completos
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch
from app.core.config import Settings, get_settings, ensure_directories


class TestSettings:
    """Testes para a classe Settings (Pydantic)"""
    
    def test_settings_instantiates(self):
        """Settings pode ser instanciada"""
        settings = Settings()
        assert settings is not None
    
    def test_settings_has_service_name(self):
        """Settings tem service_name"""
        settings = Settings()
        assert settings.service_name == "make-video"
    
    def test_settings_has_default_port(self):
        """Settings tem porta padrão"""
        settings = Settings()
        assert settings.port == 8004 or isinstance(settings.port, int)
    
    def test_settings_loads_from_env(self, monkeypatch):
        """Settings carrega variáveis de ambiente"""
        monkeypatch.setenv("PORT", "9999")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        # Recriar settings para pegar novos valores
        settings = Settings()
        
        assert settings.port == 9999
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
    
    def test_settings_has_all_required_fields(self):
        """Verifica que todos os campos obrigatórios existem"""
        settings = Settings()
        
        required_fields = [
            'service_name', 'version', 'port', 'debug',
            'redis_url', 'cache_ttl_hours', 'max_cache_size_gb',
            'youtube_search_url', 'video_downloader_url', 'audio_transcriber_url',
            'audio_upload_dir', 'shorts_cache_dir', 'output_dir',
            'log_level', 'log_dir', 'log_format',
            'video_status_db_path',
            'ffmpeg_video_codec', 'ffmpeg_audio_codec',
        ]
        
        for field in required_fields:
            assert hasattr(settings, field), f"Missing field: {field}"
    
    def test_settings_directory_paths_are_strings(self):
        """Paths de diretórios devem ser strings"""
        settings = Settings()
        
        assert isinstance(settings.audio_upload_dir, str)
        assert isinstance(settings.shorts_cache_dir, str)
        assert isinstance(settings.output_dir, str)
        assert isinstance(settings.log_dir, str)
    
    def test_settings_numeric_values_are_valid(self):
        """Valores numéricos devem ser válidos"""
        settings = Settings()
        
        assert settings.port > 0
        assert settings.cache_ttl_hours > 0
        assert settings.max_cache_size_gb > 0
        assert settings.ocr_frames_per_second > 0
        assert settings.ffmpeg_crf >= 0 and settings.ffmpeg_crf <= 51


class TestGetSettings:
    """Testes para a função get_settings()"""
    
    def test_get_settings_returns_dict(self):
        """get_settings() deve retornar um dicionário"""
        settings = get_settings()
        assert isinstance(settings, dict)
        assert len(settings) > 0
    
    def test_get_settings_is_singleton(self):
        """get_settings() deve retornar a mesma instância"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Modificar settings1 deve afetar settings2 (mesmo objeto)
        settings1['_test_key'] = 'test_value'
        assert '_test_key' in settings2
        
        # Cleanup
        del settings1['_test_key']
    
    def test_get_settings_has_basic_keys(self):
        """Verifica chaves básicas no dicionário"""
        settings = get_settings()
        
        basic_keys = [
            'service_name',
            'version',
            'port',
            'redis_url',
            'audio_upload_dir',
            'shorts_cache_dir',
            'output_dir',
            'log_dir',
        ]
        
        missing = [k for k in basic_keys if k not in settings]
        assert missing == [], f"Missing keys: {missing}"
    
    def test_get_settings_has_pipeline_directory_keys(self):
        """
        🔴 TESTE CRÍTICO: Valida que o BUG foi corrigido
        Deve ter as chaves transform_dir, validate_dir, approved_dir
        """
        settings = get_settings()
        
        # Chaves que causavam o KeyError em produção
        pipeline_keys = [
            'transform_dir',      # ❌ FALTAVA - CAUSAVA O BUG
            'validate_dir',       # ❌ FALTAVA - CAUSAVA O BUG
            'approved_dir',       # ❌ FALTAVA - POTENCIAL BUG
        ]
        
        missing_keys = [k for k in pipeline_keys if k not in settings]
        
        # Este teste deve FALHAR antes do fix e PASSAR depois
        assert missing_keys == [], f"❌ BUG NÃO CORRIGIDO! Missing keys: {missing_keys}"
    
    def test_get_settings_pipeline_dirs_are_strings(self):
        """Diretórios do pipeline devem ser strings válidas"""
        settings = get_settings()
        
        assert 'transform_dir' in settings
        assert 'validate_dir' in settings
        assert 'approved_dir' in settings
        
        assert isinstance(settings['transform_dir'], str)
        assert isinstance(settings['validate_dir'], str)
        assert isinstance(settings['approved_dir'], str)
        
        assert len(settings['transform_dir']) > 0
        assert len(settings['validate_dir']) > 0
        assert len(settings['approved_dir']) > 0
    
    def test_get_settings_all_directory_keys_present(self):
        """Validar TODAS as chaves de diretórios necessárias"""
        settings = get_settings()
        
        all_dir_keys = [
            'audio_upload_dir',
            'shorts_cache_dir',
            'output_dir',
            'log_dir',
            'transform_dir',
            'validate_dir',
            'approved_dir',
        ]
        
        missing = [k for k in all_dir_keys if k not in settings]
        assert missing == [], f"Missing directory keys: {missing}"


class TestEnsureDirectories:
    """Testes para ensure_directories()"""
    
    def test_ensure_directories_creates_dirs(self, tmp_path, monkeypatch):
        """ensure_directories() cria todos os diretórios"""
        # Configurar paths temporários
        base = tmp_path / "test_dirs"
        
        monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(base / "audio"))
        monkeypatch.setenv("SHORTS_CACHE_DIR", str(base / "shorts"))
        monkeypatch.setenv("OUTPUT_DIR", str(base / "output"))
        monkeypatch.setenv("LOG_DIR", str(base / "logs"))
        
        # Recarregar settings
        from app.core import config
        config._settings = None  # Reset singleton
        
        # Executar
        ensure_directories()
        
        # Verificar que diretórios foram criados
        settings = get_settings()
        assert Path(settings['audio_upload_dir']).exists()
        assert Path(settings['shorts_cache_dir']).exists()
        assert Path(settings['output_dir']).exists()
        assert Path(settings['log_dir']).exists()
    
    def test_ensure_directories_creates_pipeline_dirs(self, tmp_path, monkeypatch):
        """
        🔴 TESTE CRÍTICO: ensure_directories() deve criar dirs do pipeline
        """
        base = tmp_path / "pipeline_dirs"
        
        # Setar env vars
        monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(base / "audio"))
        mon  keypatch.setenv("SHORTS_CACHE_DIR", str(base / "shorts"))
        monkeypatch.setenv("OUTPUT_DIR", str(base / "output"))
        monkeypatch.setenv("LOG_DIR", str(base / "logs"))
        
        # Reset singleton
        from app.core import config
        config._settings = None
        
        # Executar
        ensure_directories()
        
        # Verificar diretórios do pipeline
        settings = get_settings()
        
        # Se as chaves existem, os diretórios devem ser criados
        if 'transform_dir' in settings:
            assert Path(settings['transform_dir']).exists()
        
        if 'validate_dir' in settings:
            assert Path(settings['validate_dir']).exists()
        
        if 'approved_dir' in settings:
            assert Path(settings['approved_dir']).exists()
    
    def test_ensure_directories_idempotent(self, tmp_path, monkeypatch):
        """ensure_directories() pode ser chamada múltiplas vezes"""
        base = tmp_path / "idempotent"
        
        monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(base / "audio"))
        monkeypatch.setenv("SHORTS_CACHE_DIR", str(base / "shorts"))
        monkeypatch.setenv("OUTPUT_DIR", str(base / "output"))
        monkeypatch.setenv("LOG_DIR", str(base / "logs"))
        
        from app.core import config
        config._settings = None
        
        # Chamar 3 vezes - não deve dar erro
        ensure_directories()
        ensure_directories()
        ensure_directories()
        
        # Verificar que ainda existem
        settings = get_settings()
        assert Path(settings['audio_upload_dir']).exists()


class TestModels:
    """Testes para app/core/models.py (se existir)"""
    
    def test_models_can_be_imported(self):
        """Modelos podem ser importados"""
        try:
            from app.core import models
            assert models is not None
        except ImportError:
            pytest.skip("models.py não existe ou sem modelos")
    
    # Adicionar testes específicos para modelos quando identificados


class TestConstants:
    """Testes para app/core/constants.py (se existir)"""
    
    def test_constants_can_be_imported(self):
        """Constantes podem ser importadas"""
        try:
            from app.core import constants
            assert constants is not None
        except ImportError:
            pytest.skip("constants.py não existe")
    
    # Adicionar testes específicos para constantes


class TestCoreInit:
    """Testes para app/core/__init__.py"""
    
    def test_core_module_imports(self):
        """Módulo core pode ser importado"""
        import app.core
        assert app.core is not None
    
    def test_core_exports_config(self):
        """core exporta config"""
        from app.core import config
        assert config is not None
    
    def test_core_exports_get_settings(self):
        """core exporta get_settings"""
        try:
            from app.core import get_settings
            assert callable(get_settings)
        except ImportError:
            # Pode não estar exportado diretamente
            from app.core.config import get_settings
            assert callable(get_settings)
```

---

## 📋 PASSO A PASSO - IMPLEMENTAÇÃO

### **PASSO 1: Aplicar os Fixes**

```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Fazer backup do arquivo original
cp app/core/config.py app/core/config.py.backup

# Editar o arquivo (usar editor de sua preferência)
nano app/core/config.py
# ou
vim app/core/config.py
# ou
code app/core/config.py
```

Adicione as 3 linhas no lugar correto dentro de `get_settings()`:

```python
"transform_dir": "./data/transform/videos",
"validate_dir": "./data/validate",
"approved_dir": "./data/approved/videos",
```

E atualize `ensure_directories()` para incluir esses diretórios.

---

### **PASSO 2: Criar Estrutura de Testes**

```bash
# Criar diretório
mkdir -p tests/unit/core

# Criar __init__.py
touch tests/unit/core/__init__.py

# Criar arquivo de teste
touch tests/unit/core/test_config.py
```

---

### **PASSO 3: Copiar Código dos Testes**

Copie todo o código da seção "IMPLEMENTAÇÃO DOS TESTES" acima para o arquivo `tests/unit/core/test_config.py`.

---

### **PASSO 4: Executar Testes**

```bash
# Executar apenas testes deste módulo
pytest tests/unit/core/test_config.py -v

# Com mais detalhes
pytest tests/unit/core/test_config.py -v -s

# Com cobertura
pytest tests/unit/core/test_config.py --cov=app.core.config --cov-report=term
```

**Antes do Fix** - Deve FALHAR:
```
FAILED tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys
❌ BUG NÃO CORRIGIDO! Missing keys: ['transform_dir', 'validate_dir', 'approved_dir']
```

**Depois do Fix** - Deve PASSAR:
```
PASSED tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys
```

---

### **PASSO 5: Validar Cobertura**

```bash
# Cobertura detalhada
pytest tests/unit/core/ --cov=app.core --cov-report=html --cov-report=term

# Ver relatório HTML
open htmlcov/index.html
```

**Meta**: Cobertura > 95% em `config.py`

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

- [ ] Fix #1 aplicado: chaves adicionadas em `get_settings()`
- [ ] Fix #2 aplicado: `ensure_directories()` atualizado
- [ ] Arquivo `tests/unit/core/test_config.py` criado
- [ ] **TESTE CRÍTICO PASSA**: `test_get_settings_has_pipeline_directory_keys`
- [ ] Todos os testes de `TestSettings` passando (8/8)
- [ ] Todos os testes de `TestGetSettings` passando (6/6)
- [ ] Todos os testes de `TestEnsureDirectories` passando (3/3)
- [ ] Cobertura de `config.py` > 95%
- [ ] Nenhum teste falhando
- [ ] `pytest tests/unit/core/ -v` 100% sucesso

---

## 🐛 TROUBLESHOOTING

### Problema: Teste ainda falha após aplicar fix

**Sintoma**:
```
AssertionError: ❌ BUG NÃO CORRIGIDO! Missing keys: ['transform_dir']
```

**Causa**: Fix não aplicado corretamente ou singleton não resetado

**Solução**:
```python
# No teste, adicione antes de get_settings():
from app.core import config
config._settings = None  # Reset singleton

settings = get_settings()
```

---

### Problema: Diretórios não sendo criados

**Sintoma**:
```
AssertionError: assert False (Path não existe)
```

**Solução**:
```bash
# Verificar permissões
chmod -R 755 ./data/

# Criar manualmente para teste
mkdir -p ./data/{transform/videos,validate,approved/videos}

# Verificar se ensure_directories() está sendo chamado
python -c "from app.core.config import ensure_directories; ensure_directories(); print('OK')"
```

---

### Problema: Import Error

**Sintoma**:
```
ModuleNotFoundError: No module named 'app'
```

**Solução**:
```bash
# Terminal 1: Adicionar ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Terminal 2: Ou instalar em editable mode
pip install -e .

# Verificar
python -c "from app.core.config import get_settings; print('OK')"
```

---

## 📊 VALIDAÇÃO FINAL

Execute e verifique que todos passam:

```bash
# Teste específico do bug
pytest tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys -v

# Todos os testes do core
pytest tests/unit/core/ -v

# Com cobertura
pytest tests/unit/core/ --cov=app.core --cov-report=term -v

# Smoke test: Importar e validar
python -c "
from app.core.config import get_settings
settings = get_settings()
assert 'transform_dir' in settings, 'BUG AINDA PRESENTE!'
assert 'validate_dir' in settings, 'BUG AINDA PRESENTE!'
assert 'approved_dir' in settings, 'BUG AINDA PRESENTE!'
print('✅ BUG CORRIGIDO COM SUCESSO!')
"
```

---

## 📝 PRÓXIMOS PASSOS

Após concluir esta sprint:

1. ✅ **VALIDAR**: Bug de produção está corrigido
2. ✅ Fazer commit do fix
   ```bash
   git add app/core/config.py tests/unit/core/
   git commit -m "fix: Adiciona chaves pipeline em get_settings() - Corrige KeyError transform_dir"
   git tag sprint-01-complete
   ```
3. ✅ Atualizar status no [README.md](README.md)
4. ✅ Partir para [SPRINT-02-SHARED.md](SPRINT-02-SHARED.md)

---

## 🎉 IMPORTÂNCIA DESTA SPRINT

> **Esta é a sprint mais crítica de todas!** Ela corrige o bug que está causando falhas em produção. Após completá-la, o CRON job deve parar de crashar.

---

**Status**: ⏳ → Atualizar para ✅ quando concluída  
**Data de Conclusão**: ___________  
**Bug Corrigido**: ⬜ Sim ⬜ Não  
**Tempo Real**: ___________
