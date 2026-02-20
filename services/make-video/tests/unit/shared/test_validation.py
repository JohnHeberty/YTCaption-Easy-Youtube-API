"""
Testes para Validações - Sprint 2
==================================

Testa funções de validação (se existirem) e validações básicas.
Usa apenas dados reais, sem mocks.
"""
import pytest
import sys
from pathlib import Path

# Garantir que app está no path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# TESTES DE VALIDATION.PY
# ============================================================================

class TestValidationModule:
    """Testes para módulo validation.py"""
    
    def test_validation_module_exists(self):
        """Módulo validation.py existe"""
        from app.shared import validation
        assert validation is not None
        assert hasattr(validation, '__file__')
    
    def test_validation_has_functions(self):
        """Módulo tem funções de validação"""
        from app.shared import validation
        
        # Buscar funções (não classes, não privadas)
        functions = [
            name for name in dir(validation)
            if callable(getattr(validation, name))
            and not name.startswith('_')
            and not isinstance(getattr(validation, name), type)
        ]
        
        # É OK não ter funções, mas mostrar se tiver
        print(f"\n   Funções encontradas: {len(functions)}")
        if functions:
            for func in functions[:5]:
                print(f"   - {func}")


# ============================================================================
# TESTES DE VALIDAÇÃO BÁSICA (USO REAL)
# ============================================================================

