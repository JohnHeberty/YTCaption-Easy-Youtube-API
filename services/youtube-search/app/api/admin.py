"""
Admin API endpoints for YouTube Search service.

This module contains administrative endpoints:
- Cleanup (basic and total)
- Statistics
- Queue management
- Metrics
"""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.config import get_settings
from app.domain.models import CleanupResponse, QueueStatsResponse, SearchServiceStatsResponse
from app.infrastructure.redis_store import YouTubeSearchJobStore as RedisJobStore
from app.infrastructure.dependencies import get_job_store_override
from app.infrastructure.celery_config import celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

settings = get_settings()


@router.post(
    "/cleanup",
    summary="Limpeza manual",
    description=(
        "Executa limpeza administrativa do serviço. Use `deep=true` para limpeza total "
        "(factory reset do Redis) e `purge_celery_queue=true` para também remover tasks "
        "pendentes na fila do Celery."
    ),
    response_model=CleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def manual_cleanup(
    deep: bool = Query(
        default=False,
        description="Quando true, remove todos os jobs do Redis via FLUSHDB.",
        examples=[False, True],
    ),
    purge_celery_queue: bool = Query(
        default=False,
        description="Quando true, revoga tasks ativas/agendadas e limpa a fila do Celery.",
        examples=[False, True],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
):
    """Executa limpeza do sistema, básica ou total, com opção de purge da fila Celery."""
    cleanup_type = "TOTAL" if deep else "basic"
    logger.warning(
        f"🔥 Starting {cleanup_type} cleanup (purge_celery={purge_celery_queue})"
    )

    try:
        if deep:
            result = await _perform_total_cleanup(store, purge_celery_queue)
        else:
            result = await _perform_basic_cleanup(store)

        logger.info(f"✅ {cleanup_type} cleanup completed successfully")
        return result

    except Exception as exc:
        logger.error(f"❌ ERROR in {cleanup_type} cleanup: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error during cleanup: {str(exc)}"
        ) from exc

async def _perform_basic_cleanup(store: RedisJobStore):
    """Execute basic cleanup: remove only expired jobs."""
    report = {"jobs_removed": 0, "errors": []}

    try:
        expired_count = await store.cleanup_expired()
        report["jobs_removed"] = expired_count
        report["message"] = (
            f"🧹 Basic cleanup completed: {expired_count} expired jobs removed"
        )

        logger.info(report["message"])
        return report

    except Exception as exc:
        logger.error(f"❌ Error in basic cleanup: {exc}")
        report["errors"].append(str(exc))
        return report

async def _perform_total_cleanup(store: RedisJobStore, purge_celery_queue: bool = False):
    """Execute total cleanup: factory reset of the system."""
    from redis import Redis

    report = {
        "jobs_removed": 0,
        "redis_flushed": False,
        "celery_queue_purged": False,
        "celery_tasks_purged": 0,
        "errors": [],
    }

    try:
        logger.warning("🔥 STARTING TOTAL SYSTEM CLEANUP - EVERYTHING WILL BE REMOVED!")

        # FLUSHDB on Redis
        await _cleanup_redis(store, report)

        # Clean Celery queue if requested
        if purge_celery_queue:
            await _cleanup_celery(report)

        report["message"] = (
            f"🔥 TOTAL CLEANUP COMPLETED: " f"{report['jobs_removed']} Redis jobs removed"
        )

        if report["errors"]:
            report["message"] += f" ⚠️ with {len(report['errors'])} errors"

        logger.warning(report["message"])
        return report

    except Exception as exc:
        logger.error(f"❌ Error in total cleanup: {exc}")
        report["errors"].append(str(exc))
        return report

async def _cleanup_redis(store: RedisJobStore, report: dict) -> None:
    """Clean up Redis data."""
    from redis import Redis

    redis_url = settings["redis_url"]

    try:
        parsed = urlparse(redis_url)
        redis_host = parsed.hostname or "localhost"
        redis_port = parsed.port or 6379
        redis_db = int(parsed.path.strip("/")) if parsed.path else 0

        logger.warning(f"🔥 Executing FLUSHDB on Redis {redis_host}:{redis_port} DB={redis_db}")

        redis = Redis(
            host=redis_host, port=redis_port, db=redis_db, decode_responses=True
        )

        keys_before = redis.keys("youtube_search:job:*")
        report["jobs_removed"] = len(keys_before)

        redis.flushdb()
        report["redis_flushed"] = True

        logger.info(f"✅ Redis FLUSHDB executed: {len(keys_before)} jobs removed")

    except Exception as exc:
        logger.error(f"❌ Error cleaning Redis: {exc}")
        report["errors"].append(f"Redis FLUSHDB: {str(exc)}")

async def _cleanup_celery(report: dict) -> None:
    """Clean up Celery queue and tasks."""
    from redis import Redis

    redis_url = settings["redis_url"]

    try:
        logger.warning("🔥 Cleaning Celery queue...")

        redis_celery = Redis.from_url(redis_url)

        # Revoke active/scheduled tasks
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()

            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        task_id = task.get("id")
                        logger.warning(f"   🛑 Revoking active task: {task_id}")
                        celery_app.control.revoke(
                            task_id, terminate=True, signal="SIGKILL"
                        )

            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    for task in tasks:
                        task_id = task.get("id") or task.get("request", {}).get("id")
                        if task_id:
                            logger.warning(f"   🛑 Revoking scheduled task: {task_id}")
                            celery_app.control.revoke(task_id, terminate=True)

        except Exception as exc:
            logger.warning(f"   ⚠️ Could not revoke tasks: {exc}")

        # Queue names in Redis
        queue_keys = [
            "youtube_search_queue",
            "celery",
            "_kombu.binding.youtube_search_queue",
            "_kombu.binding.celery",
            "unacked",
            "unacked_index",
        ]

        tasks_purged = 0
        for queue_key in queue_keys:
            queue_len = redis_celery.llen(queue_key)
            if queue_len > 0:
                tasks_purged += queue_len
            redis_celery.delete(queue_key)

        celery_result_keys = redis_celery.keys("celery-task-meta-*")
        if celery_result_keys:
            redis_celery.delete(*celery_result_keys)

        report["celery_queue_purged"] = True
        report["celery_tasks_purged"] = tasks_purged
        logger.warning(f"🔥 Celery queue purged: {tasks_purged} tasks removed")

    except Exception as exc:
        logger.error(f"❌ Error cleaning Celery queue: {exc}")
        report["errors"].append(f"Celery purge: {str(exc)}")

@router.get(
    "/stats",
    summary="Obter estatisticas",
    description="Retorna estatísticas agregadas do Redis e do Celery para o serviço de busca.",
    response_model=SearchServiceStatsResponse,
)
async def get_stats(store: RedisJobStore = Depends(get_job_store_override)):
    """Retorna estatísticas do serviço de busca, incluindo Redis e Celery."""
    stats = store.get_stats()

    # Add Celery statistics
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        stats["celery"] = {
            "active_workers": len(active_tasks) if active_tasks else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values())
            if active_tasks
            else 0,
            "broker": "redis",
            "backend": "redis",
            "queue": "youtube_search_queue",
        }
    except Exception as exc:
        stats["celery"] = {"error": str(exc), "status": "unavailable"}

    return stats

@router.get(
    "/queue",
    summary="Obter estado da fila",
    description="Inspeciona workers, tasks ativas e tasks agendadas na fila do Celery.",
    response_model=QueueStatsResponse,
)
async def get_queue_stats():
    """Retorna estatísticas da fila Celery, incluindo workers e tasks."""
    try:
        inspect = celery_app.control.inspect()

        active_workers = inspect.active()
        registered = inspect.registered()
        scheduled = inspect.scheduled()

        return {
            "broker": "redis",
            "queue_name": "youtube_search_queue",
            "active_workers": len(active_workers) if active_workers else 0,
            "registered_tasks": list(registered.values())[0] if registered else [],
            "active_tasks": active_workers if active_workers else {},
            "scheduled_tasks": scheduled if scheduled else {},
            "is_running": active_workers is not None,
        }
    except Exception as exc:
        return {"error": str(exc), "is_running": False}

@router.get("/metrics", summary="Metricas Prometheus", response_class=Response)
async def prometheus_metrics(store: RedisJobStore = Depends(get_job_store_override)):
    """Expõe métricas no formato Prometheus para o serviço de busca no YouTube."""
    svc = "youtube_search"
    stats = {}
    try:
        stats = store.get_stats()
    except Exception as exc:
        logger.warning("Metrics: failed to get stats: %s", exc)

    by_status = stats.get("by_status", {})
    total = stats.get("total_jobs", 0)

    lines = [
        f"# HELP {svc}_jobs_total Jobs in Redis store by status",
        f"# TYPE {svc}_jobs_total gauge",
    ]
    for status, count in by_status.items():
        lines.append(f'{svc}_jobs_total{{status="{status}"}} {count}')
    lines += [
        f"# HELP {svc}_jobs_store_total Total jobs in Redis store",
        f"# TYPE {svc}_jobs_store_total gauge",
        f"{svc}_jobs_store_total {total}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
