from fastapi import APIRouter, HTTPException, Request

from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Tools"])


@router.post("/v1/tools/describe-image", summary="Describe Image (Get Tags)")
async def describe_image(request: Request, image_type: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/tools/describe-image", body, ct)


@router.post("/v1/tools/generate_mask", summary="Generate Mask")
async def generate_mask(request: Request):
    try:
        body = await request.json()
        return await fooocus_client.generate_mask(body)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_mask failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
