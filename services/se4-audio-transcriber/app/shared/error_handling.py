"""
Centralized error handling utilities for Audio Transcriber service.

Provides:
- retry_on_transient_error: decorator/context manager that only retries transient I/O errors,
  NOT programming errors like ValueError/TypeError.
- wrap_with_context: helper to wrap exceptions preserving chain via ``raise ... from e``.
"""
from __future__ import annotations

import time
import functools
from typing import TypeVar, Callable, Tuple, Type
from contextlib import contextmanager

from common.log_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Transient error classification
# ---------------------------------------------------------------------------

#: Exceptions considered *transient* — safe to retry.
TRANSIENT_IO_ERRORS: Tuple[Type[Exception], ...] = (OSError, ConnectionError)

#: CUDA OOM surfaces as RuntimeError with a recognizable message substring.
_CUDA_OOM_KEYWORDS = ("cuda", "out of memory", "oom")


def _is_cuda_oom(exc: BaseException) -> bool:
    """Return True when *exc* is a RuntimeError caused by GPU OOM."""
    if not isinstance(exc, RuntimeError):
        return False
    msg = str(exc).lower()
    return any(kw in msg for kw in _CUDA_OOM_KEYWORDS)


def _is_retryable(exc: BaseException, retryable_exceptions: Tuple[Type[Exception], ...]) -> bool:
    """Decide whether an exception is transient and worth retrying."""
    if isinstance(exc, retryable_exceptions):
        return True
    # CUDA OOM is retriable even though it's a RuntimeError subclass.
    if _is_cuda_oom(exc):
        return True
    return False


# ---------------------------------------------------------------------------
# Retry decorator / context manager
# ---------------------------------------------------------------------------

T = TypeVar("T")


def retry_on_transient_error(
    max_retries: int = 3,
    retryable_exceptions: Tuple[Type[Exception], ...] = TRANSIENT_IO_ERRORS,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
):
    """Decorator that retries a function on transient I/O errors only.

    **NOT retried:** ``ValueError``, ``TypeError`` and other programming errors —
    retrying those would only burn time / resources without any chance of success.

    Args:
        max_retries: Maximum number of *additional* attempts after the first failure.
        retryable_exceptions: Tuple of exception classes considered transient.
            Defaults to ``(OSError, ConnectionError)``.  CUDA OOM (RuntimeError with
            'cuda' / 'out of memory') is always retriable regardless of this tuple.
        base_delay: Initial back-off delay in seconds.
        max_delay: Cap for exponential back-off.

    Usage::

        @retry_on_transient_error(max_retries=3)
        def download_model(): ...

        # As a context manager (for inline blocks):
        with retry_on_transient_error(max_retries=2):
            risky_io_call()
    """

    decorator_fn = _RetryDecorator(
        max_retries=max_retries,
        retryable_exceptions=retryable_exceptions,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    # Support both ``@decorator`` and ``with decorator:`` usage.
    return decorator_fn


class _RetryDecorator:
    """Dual-purpose object: callable as a decorator *and* usable as context manager."""

    def __init__(self, max_retries: int, retryable_exceptions: Tuple[Type[Exception], ...], base_delay: float, max_delay: float) -> None:
        self.max_retries = max_retries
        self.retryable_exceptions = retryable_exceptions
        self.base_delay = base_delay
        self.max_delay = max_delay

    # -- decorator protocol --------------------------------------------------

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 — we classify below
                    if not _is_retryable(exc, self.retryable_exceptions):
                        raise  # programming error → fail fast

                    last_exc = exc
                    logger.warning(
                        "Transient error on attempt %d/%d in '%s': %s",
                        attempt + 1,
                        self.max_retries + 1,
                        func.__qualname__,
                        exc,
                    )

                    if attempt < self.max_retries:
                        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                        logger.info("Retrying in %.1fs …", delay)
                        time.sleep(delay)

            raise last_exc  # type: ignore[misc]

        return wrapper

    # -- context-manager protocol --------------------------------------------

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: type | None, exc_value: BaseException | None, tb: Any) -> bool:
        if exc_type is None:
            return True

        last_exc = exc_value
        for attempt in range(self.max_retries + 1):
            try:
                raise exc_value from tb  # re-raise inside the loop body simulation
            except Exception as exc:  # noqa: BLE001
                if not _is_retryable(exc, self.retryable_exceptions):
                    return False

                last_exc = exc
                logger.warning(
                    "Transient error on attempt %d/%d in inline retry block: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )

            if attempt < self.max_retries:
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.info("Retrying in %.1fs …", delay)
                time.sleep(delay)

        # If we exhausted retries without succeeding, let the original exception propagate.
        return False


# ---------------------------------------------------------------------------
# wrap_with_context helper
# ---------------------------------------------------------------------------


def wrap_with_context(message: str) -> Any:
    """Return a context manager that wraps any caught exception with *message*, preserving chain.

    Ensures ``raise ... from e`` so the full traceback is retained (avoids losing stack context).

    Usage::

        try:
            risky_call()
        except Exception as exc:
            raise AudioTranscriptionException("Failed to transcribe") from exc

        # Equivalent with context manager inside a finally / cleanup block:
        with wrap_with_context("cleanup failed"):
            os.unlink(temp_path)
    """

    @contextmanager
    def _cm():
        try:
            yield
        except Exception as e:  # noqa: BLE001 — intentional broad catch for wrapping
            raise type(e)(f"{message}: {e}") from e

    return _cm()


# ---------------------------------------------------------------------------
# safe_cleanup helper (Pattern B consistency)
# ---------------------------------------------------------------------------


def safe_cleanup(func: Callable, label: str = "cleanup") -> None:
    """Execute *func* and silently swallow exceptions after logging a warning.

    Use for cleanup paths (finally blocks, unload_model) where failing the
    entire operation because of a best-effort teardown is undesirable.

    Args:
        func: Zero-argument callable to execute.
        label: Human-readable label used in log messages.
    """
    try:
        func()
    except Exception as e:  # noqa: BLE001 — cleanup suppression is intentional (Pattern B)
        logger.warning("⚠️ %s failed (non-critical): %s", label, e)
