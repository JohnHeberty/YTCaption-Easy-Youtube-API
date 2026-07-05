"""Tools routes for SE8 Image Engine.

Provides image description, mask generation, and pure ESRGAN upscaling.
"""

from __future__ import annotations
from common.log_utils import get_logger

from fastapi import APIRouter, File, Query, UploadFile

from app.api.image_utils import ndarray_to_base64png, read_input_image
from app.domain.models import DescribeImageResponse, GenerateMaskRequest

logger = get_logger(__name__)

router = APIRouter(tags=["Tools"])


@router.post(
    "/v1/tools/upscale-esrgan",
    summary="Pure ESRGAN upscale (no diffusion). Uses 4x-UltraSharp.",
    tags=["Tools"],
)
async def upscale_esrgan(
    file: UploadFile = File(..., description="Image to upscale"),
    scale: float = Query(2.0, ge=1.0, le=4.0, description="Output scale factor"),
) -> dict:
    """Pure ESRGAN 4x upscale — no SDXL diffusion, no color distortion.

    Loads the image, runs ESRGAN super-resolution, then resizes to
    the requested scale. Preserves original color distribution.
    """
    try:
        import cv2
        import numpy as np

        img_bytes = await file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "error": "Failed to decode image"}

        logger.info("ESRGAN input: shape=%s dtype=%s", img.shape, img.dtype)

        from app.services.upscaler import perform_upscale
        upscaled = perform_upscale(img)

        logger.info("ESRGAN output: type=%s shape=%s dtype=%s", type(upscaled).__name__, 
                     getattr(upscaled, 'shape', 'N/A'), getattr(upscaled, 'dtype', 'N/A'))

        if upscaled is None:
            return {"success": False, "error": "perform_upscale returned None"}

        # Resize from 4x to requested scale
        orig_h, orig_w = img.shape[:2]
        target_w = max(1, int(orig_w * scale))
        target_h = max(1, int(orig_h * scale))
        upscaled = cv2.resize(upscaled, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

        _, buf = cv2.imencode(".png", upscaled)
        import base64
        b64 = base64.b64encode(buf).decode("utf-8")

        logger.info("ESRGAN upscale: %dx%d -> %dx%d (scale=%.1f)",
                     img.shape[1], img.shape[0], target_w, target_h, scale)
        return {
            "success": True,
            "base64": f"data:image/png;base64,{b64}",
            "width": target_w,
            "height": target_h,
        }
    except Exception as e:
        logger.error("ESRGAN upscale failed: %s", e)
        return {"success": False, "error": str(e)}


@router.post(
    "/v1/tools/describe-image",
    response_model=DescribeImageResponse,
    tags=["Tools"],
)
def describe_image(
    image: UploadFile,
    image_type: str | None = Query(
        "Photo", description="Image type, 'Photo' or 'Anime'"
    ),
) -> DescribeImageResponse:
    """Describe an image — get tags from an image."""
    try:
        import cv2
        import numpy as np
        from modules.util import HWC3

        img_bytes = image.file.read()

        if image_type == "Photo":
            from extras.interrogate import default_interrogator
        else:
            from extras.wd14tagger import default_interrogator

        interrogator = default_interrogator
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = HWC3(img)
        result = interrogator(img)
        return DescribeImageResponse(describe=result)
    except ImportError:
        logger.warning("Required modules not available for describe-image")
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
        return ndarray_to_base64png(mask)
    except ImportError:
        logger.warning("Required modules not available for generate_mask")
        return ""
    except Exception as e:
        logger.error("generate_mask failed: %s", e)
        return ""
