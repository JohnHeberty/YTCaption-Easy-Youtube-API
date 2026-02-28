"""
Gerenciador de dispositivos GPU/CPU (Single Responsibility Principle).
Responsável APENAS por detectar e validar dispositivos de computação.
"""
import logging
from typing import Dict, Any
import torch

from ..domain.interfaces import IDeviceManager

logger = logging.getLogger(__name__)


class TorchDeviceManager(IDeviceManager):
    """
    Gerencia dispositivos de computação (GPU/CPU) usando PyTorch.
    
    Responsabilidades:
    - Detectar dispositivos disponíveis
    - Validar funcionamento de dispositivos
    - Fornecer informações sobre hardware
    """
    
    def __init__(self, preferred_device: str = "auto"):
        """
        Args:
            preferred_device: Dispositivo preferido ('auto', 'cuda', 'cpu')
        """
        self.preferred_device = preferred_device.lower()
        self._cached_device: str = None
    
    def detect_device(self) -> str:
        """
        Detecta melhor dispositivo disponível.
        
        Returns:
            'cuda' se GPU disponível e preferida, senão 'cpu'
        """
        if self._cached_device:
            return self._cached_device
        
        cuda_available = torch.cuda.is_available()
        
        if self.preferred_device == "cpu":
            self._cached_device = "cpu"
            logger.info("ℹ️ Usando CPU (configurado)")
            return "cpu"
        
        if self.preferred_device == "cuda" or self.preferred_device == "auto":
            if cuda_available:
                # Valida se GPU realmente funciona
                if self.validate_device("cuda"):
                    self._cached_device = "cuda"
                    logger.info("✅ Usando CUDA (GPU)")
                    self._log_gpu_info()
                    return "cuda"
                else:
                    logger.warning("⚠️ CUDA disponível mas falhou validação, usando CPU")
                    self._cached_device = "cpu"
                    return "cpu"
            else:
                logger.warning("⚠️ CUDA não disponível, usando CPU")
                self._cached_device = "cpu"
                return "cpu"
        
        # Fallback
        self._cached_device = "cpu"
        return "cpu"
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Retorna informações detalhadas sobre dispositivos.
        
        Returns:
            Dict com informações de CPU e GPU
        """
        info = {
            "cuda_available": torch.cuda.is_available(),
            "pytorch_version": torch.__version__,
            "preferred_device": self.preferred_device
        }
        
        if info["cuda_available"]:
            try:
                info["gpu"] = {
                    "count": torch.cuda.device_count(),
                    "devices": []
                }
                
                for i in range(torch.cuda.device_count()):
                    device_props = {
                        "id": i,
                        "name": torch.cuda.get_device_name(i),
                        "memory_total_mb": round(
                            torch.cuda.get_device_properties(i).total_memory / 1024**2, 2
                        ),
                        "compute_capability": f"{torch.cuda.get_device_properties(i).major}.{torch.cuda.get_device_properties(i).minor}"
                    }
                    
                    # Memória atual (se disponível)
                    if i == 0:  # Apenas GPU 0 por simplicidade
                        device_props["memory_allocated_mb"] = round(
                            torch.cuda.memory_allocated(i) / 1024**2, 2
                        )
                        device_props["memory_reserved_mb"] = round(
                            torch.cuda.memory_reserved(i) / 1024**2, 2
                        )
                    
                    info["gpu"]["devices"].append(device_props)
                
                info["cuda_version"] = torch.version.cuda
            except Exception as e:
                logger.error(f"Erro ao coletar info da GPU: {e}")
                info["gpu_error"] = str(e)
        
        return info
    
    def validate_device(self, device: str) -> bool:
        """
        Valida se dispositivo está funcionando corretamente.
        
        Args:
            device: 'cuda' ou 'cpu'
        
        Returns:
            True se dispositivo está operacional
        """
        try:
            if device == "cpu":
                # CPU sempre disponível
                test_tensor = torch.randn(100, 100)
                result = test_tensor @ test_tensor.T
                return result is not None
            
            elif device == "cuda":
                if not torch.cuda.is_available():
                    return False
                
                # Testa operação na GPU
                test_tensor = torch.randn(1000, 1000).to('cuda')
                result = test_tensor @ test_tensor.T
                
                # Verifica memória
                memory_allocated = torch.cuda.memory_allocated(0)
                
                # Libera memória de teste
                del test_tensor, result
                torch.cuda.empty_cache()
                
                return memory_allocated > 0
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao validar device {device}: {e}")
            return False
    
    def _log_gpu_info(self):
        """Registra informações da GPU no log"""
        try:
            info = self.get_device_info()
            if "gpu" in info and "devices" in info["gpu"]:
                for gpu in info["gpu"]["devices"]:
                    logger.info(f"   └─ GPU {gpu['id']}: {gpu['name']}")
                    logger.info(f"      └─ Memória Total: {gpu['memory_total_mb']:.0f} MB")
                    logger.info(f"      └─ Compute: {gpu['compute_capability']}")
        except Exception as e:
            logger.warning(f"Não foi possível logar info da GPU: {e}")
