"""
SE8 Image Engine — Model Manager

Manages GPU/VRAM state, device detection, model load/unload with LRU eviction.

Design decisions:
- Class-based (ModelManager singleton) instead of global state
- Config-driven (ImageEngineSettings) instead of CLI args
- Thread-safe with Lock for concurrent access
- Lazy/timer-based unload for idle models
- No xformers/DirectML/XPU (CUDA-only for now, extensible)

Architecture:
- DeviceManager handles device detection, memory queries, dtype resolution
- ModelManager handles model lifecycle (load/unload/LRU), idle timer, interrupts
- ModelManager delegates all device-level queries to its DeviceManager instance
"""

from __future__ import annotations
from common.log_utils import get_logger

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.services.device_manager import (
    CPUState,
    DeviceManager,
    VRAMState,
    _dtype_size,
    _get_torch,
)

logger = get_logger(__name__)

# Re-export enums for backward compatibility
__all__ = [
    "ModelManager",
    "get_model_manager",
    "LoadedModel",
    "ManagedModel",
    "InterruptProcessingException",
    "VRAMState",
    "CPUState",
]


# ---------------------------------------------------------------------------
# Protocol for model objects that ModelManager can track
# ---------------------------------------------------------------------------

@runtime_checkable
class ManagedModel(Protocol):
    """Protocol that model objects must satisfy to be managed by ModelManager."""

    @property
    def load_device(self) -> Any: ...

    @property
    def current_device(self) -> Any: ...

    @property
    def offload_device(self) -> Any: ...

    def model_size(self) -> int: ...

    def model_dtype(self) -> Any: ...

    def model_patches_to(self, device) -> None: ...

    def patch_model(self, device_to=None, patch_weights=True) -> Any: ...

    def unpatch_model(self, device) -> None: ...

    def is_clone(self, other) -> bool: ...


# ---------------------------------------------------------------------------
# Utility function
# ---------------------------------------------------------------------------

def _module_size(module) -> int:
    """Calculate memory size of a module's parameters in bytes."""
    mem = 0
    sd = module.state_dict()
    for k in sd:
        t = sd[k]
        mem += t.nelement() * t.element_size()
    return mem


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

    def __post_init__(self) -> None:
        if self.device is None:
            self.device = self.model.load_device

    @property
    def memory(self) -> int:
        return self.model.model_size()

    def memory_required(self, target_device: Any) -> int:
        if target_device == self.model.current_device:
            return 0
        return self.memory

    def model_load(self, lowvram_model_memory: int = 0) -> Any:
        """Load model into VRAM. If lowvram_model_memory > 0, use partial offloading."""
        torch = _get_torch()
        patch_model_to = None
        if lowvram_model_memory == 0:
            patch_model_to = self.device

        self.model.model_patches_to(self.device)
        self.model.model_patches_to(self.model.model_dtype())

        try:
            self.real_model = self.model.patch_model(device_to=patch_model_to)
        except Exception as e:
            logger.debug("patch_model failed, rolling back: %s", e)
            self.model.unpatch_model(self.model.offload_device)
            self._unload_acceleration()
            raise

        if lowvram_model_memory > 0:
            logger.info("Loading in lowvram mode: %.1f MB", lowvram_model_memory / (1024 * 1024))
            self._load_lowvram(self.real_model, lowvram_model_memory)

        self.last_used = time.monotonic()
        return self.real_model

    def _load_lowvram(self, real_model: Any, lowvram_model_memory: int) -> None:
        """Apply lowvram partial offloading to loaded model modules."""
        torch = _get_torch()
        mem_counter = 0
        for m in real_model.modules():
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

    def model_unload(self) -> None:
        """Unload model from VRAM, move to CPU."""
        self._unload_acceleration()
        self.model.unpatch_model(self.model.offload_device)
        self.model.model_patches_to(self.model.offload_device)

    def _unload_acceleration(self) -> None:
        if self.model_accelerated and self.real_model is not None:
            for m in self.real_model.modules():
                if hasattr(m, "prev_ldm_patched_cast_weights"):
                    m.ldm_patched_cast_weights = m.prev_ldm_patched_cast_weights
                    del m.prev_ldm_patched_cast_weights
            self.model_accelerated = False

    def touch(self) -> None:
        """Update last_used timestamp."""
        self.last_used = time.monotonic()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LoadedModel):
            return self.model is other.model
        return NotImplemented

    def __hash__(self) -> int:
        return id(self.model)


# ---------------------------------------------------------------------------
# ModelManager — singleton GPU/VRAM model lifecycle manager
# ---------------------------------------------------------------------------

