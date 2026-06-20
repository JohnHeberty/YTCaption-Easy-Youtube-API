"""
SE8 Image Engine — Model Manager

Manages GPU/VRAM state, device detection, model load/unload with LRU eviction.

Design decisions:
- Class-based (ModelManager singleton) instead of global state
- Config-driven (ImageEngineSettings) instead of CLI args
- Thread-safe with Lock for concurrent access
- Lazy/timer-based unload for idle models
- No xformers/DirectML/XPU (CUDA-only for now, extensible)
"""

from __future__ import annotations
from common.log_utils import get_logger

import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Protocol, runtime_checkable

import psutil

logger = get_logger(__name__)

# Lazy torch import — only load when first needed
_torch = None


def _get_torch():
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

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
# Protocol for model objects that ModelManager can track
# ---------------------------------------------------------------------------

@runtime_checkable
class ManagedModel(Protocol):
    """Protocol that model objects must satisfy to be managed by ModelManager."""

    @property
    def load_device(self): ...

    @property
    def current_device(self): ...

    @property
    def offload_device(self): ...

    def model_size(self) -> int: ...

    def model_dtype(self): ...

    def model_patches_to(self, device) -> None: ...

    def patch_model(self, device_to=None, patch_weights=True): ...

    def unpatch_model(self, device) -> None: ...

    def is_clone(self, other) -> bool: ...


# ---------------------------------------------------------------------------
# LoadedModel — wraps a managed model currently in VRAM or tracked
# ---------------------------------------------------------------------------

@dataclass
class LoadedModel:
    """Tracks a model's load state and handles VRAM transfers."""

    model: Any  # ManagedModel
    real_model: Any = field(default=None, repr=False)
    device: Any = field(default=None, repr=False)
    model_accelerated: bool = False
    last_used: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        if self.device is None:
            self.device = self.model.load_device

    @property
    def memory(self) -> int:
        return self.model.model_size()

    def memory_required(self, target_device) -> int:
        if target_device == self.model.current_device:
            return 0
        return self.memory

    def model_load(self, lowvram_model_memory: int = 0):
        """Load model into VRAM. If lowvram_model_memory > 0, use partial offloading."""
        torch = _get_torch()
        patch_model_to = None
        if lowvram_model_memory == 0:
            patch_model_to = self.device

        self.model.model_patches_to(self.device)
        self.model.model_patches_to(self.model.model_dtype())

        try:
            self.real_model = self.model.patch_model(device_to=patch_model_to)
        except Exception:
            self.model.unpatch_model(self.model.offload_device)
            self._unload_acceleration()
            raise

        if lowvram_model_memory > 0:
            logger.info("Loading in lowvram mode: %.1f MB", lowvram_model_memory / (1024 * 1024))
            mem_counter = 0
            for m in self.real_model.modules():
                if hasattr(m, "ldm_patched_cast_weights"):
                    m.prev_ldm_patched_cast_weights = m.ldm_patched_cast_weights
                    m.ldm_patched_cast_weights = True
                    module_mem = _module_size(m)
                    if mem_counter + module_mem < lowvram_model_memory:
                        m.to(self.device)
                        mem_counter += module_mem
                elif hasattr(m, "weight"):
                    m.to(self.device)
                    mem_counter += _module_size(m)
                    logger.debug("lowvram: loaded module regularly %s", m)
            self.model_accelerated = True

        self.last_used = time.monotonic()
        return self.real_model

    def model_unload(self):
        """Unload model from VRAM, move to CPU."""
        self._unload_acceleration()
        self.model.unpatch_model(self.model.offload_device)
        self.model.model_patches_to(self.model.offload_device)

    def _unload_acceleration(self):
        if self.model_accelerated and self.real_model is not None:
            for m in self.real_model.modules():
                if hasattr(m, "prev_ldm_patched_cast_weights"):
                    m.ldm_patched_cast_weights = m.prev_ldm_patched_cast_weights
                    del m.prev_ldm_patched_cast_weights
            self.model_accelerated = False

    def touch(self):
        """Update last_used timestamp."""
        self.last_used = time.monotonic()

    def __eq__(self, other):
        if isinstance(other, LoadedModel):
            return self.model is other.model
        return NotImplemented

    def __hash__(self):
        return id(self.model)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _module_size(module) -> int:
    """Calculate memory size of a module's parameters in bytes."""
    mem = 0
    sd = module.state_dict()
    for k in sd:
        t = sd[k]
        mem += t.nelement() * t.element_size()
    return mem


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
# ModelManager — singleton GPU/VRAM manager
# ---------------------------------------------------------------------------

