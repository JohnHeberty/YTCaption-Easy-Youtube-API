from pathlib import Path

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from app.infrastructure.dependencies import get_job_store_override, get_settings_dep, get_downloader_override
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
    store: VideoDownloadJobStore = Depends(get_job_store_override),
    settings: Settings = Depends(get_settings_dep),
):
    """Check service health including Redis, Celery worker, and cache directory status."""
    from app.infrastructure.celery_config import celery_app

    health = {
        "status": "healthy",
        "service": "video-downloader",
        "timestamp": now_brazil().isoformat(),
        "checks": {
            "api": "ok",
            "redis": "checking",
            "celery_worker": "checking",
            "cache_dir": "checking"
        }
    }

    try:
        store.redis.ping()
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"failed: {e}"
        health["status"] = "unhealthy"

    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        if active_workers and len(active_workers) > 0:
            health["checks"]["celery_worker"] = "ok"
            health["active_workers"] = len(active_workers)
        else:
            health["checks"]["celery_worker"] = "no workers available"
            health["status"] = "degraded"
            health["warning"] = "Celery worker não está disponível - jobs não serão processados"
    except Exception as e:
        health["checks"]["celery_worker"] = f"failed: {e}"
        health["status"] = "degraded"
        health["warning"] = "Não foi possível conectar ao Celery worker"

    cache_dir = Path(settings.cache_dir)
    if cache_dir.exists() and cache_dir.is_dir():
        health["checks"]["cache_dir"] = "ok"
    else:
        health["checks"]["cache_dir"] = "missing"
        health["status"] = "unhealthy"

    status_code = 200
    if health["status"] == "unhealthy":
        status_code = 503
    elif health["status"] == "degraded":
        status_code = 200

    return JSONResponse(content=health, status_code=status_code)


@router.get("/metrics", summary="Prometheus metrics", response_class=Response)
async def prometheus_metrics(store: VideoDownloadJobStore = Depends(get_job_store_override)):
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
async def get_user_agent_stats(downloader: YDLPVideoDownloader = Depends(get_downloader_override)):
    """Retrieve user agent usage statistics and quarantine status."""
    return downloader.get_user_agent_stats()


@router.post(
    "/user-agents/reset/{user_agent_id}",
    summary="Reset user agent",
    description="Remove um User-Agent da quarentena para que ele volte a ser elegível para novos downloads.",
    response_model=UserAgentResetResponse,
)
async def reset_user_agent(user_agent_id: str, downloader: YDLPVideoDownloader = Depends(get_downloader_override)):
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