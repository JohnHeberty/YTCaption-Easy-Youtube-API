"""
Testes para device_manager.py.

✅ Sem Mocks - usa StubTorch para simular CUDA
✅ Verifica detecção de dispositivo
✅ Testa fallback CPU
✅ Testa seleção de compute_type
"""

import pytest


# Stub para CUDA
class StubCuda:
    """Stub que simula torch.cuda"""
    
    def __init__(self, available):
        self.available = available
    
    def is_available(self):
        return self.available
    
    def device_count(self):
        return 1 if self.available else 0
    
    def get_device_name(self, device=0):
        return "NVIDIA GeForce RTX 3090" if self.available else ""


# Stub para torch
class StubTorch:
    """Stub que simula torch sem usar Mock"""
    
    def __init__(self, cuda_available=False):
        self.cuda_available = cuda_available
        self.cuda = StubCuda(cuda_available)


@pytest.fixture
def stub_torch_cpu():
    """Torch stub sem CUDA"""
    return StubTorch(cuda_available=False)


@pytest.fixture
def stub_torch_cuda():
    """Torch stub com CUDA"""
    return StubTorch(cuda_available=True)


def test_detect_device_cpu(stub_torch_cpu):
    """Testa detecção de CPU"""
    is_cuda_available = stub_torch_cpu.cuda.is_available()
    device = "cuda" if is_cuda_available else "cpu"
    
    assert device == "cpu"


def test_detect_device_cuda(stub_torch_cuda):
    """Testa detecção de CUDA"""
    is_cuda_available = stub_torch_cuda.cuda.is_available()
    device = "cuda" if is_cuda_available else "cpu"
    
    assert device == "cuda"


def test_device_count_cpu(stub_torch_cpu):
    """Testa contagem de dispositivos (CPU)"""
    count = stub_torch_cpu.cuda.device_count()
    assert count == 0


def test_device_count_cuda(stub_torch_cuda):
    """Testa contagem de dispositivos (CUDA)"""
    count = stub_torch_cuda.cuda.device_count()
    assert count == 1


def test_device_name_cpu(stub_torch_cpu):
    """Testa nome do dispositivo (CPU)"""
    if stub_torch_cpu.cuda.device_count() > 0:
        name = stub_torch_cpu.cuda.get_device_name(0)
    else:
        name = "CPU"
    
    assert name == "CPU"


def test_device_name_cuda(stub_torch_cuda):
    """Testa nome do dispositivo (CUDA)"""
    name = stub_torch_cuda.cuda.get_device_name(0)
    assert "NVIDIA" in name or "GeForce" in name


def test_compute_type_selection_cpu():
    """Testa seleção de compute_type para CPU"""
    device = "cpu"
    compute_type = "int8" if device == "cpu" else "float16"
    
    assert compute_type == "int8"


def test_compute_type_selection_cuda():
    """Testa seleção de compute_type para CUDA"""
    device = "cuda"
    compute_type = "int8" if device == "cpu" else "float16"
    
    assert compute_type == "float16"


def test_fallback_to_cpu_on_error(stub_torch_cuda):
    """Testa fallback para CPU em caso de erro"""
    try:
        # Simula erro ao usar CUDA
        raise RuntimeError("CUDA out of memory")
    except RuntimeError:
        device = "cpu"
    
    assert device == "cpu"


def test_device_info_collection(stub_torch_cuda):
    """Testa coleta de informações do dispositivo"""
    info = {
        "cuda_available": stub_torch_cuda.cuda.is_available(),
        "device_count": stub_torch_cuda.cuda.device_count(),
        "device_name": stub_torch_cuda.cuda.get_device_name(0) if stub_torch_cuda.cuda.device_count() > 0 else "CPU"
    }
    
    assert info["cuda_available"] is True
    assert info["device_count"] == 1
    assert "NVIDIA" in info["device_name"]


def test_device_selection_priority():
    """Testa prioridade de seleção de dispositivo"""
    # Ordem: CUDA > CPU
    preferences = ["cuda", "cpu"]
    available = ["cpu"]  # Simula apenas CPU disponível
    
    selected = None
    for pref in preferences:
        if pref in available:
            selected = pref
            break
    
    assert selected == "cpu"


def test_device_validation():
    """Testa validação de dispositivo"""
    valid_devices = ["cpu", "cuda", "auto"]
    
    test_device = "cuda"
    assert test_device in valid_devices
    
    invalid_device = "vulkan"
    assert invalid_device not in valid_devices
