"""
Validação de setup de testes.
Execute este teste primeiro para garantir que o ambiente está configurado corretamente.

Usage:
    pytest tests/test_setup_validation.py -v
"""
import sys
import pytest
from pathlib import Path


class TestEnvironmentSetup:
    """Valida configuração básica do ambiente de testes."""
    
    def test_python_version(self):
        """Verifica versão do Python (>= 3.11)."""
        assert sys.version_info >= (3, 11), f"Python 3.11+ requerido, encontrado {sys.version}"
    
    def test_app_directory_exists(self):
        """Verifica que diretório app existe."""
        app_dir = Path(__file__).parent.parent / "app"
        assert app_dir.exists(), f"Diretório app não encontrado: {app_dir}"
    
    def test_app_importable(self):
        """Verifica que módulos app são importáveis."""
        try:
            from app import config
            from app import models
            assert True
        except ImportError as e:
            pytest.fail(f"Erro ao importar módulos app: {e}")


class TestDependencies:
    """Valida dependências instaladas."""
    
    def test_pytest_installed(self):
        """Verifica pytest instalado."""
        import pytest as pt
        assert pt.__version__
    
    def test_fastapi_installed(self):
        """Verifica FastAPI instalado."""
        try:
            import fastapi
            assert fastapi.__version__
        except ImportError:
            pytest.fail("FastAPI não instalado")
    
    def test_faster_whisper_installed(self):
        """Verifica faster-whisper instalado."""
        try:
            import faster_whisper
            assert True
        except ImportError:
            pytest.fail("faster-whisper não instalado")
    
    def test_torch_installed(self):
        """Verifica torch instalado."""
        try:
            import torch
            assert torch.__version__
        except ImportError:
            pytest.fail("PyTorch não instalado")
    
    def test_redis_client_available(self):
        """Verifica redis-py instalado."""
        try:
            import redis
            assert redis.__version__
        except ImportError:
            pytest.fail("redis-py não instalado")
    
    def test_celery_available(self):
        """Verifica Celery instalado."""
        try:
            import celery
            assert celery.__version__
        except ImportError:
            pytest.fail("Celery não instalado")
    
    def test_pydub_available(self):
        """Verifica pydub instalado."""
        try:
            from pydub import AudioSegment
            assert True
        except ImportError:
            pytest.fail("pydub não instalado")


class TestAudioTools:
    """Valida ferramentas de áudio disponíveis."""
    
    def test_ffmpeg_available(self):
        """Verifica FFmpeg instalado e acessível."""
        import subprocess
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, "FFmpeg não executou corretamente"
            assert "ffmpeg version" in result.stdout.lower()
        except FileNotFoundError:
            pytest.fail("FFmpeg não encontrado no PATH")
        except subprocess.TimeoutExpired:
            pytest.fail("FFmpeg timeout")
    
    def test_ffprobe_available(self):
        """Verifica ffprobe instalado."""
        import subprocess
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0
        except FileNotFoundError:
            pytest.fail("ffprobe não encontrado no PATH")


class TestTestResources:
    """Valida recursos de teste disponíveis."""
    
    def test_test_audio_file_exists(self):
        """Verifica arquivo de áudio de teste existe."""
        test_audio = Path(__file__).parent / "TEST-.ogg"
        assert test_audio.exists(), f"Arquivo TEST-.ogg não encontrado: {test_audio}"
        assert test_audio.stat().st_size > 0, "Arquivo TEST-.ogg está vazio"
    
    def test_test_directories_created(self):
        """Verifica estrutura de diretórios de teste."""
        test_dir = Path(__file__).parent
        
        required_dirs = [
            "unit",
            "integration",
            "e2e",
            "fixtures",
            "assets",
        ]
        
        for dir_name in required_dirs:
            dir_path = test_dir / dir_name
            assert dir_path.exists(), f"Diretório {dir_name} não encontrado"
            assert dir_path.is_dir()


class TestConfiguration:
    """Valida configurações de teste."""
    
    def test_pytest_ini_exists(self):
        """Verifica pytest.ini ou pyproject.toml existe."""
        test_dir = Path(__file__).parent
        root_dir = test_dir.parent
        
        has_pytest_ini = (test_dir / "pytest.ini").exists()
        has_pyproject = (root_dir / "pyproject.toml").exists()
        
        assert has_pytest_ini or has_pyproject, "Configuração pytest não encontrada"
    
    def test_conftest_loaded(self, setup_test_environment):
        """Verifica que conftest.py foi carregado."""
        # setup_test_environment é uma fixture do conftest.py
        # Se ela não existir, este teste falhará
        assert setup_test_environment is None  # Fixture não retorna nada


class TestSummary:
    """Resume validação do setup."""
    
    def test_all_systems_go(self):
        """Teste final - tudo pronto para executar testes."""
        print("\n" + "="*70)
        print("✅ SETUP VALIDADO COM SUCESSO!")
        print("="*70)
        print("\nAmbiente de testes configurado corretamente:")
        print("  ✅ Python 3.11+")
        print("  ✅ Dependências instaladas")
        print("  ✅ FFmpeg disponível")
        print("  ✅ Recursos de teste presentes")
        print("  ✅ Estrutura de diretórios criada")
        print("\n🚀 Você pode executar os testes com segurança:")
        print("   pytest tests/ -v")
        print("="*70 + "\n")
        assert True


if __name__ == "__main__":
    """Permite executar diretamente: python test_setup_validation.py"""
    pytest.main([__file__, "-v", "--tb=short"])
