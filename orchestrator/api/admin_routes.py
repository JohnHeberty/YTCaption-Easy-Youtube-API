"""
Admin routes for the orchestrator service.
"""
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

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
from core.config import get_settings
from infrastructure.dependency_injection import get_pipeline_orchestrator
from modules.redis_store import get_store
from domain.models import AdminCleanupResponse, AdminStatsResponse, FactoryResetResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])
settings = get_settings()


def _get_redis_store():
    return get_store()


def _get_orchestrator():
    return get_pipeline_orchestrator()


@router.get(
    "/stats",
    summary="Obter estatisticas do orchestrator",
    description="Retorna estatísticas do orchestrator, métricas do Redis e o snapshot das configurações relevantes da pipeline.",
    response_model=AdminStatsResponse,
)
async def get_stats(redis_store=Depends(_get_redis_store)):
    """Retorna estatísticas do orchestrator, incluindo Redis e configurações ativas."""
    try:
        stats = redis_store.get_stats()

        return {
            "orchestrator": {
                "version": settings["app_version"],
                "environment": settings["environment"],
            },
            "redis": stats,
            "settings": {
                "cache_ttl_hours": settings["cache_ttl_hours"],
                "job_timeout_minutes": settings["job_timeout_minutes"],
                "poll_interval_initial": settings["poll_interval_initial"],
                "poll_interval_max": settings["poll_interval_max"],
                "max_poll_attempts": settings["max_poll_attempts"],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatisticas: {str(e)}")


@router.post(
    "/cleanup",
    summary="Limpar jobs antigos",
    description="Remove jobs antigos do Redis e, opcionalmente, limpa logs locais do orchestrator.",
    response_model=AdminCleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def cleanup_old_jobs(
    max_age_hours: int = Query(
        default=None,
        ge=1,
        description="Idade máxima em horas para manter jobs antes da remoção.",
        examples=[24, 72],
    ),
    deep: bool = Query(
        default=False,
        description="Quando true, executa limpeza mais agressiva e habilita remoção de logs locais.",
        examples=[False, True],
    ),
    remove_logs: bool = Query(
        default=False,
        description="Quando true, remove explicitamente os arquivos de log do orchestrator.",
        examples=[False, True],
    ),
    redis_store=Depends(_get_redis_store),
):
    """Remove jobs antigos do Redis e, opcionalmente, limpa arquivos de log."""
    try:
        result = {
            "message": "Cleanup executado com sucesso",
            "jobs_removed": 0,
            "logs_cleaned": False,
        }

        removed = redis_store.cleanup_old_jobs(max_age_hours)
        result["jobs_removed"] = removed

        if deep or remove_logs:
            log_dir = Path(settings["log_dir"])
            if log_dir.exists():
                for log_file in log_dir.glob("*.log*"):
                    try:
                        log_file.unlink()
                        logger.info(f"Removed log file: {log_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove {log_file}: {e}")
                result["logs_cleaned"] = True

        return result

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


@router.post(
    "/factory-reset",
    summary="Reset total",
    description=(
        "Executa limpeza destrutiva em todo o pipeline: FLUSHDB do Redis do orchestrator, "
        "remoção de logs locais e chamada de cleanup profundo nos microserviços dependentes."
    ),
    response_model=FactoryResetResponse,
    responses={500: {"description": "Internal server error"}},
)
async def factory_reset(
    redis_store=Depends(_get_redis_store),
    orchestrator=Depends(_get_orchestrator),
):
    """Executa limpeza destrutiva completa no orchestrator e aciona cleanup nos microserviços."""
    try:
        from redis import Redis
        from urllib.parse import urlparse
        import httpx

        result = {
            "message": "Factory reset executado SINCronamente em todos os servicos",
            "orchestrator": {
                "jobs_removed": 0,
                "redis_flushed": False,
                "logs_cleaned": False,
            },
            "microservices": {},
            "warning": "Todos os dados foram removidos de todos os servicos",
        }

        logger.warning("FACTORY RESET: Iniciando limpeza COMPLETA do Orchestrator")

        try:
            redis_url = settings["redis_url"]
            parsed = urlparse(redis_url)
            redis_host = parsed.hostname or "localhost"
            redis_port = parsed.port or 6379
            redis_db = int(parsed.path.strip("/")) if parsed.path else 0

            logger.warning(f"Executando FLUSHDB no Redis {redis_host}:{redis_port} DB={redis_db}")

            r = Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

            keys_before = r.keys("pipeline_job:*")
            result["orchestrator"]["jobs_removed"] = len(keys_before)

            r.flushdb()
            result["orchestrator"]["redis_flushed"] = True

            logger.info(f"Redis FLUSHDB executado: {len(keys_before)} jobs removidos")

        except Exception as e:
            logger.error(f"Erro ao limpar Redis do orchestrator: {e}")

        log_dir = Path(settings["log_dir"])
        if log_dir.exists():
            for log_file in log_dir.glob("*.log*"):
                try:
                    log_file.unlink()
                    logger.info(f"Removed log file: {log_file}")
                except Exception as e:
                    logger.warning(f"Could not remove {log_file}: {e}")
            result["orchestrator"]["logs_cleaned"] = True
            logger.warning("Factory reset: All orchestrator logs cleaned")

        microservices = []
        if orchestrator:
            microservices = [
                ("video-downloader", orchestrator.video_client),
                ("audio-normalization", orchestrator.audio_client),
                ("audio-transcriber", orchestrator.transcription_client),
            ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for service_name, service_client in microservices:
                try:
                    cleanup_url = f"{service_client.base_url}/admin/cleanup"
                    logger.warning(f"Calling FACTORY RESET for {service_name}: {cleanup_url}")

                    response = await client.post(
                        cleanup_url,
                        params={"deep": True, "purge_celery_queue": True},
                    )

                    if response.status_code == 200:
                        cleanup_data = response.json()
                        result["microservices"][service_name] = {
                            "status": "success",
                            "data": cleanup_data,
                        }
                        logger.info(f"Factory reset cleanup successful for {service_name}")
                    else:
                        result["microservices"][service_name] = {
                            "status": "error",
                            "error": f"HTTP {response.status_code}",
                        }
                        logger.error(f"Factory reset cleanup failed for {service_name}: {response.status_code}")

                except Exception as e:
                    result["microservices"][service_name] = {
                        "status": "error",
                        "error": str(e),
                    }
                    logger.error(f"Factory reset cleanup error for {service_name}: {str(e)}")

        jobs_removed = result["orchestrator"]["jobs_removed"]
        logger.warning(f"Factory reset CONCLUIDO: orchestrator ({jobs_removed} jobs) + all microservices")
        return result

    except Exception as e:
        logger.error(f"Factory reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer factory reset: {str(e)}")