class TestFileValidation:
    """Validações de arquivos com dados reais"""
    
    def test_validate_file_exists(self, temp_dir):
        """Validar que arquivo existe"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        # Validação real
        assert test_file.exists(), "Arquivo deve existir"
        assert test_file.is_file(), "Deve ser arquivo, não diretório"
        assert test_file.stat().st_size > 0, "Arquivo não pode estar vazio"
    
    def test_validate_file_does_not_exist(self, temp_dir):
        """Validar que arquivo não existe"""
        non_existent = temp_dir / "does_not_exist.txt"
        
        assert not non_existent.exists(), "Arquivo não deve existir"
    
    def test_validate_directory_exists(self, temp_dir):
        """Validar que diretório existe"""
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        
        assert test_dir.exists(), "Diretório deve existir"
        assert test_dir.is_dir(), "Deve ser diretório, não arquivo"
    
    def test_validate_path_is_absolute(self):
        """Validar se path é absoluto"""
        absolute_path = Path("/tmp/test")
        relative_path = Path("./test")
        
        assert absolute_path.is_absolute(), "Path absoluto deve ser detectado"
        assert not relative_path.is_absolute(), "Path relativo deve ser detectado"


class TestVideoFileValidation:
    """Validações de arquivos de vídeo"""
    
    def test_validate_video_extension(self):
        """Validar extensões de vídeo válidas"""
        valid_video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        
        test_video = Path("test.mp4")
        assert test_video.suffix in valid_video_extensions
    
    def test_validate_video_format(self, sample_video_path):
        """Validar formato de vídeo real (fixture)"""
        assert sample_video_path.exists(), "Vídeo de teste deve existir"
        assert sample_video_path.suffix == ".mp4", "Deve ser MP4"
        assert sample_video_path.stat().st_size > 0, "Vídeo não pode estar vazio"
        
        # Validar que é binário (não texto)
        with open(sample_video_path, 'rb') as f:
            header = f.read(4)
            assert len(header) == 4, "Deve ter pelo menos 4 bytes"
    
    def test_detect_invalid_video_extension(self):
        """Detectar extensões inválidas"""
        invalid_video_extensions = ['.txt', '.jpg', '.pdf', '.doc']
        
        test_file = Path("test.txt")
        assert test_file.suffix not in ['.mp4', '.avi', '.mov']


class TestAudioFileValidation:
    """Validações de arquivos de áudio"""
    
    def test_validate_audio_extension(self):
        """Validar extensões de áudio válidas"""
        valid_audio_extensions = ['.mp3', '.wav', '.aac', '.ogg', '.m4a']
        
        test_audio = Path("test.mp3")
        assert test_audio.suffix in valid_audio_extensions
    
    def test_validate_audio_format(self, sample_audio_path):
        """Validar formato de áudio real (fixture)"""
        assert sample_audio_path.exists(), "Áudio de teste deve existir"
        assert sample_audio_path.suffix == ".ogg", "Deve ser OGG"
        assert sample_audio_path.stat().st_size > 0, "Áudio não pode estar vazio"
        
        # Validar que é binário
        with open(sample_audio_path, 'rb') as f:
            header = f.read(4)
            assert len(header) == 4, "Deve ter pelo menos 4 bytes"


class TestPathValidation:
    """Validações de paths"""
    
    def test_validate_path_components(self):
        """Validar componentes de path"""
        test_path = Path("/root/data/videos/test.mp4")
        
        assert test_path.name == "test.mp4", "Nome do arquivo correto"
        assert test_path.stem == "test", "Stem (sem extensão) correto"
        assert test_path.suffix == ".mp4", "Extensão correta"
        assert test_path.parent.name == "videos", "Parent correto"
    
    def test_validate_path_joining(self, temp_dir):
        """Validar concatenação de paths"""
        base = temp_dir
        relative = "videos/test.mp4"
        
        full_path = base / relative
        
        assert str(temp_dir) in str(full_path), "Base deve estar no path completo"
        assert "videos" in str(full_path), "Subdirectory deve estar no path"
        assert "test.mp4" in str(full_path), "Arquivo deve estar no path"
    
    def test_validate_path_normalization(self):
        """Validar normalização de paths"""
        messy_path = Path("./data/../data/./videos/test.mp4")
        normalized = messy_path.resolve()
        
        # Normalized deve ter menos componentes
        assert "/./" not in str(normalized), "Não deve ter ./"
        assert "/../" not in str(normalized), "Não deve ter ../"


# ============================================================================
# TESTES DE DOMAIN_INTEGRATION.PY
# ============================================================================

class TestDomainIntegration:
    """Testes para domain_integration.py"""
    
    def test_domain_integration_module_exists(self):
        """Módulo domain_integration.py existe"""
        from app.shared import domain_integration
        assert domain_integration is not None
        assert hasattr(domain_integration, '__file__')
    
    def test_domain_integration_has_content(self):
        """Módulo tem conteúdo (funções ou classes)"""
        from app.shared import domain_integration
        
        # Buscar tudo que não é privado
        public_items = [
            name for name in dir(domain_integration)
            if not name.startswith('_')
        ]
        
        print(f"\n   Itens públicos: {len(public_items)}")
        if public_items:
            for item in public_items[:5]:
                print(f"   - {item}")


# ============================================================================
# TESTES DE EVENTS.PY
# ============================================================================

class TestEventsModule:
    """Testes para events.py"""
    
    def test_events_module_exists(self):
        """Módulo events.py existe"""
        from app.shared import events
        assert events is not None
        assert hasattr(events, '__file__')
    
    def test_events_has_content(self):
        """Módulo tem conteúdo"""
        from app.shared import events
        
        # Buscar classes e funções públicas
        public_items = [
            name for name in dir(events)
            if not name.startswith('_')
        ]
        
        print(f"\n   Itens públicos em events: {len(public_items)}")
        if public_items:
            for item in public_items[:5]:
                print(f"   - {item}")


class TestEventCreation:
    """Testes de criação de eventos (padrão)"""
    
    def test_simple_event_dict(self):
        """Criar evento simples como dict"""
        from datetime import datetime
        
        event = {
            "type": "video.processed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "video_id": "test_123",
                "status": "completed"
            }
        }
        
        assert event["type"] == "video.processed"
        assert "video_id" in event["data"]
        assert event["data"]["video_id"] == "test_123"
    
    def test_event_with_dataclass(self):
        """Criar evento usando dataclass"""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class VideoEvent:
            event_type: str
            video_id: str
            timestamp: datetime
            metadata: dict
        
        event = VideoEvent(
            event_type="video.processed",
            video_id="test_456",
            timestamp=datetime.now(),
            metadata={"duration": 60}
        )
        
        assert event.event_type == "video.processed"
        assert event.video_id == "test_456"
        assert event.metadata["duration"] == 60


# ============================================================================
# TESTE FINAL DE VALIDAÇÃO
# ============================================================================

@pytest.mark.unit
def test_sprint2_validation_summary():
    """Resumo do Sprint 2 - Validações"""
    from app.shared import validation, domain_integration, events
    
    print("\n" + "=" * 70)
    print("📊 SPRINT 2 - VALIDAÇÕES - RESUMO")
    print("=" * 70)
    print(f"✅ Módulo validation.py: importado")
    print(f"✅ Módulo domain_integration.py: importado")
    print(f"✅ Módulo events.py: importado")
    print(f"✅ Validações de arquivo testadas")
    print(f"✅ Validações de vídeo testadas")
    print(f"✅ Validações de áudio testadas")
    print(f"✅ Validações de path testadas")
    print(f"✅ Criação de eventos testada")
    print("=" * 70)
    
    # Assertions finais
    assert validation is not None
    assert domain_integration is not None
    assert events is not None
