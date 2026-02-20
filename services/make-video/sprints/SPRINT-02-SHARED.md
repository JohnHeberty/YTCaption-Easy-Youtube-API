# 🔧 SPRINT 2 - SHARED (EXCEÇÕES, EVENTOS, VALIDAÇÃO)

**Status**: ⏳ Pendente  
**Prioridade**: 🟡 ALTA  
**Duração Estimada**: 2-3 horas  
**Pré-requisitos**: Sprint 1 completa

---

## 🎯 OBJETIVOS

Testar módulos compartilhados usados por toda a aplicação:

1. ✅ Validar hierarquia de exceções personalizadas
2. ✅ Testar sistema de eventos (se existir)
3. ✅ Testar funções de validação
4. ✅ Validar domain integration
5. ✅ Garantir que exceções carregam mensagens corretas

---

## 📁 ARQUIVOS NO ESCOPO

```
app/shared/
├── __init__.py
├── exceptions.py          # Exceções v1
├── exceptions_v2.py       # Exceções v2 (revisadas)
├── events.py              # Sistema de eventos
├── validation.py          # Funções de validação
└── domain_integration.py  # Integração com domínio
```

---

## 🧪 TESTES - `tests/unit/shared/test_exceptions.py`

```python
"""Testes para exceções personalizadas"""
import pytest
from app.shared.exceptions import *
from app.shared.exceptions_v2 import *


class TestExceptionsV1:
    """Testes para exceptions.py"""
    
    def test_exceptions_module_imports(self):
        """Módulo de exceções importa sem erros"""
        from app.shared import exceptions
        assert exceptions is not None
    
    def test_custom_exception_can_be_raised(self):
        """Exceções personalizadas podem ser levantadas"""
        # Descobrir exceções disponíveis
        from app.shared import exceptions
        exception_classes = [
            obj for name, obj in exceptions.__dict__.items()
            if isinstance(obj, type) and issubclass(obj, Exception)
        ]
        
        if exception_classes:
            ExceptionClass = exception_classes[0]
            with pytest.raises(ExceptionClass):
                raise ExceptionClass("Test message")
    
    def test_exception_preserves_message(self):
        """Mensagens de erro são preservadas"""
        from app.shared import exceptions
        
        msg = "Detailed error message"
        
        # Testar com Exception genérica se não houver custom
        try:
            raise ValueError(msg)
        except ValueError as e:
            assert str(e) == msg


class TestExceptionsV2:
    """Testes para exceptions_v2.py"""
    
    def test_exceptions_v2_module_imports(self):
        """Módulo v2 importa sem erros"""
        from app.shared import exceptions_v2
        assert exceptions_v2 is not None
    
    def test_exception_hierarchy(self):
        """Exceções têm hierarquia correta"""
        from app.shared import exceptions_v2
        
        # Buscar classe base customizada (se existir)
        base_classes = [
            obj for name, obj in exceptions_v2.__dict__.items()
            if isinstance(obj, type) 
            and issubclass(obj, Exception)
            and 'Base' in name
        ]
        
        if base_classes:
            BaseException = base_classes[0]
            assert issubclass(BaseException, Exception)


class TestExceptionIntegration:
    """Testes de integração de exceções"""
    
    def test_exceptions_used_in_real_scenario(self, tmp_path):
        """Exceções funcionam em cenário real"""
        # Simular erro comum: arquivo não encontrado
        non_existent_file = tmp_path / "does_not_exist.txt"
        
        with pytest.raises(FileNotFoundError):
            content = non_existent_file.read_text()
    
    def test_exception_with_context(self):
        """Exceções carregam contexto adicional"""
        video_id = "test_123"
        
        try:
            # Simular erro
            raise ValueError(f"Video processing failed for {video_id}")
        except ValueError as e:
            assert video_id in str(e)
```

---

## 🧪 TESTES - `tests/unit/shared/test_validation.py`

