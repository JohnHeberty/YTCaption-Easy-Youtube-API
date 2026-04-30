"""
YouTube Search Service - Main Application

Microservice for YouTube search operations with Celery + Redis and 24h cache.
Follows SOLID principles and clean architecture.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers
from common.datetime_utils import now_brazil

from app.core.config import get_settings
from app.infrastructure.redis_store import YouTubeSearchJobStore as RedisJobStore
from app.infrastructure.celery_config import celery_app
from app.infrastructure.dependencies import get_job_store
from app.shared.exceptions import (
    YouTubeSearchException,
    ServiceException,
    InvalidRequestError,
    exception_handler,
)
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.domain.models import HealthResponse, RootResponse

# Import API routers
from app.api import routes as api_routes
from app.api import search, jobs, admin

# Configuration
settings = get_settings()
setup_structured_logging(
    service_name="youtube-search",
    log_level=settings["log_level"],
    log_dir=settings.get("log_dir", "./logs"),
    json_format=True,
)
logger = get_logger(__name__)


# ============================================================================
# LIFECYCLE
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — replaces deprecated @app.on_event."""
    # ---- startup ----
    try:
        await job_store.start_cleanup_task()
        logger.info("YouTube Search Service started successfully")
    except Exception as exc:
        logger.error("Error during startup: %s", exc)
        raise

    yield

    # ---- shutdown ----
    try:
        await job_store.stop_cleanup_task()
        logger.info("YouTube Search Service stopped gracefully")
    except Exception as exc:
        logger.error("Error during shutdown: %s", exc)


# Global instances
app = FastAPI(
    title="YouTube Search Service",
    description="Microservice for YouTube search operations with Celery + Redis and 24h cache",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup exception handlers from common library
setup_exception_handlers(app, debug=settings.get("debug", False))

# Exception handlers - mantidos para compatibilidade
app.add_exception_handler(YouTubeSearchException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)
app.add_exception_handler(InvalidRequestError, exception_handler)

# CORS middleware
if settings["cors"]["enabled"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings["cors"]["origins"],
        allow_credentials=settings["cors"]["credentials"],
        allow_methods=settings["cors"]["methods"],
        allow_headers=settings["cors"]["headers"],
    )

# Rate limiting middleware (per-IP sliding window)
rate_limit_config = settings.get("rate_limit", {})
if isinstance(rate_limit_config, dict) and rate_limit_config.get("enabled", True):
    app.add_middleware(
        RateLimiterMiddleware,
        max_requests=rate_limit_config.get("max_requests")
        or rate_limit_config.get("requests_per_minute", 100),
        window_seconds=rate_limit_config.get("window_seconds")
        or rate_limit_config.get("period_seconds", 60),
    )

# Use Redis as shared store (via DI)
job_store = get_job_store()

# Include API routers
app.include_router(api_routes.router)


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get(
    "/health",
    summary="Health check",
    description=(
        "Executa verificação profunda do serviço, incluindo Redis, espaço em disco, "
        "workers Celery e carregamento da biblioteca de busca."
    ),
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check():
    """Deep health check - validates critical resources."""
    import shutil

    health_status = {
        "status": "healthy",
        "service": "youtube-search",
        "version": settings["version"],
        "timestamp": now_brazil().isoformat(),
        "checks": {},
    }

    is_healthy = True

    # Check Redis
    try:
        job_store.redis.ping()
        stats = job_store.get_stats()
        health_status["checks"]["redis"] = {
            "status": "ok",
            "message": "Connected",
            "jobs": stats,
        }
    except Exception as exc:
        health_status["checks"]["redis"] = {"status": "error", "message": str(exc)}
        is_healthy = False

    # Check disk space
    try:
        logs_dir = Path(settings["log_dir"])
        logs_dir.mkdir(exist_ok=True, parents=True)
        disk_stats = shutil.disk_usage(logs_dir)
        free_gb = disk_stats.free / (1024**3)
        percent_free = (disk_stats.free / disk_stats.total) * 100

        disk_status = "ok" if percent_free > 10 else "warning" if percent_free > 5 else "critical"
        if percent_free <= 5:
            is_healthy = False

        health_status["checks"]["disk_space"] = {
            "status": disk_status,
            "free_gb": round(free_gb, 2),
            "percent_free": round(percent_free, 2),
        }
    except Exception as exc:
        health_status["checks"]["disk_space"] = {"status": "error", "message": str(exc)}
        is_healthy = False

    # Check Celery workers
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        if active_workers:
            health_status["checks"]["celery_workers"] = {
                "status": "ok",
                "workers": len(active_workers),
                "active_tasks": sum(len(tasks) for tasks in active_workers.values()),
            }
        else:
            health_status["checks"]["celery_workers"] = {
                "status": "warning",
                "message": "No active workers detected",
            }
    except Exception as exc:
        health_status["checks"]["celery_workers"] = {"status": "error", "message": str(exc)}

    # Check ytbpy library
    try:
        from app.services.ytbpy import video  # noqa: F401
        health_status["checks"]["ytbpy"] = {"status": "ok", "message": "Library loaded"}
    except Exception as exc:
        health_status["checks"]["ytbpy"] = {"status": "error", "message": str(exc)}
        is_healthy = False

    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    status_code = 200 if is_healthy else 503

    return JSONResponse(content=health_status, status_code=status_code)


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get(
    "/",
    summary="Service info",
    description="Retorna o catálogo resumido dos principais endpoints públicos do serviço.",
    response_model=RootResponse,
)
async def root():
    """Root endpoint."""
    return {
        "service": "YouTube Search Service",
        "version": settings["version"],
        "status": "running",
        "endpoints": {
            "health": "/health (GET) - Health check",
            "search_video_info": "/search/video-info (POST) - Get video information",
            "search_channel_info": "/search/channel-info (POST) - Get channel information",
            "search_playlist_info": "/search/playlist-info (POST) - Get playlist information",
            "search_videos": "/search/videos (POST) - Search videos",
            "search_shorts": "/search/shorts (POST) - Search YouTube Shorts (≤60s)",
            "search_related_videos": "/search/related-videos (POST) - Get related videos",
            "get_job": "/jobs/{job_id} (GET) - Get job status",
            "list_jobs": "/jobs (GET) - List all jobs",
            "delete_job": "/jobs/{job_id} (DELETE) - Delete job",
            "admin_stats": "/admin/stats (GET) - System statistics",
            "admin_queue": "/admin/queue (GET) - Celery queue stats",
            "admin_cleanup": "/admin/cleanup (POST) - System cleanup",
            "docs": "/docs - API documentation",
        },
    }
