"""Image generation service using SE8."""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

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

    def _enrich_prompt(self, visual: str, global_style: dict[str, Any] | None) -> str:
        """Enrich visual prompt with global_style metadata.

        Appends visual_style and tone to create more coherent images.
        """
        if not global_style:
            return visual

        parts = [visual]

        # Add visual_style if present
        vs = global_style.get("visual_style")
        if vs:
            parts.append(f", {vs}")

        # Add tone if present (helps SDXL understand mood)
        tone = global_style.get("tone")
        if tone:
            parts.append(f", mood: {tone}")

        return "".join(parts)

    def _enrich_scene_prompt(
        self,
        scene: SceneSuggestion,
        global_style: dict[str, Any] | None,
    ) -> tuple[str, str]:
        """Enrich prompt and negative_prompt using scene-level metadata.

        Uses shot_type, composition, lighting, color_mood, subject, environment.
        Returns (enriched_prompt, enriched_negative_prompt).
        """
        prompt_parts: list[str] = [scene.visual]
        neg_parts: list[str] = [scene.negative_prompt] if scene.negative_prompt else []

        # Extract scene-level image metadata (stored as extra fields)
        # These come from make-video.json but aren't in SceneSuggestion model
        # We'll use global_style for now and scene.negative_prompt
        if global_style:
            # Add visual_style and tone
            vs = global_style.get("visual_style")
            if vs:
                prompt_parts.append(f", {vs}")
            tone = global_style.get("tone")
            if tone:
                prompt_parts.append(f", mood: {tone}")

            # Boolean flags → negative terms
            if global_style.get("no_people_or_faces"):
                neg_parts.append("people, faces, humans, persons, crowds")
            if global_style.get("no_supernatural_confirmation"):
                neg_parts.append("ghosts, spirits, supernatural entities, paranormal")
            if global_style.get("no_new_facts"):
                neg_parts.append("text, letters, words, signage, documents")

            # Safety rules
            safety = global_style.get("safety")
            if safety and isinstance(safety, str):
                neg_parts.append(safety)

        return "".join(prompt_parts), ", ".join(neg_parts) if neg_parts else ""

    async def generate_all(
        self,
        scenes: list[SceneSuggestion],
        aspect_ratio: str = "9:16",
        steps: int = 30,
        performance: str = "Quality",
        output_dir: str = "/tmp",
        progress_callback: Callable[[float], Awaitable[None]] | None = None,
        global_style: dict[str, Any] | None = None,
    ) -> list[str]:
        """Generate images for all scenes. Returns list of image paths."""
        width, height = self._get_dimensions(aspect_ratio)
        image_paths: list[str] = []

        sorted_scenes = sorted(scenes, key=lambda s: s.t)

        for i, scene in enumerate(sorted_scenes):
            # Enrich prompt and negative_prompt with scene metadata
            enriched_prompt, enriched_negative = self._enrich_scene_prompt(scene, global_style)
            enhanced_prompt = enriched_prompt + self.cinematic_suffix
            logger.info("Generating image %d/%d: %s...", i + 1, len(sorted_scenes), scene.visual[:50])

            images = await self.client.generate_image(
                prompt=enhanced_prompt,
                width=width,
                height=height,
                steps=steps,
                performance=performance,
                negative_prompt=enriched_negative if enriched_negative else None,
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
            logger.info("Image saved: %s", image_path)

            if progress_callback:
                progress = ((i + 1) / len(sorted_scenes)) * 100
                await progress_callback(progress)

        return image_paths
