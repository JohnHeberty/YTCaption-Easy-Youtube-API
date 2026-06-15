"""
Resilient HTTP client with retry and exponential backoff.

Wraps httpx.AsyncClient with tenacity-based retry for transient failures.
Used by all microservices for inter-service communication.

Usage:
    client = ResilientHttpClient(base_url="http://video-downloader:8002")
    response = await client.get("/health")
    response = await client.post("/jobs", json={"url": "..."})
"""
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)


class ResilientHttpClient:
    """HTTP client with automatic retry for transient failures.

    Attributes:
        base_url: Base URL of the target service
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        min_wait: Minimum wait between retries (seconds)
        max_wait: Maximum wait between retries (seconds)
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        min_wait: float = 2.0,
        max_wait: float = 60.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_wait = min_wait
        self.max_wait = max_wait
        self._headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the underlying httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._headers,
            )
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with retry logic."""
        client = await self._get_client()
        url = path if path.startswith("http") else path
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, url, **kwargs)

                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries - 1:
                        wait_time = min(self.min_wait * (2 ** attempt), self.max_wait)
                        logger.warning(
                            f"Retrying {method} {path} (status {response.status_code}, "
                            f"attempt {attempt + 1}/{self.max_retries}, wait {wait_time:.1f}s)"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    return response

                return response

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = min(self.min_wait * (2 ** attempt), self.max_wait)
                    logger.warning(
                        f"Retrying {method} {path} ({type(e).__name__}, "
                        f"attempt {attempt + 1}/{self.max_retries}, wait {wait_time:.1f}s)"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

        if last_exception:
            raise last_exception

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """GET request with retry."""
        return await self._request_with_retry("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        """POST request with retry."""
        return await self._request_with_retry("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        """PUT request with retry."""
        return await self._request_with_retry("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        """DELETE request with retry."""
        return await self._request_with_retry("DELETE", path, **kwargs)

    async def health_check(self) -> Dict[str, Any]:
        """Check health of the target service.

        Returns:
            Dict with status and service info
        """
        try:
            response = await self.get("/health", timeout=5.0)
            if response.status_code == 200:
                return response.json()
            return {"status": "unhealthy", "status_code": response.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}