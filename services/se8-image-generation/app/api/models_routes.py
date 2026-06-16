from fastapi import APIRouter, HTTPException

from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/engines", tags=["Engines"])


@router.get("/all-models", summary="Get All Model Filenames")
async def get_all_models():
    try:
        return await fooocus_client.all_models()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("all_models failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/styles", summary="Get All Styles")
async def get_styles():
    try:
        return await fooocus_client.styles()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("styles failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/styles-detail", summary="Get Styles with Prompt Templates")
async def get_styles_detail():
    try:
        return await fooocus_client.styles_detail()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("styles_detail failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/clean_vram", summary="Clean VRAM (Unload Models)")
async def clean_vram():
    try:
        return await fooocus_client.clean_vram()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("clean_vram failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
