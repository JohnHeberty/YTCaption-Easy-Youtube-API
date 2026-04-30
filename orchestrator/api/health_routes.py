"""
Health check routes for the orchestrator service.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from common.log_utils import get_logger
from domain.models import HealthResponse
from core.config import get_settings
from infrastructure.dependency_injection import (
    get_app_start_time,
    get_health_checker,
    get_pipeline_orchestrator,
)
from modules.redis_store import get_store

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])
settings = get_settings()


def _get_redis_store():
    return get_store()


def _get_orchestrator():
    return get_pipeline_orchestrator()


@router.get("/health", summary="Verificar saude", response_model=HealthResponse, tags=["Health"], responses={503: {"description": "Service unavailable"}})
async def health_check(
    redis_store=Depends(_get_redis_store),
    orchestrator=Depends(_get_orchestrator),
):
    """Verifica a saúde do orchestrator e dos microserviços dependentes."""
    try:
        app_start_time = get_app_start_time()
        uptime = (now_brazil() - app_start_time).total_seconds() if app_start_time else 0

        redis_ok = False
        if redis_store:
            try:
                redis_ok = redis_store.ping()
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")

        microservices_status = {}
        if orchestrator:
            try:
                microservices_status = await orchestrator.check_services_health()
            except Exception as e:
                logger.error(f"Failed to check microservices health: {e}")
                microservices_status = {"error": str(e)}

        all_healthy = redis_ok and all(
            s == "healthy" for s in microservices_status.values() if isinstance(s, str)
        )

        overall_status = "healthy" if all_healthy else "degraded"
        if not redis_ok:
            overall_status = "unhealthy"

        return HealthResponse(
            status=overall_status,
            service="orchestrator",
            version=settings["app_version"],
            timestamp=now_brazil(),
            microservices=microservices_status,
            uptime_seconds=uptime,
            redis_connected=redis_ok,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}",
        )