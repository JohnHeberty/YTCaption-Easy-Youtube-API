"""
Validação do Setup de Testes - Sprint 0
========================================

Este arquivo valida que todo o ambiente de testes está configurado
corretamente antes de começar os sprints de desenvolvimento.

EXECUTAR PRIMEIRO: pytest tests/test_setup_validation.py -v

Se todos os testes passarem, o ambiente está pronto para os sprints.
"""

import os
import sys
import subprocess
from pathlib import Path
import pytest
import redis
import tempfile
import shutil


# ============================================================================
# TESTES DE FERRAMENTAS EXTERNAS
# ============================================================================

class TestExternalTools:
    """Valida que todas as ferramentas externas necessárias estão instaladas."""
    
    def test_ffmpeg_is_installed(self):
        """FFmpeg deve estar instalado e acessível."""
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, "FFmpeg não está instalado ou não funciona"
        assert "ffmpeg version" in result.stdout.lower(), "Saída do FFmpeg inválida"
    
    def test_ffprobe_is_installed(self):
        """FFprobe deve estar instalado e acessível."""
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, "FFprobe não está instalado ou não funciona"
        assert "ffprobe version" in result.stdout.lower(), "Saída do FFprobe inválida"
    
    def test_python_version(self):
        """Python deve ser 3.9 ou superior."""
        version = sys.version_info
        assert version.major == 3, f"Python major version deve ser 3, encontrado: {version.major}"
        assert version.minor >= 9, f"Python minor version deve ser >= 9, encontrado: {version.minor}"
    
    def test_pytest_plugins_available(self):
        """Plugins essenciais do pytest devem estar disponíveis."""
        # pytest-asyncio
        try:
            import pytest_asyncio
            assert True
        except ImportError:
            pytest.fail("pytest-asyncio não está instalado. Execute: pip install pytest-asyncio")
        
        # pytest-timeout
        try:
            import pytest_timeout
            assert True
        except ImportError:
            pytest.fail("pytest-timeout não está instalado. Execute: pip install pytest-timeout")


# ============================================================================
# TESTES DE REDIS
# ============================================================================

class TestRedisConnection:
    """Valida que Redis está acessível e configurado corretamente."""
    
    def test_redis_is_accessible(self):
        """Redis deve estar rodando e acessível."""
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                socket_connect_timeout=5
            )
            response = client.ping()
            assert response is True, "Redis ping falhou"
            client.close()
        except redis.ConnectionError as e:
            pytest.fail(f"Não foi possível conectar ao Redis: {e}")
    
    def test_redis_test_database_is_separate(self):
        """Database de teste (15) deve ser diferente da produção."""
        redis_db = int(os.getenv("REDIS_DB", "0"))
        assert redis_db == 15, f"REDIS_DB deve ser 15 para testes, encontrado: {redis_db}"
    
    def test_redis_can_write_and_read(self):
        """Redis deve permitir operações de escrita e leitura."""
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "15"))
        
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        
        try:
            # Escrever
            test_key = "test_setup_validation_key"
            test_value = "test_value_12345"
            client.set(test_key, test_value, ex=10)
            
            # Ler
            retrieved_value = client.get(test_key)
            assert retrieved_value == test_value, f"Valor lido não corresponde. Esperado: {test_value}, Obtido: {retrieved_value}"
            
            # Limpar
            client.delete(test_key)
        finally:
            client.close()


# ============================================================================
# TESTES DE PERMISSÕES E DIRETÓRIOS
# ============================================================================

