from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/generation", tags=["GenerateV1"])


@router.post("/text-to-image", summary="Text to Image Generation")
async def text_to_image(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/generation/text-to-image", body, ct, accept)


@router.post("/image-upscale-vary", summary="Image Upscale or Vary")
async def image_upscale_vary(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/generation/image-upscale-vary", body, ct, accept)


@router.post("/image-inpaint-outpaint", summary="Image Inpaint or Outpaint")
async def image_inpaint_outpaint(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/generation/image-inpaint-outpaint", body, ct, accept)


@router.post("/image-prompt", summary="Image Prompt")
async def image_prompt(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/generation/image-prompt", body, ct, accept)


@router.post("/image-enhance", summary="Image Enhance")
async def image_enhance(request: Request, accept: str = None):
    body = await request.body()
    ct = request.headers.get("content-type", "")
    return await fooocus_client.proxy_raw_post("/v1/generation/image-enhance", body, ct, accept)


@router.post("/stop", summary="Stop Generation")
async def stop():
    try:
        return await fooocus_client.stop()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stop failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/query-job", summary="Query Job Status")
async def query_job(job_id: str, require_step_preview: bool = False):
    try:
        return await fooocus_client.query_job(job_id, require_step_preview)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("query_job failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/job-queue", summary="Job Queue Info")
async def job_queue():
    try:
        return await fooocus_client.job_queue()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("job_queue failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/job-history", summary="Job History")
async def job_history(job_id: str = None, page: int = 0, page_size: int = 20, delete: bool = False):
    try:
        return await fooocus_client.job_history(job_id, page, page_size, delete)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("job_history failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/outputs", summary="List Output Images")
async def list_outputs():
    try:
        return await fooocus_client.list_outputs()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_outputs failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
