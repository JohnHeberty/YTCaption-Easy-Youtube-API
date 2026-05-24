"""
Dependency injection utilities for service dependencies.

Provides ``Dep[T]`` — a lightweight wrapper around a factory callable
that supports test-time overrides without module-level mutable globals.

Usage::

    # service/app/infrastructure/dependencies.py
    from common.di import Dep

    @lru_cache(maxsize=1)
    def _build_store() -> Store:
        return Store(url=settings.redis_url)

    store = Dep(_build_store)          # production   → calls _build_store()
                                        # test .set()  → returns override

    # In routes:
    @router.get("/jobs/{job_id}")
    def get_job(job_store=Depends(store)):   # Dep(…) is a callable
        ...

    # In conftest.py / tests:
    store.set(mock_store)
    # run test logic …
    store.reset()                            # back to production
"""
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class Dep(Generic[T]):
    """Injectable dependency with a **set** / **reset** override mechanism.

    ``Dep(factory)`` wraps a zero-argument callable.  Calling the
    ``Dep`` instance (``dep()``) returns the override value when one
    has been set, otherwise delegates to *factory*.

    Because the instance itself is a callable it can be used directly
    with FastAPI's ``Depends()``, replacing the typical ``get_*_override``
    boilerplate.
    """

    __slots__ = ("_factory", "_override")

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._override: Optional[T] = None

    def __call__(self) -> T:
        if self._override is not None:
            return self._override
        return self._factory()

    def set(self, value: T) -> None:
        """Replace the dependency with *value* (e.g. a test double)."""
        self._override = value

    def reset(self) -> None:
        """Restore the original factory behaviour."""
        self._override = None
