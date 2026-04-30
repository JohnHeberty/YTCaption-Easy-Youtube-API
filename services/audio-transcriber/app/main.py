import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers

from app.shared.exceptions import AudioTranscriptionException, ServiceException, exception_handler
from app.domain.models import WhisperEngine
from app.api.schemas import RootResponse
from app.core.config import get_settings
from app.infrastructure.dependencies import get_job_store, get_processor

settings = get_settings()
setup_structured_logging(
    service_name="audio-transcriber",
    log_level=settings['log_level'],
    log_dir=settings.get('log_dir', './logs'),
    json_format=(settings.get('log_format', 'json') == 'json')
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store = get_job_store()
    processor = get_processor()
    try:
        await job_store.start_cleanup_task()
        logger.info("Audio Transcription Service iniciado com sucesso")

        preload_model = os.getenv('WHISPER_PRELOAD_MODEL', 'true').lower() == 'true'
        if preload_model:
            logger.info("🚀 Pré-carregando modelo Whisper no startup...")
            try:
                result = processor.load_model_explicit()
                if result["success"]:
                    logger.info("✅ %s", result['message'])
                else:
                    logger.warning("⚠️ Falha no pré-carregamento: %s", result['message'])
            except Exception as e:
                logger.error("❌ Erro ao pré-carregar modelo: %s", e)
                logger.warning("⚠️ Serviço continuará funcionando. Modelo será carregado sob demanda.")
        else:
            logger.info("ℹ️ Pré-carregamento de modelo DESABILITADO (WHISPER_PRELOAD_MODEL=false)")
    except Exception as e:
        logger.error("Erro durante inicialização: %s", e)
        raise

    yield

    try:
        await job_store.stop_cleanup_task()
        logger.info("Audio Transcription Service parado graciosamente")
    except Exception as e:
        logger.error("Erro durante shutdown: %s", e)


app = FastAPI(
    title="Audio Transcription Service",
    description="Microserviço para transcrição de áudio com cache de 24h",
    version="2.0.0",
    lifespan=lifespan,
)

setup_exception_handlers(app, debug=settings.get('debug', False))

app.add_exception_handler(AudioTranscriptionException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)

from app.api import jobs_router, admin_router, model_router, health_router

app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(model_router)
app.include_router(health_router)


@app.get(
    "/",
    summary="Service info",
    description="Retorna a visão geral do serviço e o catálogo resumido dos endpoints públicos de transcrição.",
    response_model=RootResponse,
)
async def root():
    return {
        "service": "Audio Transcription Service",
        "version": "2.0.0",
        "status": "running",
        "description": "Microserviço para transcrição de áudio com cache de 24h",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "jobs": {
                "create": "POST /jobs",
                "get": "GET /jobs/{job_id}",
                "list": "GET /jobs",
                "download": "GET /jobs/{job_id}/download",
                "text": "GET /jobs/{job_id}/text",
                "transcription": "GET /jobs/{job_id}/transcription",
                "delete": "DELETE /jobs/{job_id}",
                "orphaned": "GET /jobs/orphaned",
                "orphaned_cleanup": "POST /jobs/orphaned/cleanup"
            },
            "metadata": {
                "languages": "GET /languages",
                "engines": "GET /engines"
            },
            "admin": {
                "stats": "GET /admin/stats",
                "queue": "GET /admin/queue",
                "cleanup": "POST /admin/cleanup"
            },
            "model": {
                "status": "GET /model/status",
                "load": "POST /model/load",
                "unload": "POST /model/unload"
            }
        }
    }