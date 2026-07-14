from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

from common.job_utils import JobStatus

from app.infrastructure.dependencies import job_store, get_settings_dep
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.core.constants import BYTES_PER_MB
from app.core.config import Settings
from app.core.models import CleanupResponse, FixStuckJobsResponse, QueueInfoResponse, StatsResponse

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)


async def _cleanup_directory(
    dir_path: Path,
    report: dict[str, Any],
    *,
    max_age_hours: int | None = None,
    label: str = "Cache",
) -> None:
    """Delete files in dir_path, tracking count and space freed."""
    if not dir_path.exists():
        return
    deleted_count = 0
    for file_path in dir_path.iterdir():
        if not file_path.is_file():
            continue
        try:
            if max_age_hours is not None:
                age = now_brazil() - datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                )
                if age <= timedelta(hours=max_age_hours):
                    continue
            size_mb = file_path.stat().st_size / BYTES_PER_MB
            await asyncio.to_thread(file_path.unlink)
            deleted_count += 1
            report["space_freed_mb"] += size_mb
        except Exception as e:
            logger.error(f"❌ Erro ao remover {label.lower()} {file_path.name}: {e}")
            report["errors"].append(f"{label}/{file_path.name}: {str(e)}")
    report["files_deleted"] += deleted_count
    if deleted_count > 0:
        logger.info(f"🗑️  {label}: {deleted_count} arquivos removidos")
    else:
        logger.info(f"✓ {label}: nenhum arquivo encontrado")


async def _perform_basic_cleanup(store: VideoDownloadJobStore, settings: Settings) -> dict[str, Any]:
    from redis import Redis

    try:
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "errors": []
        }

        logger.info("🧹 Iniciando limpeza básica (jobs expirados)...")

        try:
            redis = Redis.from_url(settings.redis_url, decode_responses=True)
            keys = redis.keys("job:*")
            now = now_brazil()
            expired_count = 0

            for key in keys:
                job_data = redis.get(key)
                if job_data:
                    try:
                        job = json.loads(job_data)
                        raw_ts = job.get("created_at", "")
                        created_at = datetime.fromisoformat(raw_ts)
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        age = now - created_at

                        if age > timedelta(hours=24):
                            redis.delete(key)
                            expired_count += 1
                    except (ValueError, TypeError, AttributeError, KeyError) as err:
                        logger.debug(f"Invalid job data in {key}: {err}")
                        pass

            report["jobs_removed"] = expired_count
            logger.info(f"🗑️  Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")

        await _cleanup_directory(Path(settings.cache_dir), report, max_age_hours=24, label="Cache")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        report["message"] = f"✓ Limpeza básica concluída: {report['jobs_removed']} jobs + {report['files_deleted']} arquivos ({report['space_freed_mb']}MB)"

        logger.info(f"✓ {report['message']}")
        if report["errors"]:
            logger.warning(f"⚠️  {len(report['errors'])} erros durante limpeza")

        return report

    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na limpeza básica: {e}")
        return {"error": str(e)}


