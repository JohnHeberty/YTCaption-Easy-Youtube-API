"""Image saving and result building — pure I/O, no GPU.

Extracted from worker.py to enable isolated unit testing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


def save_output_file(
    img,
    output_dir: str = "",
    subfolder: str = "",
    filename: str | None = None,
) -> str:
    """Save a PIL/numpy image to the outputs directory. Returns the file path."""
    import numpy as np

    if not output_dir:
        from app.core.config import get_settings
        output_dir = get_settings().output_dir

    # Convert to numpy if needed
    if hasattr(img, "save"):
        img_array = np.array(img)
    elif isinstance(img, np.ndarray):
        img_array = img
    else:
        img_array = np.array(img)

    # Build output path
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d_%H-%M-%S")

    if not filename:
        filename = f"{time_str}.png"

    out_dir = Path(output_dir) / date_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    # Save via PIL
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(img_array.astype(np.uint8) if img_array.dtype != np.uint8 else img_array)
        pil_img.save(str(out_path))
    except ImportError:
        # Fallback: save as raw PNG using cv2 if available
        import cv2
        cv2.imwrite(str(out_path), cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))

    return str(out_path)


def save_and_log(
    async_task,
    imgs: list,
    loras: list,
    use_expansion: bool,
    width: int,
    height: int,
    persist_image: bool = True,
) -> list[str]:
    """Save images and log metadata. Returns list of file paths."""
    img_paths = []

    for i, img in enumerate(imgs):
        if isinstance(img, str):
            # Already a file path
            img_paths.append(img)
            continue

        seed = async_task.seed if i == 0 else str(int(async_task.seed) + i) if async_task.seed.isdigit() else async_task.seed
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{seed}.png"
        path = save_output_file(img, filename=filename)
        img_paths.append(path)

    return img_paths