class ModelManager:
    """
    Manages GPU/VRAM state and model lifecycle.

    Singleton per process — use ModelManager.instance() to get the global instance.
    Thread-safe for concurrent load/unload operations.

    Delegates device-level queries (detection, memory, dtype) to DeviceManager.
    """

    _instance: ModelManager | None = None
    _lock_class = threading.Lock()

    def __init__(self, settings: Any = None) -> None:
        from app.core.config import get_settings
        self._settings = settings or get_settings()

        # Device manager — handles all device-level concerns
        self._device_mgr = DeviceManager(self._settings)

        self._lock = threading.Lock()

        # Model state (LRU: most recent at index 0)
        self._loaded_models: list[LoadedModel] = []

        # Lazy unload timer
        self._idle_timer: threading.Timer | None = None
        self._idle_timeout = self._settings.model_idle_timeout

    @classmethod
    def instance(cls, settings: Any = None) -> ModelManager:
        """Get or create the singleton ModelManager."""
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance.unload_all()
                cls._instance = None

    # -----------------------------------------------------------------------
    # Device delegation — backward-compatible properties
    # -----------------------------------------------------------------------

    @property
    def device(self) -> Any:
        """Get the primary torch device."""
        return self._device_mgr.device

    @property
    def device_name(self) -> str:
        return self._device_mgr.device_name

    @property
    def vram_state(self) -> VRAMState:
        return self._device_mgr.vram_state

    @property
    def cpu_state(self) -> CPUState:
        return self._device_mgr.cpu_state

    @property
    def total_vram_mb(self) -> float:
        return self._device_mgr.total_vram_mb

    def is_nvidia(self) -> bool:
        return self._device_mgr.is_nvidia()

    def is_device_cpu(self, device: Any = None) -> bool:
        return self._device_mgr.is_device_cpu(device)

    def is_device_mps(self, device: Any = None) -> bool:
        return self._device_mgr.is_device_mps(device)

    def is_gpu_available(self) -> bool:
        return self._device_mgr.is_gpu_available()

    def get_total_memory(self, device: Any = None) -> int:
        return self._device_mgr.get_total_memory(device)

    def get_free_memory(self, device: Any = None, torch_free_too: bool = False) -> int | tuple[int, int]:
        return self._device_mgr.get_free_memory(device, torch_free_too)

    # -----------------------------------------------------------------------
    # Dtype delegation — backward-compatible
    # -----------------------------------------------------------------------

    def unet_offload_device(self) -> Any:
        return self._device_mgr.unet_offload_device()

    def unet_initial_load_device(self, parameters: int, dtype: Any) -> Any:
        return self._device_mgr.unet_initial_load_device(parameters, dtype)

    def unet_dtype(self, device: Any = None, model_params: int = 0) -> Any:
        return self._device_mgr.unet_dtype(device, model_params)

    def should_use_fp16(self, device: Any = None, model_params: int = 0, prioritize_performance: bool = True) -> bool:
        return self._device_mgr.should_use_fp16(device, model_params, prioritize_performance)

    def text_encoder_device(self) -> Any:
        return self._device_mgr.text_encoder_device()

    def text_encoder_offload_device(self) -> Any:
        return self._device_mgr.text_encoder_offload_device()

    def text_encoder_dtype(self, device: Any = None) -> Any:
        return self._device_mgr.text_encoder_dtype(device)

    def vae_device(self) -> Any:
        return self._device_mgr.vae_device()

    def vae_dtype(self) -> Any:
        return self._device_mgr.vae_dtype()

    def intermediate_device(self) -> Any:
        return self._device_mgr.intermediate_device()

    def unet_manual_cast(self, weight_dtype: Any, inference_device: Any) -> Any | None:
        return self._device_mgr.unet_manual_cast(weight_dtype, inference_device)

    def pytorch_attention_enabled(self) -> bool:
        return self._device_mgr.pytorch_attention_enabled()

    def pytorch_attention_flash_attention(self) -> bool:
        return self._device_mgr.pytorch_attention_flash_attention()

    # -----------------------------------------------------------------------
    # Model loading (LRU eviction)
    # -----------------------------------------------------------------------

    def minimum_inference_memory(self) -> int:
        """Minimum memory needed for inference (1 GB)."""
        return 1024 * 1024 * 1024

    def load_models_gpu(self, models: list, memory_required: int = 0) -> None:
        """Load models into GPU memory with LRU eviction."""
        with self._lock:
            self._load_models_gpu_impl(models, memory_required)
            self._cancel_idle_timer()
            if self._settings.gpu_mode == "lazy":
                self._start_idle_timer()

    def _load_models_gpu_impl(self, models: list, memory_required: int = 0) -> None:
        inference_memory = self.minimum_inference_memory()
        extra_mem = max(inference_memory, memory_required)

        models_to_load, models_already_loaded = self._categorize_models(models)

        if not models_to_load:
            self._ensure_free_memory(extra_mem, models_already_loaded)
            return

        logger.info("Loading %d new model(s)", len(models_to_load))
        self._prepare_and_load_models(models_to_load, models_already_loaded, extra_mem, inference_memory)

    def _categorize_models(self, models: list) -> tuple[list[LoadedModel], list[LoadedModel]]:
        """Separate models into already-loaded and need-to-load."""
        models_to_load: list[LoadedModel] = []
        models_already_loaded: list[LoadedModel] = []

        for x in models:
            loaded = LoadedModel(x)
            if loaded in self._loaded_models:
                idx = self._loaded_models.index(loaded)
                self._loaded_models.insert(0, self._loaded_models.pop(idx))
                self._loaded_models[0].touch()
                models_already_loaded.append(self._loaded_models[0])
            else:
                models_to_load.append(loaded)

        return models_to_load, models_already_loaded

    def _ensure_free_memory(self, extra_mem: int, keep_loaded: list[LoadedModel]) -> None:
        """Ensure enough free memory for existing models."""
        devices = set(m.device for m in keep_loaded)
        for d in devices:
            if not self.is_device_cpu(d):
                self._free_memory(extra_mem, d, keep_loaded)

    def _prepare_and_load_models(
        self,
        models_to_load: list[LoadedModel],
        models_already_loaded: list[LoadedModel],
        extra_mem: int,
        inference_memory: int,
    ) -> None:
        """Calculate memory needs, free space, and load each model."""
        total_mem_needed: dict = {}
        for loaded in models_to_load:
            self._unload_model_clones(loaded.model)
            dev = loaded.device
            total_mem_needed[dev] = total_mem_needed.get(dev, 0) + loaded.memory_required(dev)

        for dev, needed in total_mem_needed.items():
            if not self.is_device_cpu(dev):
                self._free_memory(int(needed * 1.3) + extra_mem, dev, models_already_loaded)

        for loaded in models_to_load:
            lowvram_memory = self._calculate_lowvram_memory(loaded, inference_memory)
            loaded.model_load(lowvram_memory)
            self._loaded_models.insert(0, loaded)

    def _calculate_lowvram_memory(self, loaded: LoadedModel, inference_memory: int) -> int:
        """Calculate lowvram memory allocation for a model."""
        torch = _get_torch()
        torch_dev = loaded.device
        if self.is_device_cpu(torch_dev):
            vram_set = VRAMState.DISABLED
        else:
            vram_set = self._device_mgr._vram_state

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

        return lowvram_memory

    def _free_memory(self, memory_required: int, device: Any, keep_loaded: list) -> None:
        """Evict models from VRAM to free memory (LRU order, oldest first)."""
        unloaded = False
        for i in range(len(self._loaded_models) - 1, -1, -1):
            if not self._device_mgr._always_vram_offload:
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
            if self._device_mgr._vram_state != VRAMState.HIGH_VRAM:
                mem_free_total, mem_free_torch = self.get_free_memory(device, torch_free_too=True)
                if mem_free_torch > mem_free_total * 0.25:
                    self._soft_empty_cache()

    def _unload_model_clones(self, model: Any) -> None:
        """Unload any cloned versions of a model."""
        to_unload = []
        for i, loaded in enumerate(self._loaded_models):
            if model.is_clone(loaded.model):
                to_unload.append(i)
        for i in reversed(to_unload):
            popped = self._loaded_models.pop(i)
            popped.model_unload()

    def _soft_empty_cache(self, force: bool = False) -> None:
        """Release unused CUDA/MPS memory back to the system."""
        torch = _get_torch()
        if self._device_mgr._cpu_state == CPUState.MPS:
            torch.mps.empty_cache()
        elif self.is_nvidia():
            if force or self.is_nvidia():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

    def cleanup_models(self) -> None:
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

    def unload_all(self) -> None:
        """Unload all models from VRAM."""
        with self._lock:
            self._free_memory(int(1e30), self.device, [])
            self._cancel_idle_timer()

    # -----------------------------------------------------------------------
    # Lazy unload timer
    # -----------------------------------------------------------------------

    def _start_idle_timer(self) -> None:
        """Start timer to unload idle models after timeout."""
        self._cancel_idle_timer()
        if self._idle_timeout > 0:
            self._idle_timer = threading.Timer(self._idle_timeout, self._idle_unload)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _cancel_idle_timer(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _idle_unload(self) -> None:
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
    # Interrupt processing
    # -----------------------------------------------------------------------

    _interrupt_processing = False
    _interrupt_mutex = threading.RLock()

    def interrupt_current_processing(self, value: bool = True) -> None:
        """Signal to interrupt the current generation."""
        with self._interrupt_mutex:
            self._interrupt_processing = value

    def processing_interrupted(self) -> bool:
        """Check if processing was interrupted."""
        with self._interrupt_mutex:
            return self._interrupt_processing

    def throw_if_interrupted(self) -> None:
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
