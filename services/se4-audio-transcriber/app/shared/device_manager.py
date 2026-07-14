"""Re-export TorchDeviceManager from services for backward compatibility."""
from __future__ import annotations

from ..services.device_manager import TorchDeviceManager

__all__ = ["TorchDeviceManager"]
