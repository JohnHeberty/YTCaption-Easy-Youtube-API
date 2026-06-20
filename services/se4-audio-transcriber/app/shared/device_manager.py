"""Gerenciador de dispositivos GPU/CPU (Single Responsibility Principle)."""
from __future__ import annotations

from typing import Any
import torch

from ..domain.interfaces import IDeviceManager
from common.log_utils import get_logger

logger = get_logger(__name__)


class TorchDeviceManager(IDeviceManager):
    """Detecta e valida dispositivos de computação usando PyTorch."""

    def __init__(self, preferred_device: str = "auto") -> None:
        self.preferred_device = self._normalize(preferred_device)
        self._cached_device: str | None = None

    @staticmethod
    def _normalize(device: str) -> str:
        normalized = device.lower() if device else "auto"
        if not normalized or normalized == "cpu":
            return "cpu"
        if normalized != "cuda":
            return "auto"
        return "cuda"

    # -- IDeviceManager --------------------------------------------------

    def detect_device(self) -> str:
        """Detecta melhor dispositivo disponível (cuda/cpu)."""
        if self._cached_device is not None:
            return self._cached_device

        if self.preferred_device == "cpu":
            self._cached_device = "cpu"
            logger.info("Usando CPU (configurado)")
            return "cpu"

        if torch.cuda.is_available() and self.validate_device("cuda"):
            self._cached_device = "cuda"
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA detectado: {device_name}")
            return "cuda"

        logger.warning("CUDA não disponível ou falhou validação, usando CPU")
        self._cached_device = "cpu"
        return "cpu"

    def get_device_info(self) -> dict[str, Any]:
        """Retorna informações sobre dispositivos disponíveis."""
        info: Dict[str, Any] = {
            "cuda_available": torch.cuda.is_available(),
            "pytorch_version": torch.__version__,
            "preferred_device": self.preferred_device,
        }

        if not info["cuda_available"]:
            return info

        try:
            devices = []
            for i in range(torch.cuda.device_count()):
                props = {
                    "id": i,
                    "name": torch.cuda.get_device_name(i),
                    "memory_total_mb": round(
                        torch.cuda.get_device_properties(i).total_memory / 1024**2, 2
                    ),
                }
                if i == 0:
                    props["memory_allocated_mb"] = round(
                        torch.cuda.memory_allocated(i) / 1024**2, 2
                    )
                    props["memory_reserved_mb"] = round(
                        torch.cuda.memory_reserved(i) / 1024**2, 2
                    )
                devices.append(props)

            info["gpu"] = {
                "count": torch.cuda.device_count(),
                "devices": devices,
            }
        except Exception as e:
            logger.error(f"Erro ao coletar info da GPU: {e}")
            info["gpu_error"] = str(e)

        return info

    def validate_device(self, device: str) -> bool:
        """Valida se dispositivo está funcionando."""
        try:
            if device == "cpu":
                t = torch.randn(100, 100)
                _ = t @ t.T
                return True

            if device == "cuda" and torch.cuda.is_available():
                t = torch.randn(1000, 1000).to("cuda")
                _ = t @ t.T
                del t
                torch.cuda.empty_cache()
                return True

            return False
        except Exception as e:
            logger.error(f"Erro ao validar device {device}: {e}")
            return False
