"""
SE8 Image Engine — Device Manager

Handles GPU/CPU/MPS device detection, VRAM state, memory queries, dtype
resolution, and attention capabilities. Extracted from ModelManager to
separate device-level concerns from model lifecycle management.

Design decisions:
- Pure device state — no model loading or LRU logic
- Thread-safe: initialized once, then read-only after init
- Lazy torch import — only loads when first needed
- Config-driven via ImageEngineSettings
"""

from __future__ import annotations
from common.log_utils import get_logger

import threading
from typing import Any

import psutil

logger = get_logger(__name__)

# Lazy torch import — only load when first needed
_torch = None


def _get_torch() -> Any:
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

from enum import Enum


class VRAMState(Enum):
    DISABLED = 0
    NO_VRAM = 1
    LOW_VRAM = 2
    NORMAL_VRAM = 3
    HIGH_VRAM = 4
    SHARED = 5


class CPUState(Enum):
    GPU = 0
    CPU = 1
    MPS = 2


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _dtype_size(dtype) -> int:
    """Return byte size for a torch dtype."""
    torch = _get_torch()
    if dtype in (torch.float16, torch.bfloat16):
        return 2
    if dtype == torch.float32:
        return 4
    try:
        return dtype.itemsize
    except AttributeError:
        return 4


# ---------------------------------------------------------------------------
# DeviceManager — device detection, memory, dtype, attention
# ---------------------------------------------------------------------------

