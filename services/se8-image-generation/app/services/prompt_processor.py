"""Prompt engineering and text processing — stateless string transformations.

Extracted from worker.py to enable isolated unit testing.
"""
from __future__ import annotations

import random
import re
from typing import Any

from app.domain.task_models import AsyncTask
from app.services.task_builder import parse_aspect_ratio, apply_performance_defaults


def wildcards(text: str, seed: int) -> str:
    """Simple wildcard replacement: {random|option1|option2} -> random pick."""

    def replace_wildcard(match):
        options = match.group(1).split("|")
        rng = random.Random(seed)
        return rng.choice(options)

    return re.sub(r"\{([^}]+)\}", replace_wildcard, text)


def apply_style(
    prompt: str,
    negative: str,
    styles: list,
) -> tuple[str, str]:
    """Apply style presets to prompt/negative."""
    positive_additions = []
    for style in styles:
        if isinstance(style, str):
            positive_additions.append(style)
    if positive_additions:
        prompt = prompt + ", " + ", ".join(positive_additions)
    return prompt, negative


def process_prompt(
    async_task: AsyncTask,
    pipeline: Any,
) -> tuple[list, bool, list, int]:
    """Process prompt: refresh models, encode text. Returns (tasks, use_expansion, loras, progress)."""
    seed = int(async_task.seed) if async_task.seed.isdigit() else random.randint(0, 2**32 - 1)
    async_task.seed = str(seed)

    width, height = parse_aspect_ratio(async_task.aspect_ratios_selection)

    # Apply performance defaults
    apply_performance_defaults(async_task)

    # Refresh pipeline
    pipeline.refresh_everything(
        refiner_model_name=async_task.refiner_model_name,
        base_model_name=async_task.base_model_name,
        loras=async_task.loras,
        vae_name=async_task.vae_name,
    )

    # Process each image number
    tasks = []
    for i in range(async_task.image_number):
        current_seed = seed + i if not async_task.disable_seed_increment else seed
        prompt = wildcards(async_task.prompt, current_seed)
        prompt, negative = apply_style(prompt, async_task.negative_prompt, async_task.style_selections)
        tasks.append({
            "seed": current_seed,
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
        })

    return tasks, False, async_task.loras, 0
