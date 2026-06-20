"""HTTP clients for communicating with SE7 and SE8."""
import asyncio
from common.log_utils import get_logger
from typing import Optional

import httpx

from app.core.config import settings

logger = get_logger(__name__)


class ServiceClient:
    """Base HTTP client with retry logic."""

    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = None):
        self.base_url = base_url or ""
        self.api_key = api_key or ""
        self.timeout = timeout or 30
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=self.timeout,
        )

    async def close(self):
        await self.client.aclose()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> httpx.Response:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Request failed (attempt {attempt + 1}): {e}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
        raise last_error


class SE7Client(ServiceClient):
    """Client for SE7 Audio Generation service."""

    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = None):
        super().__init__(
            base_url=base_url or settings.se7_url,
            api_key=api_key or settings.se7_api_key,
            timeout=timeout or settings.se7_timeout,
        )

    async def create_job(
        self,
        text: str,
        voice_id: str = "builtin_feminino",
        exaggeration: float = None,
        cfg_weight: float = None,
        temperature: float = None,
        normalize_text: bool = True,
    ) -> str:
        """Create an audio generation job. Returns job_id."""
        data = {
            "text": text,
            "voice_id": voice_id,
            "exaggeration": str(exaggeration if exaggeration is not None else settings.tts_exaggeration),
            "cfg_weight": str(cfg_weight if cfg_weight is not None else settings.tts_cfg_weight),
            "temperature": str(temperature if temperature is not None else settings.tts_temperature),
            "normalize_text": str(normalize_text).lower(),
        }
        response = await self._request_with_retry("POST", "/jobs", data=data)
        result = response.json()
        return result.get("job_id") or result.get("id")

    async def poll_job(self, job_id: str) -> dict:
        """Poll job status until completed."""
        import time
        start = time.time()
        while time.time() - start < settings.se7_timeout:
            response = await self._request_with_retry("GET", f"/jobs/{job_id}")
            data = response.json()
            status = data.get("status")
            if status == "completed":
                return data
            elif status == "failed":
                raise Exception(f"SE7 job failed: {data.get('error')}")
            await asyncio.sleep(settings.se7_poll_interval)
        raise TimeoutError(f"SE7 job {job_id} timed out after {settings.se7_timeout}s")

    async def download_audio(self, job_id: str) -> bytes:
        """Download completed audio file."""
        response = await self._request_with_retry("GET", f"/jobs/{job_id}/download")
        return response.content


class SE8Client(ServiceClient):
    """Client for SE8 Image Generation service.

    SE8 returns images synchronously — no job_id, no polling.
    POST /v1/generation/text-to-image returns a list of image objects.
    """

    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = None):
        super().__init__(
            base_url=base_url or settings.se8_url,
            api_key=api_key or settings.se8_api_key,
            timeout=timeout or settings.se8_timeout,
        )

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        performance: str = "Quality",
    ) -> list[dict]:
        """Generate image synchronously. Returns list of image dicts with 'url' key."""
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "performance": performance,
        }
        response = await self._request_with_retry(
            "POST",
            "/v1/generation/text-to-image",
            json=payload,
        )
        result = response.json()
        if not isinstance(result, list):
            raise ValueError(f"SE8 returned unexpected format: {type(result)}")
        if len(result) == 0:
            raise ValueError("SE8 returned empty image list")
        return result

    async def download_image(self, file_path: str) -> bytes:
        """Download generated image by file path (e.g., /files/2026-06-18/image.png)."""
        response = await self._request_with_retry("GET", file_path)
        return response.content
