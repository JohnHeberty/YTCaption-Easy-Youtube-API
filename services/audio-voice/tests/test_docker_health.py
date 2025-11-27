"""
Testes de health check do container Docker
Sprint 1: Infraestrutura
"""
import pytest
import os
import sys


class TestDockerEnvironment:
    """
    Valida que ambiente Docker está configurado corretamente
    """
    
    def test_python_version(self):
        """Python deve ser 3.10 ou superior"""
        version = sys.version_info
        assert version >= (3, 10), f"Python {version.major}.{version.minor} too old, need ≥3.10"
    
    def test_required_directories_exist(self):
        """Diretórios principais devem existir"""
        base_dir = "/app" if os.path.exists("/app") else "."
        
        required_dirs = [
            "uploads",
            "processed",
            "temp",
            "logs",
            "voice_profiles",
            "models"
        ]
        
        for dir_name in required_dirs:
            dir_path = os.path.join(base_dir, dir_name)
            assert os.path.exists(dir_path), f"Directory {dir_path} should exist"
            assert os.path.isdir(dir_path), f"{dir_path} should be a directory"
    
    def test_required_directories_writable(self):
        """Diretórios principais devem ser graváveis"""
        base_dir = "/app" if os.path.exists("/app") else "."
        
        writable_dirs = [
            "uploads",
            "processed",
            "temp",
            "logs"
        ]
        
        for dir_name in writable_dirs:
            dir_path = os.path.join(base_dir, dir_name)
            if os.path.exists(dir_path):
                assert os.access(dir_path, os.W_OK), f"{dir_path} should be writable"
    
    def test_nvidia_env_vars(self):
        """Variáveis de ambiente NVIDIA devem estar configuradas"""
        # Apenas valida se estamos em ambiente Docker
        if os.path.exists("/.dockerenv"):
            assert os.getenv("NVIDIA_VISIBLE_DEVICES"), "NVIDIA_VISIBLE_DEVICES not set"
            assert os.getenv("NVIDIA_DRIVER_CAPABILITIES"), "NVIDIA_DRIVER_CAPABILITIES not set"
    
    def test_cuda_env_vars(self):
        """Variáveis de ambiente CUDA devem estar configuradas"""
        if os.path.exists("/.dockerenv"):
            # CUDA_VISIBLE_DEVICES pode ser "0" ou "all"
            cuda_devices = os.getenv("CUDA_VISIBLE_DEVICES")
            assert cuda_devices is not None, "CUDA_VISIBLE_DEVICES not set"
    
    def test_force_cuda_enabled(self):
        """FORCE_CUDA deve estar habilitado"""
        if os.path.exists("/.dockerenv"):
            force_cuda = os.getenv("FORCE_CUDA")
            assert force_cuda == "1", "FORCE_CUDA should be set to 1"


class TestSystemDependencies:
    """
    Valida que dependências do sistema estão instaladas
    """
    
    def test_ffmpeg_available(self):
        """ffmpeg deve estar instalado"""
        import subprocess
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, "ffmpeg command failed"
            assert "ffmpeg version" in result.stdout, "ffmpeg version not found in output"
        except FileNotFoundError:
            pytest.fail("ffmpeg not found in PATH")
    
    def test_libsndfile_available(self):
        """libsndfile deve estar disponível (via soundfile)"""
        try:
            import soundfile
            # Tenta ler metadados de um arquivo vazio (apenas valida import)
            assert hasattr(soundfile, 'read'), "soundfile.read not available"
        except ImportError:
            pytest.fail("soundfile package not installed")
    
    def test_torch_available(self):
        """PyTorch deve estar disponível"""
        try:
            import torch
            assert hasattr(torch, 'tensor'), "torch.tensor not available"
        except ImportError:
            pytest.fail("torch package not installed")
    
    def test_torchaudio_available(self):
        """torchaudio deve estar disponível"""
        try:
            import torchaudio
            assert hasattr(torchaudio, 'load'), "torchaudio.load not available"
        except ImportError:
            pytest.fail("torchaudio package not installed")


class TestHealthCheckEndpoint:
    """
    Valida que health check HTTP funciona (se serviço estiver rodando)
    """
    
    @pytest.mark.skipif(
        not os.path.exists("/.dockerenv"),
        reason="Only runs inside Docker container"
    )
    def test_health_endpoint_responds(self):
        """Endpoint / deve responder (basic health)"""
        try:
            import requests
            response = requests.get("http://localhost:8005/", timeout=5)
            assert response.status_code in [200, 404], \
                f"Health endpoint returned {response.status_code}"
        except requests.exceptions.ConnectionError:
            # Serviço pode não estar rodando em testes unitários
            pytest.skip("Service not running")
        except ImportError:
            pytest.skip("requests package not available")
