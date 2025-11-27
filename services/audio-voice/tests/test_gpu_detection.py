"""
Testes de detecção e disponibilidade de GPU
Sprint 1: Infraestrutura Docker + CUDA
"""
import pytest
import torch
import time


class TestGPUDetection:
    """
    Testes para validar que GPU está disponível e funcional
    """
    
    def test_cuda_available(self):
        """GPU NVIDIA deve estar disponível via CUDA"""
        assert torch.cuda.is_available(), "CUDA not available - GPU required for RVC"
    
    def test_cuda_device_count(self):
        """Deve haver pelo menos 1 GPU disponível"""
        device_count = torch.cuda.device_count()
        assert device_count >= 1, f"Expected ≥1 GPU, found {device_count}"
    
    def test_cuda_device_name(self):
        """Nome da GPU deve ser identificável"""
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            assert len(device_name) > 0, "GPU name should not be empty"
            assert "NVIDIA" in device_name or "Tesla" in device_name or "GeForce" in device_name or "RTX" in device_name, \
                f"Unexpected GPU: {device_name}"
    
    def test_cuda_memory_available(self):
        """GPU deve ter memória suficiente (≥12GB)"""
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            total_memory = torch.cuda.get_device_properties(device).total_memory
            total_memory_gb = total_memory / (1024**3)
            
            assert total_memory_gb >= 12.0, \
                f"GPU has {total_memory_gb:.1f}GB VRAM, minimum 12GB required"
    
    def test_cuda_compute_capability(self):
        """GPU deve ter Compute Capability ≥7.0 (RTX 2000+)"""
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            capability = torch.cuda.get_device_capability(device)
            major, minor = capability
            
            assert major >= 7, \
                f"GPU Compute Capability {major}.{minor} too old, need ≥7.0"
    
    def test_simple_gpu_operation(self):
        """Deve conseguir executar operação simples na GPU"""
        if torch.cuda.is_available():
            device = torch.device('cuda:0')
            
            # Cria tensor na GPU
            x = torch.randn(100, 100, device=device)
            y = torch.randn(100, 100, device=device)
            
            # Operação na GPU
            z = torch.matmul(x, y)
            
            assert z.device.type == 'cuda', "Operation should execute on GPU"
            assert z.shape == (100, 100), "Result shape incorrect"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="GPU tests require CUDA")
class TestGPUPerformance:
    """
    Testes de performance básica da GPU
    """
    
    def test_gpu_faster_than_cpu(self):
        """GPU deve ser mais rápida que CPU para operações grandes"""
        size = 5000
        
        # CPU
        x_cpu = torch.randn(size, size)
        y_cpu = torch.randn(size, size)
        
        start_cpu = time.time()
        z_cpu = torch.matmul(x_cpu, y_cpu)
        cpu_time = time.time() - start_cpu
        
        # GPU
        device = torch.device('cuda:0')
        x_gpu = torch.randn(size, size, device=device)
        y_gpu = torch.randn(size, size, device=device)
        
        # Warmup
        torch.matmul(x_gpu, y_gpu)
        torch.cuda.synchronize()
        
        # Measure
        start_gpu = time.time()
        z_gpu = torch.matmul(x_gpu, y_gpu)
        torch.cuda.synchronize()
        gpu_time = time.time() - start_gpu
        
        # GPU deve ser significativamente mais rápida (pelo menos 5x)
        speedup = cpu_time / gpu_time
        assert speedup > 5.0, f"GPU speedup {speedup:.1f}x is too low, expected >5x"
    
    def test_gpu_memory_allocation(self):
        """Deve conseguir alocar e liberar memória GPU"""
        if torch.cuda.is_available():
            device = torch.device('cuda:0')
            
            # Memória antes
            torch.cuda.empty_cache()
            mem_before = torch.cuda.memory_allocated(device)
            
            # Aloca tensor grande (1GB)
            size = 16384
            x = torch.randn(size, size, device=device)
            mem_after = torch.cuda.memory_allocated(device)
            
            # Deve ter alocado memória
            allocated = mem_after - mem_before
            assert allocated > 0, "Should have allocated GPU memory"
            
            # Libera
            del x
            torch.cuda.empty_cache()
            mem_final = torch.cuda.memory_allocated(device)
            
            # Memória deve estar próxima do inicial (tolerância 100MB)
            diff = abs(mem_final - mem_before)
            assert diff < 100 * 1024 * 1024, f"Memory leak detected: {diff / 1024**2:.1f}MB not freed"


class TestDockerHealthCheck:
    """
    Testes que validam health check do container
    """
    
    def test_pytorch_version(self):
        """PyTorch deve estar instalado com versão correta"""
        assert hasattr(torch, '__version__'), "PyTorch not installed"
        version = torch.__version__
        # Deve ser 2.4.0 ou superior
        major, minor = map(int, version.split('.')[:2])
        assert (major, minor) >= (2, 4), f"PyTorch {version} too old, need ≥2.4.0"
    
    def test_cuda_version_compatibility(self):
        """Versão CUDA deve ser compatível (12.1)"""
        if torch.cuda.is_available():
            cuda_version = torch.version.cuda
            assert cuda_version is not None, "CUDA version not detected"
            # Aceita 12.1.x
            assert cuda_version.startswith('12.1'), \
                f"CUDA version {cuda_version} incompatible, need 12.1.x"
    
    def test_gpu_device_properties(self):
        """Deve conseguir ler propriedades da GPU"""
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(device)
            
            assert props.name, "GPU name should be available"
            assert props.total_memory > 0, "GPU memory should be >0"
            assert props.major >= 7, "GPU compute capability too old"