def _parse_redis_url(redis_url: str) -> tuple[str, int, int]:
    """Parse Redis URL into (host, port, db) components."""
    from urllib.parse import urlparse

    parsed = urlparse(redis_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    db = int(parsed.path.strip('/')) if parsed.path else 0
    return host, port, db


async def _flush_redis_db(
    redis_host: str, redis_port: int, redis_db: int, report: dict[str, Any]
) -> None:
    """Flush the entire Redis database, removing all jobs and keys."""
    from redis import Redis

    try:
        logger.warning(
            f"🔥 Executando FLUSHDB no Redis {redis_host}:{redis_port} DB={redis_db}"
        )
        redis = Redis(
            host=redis_host, port=redis_port, db=redis_db, decode_responses=True
        )
        keys_before = redis.keys("job:*")
        report["jobs_removed"] = len(keys_before)
        redis.flushdb()
        report["redis_flushed"] = True
        logger.info(
            f"✅ Redis FLUSHDB executado: {len(keys_before)} jobs "
            f"+ todas as outras keys removidas"
        )
    except Exception as e:
        logger.error(f"❌ Erro ao limpar Redis: {e}")
        report["errors"].append(f"Redis FLUSHDB: {str(e)}")


async def _revoke_celery_tasks() -> None:
    """Revoke active and scheduled Celery tasks."""
    try:
        from celery import current_app

        logger.warning("🔥 Revogando tasks Celery ativas e agendadas...")

        try:
            inspect = current_app.control.inspect()
            active_tasks = inspect.active()

            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        task_id = task.get('id')
                        logger.warning(f"   🛑 Revogando task ativa: {task_id}")
                        current_app.control.revoke(
                            task_id, terminate=True, signal='SIGKILL'
                        )
                logger.info(
                    f"   ✓ {sum(len(t) for t in active_tasks.values())} "
                    f"tasks ativas revogadas"
                )

            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    for task in tasks:
                        task_id = (
                            task.get('id') or task.get('request', {}).get('id')
                        )
                        if task_id:
                            logger.warning(
                                f"   🛑 Revogando task agendada: {task_id}"
                            )
                            current_app.control.revoke(task_id, terminate=True)
                logger.info(
                    f"   ✓ {sum(len(t) for t in scheduled_tasks.values())} "
                    f"tasks agendadas revogadas"
                )

        except Exception as e:
            logger.warning(f"   ⚠️ Não foi possível revogar tasks: {e}")

    except Exception as e:
        logger.error(f"❌ Erro ao revogar tasks Celery: {e}")


async def _purge_celery_queues(
    redis_url: str, report: dict[str, Any]
) -> None:
    """Delete Celery queue keys and task result keys from Redis."""
    from redis import Redis

    try:
        redis_celery = Redis.from_url(redis_url)

        queue_keys = [
            "video_downloader_queue",
            "celery",
            "_kombu.binding.video_downloader_queue",
            "_kombu.binding.celery",
            "unacked",
            "unacked_index",
        ]

        tasks_purged = 0
        for queue_key in queue_keys:
            queue_len = redis_celery.llen(queue_key)
            if queue_len > 0:
                logger.info(f"   Fila '{queue_key}': {queue_len} tasks")
                tasks_purged += queue_len

            deleted = redis_celery.delete(queue_key)
            if deleted:
                logger.info(f"   ✓ Fila '{queue_key}' removida")

        celery_result_keys = redis_celery.keys("celery-task-meta-*")
        if celery_result_keys:
            redis_celery.delete(*celery_result_keys)
            logger.info(
                f"   ✓ {len(celery_result_keys)} resultados Celery removidos"
            )

        report["celery_queue_purged"] = True
        report["celery_tasks_purged"] = tasks_purged
        logger.warning(f"🔥 Fila Celery purgada: {tasks_purged} tasks removidas")

    except Exception as e:
        logger.error(f"❌ Erro ao limpar fila Celery: {e}")
        report["errors"].append(f"Celery: {str(e)}")


async def _recheck_and_flush_redis(
    redis_host: str, redis_port: int, redis_db: int, report: dict[str, Any]
) -> None:
    """Re-check for new jobs after cleanup and flush again if needed."""
    from redis import Redis

    try:
        redis = Redis(
            host=redis_host, port=redis_port, db=redis_db, decode_responses=True
        )
        keys_after = redis.keys("job:*")
        if keys_after:
            logger.warning(
                f"⚠️ {len(keys_after)} jobs foram salvos DURANTE a limpeza! "
                f"Executando FLUSHDB novamente..."
            )
            redis.flushdb()
            report["jobs_removed"] += len(keys_after)
            logger.info(
                f"✅ SEGUNDO FLUSHDB executado: "
                f"{len(keys_after)} jobs adicionais removidos"
            )
        else:
            logger.info("✓ Nenhum job novo detectado após limpeza")
    except Exception as e:
        logger.error(f"❌ Erro no segundo FLUSHDB: {e}")
        report["errors"].append(f"Segundo FLUSHDB: {str(e)}")


async def _perform_total_cleanup(store: VideoDownloadJobStore, settings: Settings, purge_celery_queue: bool = False) -> dict[str, Any]:
    try:
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": []
        }

        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")

        redis_url = settings.redis_url
        redis_host, redis_port, redis_db = _parse_redis_url(redis_url)

        await _flush_redis_db(redis_host, redis_port, redis_db, report)

        if purge_celery_queue:
            await _revoke_celery_tasks()
            await _purge_celery_queues(redis_url, report)
        else:
            logger.info("⏭️  Fila Celery NÃO será limpa (purge_celery_queue=false)")

        await _cleanup_directory(Path(settings.cache_dir), report, label="Cache")
        await _cleanup_directory(Path("./downloads"), report, label="Downloads")
        await _cleanup_directory(Path("./data/temp"), report, label="Temp")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)

        await _recheck_and_flush_redis(redis_host, redis_port, redis_db, report)

        report["message"] = (
            f"🔥 LIMPEZA TOTAL CONCLUÍDA: "
            f"{report['jobs_removed']} jobs do Redis + "
            f"{report['files_deleted']} arquivos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )

        if report["errors"]:
            report["message"] += f" ⚠️ com {len(report['errors'])} erros"

        logger.warning(report["message"])
        return report

    except Exception as e:
        logger.error(f"❌ Erro na limpeza total: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0}


@router.post("/cleanup", summary="Manual cleanup", response_model=CleanupResponse, responses={500: {"description": "Internal server error"}})
async def manual_cleanup(
    deep: bool = Query(
        False,
        description="Quando true executa limpeza total (factory reset).",
        examples=[False, True],
    ),
    purge_celery_queue: bool = Query(
        False,
        description="Quando true, também limpa a fila/tarefas do Celery.",
        examples=[False, True],
    ),
    store: VideoDownloadJobStore = Depends(job_store),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, Any]:
    """Perform system cleanup: basic (expired jobs) or total (factory reset)."""
    cleanup_type = "TOTAL" if deep else "básica"
    logger.warning(f"🔥 Iniciando limpeza {cleanup_type} SÍNCRONA (purge_celery={purge_celery_queue})")

    try:
        if deep:
            result = await _perform_total_cleanup(store, settings, purge_celery_queue)
        else:
            result = await _perform_basic_cleanup(store, settings)

        logger.info(f"✅ Limpeza {cleanup_type} CONCLUÍDA com sucesso")
        return result

    except Exception as e:
        logger.error(f"❌ ERRO na limpeza {cleanup_type}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao fazer cleanup: {str(e)}")


@router.get("/stats", summary="Get stats", response_model=StatsResponse)
async def get_stats(
    store: VideoDownloadJobStore = Depends(job_store),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, Any]:
    """Retrieve download service statistics including Redis, cache, and Celery info."""
    from app.infrastructure.celery_config import celery_app

    stats = store.get_stats()

    cache_path = Path(settings.cache_dir)
    if cache_path.exists():
        files = list(cache_path.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        stats["cache"] = {
            "files_count": len(files),
            "total_size_mb": round(total_size / BYTES_PER_MB, 2)
        }

    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        stats["celery"] = {
            "active_workers": len(active_tasks) if active_tasks else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
            "broker": "redis",
            "backend": "redis"
        }
    except Exception as e:
        stats["celery"] = {
            "error": str(e),
            "status": "unavailable"
        }

    return stats


@router.get("/queue", summary="Get queue info", response_model=QueueInfoResponse, responses={500: {"description": "Internal server error"}})
async def get_queue_info_endpoint(store: VideoDownloadJobStore = Depends(job_store)) -> dict[str, Any]:
    """Retrieve Celery queue information for the download service."""
    try:
        queue_info = await store.get_queue_info()

        return {
            "status": "success",
            "queue": queue_info
        }

    except Exception as e:
        logger.error(f"Error getting queue info: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get queue info: {str(e)}")


@router.post("/fix-stuck-jobs", summary="Fix stuck jobs", response_model=FixStuckJobsResponse, responses={500: {"description": "Internal server error"}})
async def fix_stuck_jobs(
    max_age_minutes: int = Query(
        30,
        ge=1,
        description="Idade mínima em minutos para considerar job travado em queued.",
        examples=[30, 60],
    ),
    store: VideoDownloadJobStore = Depends(job_store),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, Any]:
    """Mark download jobs stuck in QUEUED status beyond a threshold as FAILED."""
    try:
        logger.info(f"🔍 Procurando jobs travados em QUEUED (>{max_age_minutes}min)")

        keys = store.redis.keys("job:*")
        now = now_brazil()
        fixed_count = 0

        for key in keys:
            try:
                data = store.redis.get(key)
                if not data:
                    continue

                job_dict = json.loads(data)

                if job_dict.get('status') != 'queued':
                    continue

                created_at = datetime.fromisoformat(job_dict.get('created_at', ''))
                age = now - created_at

                if age > timedelta(minutes=max_age_minutes):
                    job_dict['status'] = 'failed'
                    job_dict['error_message'] = f'Job travado em QUEUED por {age.total_seconds()/60:.1f} minutos - worker provavelmente crashou'
                    job_dict['progress'] = 0.0

                    store.redis.set(key, json.dumps(job_dict))
                    fixed_count += 1

                    logger.info(f"🔧 Job {job_dict['id']} marcado como FAILED (travado por {age.total_seconds()/60:.1f}min)")

            except Exception as job_err:
                logger.error(f"Erro ao processar job {key}: {job_err}")
                continue

        logger.info(f"✅ Fix concluído: {fixed_count} jobs corrigidos")

        return {
            "fixed_count": fixed_count,
            "max_age_minutes": max_age_minutes,
            "message": f"Corrigidos {fixed_count} jobs travados em QUEUED"
        }

    except Exception as e:
        logger.error(f"❌ Erro ao corrigir jobs travados: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