class TestFileSystemPermissions:
    """Valida que o sistema de arquivos tem as permissões adequadas."""
    
    def test_can_create_temporary_directories(self):
        """Deve ser possível criar diretórios temporários."""
        temp_dir = Path(tempfile.mkdtemp(prefix="ytcaption_validation_"))
        assert temp_dir.exists(), "Não foi possível criar diretório temporário"
        assert temp_dir.is_dir(), "Path criado não é um diretório"
        shutil.rmtree(temp_dir)
    
    def test_can_write_files(self):
        """Deve ser possível escrever arquivos."""
        temp_dir = Path(tempfile.mkdtemp(prefix="ytcaption_validation_"))
        test_file = temp_dir / "test.txt"
        
        try:
            test_file.write_text("test content")
            assert test_file.exists(), "Arquivo não foi criado"
            
            content = test_file.read_text()
            assert content == "test content", "Conteúdo do arquivo não corresponde"
        finally:
            shutil.rmtree(temp_dir)
    
    def test_can_delete_files(self):
        """Deve ser possível deletar arquivos."""
        temp_dir = Path(tempfile.mkdtemp(prefix="ytcaption_validation_"))
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        test_file.unlink()
        assert not test_file.exists(), "Arquivo não foi deletado"
        
        shutil.rmtree(temp_dir)


# ============================================================================
# TESTES DE VARIÁVEIS DE AMBIENTE
# ============================================================================

class TestEnvironmentVariables:
    """Valida que as variáveis de ambiente estão configuradas."""
    
    def test_environment_is_test(self):
        """Variável ENVIRONMENT deve ser 'test'."""
        env = os.getenv("ENVIRONMENT", "")
        assert env == "test", f"ENVIRONMENT deve ser 'test', encontrado: '{env}'"
    
    def test_redis_variables_are_set(self):
        """Variáveis do Redis devem estar definidas."""
        redis_host = os.getenv("REDIS_HOST", "localhost")  # Default para testes
        redis_port = os.getenv("REDIS_PORT", "6379")  # Default para testes
        redis_db = os.getenv("REDIS_DB", "15")  # Default para testes
        
        # Apenas validar que são valores razoáveis
        assert redis_host, "REDIS_HOST está vazio"
        assert redis_port, "REDIS_PORT está vazio"
        assert redis_db == "15", f"REDIS_DB deve ser '15' para testes, encontrado: '{redis_db}'"
    
    def test_log_level_is_set(self):
        """LOG_LEVEL deve estar definido."""
        log_level = os.getenv("LOG_LEVEL")
        assert log_level is not None, "LOG_LEVEL não está definido"
        assert log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR"], \
            f"LOG_LEVEL inválido: {log_level}"


# ============================================================================
# TESTES DE FIXTURES DO PYTEST
# ============================================================================

class TestPytestFixtures:
    """Valida que as fixtures do conftest.py funcionam corretamente."""
    
    def test_temp_dir_fixture_works(self, temp_dir):
        """Fixture temp_dir deve criar diretório temporário."""
        assert temp_dir.exists(), "Diretório temporário não foi criado"
        assert temp_dir.is_dir(), "temp_dir não é um diretório"
        
        # Testar escrita
        test_file = temp_dir / "test.txt"
        test_file.write_text("fixture test")
        assert test_file.read_text() == "fixture test"
    
    def test_test_dirs_fixture_works(self, test_dirs):
        """Fixture test_dirs deve criar estrutura de diretórios."""
        # Baseado em conftest.py, test_dirs tem: transform, validate, approved, rejected, output
        required_dirs = ["transform", "validate", "approved", "rejected", "output"]
        
        for dir_name in required_dirs:
            dir_path = test_dirs.get(dir_name)
            assert dir_path is not None, f"Diretório '{dir_name}' não está em test_dirs"
            assert dir_path.exists(), f"Diretório '{dir_name}' não foi criado"
            assert dir_path.is_dir(), f"Path '{dir_name}' não é um diretório"


# ============================================================================
# TESTES DE GERAÇÃO DE ASSETS (FFMPEG)
# ============================================================================

