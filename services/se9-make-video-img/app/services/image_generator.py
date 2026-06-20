"""Image generation service using SE8."""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from common.log_utils import get_logger

from app.core.constants import IMAGE_ASPECT_RATIOS
from app.core.models import SceneSuggestion
from app.infrastructure.http_client import SE8Client

logger = get_logger(__name__)


class ImageGenerator:
    """Generate images from scene suggestions using SE8."""

    cinematic_suffix: str = (
        ", cinematic composition, depth of field, "
        "volumetric lighting, high detail, "
        "professional photography, 8k resolution"
    )

    def __init__(self, client: SE8Client | None = None, cinematic_suffix: str | None = None) -> None:
        self.client = client or SE8Client()
        if cinematic_suffix is not None:
            self.cinematic_suffix = cinematic_suffix

    async def close(self) -> None:
        await self.client.close()

    def _get_dimensions(self, aspect_ratio: str) -> tuple[int, int]:
        """Get width/height from aspect ratio."""
        return IMAGE_ASPECT_RATIOS.get(aspect_ratio, (1024, 1792))

    async def generate_all(
        self,
        scenes: list[SceneSuggestion],
        aspect_ratio: str = "9:16",
        steps: int = 30,
        performance: str = "Quality",
        output_dir: str = "/tmp",
        progress_callback: Callable[[float], Awaitable[None]] | None = None,
    ) -> list[str]:
        """Generate images for all scenes. Returns list of image paths."""
        width, height = self._get_dimensions(aspect_ratio)
        image_paths: list[str] = []

        sorted_scenes = sorted(scenes, key=lambda s: s.t)

        for i, scene in enumerate(sorted_scenes):
            # Frente C: Add cinematic suffix for depth and visual quality
            enhanced_prompt = scene.visual + self.cinematic_suffix
            logger.info(f"Generating image {i + 1}/{len(sorted_scenes)}: {scene.visual[:50]}...")

            images = await self.client.generate_image(
                prompt=enhanced_prompt,
                width=width,
                height=height,
                steps=steps,
                performance=performance,
            )

            first = images[0]
            file_path = first.get("url") or first.get("path")
            if not file_path:
                raise ValueError(f"No URL in SE8 response: {first}")
            image_data = await self.client.download_image(file_path)

            image_path = os.path.join(output_dir, f"scene_{int(scene.t)}.png")
            with open(image_path, "wb") as f:
                f.write(image_data)

            image_paths.append(image_path)
            logger.info(f"Image saved: {image_path}")

            if progress_callback:
                progress = ((i + 1) / len(sorted_scenes)) * 100
                await progress_callback(progress)

        return image_paths
