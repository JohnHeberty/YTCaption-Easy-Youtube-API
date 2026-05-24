from pathlib import Path

from common.health_utils import ServiceHealthChecker
from common.log_utils import get_logger

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from app.infrastructure.dependencies import job_store, get_settings_dep, downloader
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.core.config import Settings
from app.services.video_downloader import YDLPVideoDownloader
from app.core.models import HealthResponse, UserAgentResetResponse, UserAgentStatsResponse

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get(
    "/health",
    summary="Health check",
    description="Verifica API, Redis, workers Celery e diretório de cache do serviço.",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check(
    store: VideoDownloadJobStore = Depends(job_store),
    settings: Settings = Depends(get_settings_dep),
):
    """Check service health including Redis, Celery worker, and cache directory status."""
    from app.infrastructure.celery_config import celery_app

    checker = ServiceHealthChecker("video-downloader", version=settings.get("version", "3.0.0"))
    checker.add_check("redis", lambda: ServiceHealthChecker.check_redis(store.redis))
    checker.add_check("celery_worker", lambda: ServiceHealthChecker.check_celery(celery_app))
    checker.add_check("cache_dir", lambda: _check_cache_dir(settings.cache_dir))

    result = await checker.check_all()

    status_code = 200
    if result["status"] == "unhealthy":
        status_code = 503
    elif result["status"] == "degraded":
        status_code = 200

    return JSONResponse(content=result, status_code=status_code)


def _check_cache_dir(cache_dir: str) -> dict:
    path = Path(cache_dir)
    if path.exists() and path.is_dir():
        return {"status": "ok"}
    return {"status": "error", "message": f"Cache directory missing: {cache_dir}"}


@router.get("/metrics", summary="Prometheus metrics", response_class=Response)
async def prometheus_metrics(store: VideoDownloadJobStore = Depends(job_store)):
    """Expose Prometheus-format metrics for the download service."""
    svc = "video_downloader"
    stats: dict = {}
    try:
        stats = store.get_stats()
    except Exception as _e:
        logger.warning("Metrics: failed to get stats: %s", _e)

    by_status = stats.get("by_status", {})
    total = stats.get("total_jobs", 0)

    lines = [
        f"# HELP {svc}_jobs_total Jobs in Redis store by status",
        f"# TYPE {svc}_jobs_total gauge",
    ]
    for _status, _count in by_status.items():
        lines.append(f'{svc}_jobs_total{{status="{_status}"}} {_count}')
    lines += [
        f"# HELP {svc}_jobs_store_total Total jobs in Redis store",
        f"# TYPE {svc}_jobs_store_total gauge",
        f"{svc}_jobs_store_total {total}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.get(
    "/user-agents/stats",
    summary="User agent stats",
    description="Retorna estatísticas de uso, quarentena e qualidade média dos User-Agents disponíveis.",
    response_model=UserAgentStatsResponse,
)
async def get_user_agent_stats(downloader: YDLPVideoDownloader = Depends(downloader)):
    """Retrieve user agent usage statistics and quarantine status."""
    return downloader.get_user_agent_stats()


@router.post(
    "/user-agents/reset/{user_agent_id}",
    summary="Reset user agent",
    description="Remove um User-Agent da quarentena para que ele volte a ser elegível para novos downloads.",
    response_model=UserAgentResetResponse,
)
async def reset_user_agent(user_agent_id: str, downloader: YDLPVideoDownloader = Depends(downloader)):
    """Reset a quarantined user agent so it can be used again for downloads."""
    stats = downloader.get_user_agent_stats()
    matching_ua = None

    for quarantined_ua in stats.get('quarantined_uas', []):
        if quarantined_ua.startswith(user_agent_id) or user_agent_id in quarantined_ua:
            matching_ua = quarantined_ua
            break

    if not matching_ua:
        matching_ua = user_agent_id

    success = downloader.reset_user_agent(matching_ua)

    return {
        "success": success,
        "user_agent": matching_ua[:50] + "..." if len(matching_ua) > 50 else matching_ua,
        "message": f"User-Agent {'resetado com sucesso' if success else 'não encontrado'}"
    }