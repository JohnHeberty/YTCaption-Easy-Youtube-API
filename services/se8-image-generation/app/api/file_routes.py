from fastapi import APIRouter, HTTPException

from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Files"])


@router.get("/files/{date}/{file_name}", summary="Get Output File")
async def get_output_file(date: str, file_name: str):
    try:
        content, content_type = await fooocus_client.get_output_file(date, file_name)
        from fastapi.responses import Response
        return Response(content=content, media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_output_file failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
