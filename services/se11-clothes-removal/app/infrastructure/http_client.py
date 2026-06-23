"""HTTP clients for communicating with SE10 and SE8."""
from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

import httpx
from common.log_utils import get_logger

from app.core.config import settings

logger = get_logger(__name__)


def _fix_b64_padding(s: str) -> str:
    """Fix base64 padding if missing."""
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


class ServiceClient:
    """Base HTTP client with retry logic."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any,
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

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.se10_url,
            api_key=settings.se10_api_key,
            timeout=settings.se10_timeout,
        )

    async def segment(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
        classes: str | None = None,
        box_threshold: float | None = None,
        text_threshold: float | None = None,
        mode: str = "clothes",
        detector: str = "groundingdino",
    ) -> dict[str, Any]:
        """Send image to SE10 for segmentation.

        Args:
            mode: "clothes" for clothing detection, "person" for person detection.
            detector: "groundingdino" (default) or "florence2" for alternative detector.

        Returns dict with keys: detected, objects, masks, mask_image, processing_time_ms
        """
        form_data: dict[str, str] = {}
        files = {"file": (filename, image_bytes, "image/jpeg")}
        if classes:
            form_data["classes"] = classes
        if box_threshold is not None:
            form_data["box_threshold"] = str(box_threshold)
        if text_threshold is not None:
            form_data["text_threshold"] = str(text_threshold)
        if mode:
            form_data["mode"] = mode
        if detector:
            form_data["detector"] = detector

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

    async def health(self) -> dict[str, Any]:
        """Check SE10 health."""
        response = await self._request_with_retry("GET", "/health")
        return response.json()


class SE8Client(ServiceClient):
    """Client for SE8 Image Generation (inpainting)."""

    def __init__(self) -> None:
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
        inpaint_strength: float = 0.4,
        inpaint_respective_field: float = 0.85,
        inpaint_erode_or_dilate: int = -10,
        style: str = "",
        loras: list[dict[str, Any]] | None = None,
        image_prompts: list[dict[str, Any]] | None = None,
        base_model: str = "juggernautXL_v8Rundiffusion.safetensors",
    ) -> dict[str, Any]:
        """Send image + mask to SE8 for inpainting.

        Args:
            image_b64: Base64 image string (with or without data URI prefix)
            mask_b64: Base64 mask string (with or without data URI prefix)
            prompt: Inpainting prompt
            negative_prompt: Negative prompt
            inpaint_strength: Strength of inpainting (0.0-1.0)
            inpaint_respective_field: Crop area fraction (0.0-1.0)
            style: Style selection
            loras: Optional LoRA overrides

        Returns dict with keys: base64, url, seed, finish_reason
        """
        # Calculate best SDXL aspect ratio from input image dimensions
        aspect_str = self._pick_sdxl_ratio(image_b64)

        # Use stronger negative prompt for cleaner results
        if not negative_prompt:
            negative_prompt = (
                "deformed, blurry, low quality, extra limbs, disfigured, "
                "poorly drawn face, watermark, text, ugly, bad anatomy, "
                "bad proportions, mutated hands, extra fingers"
            )

        # LoRAs: NsfwPov (skin) + offset (quality) + detail (texture)
        if loras is None:
            loras = [
                {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.2},
                {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
                {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
            ]

        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style_selections": [style] if style else [],
            "performance_selection": "Speed",
            "aspect_ratios_selection": aspect_str,
            "image_number": 1,
            "image_seed": -1,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": base_model,
            "loras": loras,
            "input_image": image_b64,
            "input_mask": mask_b64,
            "inpaint_additional_prompt": prompt,
            "async_process": False,
            "require_base64": False,
            "advanced_params": {
                "inpaint_engine": "v2.6",
                "inpaint_strength": inpaint_strength,
                "inpaint_respective_field": inpaint_respective_field,
                "inpaint_disable_initial_latent": False,
                "inpaint_erode_or_dilate": inpaint_erode_or_dilate,
            },
        }

        # Add IP-Adapter image prompts if provided
        if image_prompts:
            payload["image_prompts"] = image_prompts
            logger.info("SE8: IP-Adapter enabled with %d reference images", len(image_prompts))
        else:
            payload["image_prompts"] = [
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.6, "cn_type": "ImagePrompt"},
            ] * 4

        # Retry loop for empty SE8 results (CUDA assertion failures return [])
        max_attempts = 3
        for attempt in range(max_attempts):
            response = await self._request_with_retry(
                "POST",
                "/v1/generation/image-inpaint-outpaint",
                json=payload,
            )
            result = response.json()
            # SE8 may return list-of-lists or list-of-dicts — unwrap until we get a dict
            item = result
            while isinstance(item, list) and len(item) > 0:
                item = item[0]
            if isinstance(item, dict) and item.get("finish_reason") == "SUCCESS":
                break
            if isinstance(item, list) and len(item) == 0:
                wait = 5 * (attempt + 1)  # 5s, 10s, 15s — CUDA needs time to recover
                logger.warning("SE8 returned empty list (attempt %d/%d), waiting %ds before retry...", attempt + 1, max_attempts, wait)
                import asyncio
                await asyncio.sleep(wait)
                continue
            if isinstance(item, dict):
                break

        if not isinstance(item, dict):
            raise Exception(f"SE8 returned unexpected type: {type(item).__name__}, value: {str(item)[:200]}")

        # SE8 returns file URL when require_base64=False — download image bytes
        url_val = item.get("url", "")
        if url_val and not url_val.startswith("data:"):
            file_url = url_val if url_val.startswith("http") else f"{self.base_url}{url_val}"
            logger.info("SE8: downloading result from %s", file_url)
            try:
                dl_resp = await self._request_with_retry("GET", url_val)
                img_bytes = dl_resp.content
                item["base64"] = base64.b64encode(img_bytes).decode("utf-8")
                logger.info("SE8: downloaded %d bytes", len(img_bytes))
            except Exception as e:
                logger.error("SE8: failed to download from %s: %s", file_url, e)
                raise

        # Fallback: SE8 sometimes returns base64 in 'url' field as data URI
        if not item.get("base64") and item.get("url"):
            url_val = item["url"]
            data_idx = url_val.find("data:image")
            if data_idx >= 0:
                item["base64"] = url_val[data_idx:]

        return item

    async def health(self) -> dict[str, Any]:
        """Check SE8 health."""
        response = await self._request_with_retry("GET", "/health")
        return response.json()

    async def enhance(
        self,
        image_b64: str,
        strength: str = "Vary (Subtle)",
    ) -> dict[str, Any]:
        """Enhance/vary image via SE8."""
        payload: dict[str, Any] = {
            "prompt": "natural skin, photorealistic, high quality",
            "negative_prompt": "deformed, blurry, bad anatomy, text, watermark",
            "style_selections": [],
            "performance_selection": "Speed",
            "aspect_ratios_selection": "1152*896",
            "image_number": 1,
            "image_seed": -1,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
            "loras": [
                {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
                {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
            ],
            "current_tab": "enhance",
            "enhance_input_image": image_b64,
            "enhance_checkbox": True,
            "enhance_uov_method": strength,
            "enhance_uov_processing_order": "Before First Enhancement",
            "enhance_uov_prompt_type": "Original Prompts",
            "save_final_enhanced_image_only": True,
            "enhance_ctrlnets": [],
            "async_process": False,
            "require_base64": False,
            "image_prompts": [],
        }

        response = await self._request_with_retry(
            "POST", "/v1/generation/image-enhance", json=payload,
        )
        result = response.json()
        item = result
        while isinstance(item, list) and len(item) > 0:
            item = item[0]

        if not isinstance(item, dict):
            raise Exception(f"SE8 enhance returned: {type(item).__name__}")

        url_val = item.get("url", "")
        if url_val and not url_val.startswith("data:"):
            try:
                dl_resp = await self._request_with_retry("GET", url_val)
                item["base64"] = base64.b64encode(dl_resp.content).decode("utf-8")
            except Exception:
                pass

        if not item.get("base64") and item.get("url"):
            url_val = item["url"]
            data_idx = url_val.find("data:image")
            if data_idx >= 0:
                item["base64"] = url_val[data_idx:]

        return item

    async def upscale(
        self,
        image_b64: str,
        scale: float = 2.0,
    ) -> dict[str, Any]:
        """Upscale image via SE8."""
        payload: dict[str, Any] = {
            "prompt": "",
            "negative_prompt": "",
            "style_selections": [],
            "performance_selection": "Speed",
            "aspect_ratios_selection": "1152*896",
            "image_number": 1,
            "image_seed": -1,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
            "loras": [
                {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
                {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
            ],
            "input_image": image_b64,
            "uov_method": "Upscale (2x)",
            "upscale_value": scale,
            "async_process": False,
            "require_base64": False,
            "current_tab": "uov",
            "image_prompts": [],
        }

        response = await self._request_with_retry(
            "POST", "/v1/generation/image-upscale-vary", json=payload,
        )
        result = response.json()
        item = result
        while isinstance(item, list) and len(item) > 0:
            item = item[0]

        if not isinstance(item, dict):
            raise Exception(f"SE8 upscale returned: {type(item).__name__}")

        url_val = item.get("url", "")
        if url_val and not url_val.startswith("data:"):
            try:
                dl_resp = await self._request_with_retry("GET", url_val)
                item["base64"] = base64.b64encode(dl_resp.content).decode("utf-8")
            except Exception:
                pass

        if not item.get("base64") and item.get("url"):
            url_val = item["url"]
            data_idx = url_val.find("data:image")
            if data_idx >= 0:
                item["base64"] = url_val[data_idx:]

        return item

    @staticmethod
    def _pick_sdxl_ratio(image_b64: str) -> str:
        """Pick closest SDXL aspect ratio from input image dimensions."""
        from PIL import Image

        # SDXL supported ratios: (width, height)
        sdxl_ratios = [
            (704, 1408), (704, 1344), (768, 1344), (768, 1280),
            (832, 1216), (832, 1152), (896, 1152), (896, 1088),
            (960, 1088), (960, 1024), (1024, 1024), (1024, 960),
            (1088, 960), (1088, 896), (1152, 896), (1152, 832),
            (1216, 832), (1280, 768), (1344, 768), (1344, 704),
            (1408, 704), (1472, 704), (1536, 640), (1600, 640),
            (1664, 576), (1728, 576),
        ]

        try:
            # Strip data URI prefix
            raw = image_b64
            if "," in raw and raw.startswith("data:"):
                raw = raw.split(",", 1)[1]
            raw = _fix_b64_padding(raw)

            img_bytes = base64.b64decode(raw)
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            input_ratio = w / h

            best = min(sdxl_ratios, key=lambda r: abs(r[0] / r[1] - input_ratio))
            return f"{best[0]}*{best[1]}"
        except Exception as e:
            logger.warning("Failed to detect image aspect ratio: %s, using default", e)
            return "1024*1024"
