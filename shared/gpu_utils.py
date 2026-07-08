"""GPU memory cleanup utilities for CUDA workloads.

Provides a single, consistent CUDA memory cleanup sequence that all
services should use after unloading GPU models. Centralizes the logic
to avoid duplication and ensures every service gets the full cleanup
stack: GC → sync → cache → ipc → malloc_trim.

Usage::

    from common.gpu_utils import cleanup_cuda

    # After deleting model references:
    del self._model
    self._model = None
    cleanup_cuda()
"""
from __future__ import annotations

import ctypes
import gc
import logging

logger = logging.getLogger(__name__)

_CLEANUP_DONE = False


def cleanup_cuda() -> None:
    """Full CUDA memory cleanup sequence.

    Executes in order:
    1. Python garbage collection (frees unreferenced objects)
    2. ``torch.cuda.synchronize()`` — waits for all pending GPU ops
    3. ``torch.cuda.empty_cache()`` — releases CUDA caching allocator
    4. ``torch.cuda.ipc_collect()`` — frees driver-retained IPC memory
    5. ``malloc_trim()`` — returns freed heap pages to OS (Linux only)

    Every step is independently guarded. If torch is not installed or
    CUDA is unavailable, those steps are silently skipped. This function
    is always safe to call.
    """
    gc.collect()

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass
    except Exception:
        logger.debug("CUDA cleanup steps skipped", exc_info=True)

    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
