from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.services.image_service import fooocus_client
from app.core.config import get_settings
from common.log_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    fooocus_ok = await fooocus_client.health_check()
    return {
        "status": "healthy" if fooocus_ok else "degraded",
        "service": "image-generation",
        "fooocus_api": "connected" if fooocus_ok else "disconnected",
    }


@router.get("/health/deep")
async def health_deep():
    fooocus_ok = await fooocus_client.health_check()
    return {
        "status": "healthy" if fooocus_ok else "degraded",
        "service": "image-generation",
        "checks": {
            "fooocus_api": "connected" if fooocus_ok else "disconnected",
        },
    }


@router.get("/", include_in_schema=False)
async def home():
    try:
        result = await fooocus_client.home()
        if isinstance(result, str):
            return HTMLResponse(content=result)
        if isinstance(result, dict) and "raw" in result:
            return HTMLResponse(content=result["raw"])
        return result
    except Exception as e:
        return {
            "service": "se8-image-generation",
            "status": "ok",
            "docs": "/docs",
            "fooocus_api": settings.fooocus_api_url,
        }


@router.get("/ping")
async def ping():
    fooocus_ok = await fooocus_client.health_check()
    if fooocus_ok:
        return "pong"
    raise HTTPException(status_code=503, detail="Fooocus API unavailable")