class ModelManager:
    """
    Manages GPU/VRAM state and model lifecycle.

    Singleton per process — use ModelManager.instance() to get the global instance.
    Thread-safe for concurrent load/unload operations.
    """

    _instance: Optional[ModelManager] = None
    _lock_class = threading.Lock()

    def __init__(self, settings=None):
        from app.core.config import get_settings
        self._settings = settings or get_settings()
        self._torch = None  # lazy
        self._lock = threading.Lock()

        # State
        self._cpu_state = CPUState.GPU
        self._vram_state = VRAMState.NORMAL_VRAM
        self._total_vram_mb: float = 0.0
        self._total_ram_mb: float = 0.0

        # Loaded models (LRU: most recent at index 0)
        self._loaded_models: List[LoadedModel] = []

        # Lazy unload timer
        self._idle_timer: Optional[threading.Timer] = None
        self._idle_timeout = self._settings.model_idle_timeout

        # Force flags (configurable)
        self._force_fp32 = False
        self._force_fp16 = False
        self._always_vram_offload = False

        # Initialize
        self._detect_device()
        self._detect_vram_state()

    @classmethod
    def instance(cls, settings=None) -> ModelManager:
        """Get or create the singleton ModelManager."""
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance.unload_all()
                cls._instance = None

    # -----------------------------------------------------------------------
    # Device detection
    # -----------------------------------------------------------------------

    def _get_torch(self):
        if self._torch is None:
            import torch
            self._torch = torch
            # Set CUDA device if configured
            device_id = self._settings.gpu_device_id
            if device_id is not None:
                import os
                os.environ["CUDA_VISIBLE_DEVICES"] = str(device_id)
        return self._torch

    def _detect_device(self):
        """Detect available compute device (CUDA/MPS/CPU)."""
        torch = self._get_torch()

        # Check MPS (Apple Silicon)
        try:
            if torch.backends.mps.is_available():
                self._cpu_state = CPUState.MPS
                logger.info("Detected Apple MPS device")
                return
        except (AttributeError, RuntimeError):
            pass

        # Check CUDA
        if torch.cuda.is_available():
            self._cpu_state = CPUState.GPU
            device = torch.cuda.current_device()
            name = torch.cuda.get_device_name(device)
            logger.info("Detected CUDA device: %s (device %d)", name, device)
            return

        # Fallback to CPU
        self._cpu_state = CPUState.CPU
        logger.warning("No GPU detected — running on CPU")

    def _detect_vram_state(self):
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

        # Check configured mode
        mode = self._settings.gpu_mode
        if mode == "eager":
            self._vram_state = VRAMState.HIGH_VRAM
            logger.info("VRAM state: HIGH_VRAM (eager mode)")
            return

        # Auto-detect based on available VRAM
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
    def device(self):
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

    def is_device_cpu(self, device=None) -> bool:
        if device is None:
            device = self.device
        return hasattr(device, 'type') and device.type == 'cpu'

    def is_device_mps(self, device=None) -> bool:
        if device is None:
            device = self.device
        return hasattr(device, 'type') and device.type == 'mps'

    def is_gpu_available(self) -> bool:
        return self._cpu_state == CPUState.GPU

    # -----------------------------------------------------------------------
    # Memory queries
    # -----------------------------------------------------------------------

    def get_total_memory(self, device=None) -> int:
        """Get total memory (VRAM or RAM) in bytes."""
        torch = self._get_torch()
        if device is None:
            device = self.device

        if self.is_device_cpu(device) or self.is_device_mps(device):
            return psutil.virtual_memory().total

        if self.is_nvidia():
            _, mem_total = torch.cuda.mem_get_info(device)
            return mem_total

        # Fallback
        return psutil.virtual_memory().total

    def get_free_memory(self, device=None, torch_free_too: bool = False):
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

        # Fallback
        mem_free = psutil.virtual_memory().available
        if torch_free_too:
            return (mem_free, mem_free)
        return mem_free

    # -----------------------------------------------------------------------
    # Model loading (LRU eviction)
    # -----------------------------------------------------------------------

    def minimum_inference_memory(self) -> int:
        """Minimum memory needed for inference (1 GB)."""
        return 1024 * 1024 * 1024

    def load_models_gpu(self, models: list, memory_required: int = 0):
        """
        Load models into GPU memory with LRU eviction.

        If a model is already loaded, move it to front of LRU list.
        Otherwise, evict oldest models to make room, then load.
        """
        with self._lock:
            self._load_models_gpu_impl(models, memory_required)
            self._cancel_idle_timer()
            if self._settings.gpu_mode == "lazy":
                self._start_idle_timer()

    def _load_models_gpu_impl(self, models: list, memory_required: int = 0):
        inference_memory = self.minimum_inference_memory()
        extra_mem = max(inference_memory, memory_required)

        models_to_load: List[LoadedModel] = []
        models_already_loaded: List[LoadedModel] = []

        for x in models:
            loaded = LoadedModel(x)
            if loaded in self._loaded_models:
                idx = self._loaded_models.index(loaded)
                self._loaded_models.insert(0, self._loaded_models.pop(idx))
                self._loaded_models[0].touch()
                models_already_loaded.append(self._loaded_models[0])
            else:
                models_to_load.append(loaded)

        if not models_to_load:
            # Just ensure enough free memory for existing models
            devices = set(m.device for m in models_already_loaded)
            for d in devices:
                if not self.is_device_cpu(d):
                    self._free_memory(extra_mem, d, models_already_loaded)
            return

        logger.info("Loading %d new model(s)", len(models_to_load))

        # Calculate total memory needed per device
        total_mem_needed: dict = {}
        for loaded in models_to_load:
            self._unload_model_clones(loaded.model)
            dev = loaded.device
            total_mem_needed[dev] = total_mem_needed.get(dev, 0) + loaded.memory_required(dev)

        # Free memory on each device
        for dev, needed in total_mem_needed.items():
            if not self.is_device_cpu(dev):
                self._free_memory(int(needed * 1.3) + extra_mem, dev, models_already_loaded)

        # Load each model
        for loaded in models_to_load:
            torch_dev = loaded.device
            if self.is_device_cpu(torch_dev):
                vram_set = VRAMState.DISABLED
            else:
                vram_set = self._vram_state

            lowvram_memory = 0
            if vram_set in (VRAMState.LOW_VRAM, VRAMState.NORMAL_VRAM):
                model_size = loaded.memory_required(torch_dev)
                current_free = self.get_free_memory(torch_dev)
                lowvram_memory = int(max(64 * 1024 * 1024, (current_free - 1024 * 1024 * 1024) / 1.3))
                if model_size > (current_free - inference_memory):
                    vram_set = VRAMState.LOW_VRAM
                else:
                    lowvram_memory = 0

            if vram_set == VRAMState.NO_VRAM:
                lowvram_memory = 64 * 1024 * 1024

            loaded.model_load(lowvram_memory)
            self._loaded_models.insert(0, loaded)

    def _free_memory(self, memory_required: int, device, keep_loaded: list):
        """Evict models from VRAM to free memory (LRU order, oldest first)."""
        unloaded = False
        for i in range(len(self._loaded_models) - 1, -1, -1):
            if not self._always_vram_offload:
                if self.get_free_memory(device) > memory_required:
                    break
            m = self._loaded_models[i]
            if m.device == device and m not in keep_loaded:
                popped = self._loaded_models.pop(i)
                popped.model_unload()
                del popped
                unloaded = True

        if unloaded:
            self._soft_empty_cache()
        else:
            if self._vram_state != VRAMState.HIGH_VRAM:
                mem_free_total, mem_free_torch = self.get_free_memory(device, torch_free_too=True)
                if mem_free_torch > mem_free_total * 0.25:
                    self._soft_empty_cache()

    def _unload_model_clones(self, model):
        """Unload any cloned versions of a model."""
        to_unload = []
        for i, loaded in enumerate(self._loaded_models):
            if model.is_clone(loaded.model):
                to_unload.append(i)
        for i in reversed(to_unload):
            popped = self._loaded_models.pop(i)
            popped.model_unload()

    def _soft_empty_cache(self, force: bool = False):
        """Release unused CUDA/MPS memory back to the system."""
        torch = self._get_torch()
        if self._cpu_state == CPUState.MPS:
            torch.mps.empty_cache()
        elif self.is_nvidia():
            if force or self.is_nvidia():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

    def cleanup_models(self):
        """Remove models with refcount <= 2 (no external references)."""
        with self._lock:
            to_delete = []
            for i, loaded in enumerate(self._loaded_models):
                if sys.getrefcount(loaded.model) <= 2:
                    to_delete.append(i)
            for i in reversed(to_delete):
                popped = self._loaded_models.pop(i)
                popped.model_unload()
                del popped

    def unload_all(self):
        """Unload all models from VRAM."""
        with self._lock:
            self._free_memory(int(1e30), self.device, [])
            self._cancel_idle_timer()

    # -----------------------------------------------------------------------
    # Lazy unload timer
    # -----------------------------------------------------------------------

    def _start_idle_timer(self):
        """Start timer to unload idle models after timeout."""
        self._cancel_idle_timer()
        if self._idle_timeout > 0:
            self._idle_timer = threading.Timer(self._idle_timeout, self._idle_unload)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _cancel_idle_timer(self):
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _idle_unload(self):
        """Unload models that have been idle beyond the timeout."""
        with self._lock:
            now = time.monotonic()
            to_unload = []
            for i, loaded in enumerate(self._loaded_models):
                if (now - loaded.last_used) > self._idle_timeout:
                    to_unload.append(i)
            for i in reversed(to_unload):
                popped = self._loaded_models.pop(i)
                logger.info("Idle unload: model %s (idle %.0fs)", popped.model, now - popped.last_used)
                popped.model_unload()
            if self._loaded_models:
                self._start_idle_timer()

    # -----------------------------------------------------------------------
    # Dtype helpers
    # -----------------------------------------------------------------------

    def unet_offload_device(self):
        """Device to offload UNet to when not in use."""
        if self._vram_state == VRAMState.HIGH_VRAM:
            return self.device
        return self._get_torch().device("cpu")

    def unet_initial_load_device(self, parameters: int, dtype) -> str:
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

    def unet_dtype(self, device=None, model_params: int = 0):
        """Determine UNet dtype based on hardware capabilities."""
        torch = self._get_torch()
        if self._force_fp32:
            return torch.float32
        if self._force_fp16:
            return torch.float16
        if self.should_use_fp16(device=device, model_params=model_params):
            return torch.float16
        return torch.float32

    def should_use_fp16(self, device=None, model_params: int = 0, prioritize_performance: bool = True) -> bool:
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
        # FP16 broken on some NVIDIA 16-series
        broken_16 = ["1660", "1650", "1630", "T500", "T550", "T600", "MX550", "MX450"]
        for name in broken_16:
            if name in props.name:
                return False
        return props.major >= 7

    def text_encoder_device(self):
        """Device for text encoder (CLIP)."""
        torch = self._get_torch()
        if self._vram_state in (VRAMState.HIGH_VRAM, VRAMState.NORMAL_VRAM):
            if self.should_use_fp16(prioritize_performance=False):
                return self.device
        return torch.device("cpu")

    def text_encoder_offload_device(self):
        """Offload device for text encoder (always CPU unless always_gpu mode)."""
        torch = self._get_torch()
        if self._vram_state == VRAMState.NO_VRAM:
            return torch.device("cpu")
        return torch.device("cpu")

    def text_encoder_dtype(self, device=None):
        """Determine text encoder dtype."""
        torch = self._get_torch()
        if self.is_device_cpu(device):
            return torch.float16
        if self.should_use_fp16(device, prioritize_performance=False):
            return torch.float16
        return torch.float32

    def vae_device(self):
        """Device for VAE."""
        return self.device

    def vae_dtype(self):
        """Determine VAE dtype."""
        torch = self._get_torch()
        if self.is_nvidia():
            try:
                if torch.cuda.is_bf16_supported():
                    props = torch.cuda.get_device_properties(self.device)
                    if props.major >= 8:
                        return torch.bfloat16
            except Exception:
                pass
        return torch.float32

    def intermediate_device(self):
        """Device for intermediate computations."""
        return self.device

    def unet_manual_cast(self, weight_dtype, inference_device):
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

    # -----------------------------------------------------------------------
    # Interrupt processing
    # -----------------------------------------------------------------------

    _interrupt_processing = False
    _interrupt_mutex = threading.RLock()

    def interrupt_current_processing(self, value: bool = True):
        """Signal to interrupt the current generation."""
        with self._interrupt_mutex:
            self._interrupt_processing = value

    def processing_interrupted(self) -> bool:
        """Check if processing was interrupted."""
        with self._interrupt_mutex:
            return self._interrupt_processing

    def throw_if_interrupted(self):
        """Raise InterruptProcessingException if interrupted."""
        with self._interrupt_mutex:
            if self._interrupt_processing:
                self._interrupt_processing = False
                raise InterruptProcessingException()


class InterruptProcessingException(Exception):
    pass


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def get_model_manager() -> ModelManager:
    """Get the global ModelManager singleton."""
    return ModelManager.instance()