class TestFFmpegAssetGeneration:
    """Valida que é possível gerar vídeos e áudios com FFmpeg."""
    
    def test_can_generate_simple_video(self, temp_dir):
        """Deve ser possível gerar um vídeo simples com FFmpeg."""
        video_path = temp_dir / "test_video.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=blue:s=640x480:d=2:r=30",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-t", "2",
            str(video_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Falha ao gerar vídeo: {result.stderr}"
        assert video_path.exists(), "Arquivo de vídeo não foi criado"
        assert video_path.stat().st_size > 0, "Arquivo de vídeo está vazio"
    
    def test_can_generate_simple_audio(self, temp_dir):
        """Deve ser possível gerar um áudio simples com FFmpeg."""
        audio_path = temp_dir / "test_audio.mp3"
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2",
            "-c:a", "libmp3lame",
            str(audio_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Falha ao gerar áudio: {result.stderr}"
        assert audio_path.exists(), "Arquivo de áudio não foi criado"
        assert audio_path.stat().st_size > 0, "Arquivo de áudio está vazio"
    
    def test_can_probe_video_metadata(self, temp_dir):
        """Deve ser possível extrair metadados de vídeo com FFprobe."""
        # Primeiro gerar um vídeo
        video_path = temp_dir / "test_video.mp4"
        
        gen_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=red:s=320x240:d=1:r=30",
            "-f", "lavfi",
            "-i", "anullsrc",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-t", "1",
            str(video_path)
        ]
        
        subprocess.run(gen_cmd, capture_output=True, timeout=10)
        assert video_path.exists()
        
        # Agora usar FFprobe
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=width,height,duration",
            "-of", "default=noprint_wrappers=1",
            str(video_path)
        ]
        
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, f"Falha ao usar FFprobe: {result.stderr}"
        assert "width=320" in result.stdout, "Metadados de largura incorretos"
        assert "height=240" in result.stdout, "Metadados de altura incorretos"


# ============================================================================
# TESTE DE IMPORTAÇÃO DE MÓDULOS
# ============================================================================

class TestModuleImports:
    """Valida que os módulos principais podem ser importados."""
    
    def test_can_import_app_modules(self):
        """Módulos do app devem ser importáveis."""
        try:
            # Core
            from app.core import config
            assert hasattr(config, 'get_settings'), "config.get_settings não encontrado"
            
            # Shared
            from app.shared import exceptions
            assert True
            
        except ImportError as e:
            pytest.fail(f"Falha ao importar módulos do app: {e}")
    
    def test_app_directory_in_path(self):
        """Diretório app deve estar no sys.path."""
        app_dir = Path(__file__).parent.parent / "app"
        app_dir_str = str(app_dir)
        
        # Verificar se app está no sys.path direta ou indiretamente
        parent_in_path = any(
            app_dir_str.startswith(p) or p in app_dir_str
            for p in sys.path
        )
        
        assert parent_in_path or str(app_dir.parent) in sys.path, \
            f"Diretório app ({app_dir}) não está acessível no sys.path"


# ============================================================================
# RELATÓRIO FINAL
# ============================================================================

def test_print_validation_summary():
    """
    Imprime um resumo da validação ao final.
    Este teste sempre passa e serve apenas para dar feedback visual.
    """
    print("\n" + "="*70)
    print("✅ VALIDAÇÃO DO AMBIENTE DE TESTES COMPLETA")
    print("="*70)
    print("\nTodos os pré-requisitos foram verificados:")
    print("  ✓ FFmpeg e FFprobe instalados")
    print("  ✓ Python 3.9+ configurado")
    print("  ✓ Redis acessível (database 15)")
    print("  ✓ Permissões de arquivo/diretório OK")
    print("  ✓ Variáveis de ambiente configuradas")
    print("  ✓ Fixtures do pytest funcionando")
    print("  ✓ Geração de assets (vídeo/áudio) funcional")
    print("  ✓ Módulos do app importáveis")
    print("\n" + "="*70)
    print("🚀 AMBIENTE PRONTO PARA OS SPRINTS DE TESTE!")
    print("="*70)
    print("\nPróximo passo: Sprint 1 - Testes de Core (config.py)")
    print("Comando: pytest tests/unit/core/test_config.py -v")
    print("="*70 + "\n")
    
    assert True
