"""
API principal do orquestrador
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager

from common.log_utils import setup_structured_logging, get_logger
from common.datetime_utils import now_brazil
from common.fastapi_utils import create_service_app

from domain.models import (
    PipelineRequest, PipelineResponse, PipelineJob, PipelineStatus, RootResponse,
)
from infrastructure.dependency_injection import get_pipeline_orchestrator, get_health_checker, set_app_start_time
from infrastructure.redis_store import RedisStore, get_store
from services.pipeline_background import execute_pipeline_background
from infrastructure.microservice_client import MicroserviceClient
from core.config import get_settings
from core.exceptions import ValidationError, JobCreationError, RedisConnectionError
from core.constants import Timeouts, HealthStatus
from api.health_routes import router as health_router
from api.admin_routes import router as admin_router
from api.jobs_routes import router as jobs_router

settings = get_settings()

setup_structured_logging(
    service_name="orchestrator",
    log_level="INFO",
    log_dir=settings.log_dir,
)
logger = get_logger(__name__)

orchestrator = None
redis_store = None
app_start_time = now_brazil()


async def validate_configuration():
    logger.info("Validating configuration...")
    if not redis_store:
        raise RuntimeError("Redis store not initialized")
    if not redis_store.ping():
        raise RuntimeError("Redis not accessible - cannot start service")
    logger.info("Redis connection validated")
    services_to_check = ["se2-video-downloader", "se3-audio-normalization", "se4-audio-transcriber"]
    for service_name in services_to_check:
        try:
            client = MicroserviceClient(service_name)
            health = await client.check_health()
            if health.get("status") == "healthy":
                logger.info(f"{service_name} is healthy")
            else:
                logger.warning(f"{service_name} is not healthy: {health}")
        except Exception as e:
            logger.warning(f"Failed to check {service_name} health: {e}")
    logger.info("Configuration validation complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, redis_store, app_start_time
    logger.info("Starting YouTube Caption Orchestrator API")
    try:
        redis_store = get_store()
        orchestrator = get_pipeline_orchestrator(redis_store=redis_store)
        await validate_configuration()
        app_start_time = now_brazil()
        set_app_start_time(app_start_time)
    except Exception as e:
        logger.critical(f"Failed to initialize orchestrator: {str(e)}", exc_info=True)
        raise
    yield
    logger.info("Shutting down Orchestrator API...")


cors_config = {
    "allow_origins": ["*"],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}


def setup_routers(app):
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(jobs_router)


app = create_service_app(
    service_name="orchestrator",
    title="YouTube Caption Orchestrator API",
    description="API orquestradora para processar videos do YouTube: download -> normalizacao -> transcricao",
    version=settings["app_version"],
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    cors_config=cors_config,
    use_shared_exception_handlers=False,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.method} {request.url.path}", extra={'errors': exc.errors()})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Unhandled exception on {request.method} {request.url.path}", exc_info=True, extra={'exception_type': type(exc).__name__, 'exception_message': str(exc)})
    response_data = {"error": "INTERNAL_ERROR", "message": "An unexpected error occurred. Please contact support if the problem persists."}
    if settings.get("debug", False):
        response_data["debug_info"] = {"exception_type": type(exc).__name__, "exception_message": str(exc)}
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=response_data)


@app.get(
    "/",
    tags=["Root"],
    summary="Service info",
    description="Retorna a visão geral do orchestrator e os endpoints principais para iniciar e acompanhar pipelines.",
    response_model=RootResponse,
)
async def root():
    return {
        "service": "YouTube Caption Orchestrator",
        "version": settings["app_version"],
        "status": "running",
        "endpoints": {
            "health": "/health",
            "process": "/process (POST) - Inicia novo pipeline",
            "job_status": "/jobs/{job_id} (GET) - Consulta status com progresso em tempo real",
            "list_jobs": "/jobs (GET)",
            "docs": "/docs",
        },
    }


@app.post(
    "/process",
    response_model=PipelineResponse,
    tags=["Pipeline"],
    summary="Start pipeline processing",
    description="Inicia o pipeline completo para um vídeo do YouTube: download, normalização de áudio e transcrição.",
)
async def process_youtube_video(request: PipelineRequest, background_tasks: BackgroundTasks):
    try:
        job = await _create_pipeline_job(request)
        redis_store.save_job(job)
        background_tasks.add_task(execute_pipeline_background, job.id)
        return PipelineResponse(
            job_id=job.id,
            status=job.status,
            message="Pipeline iniciado com sucesso. Use /jobs/{job_id} para acompanhar o progresso.",
            youtube_url=job.youtube_url,
            overall_progress=0.0,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except JobCreationError as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _create_pipeline_job(request: PipelineRequest) -> PipelineJob:
    return PipelineJob.create_new(
        youtube_url=request.youtube_url,
        language=request.language or settings["default_language"],
        language_out=request.language_out,
        remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
        convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
        apply_highpass_filter=request.apply_highpass_filter if request.apply_highpass_filter is not None else False,
        set_sample_rate_16k=request.set_sample_rate_16k if request.set_sample_rate_16k is not None else settings["default_sample_rate_16k"],
    )
