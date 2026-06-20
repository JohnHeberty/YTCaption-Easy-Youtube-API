"""HTTP clients for communicating with SE10 and SE8."""
import asyncio
import base64
import io
from typing import Optional

import httpx
from common.log_utils import get_logger

from app.core.config import settings

logger = get_logger(__name__)


class ServiceClient:
    """Base HTTP client with retry logic."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout,
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
                    logger.warning(
                        "Request failed (attempt %d): %s, retrying in %ds",
                        attempt + 1, e, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Request failed after %d attempts: %s", max_retries, e)
        raise last_error


class SE10Client(ServiceClient):
    """Client for SE10 Clothes Segmentation."""

    def __init__(self):
        super().__init__(
            base_url=settings.se10_url,
            api_key=settings.se10_api_key,
            timeout=settings.se10_timeout,
        )

    async def segment(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
        classes: Optional[str] = None,
        box_threshold: Optional[float] = None,
        text_threshold: Optional[float] = None,
    ) -> dict:
        """Send image to SE10 for clothing segmentation.

        Returns dict with keys: detected, objects, masks, mask_image, processing_time_ms
        """
        form_data = {}
        files = {"file": (filename, image_bytes, "image/jpeg")}
        if classes:
            form_data["classes"] = classes
        if box_threshold is not None:
            form_data["box_threshold"] = str(box_threshold)
        if text_threshold is not None:
            form_data["text_threshold"] = str(text_threshold)

        response = await self._request_with_retry(
            "POST",
            "/v1/segment",
            files=files,
            data=form_data,
        )
        result = response.json()
        if not result.get("success"):
            raise Exception(f"SE10 segmentation failed: {result.get('message', 'Unknown error')}")
        return result.get("result", {})

    async def health(self) -> dict:
        """Check SE10 health."""
        response = await self._request_with_retry("GET", "/health")
        return response.json()


class SE8Client(ServiceClient):
    """Client for SE8 Image Generation (inpainting)."""

    def __init__(self):
        super().__init__(
            base_url=settings.se8_url,
            api_key=settings.se8_api_key,
            timeout=settings.se8_timeout,
        )

    async def inpaint(
        self,
        image_b64: str,
        mask_b64: str,
        prompt: str = "",
        negative_prompt: str = "",
        inpaint_strength: float = 1.0,
        style: str = "Fooocus Inpaint",
    ) -> dict:
        """Send image + mask to SE8 for inpainting.

        Args:
            image_b64: Base64 image string (with or without data URI prefix)
            mask_b64: Base64 mask string (with or without data URI prefix)
            prompt: Inpainting prompt
            negative_prompt: Negative prompt
            inpaint_strength: Strength of inpainting (0.0-1.0)
            style: Style selection

        Returns dict with keys: base64, url, seed, finish_reason
        """
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style_selections": [style, "Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"],
            "performance_selection": "Speed",
            "aspect_ratios_selection": "1152*896",
            "image_number": 1,
            "image_seed": -1,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
            "input_image": image_b64,
            "input_mask": mask_b64,
            "inpaint_additional_prompt": prompt,
            "async_process": False,
            "require_base64": True,
        }

        if inpaint_strength != 1.0:
            payload["advanced_params"] = {
                "inpaint_strength": inpaint_strength,
                "inpaint_engine": "v2.6",
            }

        response = await self._request_with_retry(
            "POST",
            "/v1/generation/image-inpaint-outpaint",
            json=payload,
        )
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    async def health(self) -> dict:
        """Check SE8 health."""
        response = await self._request_with_retry("GET", "/health")
        return response.json()
