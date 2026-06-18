"""Image generation service using SE8."""
import logging
import os
from typing import Optional

from app.core.models import SceneSuggestion
from app.infrastructure.http_client import SE8Client

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Generate images from scene suggestions using SE8."""

    def __init__(self):
        self.client = SE8Client()

    async def close(self):
        await self.client.close()

    def _get_dimensions(self, aspect_ratio: str) -> tuple[int, int]:
        """Get width/height from aspect ratio."""
        ratios = {
            "9:16": (1024, 1792),
            "16:9": (1792, 1024),
            "1:1": (1024, 1024),
        }
        return ratios.get(aspect_ratio, (1024, 1792))

    async def generate_all(
        self,
        scenes: list[SceneSuggestion],
        aspect_ratio: str = "9:16",
        steps: int = 30,
        performance: str = "Quality",
        output_dir: str = "/tmp",
        progress_callback=None,
    ) -> list[str]:
        """Generate images for all scenes. Returns list of image paths."""
        width, height = self._get_dimensions(aspect_ratio)
        image_paths = []

        sorted_scenes = sorted(scenes, key=lambda s: s.t)

        for i, scene in enumerate(sorted_scenes):
            logger.info(f"Generating image {i + 1}/{len(sorted_scenes)}: {scene.visual[:50]}...")

            job_id = await self.client.create_job(
                prompt=scene.visual,
                width=width,
                height=height,
                steps=steps,
                performance=performance,
            )
            result = await self.client.poll_job(job_id)

            image_data = await self._download_image(result)
            image_path = os.path.join(output_dir, f"scene_{int(scene.t)}.png")
            with open(image_path, "wb") as f:
                f.write(image_data)

            image_paths.append(image_path)
            logger.info(f"Image saved: {image_path}")

            if progress_callback:
                progress = ((i + 1) / len(sorted_scenes)) * 100
                await progress_callback(progress)

        return image_paths

    async def _download_image(self, job_result: dict) -> bytes:
        """Download image from SE8 result."""
        file_path = job_result.get("file_path") or job_result.get("output_path")
        if file_path:
            return await self.client.download_image(file_path)

        images = job_result.get("images") or job_result.get("output", [])
        if images and isinstance(images, list) and len(images) > 0:
            first_image = images[0]
            if isinstance(first_image, dict):
                file_path = first_image.get("path") or first_image.get("url")
            else:
                file_path = str(first_image)
            if file_path:
                return await self.client.download_image(file_path)

        raise ValueError("No image found in SE8 response")