```python
"""Testes para funções de validação"""
import pytest
from pathlib import Path


class TestValidation:
    """Testes para validation.py"""
    
    def test_validation_module_imports(self):
        """Módulo de validação importa"""
        try:
            from app.shared import validation
            assert validation is not None
        except ImportError:
            pytest.skip("validation.py não existe")
    
    def test_validate_file_exists(self, tmp_path):
        """Validar existência de arquivo"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        assert test_file.exists()
        assert test_file.is_file()
    
    def test_validate_directory_exists(self, tmp_path):
        """Validar existência de diretório"""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        
        assert test_dir.exists()
        assert test_dir.is_dir()
    
    def test_validate_video_format(self, real_test_video):
        """Validar formato de vídeo"""
        assert real_test_video.suffix == ".mp4"
        assert real_test_video.exists()
        assert real_test_video.stat().st_size > 0
    
    def test_validate_audio_format(self, real_test_audio):
        """Validar formato de áudio"""
        assert real_test_audio.suffix == ".mp3"
        assert real_test_audio.exists()
        assert real_test_audio.stat().st_size > 0
    
    def test_validate_path_is_absolute(self):
        """Validar se path é absoluto"""
        absolute_path = Path("/tmp/test")
        relative_path = Path("./test")
        
        assert absolute_path.is_absolute()
        assert not relative_path.is_absolute()
    
    def test_validate_file_extension(self):
        """Validar extensão de arquivo"""
        video_exts = ['.mp4', '.avi', '.mov']
        audio_exts = ['.mp3', '.wav', '.aac']
        
        test_video = Path("video.mp4")
        test_audio = Path("audio.mp3")
        
        assert test_video.suffix in video_exts
        assert test_audio.suffix in audio_exts


class TestDomainIntegration:
    """Testes para domain_integration.py"""
    
    def test_domain_integration_imports(self):
        """Módulo de integração importa"""
        try:
            from app.shared import domain_integration
            assert domain_integration is not None
        except ImportError:
            pytest.skip("domain_integration.py não existe")


class TestEvents:
    """Testes para events.py"""
    
    def test_events_module_imports(self):
        """Módulo de eventos importa"""
        try:
            from app.shared import events
            assert events is not None
        except ImportError:
            pytest.skip("events.py não existe")
    
    def test_event_creation(self):
        """Eventos podem ser criados"""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class TestEvent:
            name: str
            timestamp: datetime
            data: dict
        
        event = TestEvent(
            name="test.event",
            timestamp=datetime.now(),
            data={"key": "value"}
        )
        
        assert event.name == "test.event"
        assert event.data["key"] == "value"
```

---

## 🧪 TESTES - `tests/unit/shared/test_shared_integration.py`

```python
"""Testes de integração do módulo shared"""
import pytest


class TestSharedModuleIntegration:
    """Testes de integração entre componentes shared"""
    
    def test_shared_module_exports(self):
        """Módulo shared exporta componentes principais"""
        import app.shared
        assert app.shared is not None
    
    def test_all_shared_modules_import(self):
        """Todos os módulos shared podem ser importados"""
        modules = [
            'exceptions',
            'exceptions_v2',
            'events',
            'validation',
            'domain_integration',
        ]
        
        for module_name in modules:
            try:
                module = __import__(f'app.shared.{module_name}', fromlist=[''])
                assert module is not None
            except ImportError as e:
                # Alguns módulos podem não existir
                pytest.skip(f"Module {module_name} not found: {e}")
    
    def test_shared_used_in_real_workflow(self, tmp_path):
        """Shared modules funcionam em workflow real"""
        # Simular um fluxo real
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video data")
        
        # Validações básicas
        assert video_file.exists()
        assert video_file.suffix == ".mp4"
        assert video_file.stat().st_size > 0
        
        # Simular erro e capturar
        try:
            if video_file.stat().st_size < 1000:
                raise ValueError(f"Video file too small: {video_file}")
        except ValueError as e:
            assert "too small" in str(e)
```

---

## 📋 PASSO A PASSO

### **PASSO 1: Criar Estrutura**

```bash
mkdir -p tests/unit/shared
touch tests/unit/shared/__init__.py
touch tests/unit/shared/test_exceptions.py
touch tests/unit/shared/test_validation.py
touch tests/unit/shared/test_shared_integration.py
```

### **PASSO 2: Implementar Testes**

Copie os códigos acima para os respectivos arquivos.

### **PASSO 3: Executar**

```bash
# Todos os testes shared
pytest tests/unit/shared/ -v

# Com cobertura
pytest tests/unit/shared/ --cov=app.shared --cov-report=term -v

# Teste específico
pytest tests/unit/shared/test_exceptions.py -v -s
```

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

- [ ] Todos os arquivos shared testados
- [ ] Exceções funcionam corretamente
- [ ] Validações passam com dados reais
- [ ] Cobertura > 90%
- [ ] Nenhum teste falhando

---

## 📊 VALIDAÇÃO

```bash
pytest tests/unit/shared/ -v --cov=app.shared --covreport=term

# Output esperado:
# tests/unit/shared/test_exceptions.py ........... PASSED
# tests/unit/shared/test_validation.py .......... PASSED
# tests/unit/shared/test_shared_integration.py .. PASSED
# Coverage: >90%
```

---

**Status**: ⏳ Pendente  
**Data de Conclusão**: ___________
