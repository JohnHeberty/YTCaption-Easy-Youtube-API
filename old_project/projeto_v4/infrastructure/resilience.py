import asyncio
import random
from functools import wraps
from typing import Any, Awaitable, Callable


async def with_timeout(coro: Awaitable[Any], timeout_s: float) -> Any:
    """Run an async operation with a timeout."""
    return await asyncio.wait_for(coro, timeout=timeout_s)


def retry_async(max_retries: int = 2, base_delay: float = 0.2, max_delay: float = 2.0, jitter: float = 0.1):
    """Lightweight async retry with exponential backoff and jitter."""

    def deco(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            attempt = 0
            last_exc: Exception | None = None
            while attempt <= max_retries:
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 keep generic for resilience at edges
                    last_exc = e
                    if attempt == max_retries:
                        break
                    delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, jitter)
                    await asyncio.sleep(delay)
                    attempt += 1
            assert last_exc is not None
            raise last_exc

        return wrapper

    return deco
