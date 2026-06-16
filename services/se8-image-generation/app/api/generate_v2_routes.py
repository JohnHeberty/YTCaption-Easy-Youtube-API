from fastapi import APIRouter, Request

from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/v2/generation", tags=["GenerateV2"])


@router.post("/text-to-image-with-ip", summary="Text to Image With IP")
async def text_to_image_with_ip(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v2/generation/text-to-image-with-ip", body, ct, accept)


@router.post("/image-upscale-vary", summary="Image Upscale or Vary (V2)")
async def image_upscale_vary_v2(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v2/generation/image-upscale-vary", body, ct, accept)


@router.post("/image-inpaint-outpaint", summary="Image Inpaint or Outpaint (V2)")
async def image_inpaint_outpaint_v2(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v2/generation/image-inpaint-outpaint", body, ct, accept)


@router.post("/image-prompt", summary="Image Prompt (V2)")
async def image_prompt_v2(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v2/generation/image-prompt", body, ct, accept)


@router.post("/image-enhance", summary="Image Enhance (V2)")
async def image_enhance_v2(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v2/generation/image-enhance", body, ct, accept)