class DeviceManager:
    """Manages GPU/CPU/MPS device state, memory queries, and dtype resolution.

    Initialized once at startup; all query methods are safe to call
    concurrently after construction.
    """

    def __init__(self, settings: Any = None) -> None:
        from app.core.config import get_settings
        self._settings = settings or get_settings()
        self._torch: Any = None  # lazy
        self._lock = threading.Lock()

        # State
        self._cpu_state = CPUState.GPU
        self._vram_state = VRAMState.NORMAL_VRAM
        self._total_vram_mb: float = 0.0
        self._total_ram_mb: float = 0.0

        # Force flags (configurable)
        self._force_fp32 = False
        self._force_fp16 = False
        self._always_vram_offload = False

        # Initialize
        self._detect_device()
        self._detect_vram_state()

    # -----------------------------------------------------------------------
    # Lazy torch import
    # -----------------------------------------------------------------------

    def _get_torch(self) -> Any:
        if self._torch is None:
            import torch
            self._torch = torch
            device_id = self._settings.gpu_device_id
            if device_id is not None:
                import os
                os.environ["CUDA_VISIBLE_DEVICES"] = str(device_id)
        return self._torch

    # -----------------------------------------------------------------------
    # Device detection
    # -----------------------------------------------------------------------

    def _detect_device(self) -> None:
        """Detect available compute device (CUDA/MPS/CPU)."""
        torch = self._get_torch()

        try:
            if torch.backends.mps.is_available():
                self._cpu_state = CPUState.MPS
                logger.info("Detected Apple MPS device")
                return
        except (AttributeError, RuntimeError):
            pass

        if torch.cuda.is_available():
            self._cpu_state = CPUState.GPU
            device = torch.cuda.current_device()
            name = torch.cuda.get_device_name(device)
            logger.info("Detected CUDA device: %s (device %d)", name, device)
            return

        self._cpu_state = CPUState.CPU
        logger.warning("No GPU detected — running on CPU")

    def _detect_vram_state(self) -> None:
        """Determine VRAM state based on available memory."""
        torch = self._get_torch()

        if self._cpu_state != CPUState.GPU:
            self._vram_state = VRAMState.DISABLED
            logger.info("VRAM state: DISABLED (no GPU)")
            return

        if self._cpu_state == CPUState.MPS:
            self._vram_state = VRAMState.SHARED
            logger.info("VRAM state: SHARED (MPS)")
            return

        mode = self._settings.gpu_mode
        if mode == "eager":
            self._vram_state = VRAMState.HIGH_VRAM
            logger.info("VRAM state: HIGH_VRAM (eager mode)")
            return

        self._total_vram_mb = self.get_total_memory() / (1024 * 1024)
        self._total_ram_mb = psutil.virtual_memory().total / (1024 * 1024)
        logger.info("Total VRAM: %.0f MB, Total RAM: %.0f MB", self._total_vram_mb, self._total_ram_mb)

        max_vram = self._settings.max_vram_mb
        if max_vram > 0:
            self._total_vram_mb = min(self._total_vram_mb, max_vram)

        if self._total_vram_mb <= 4096:
            self._vram_state = VRAMState.LOW_VRAM
        else:
            self._vram_state = VRAMState.NORMAL_VRAM

        logger.info("VRAM state: %s", self._vram_state.name)

    # -----------------------------------------------------------------------
    # Device queries
    # -----------------------------------------------------------------------

    @property
    def device(self) -> Any:
        """Get the primary torch device."""
        torch = self._get_torch()
        if self._cpu_state == CPUState.MPS:
            return torch.device("mps")
        if self._cpu_state == CPUState.CPU:
            return torch.device("cpu")
        return torch.device(torch.cuda.current_device())

    @property
    def device_name(self) -> str:
        """Get human-readable device name."""
        torch = self._get_torch()
        dev = self.device
        if hasattr(dev, 'type'):
            if dev.type == 'cuda':
                return f"{dev} : {torch.cuda.get_device_name(dev)}"
            return str(dev.type)
        return str(dev)

    @property
    def vram_state(self) -> VRAMState:
        return self._vram_state

    @property
    def cpu_state(self) -> CPUState:
        return self._cpu_state

    @property
    def total_vram_mb(self) -> float:
        return self._total_vram_mb

    def is_nvidia(self) -> bool:
        return self._cpu_state == CPUState.GPU and bool(self._get_torch().version.cuda)

    def is_device_cpu(self, device: Any = None) -> bool:
        if device is None:
            device = self.device
        return hasattr(device, 'type') and device.type == 'cpu'

    def is_device_mps(self, device: Any = None) -> bool:
        if device is None:
            device = self.device
        return hasattr(device, 'type') and device.type == 'mps'

    def is_gpu_available(self) -> bool:
        return self._cpu_state == CPUState.GPU

    # -----------------------------------------------------------------------
    # Memory queries
    # -----------------------------------------------------------------------

    def get_total_memory(self, device: Any = None) -> int:
        """Get total memory (VRAM or RAM) in bytes."""
        torch = self._get_torch()
        if device is None:
            device = self.device

        if self.is_device_cpu(device) or self.is_device_mps(device):
            return psutil.virtual_memory().total

        if self.is_nvidia():
            _, mem_total = torch.cuda.mem_get_info(device)
            return mem_total

        return psutil.virtual_memory().total

    def get_free_memory(self, device: Any = None, torch_free_too: bool = False) -> int | tuple[int, int]:
        """Get free memory in bytes. Optionally return torch-reserved free too."""
        torch = self._get_torch()
        if device is None:
            device = self.device

        if self.is_device_cpu(device) or self.is_device_mps(device):
            mem_free = psutil.virtual_memory().available
            if torch_free_too:
                return (mem_free, mem_free)
            return mem_free

        if self.is_nvidia():
            stats = torch.cuda.memory_stats(device)
            mem_active = stats['active_bytes.all.current']
            mem_reserved = stats['reserved_bytes.all.current']
            mem_free_cuda, _ = torch.cuda.mem_get_info(device)
            mem_free_torch = mem_reserved - mem_active
            mem_free_total = mem_free_cuda + mem_free_torch
            if torch_free_too:
                return (mem_free_total, mem_free_torch)
            return mem_free_total

        mem_free = psutil.virtual_memory().available
        if torch_free_too:
            return (mem_free, mem_free)
        return mem_free

    # -----------------------------------------------------------------------
    # Dtype resolution
    # -----------------------------------------------------------------------

    def unet_offload_device(self) -> Any:
        """Device to offload UNet to when not in use."""
        torch = self._get_torch()
        if self._vram_state == VRAMState.HIGH_VRAM:
            return self.device
        return torch.device("cpu")

    def unet_initial_load_device(self, parameters: int, dtype: Any) -> Any:
        """Determine initial load device for UNet based on available memory."""
        torch = self._get_torch()
        if self._vram_state == VRAMState.HIGH_VRAM:
            return self.device
        if self._always_vram_offload:
            return torch.device("cpu")

        model_size = _dtype_size(dtype) * parameters
        mem_dev = self.get_free_memory(self.device)
        mem_cpu = self.get_free_memory(torch.device("cpu"))
        if mem_dev > mem_cpu and model_size < mem_dev:
            return self.device
        return torch.device("cpu")

    def unet_dtype(self, device: Any = None, model_params: int = 0) -> Any:
        """Determine UNet dtype based on hardware capabilities."""
        torch = self._get_torch()
        if self._force_fp32:
            return torch.float32
        if self._force_fp16:
            return torch.float16
        if self.should_use_fp16(device=device, model_params=model_params):
            return torch.float16
        return torch.float32

    def should_use_fp16(
        self,
        device: Any = None,
        model_params: int = 0,
        prioritize_performance: bool = True,
    ) -> bool:
        """Determine if FP16 should be used for a model."""
        torch = self._get_torch()
        if device is not None and self.is_device_cpu(device):
            return False
        if self._force_fp16:
            return True
        if device is not None and self.is_device_mps(device):
            return False
        if self._force_fp32:
            return False
        if self._cpu_state in (CPUState.CPU, CPUState.MPS):
            return False
        if torch.cuda.is_bf16_supported():
            return True
        props = torch.cuda.get_device_properties("cuda")
        if props.major < 6:
            return False
        broken_16 = ["1660", "1650", "1630", "T500", "T550", "T600", "MX550", "MX450"]
        for name in broken_16:
            if name in props.name:
                return False
        return props.major >= 7

    def text_encoder_device(self) -> Any:
        """Device for text encoder (CLIP)."""
        torch = self._get_torch()
        if self._vram_state in (VRAMState.HIGH_VRAM, VRAMState.NORMAL_VRAM):
            if self.should_use_fp16(prioritize_performance=False):
                return self.device
        return torch.device("cpu")

    def text_encoder_offload_device(self) -> Any:
        """Offload device for text encoder (always CPU unless always_gpu mode)."""
        torch = self._get_torch()
        if self._vram_state == VRAMState.NO_VRAM:
            return torch.device("cpu")
        return torch.device("cpu")

    def text_encoder_dtype(self, device: Any = None) -> Any:
        """Determine text encoder dtype."""
        torch = self._get_torch()
        if self.is_device_cpu(device):
            return torch.float16
        if self.should_use_fp16(device, prioritize_performance=False):
            return torch.float16
        return torch.float32

    def vae_device(self) -> Any:
        """Device for VAE."""
        return self.device

    def vae_dtype(self) -> Any:
        """Determine VAE dtype."""
        torch = self._get_torch()
        if self.is_nvidia():
            try:
                if torch.cuda.is_bf16_supported():
                    props = torch.cuda.get_device_properties(self.device)
                    if props.major >= 8:
                        return torch.bfloat16
            except (RuntimeError, OSError) as e:
                logger.debug("bf16 detection failed: %s", e)
        return torch.float32

    def intermediate_device(self) -> Any:
        """Device for intermediate computations."""
        return self.device

    def unet_manual_cast(self, weight_dtype: Any, inference_device: Any) -> Any | None:
        """Determine if manual casting is needed for UNet."""
        torch = self._get_torch()
        if weight_dtype == torch.float32:
            return None
        if self.should_use_fp16(inference_device, prioritize_performance=False):
            if weight_dtype == torch.float16:
                return None
            return torch.float16
        return torch.float32

    # -----------------------------------------------------------------------
    # Attention & optimization
    # -----------------------------------------------------------------------

    def pytorch_attention_enabled(self) -> bool:
        """Check if PyTorch SDPA attention is enabled."""
        if self._cpu_state != CPUState.GPU:
            return False
        if self.is_nvidia():
            return True
        return False

    def pytorch_attention_flash_attention(self) -> bool:
        """Check if flash attention is available."""
        if self.pytorch_attention_enabled() and self.is_nvidia():
            return True
        return False
