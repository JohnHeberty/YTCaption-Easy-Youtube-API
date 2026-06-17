"""Tools routes for SE9 Image Engine.

Clean-room rewrite of FOOOCUS tools endpoints.
Provides image description and mask generation.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile

from app.domain.models import DescribeImageResponse, GenerateMaskRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tools"])


@router.post(
    "/v1/tools/describe-image",
    response_model=DescribeImageResponse,
    tags=["Tools"],
)
def describe_image(
    image: UploadFile,
    image_type: Optional[str] = Query(
        "Photo", description="Image type, 'Photo' or 'Anime'"
    ),
):
    """Describe an image — get tags from an image."""
    try:
        from modules.util import HWC3

        img_bytes = image.file.read()

        if image_type == "Photo":
            from extras.interrogate import default_interrogator

            interrogator = default_interrogator
        else:
            from extras.wd14tagger import default_interrogator

            interrogator = default_interrogator

        import numpy as np
        import cv2

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = HWC3(img)
        result = interrogator(img)
        return DescribeImageResponse(describe=result)
    except ImportError:
        logger.warning("Fooocus modules not available for describe-image")
        return DescribeImageResponse(describe="Module not available")
    except Exception as e:
        logger.error("describe-image failed: %s", e)
        return DescribeImageResponse(describe=f"Error: {e}")


@router.post(
    "/v1/tools/generate_mask",
    summary="Generate mask endpoint",
    tags=["Tools"],
)
async def generate_mask(mask_options: GenerateMaskRequest) -> str:
    """Generate a mask from an image."""
    try:
        from extras.inpaint_mask import SAMOptions, generate_mask_from_image
        from fooocusapi.utils.img_utils import narray_to_base64img, read_input_image

        image = read_input_image(mask_options.image)
        extras = {}
        sam_options = None

        if mask_options.mask_model == "u2net_cloth_seg":
            extras["cloth_category"] = mask_options.cloth_category
        elif mask_options.mask_model == "sam":
            sam_options = SAMOptions(
                dino_prompt=mask_options.dino_prompt_text,
                dino_box_threshold=mask_options.box_threshold,
                dino_text_threshold=mask_options.text_threshold,
                dino_erode_or_dilate=mask_options.dino_erode_or_dilate,
                dino_debug=mask_options.dino_debug,
                max_detections=mask_options.sam_max_detections,
                model_type=mask_options.sam_model,
            )

        mask, _, _, _ = generate_mask_from_image(
            image, mask_options.mask_model, extras, sam_options
        )
        return narray_to_base64img(mask)
    except ImportError:
        logger.warning("Fooocus modules not available for generate_mask")
        return ""
    except Exception as e:
        logger.error("generate_mask failed: %s", e)
        return ""
