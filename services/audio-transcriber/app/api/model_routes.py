from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import TYPE_CHECKING

from common.log_utils import get_logger
from app.api.schemas import ModelActionResponse, ModelStatusResponse
from app.infrastructure.dependencies import get_processor_override

if TYPE_CHECKING:
    from app.services.processor import TranscriptionProcessor

logger = get_logger(__name__)

router = APIRouter(prefix="/model", tags=["Model"])


@router.post("/load", summary="Load Whisper model", response_model=ModelActionResponse, responses={500: {"description": "Failed to load model"}})
async def load_whisper_model(processor: "TranscriptionProcessor" = Depends(get_processor_override)):
    """Explicitly load the Whisper model into memory for transcription."""
    try:
        logger.info("📤 Requisição para carregar modelo Whisper")
        result = processor.load_model_explicit()

        if result["success"]:
            logger.info(f"✅ Modelo carregado: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=200
            )
        else:
            logger.error(f"❌ Falha ao carregar: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=500
            )

    except Exception as e:
        error_msg = f"Erro inesperado ao carregar modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/unload", summary="Unload Whisper model", response_model=ModelActionResponse, responses={500: {"description": "Failed to unload model"}})
async def unload_whisper_model(processor: "TranscriptionProcessor" = Depends(get_processor_override)):
    """Unload the Whisper model from memory to free GPU/CPU resources."""
    try:
        logger.info("📥 Requisição para descarregar modelo Whisper")
        result = processor.unload_model()

        if result["success"]:
            logger.info(f"✅ Modelo descarregado: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=200
            )
        else:
            logger.error(f"❌ Falha ao descarregar: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=500
            )

    except Exception as e:
        error_msg = f"Erro inesperado ao descarregar modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/status", summary="Model status", response_model=ModelStatusResponse, responses={500: {"description": "Failed to get model status"}})
async def get_model_status(processor: "TranscriptionProcessor" = Depends(get_processor_override)):
    """Query the current loading status and metadata of the Whisper model."""
    try:
        status = processor.get_model_status()
        return JSONResponse(content=status, status_code=200)
    except Exception as e:
        error_msg = f"Erro ao consultar status do modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)