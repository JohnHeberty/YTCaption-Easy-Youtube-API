import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from app.api.schemas import (
    AdminCleanupResponse,
    AdminOrphanCleanupResponse,
    AdminStatsResponse,
    QueueInfoResponse,
)
from app.core.config import get_settings
from app.infrastructure.dependencies import get_job_store_override
from app.infrastructure.redis_store import RedisJobStore

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin", tags=["Admin"])


async def _perform_basic_cleanup(store: RedisJobStore):
    try:
        report = {"jobs_removed": 0, "files_deleted": 0, "space_freed_mb": 0.0, "errors": []}
        logger.info("🧹 Iniciando limpeza básica (jobs expirados)...")

        try:
            keys = store.redis.keys("transcription_job:*")
            now = now_brazil()
            expired_count = 0
            for key in keys:
                job_data = store.redis.get(key)
                if job_data:
                    import json
                    try:
                        job = json.loads(job_data)
                        created_at = datetime.fromisoformat(job.get("created_at", ""))
                        if (now - created_at) > timedelta(hours=24):
                            store.redis.delete(key)
                            expired_count += 1
                    except (ValueError, TypeError, AttributeError, KeyError) as err:
                        logger.debug(f"Invalid job data in {key}: {err}")
                        pass
            report["jobs_removed"] = expired_count
            logger.info(f"🗑️  Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")

        for dir_name, dir_key in [("uploads", "upload_dir"), ("transcriptions", "transcription_dir"), ("temp", "temp_dir")]:
            dir_path = Path(settings.get(dir_key, f'./{dir_name}'))
            if dir_path.exists():
                deleted_count = 0
                for file_path in dir_path.iterdir():
                    if not file_path.is_file():
                        continue
                    try:
                        age = now_brazil() - datetime.fromtimestamp(file_path.stat().st_mtime)
                        if age > timedelta(hours=24):
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            await asyncio.to_thread(file_path.unlink)
                            deleted_count += 1
                            report["space_freed_mb"] += size_mb
                    except Exception as e:
                        logger.error(f"❌ Erro ao remover {file_path.name}: {e}")
                        report["errors"].append(f"{dir_name}/{file_path.name}: {str(e)}")
                report["files_deleted"] += deleted_count
                if deleted_count > 0:
                    logger.info(f"🗑️  {dir_name.capitalize()}: {deleted_count} arquivos órfãos removidos")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        logger.info(f"✓ Limpeza básica: {report['jobs_removed']} jobs + {report['files_deleted']} arquivos ({report['space_freed_mb']}MB)")
        return report
    except Exception as e:
        logger.error(f"❌ ERRO na limpeza básica: {e}")
        return {"error": str(e)}


async def _perform_cleanup(store: RedisJobStore, purge_celery_queue: bool = False):
    try:
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "models_deleted": 0,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": []
        }

        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")

        try:
            redis_url = store.redis.connection_pool.connection_kwargs.get('host') or 'localhost'
            redis_port = store.redis.connection_pool.connection_kwargs.get('port') or 6379
            redis_db = store.redis.connection_pool.connection_kwargs.get('db') or 0

            logger.warning(f"🔥 Executando FLUSHDB no Redis {redis_url}:{redis_port} DB={redis_db}")

            keys_before = store.redis.keys("transcription_job:*")
            report["jobs_removed"] = len(keys_before)

            store.redis.flushdb()
            report["redis_flushed"] = True

            logger.info(f"✅ Redis FLUSHDB executado: {len(keys_before)} jobs + todas as outras keys removidas")

        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis FLUSHDB: {str(e)}")

        if purge_celery_queue:
            try:
                logger.warning("🔥 Limpando fila Celery 'audio_transcriber_queue'...")

                redis_celery = store.redis

                queue_keys = [
                    "audio_transcriber_queue",
                    "audio_transcription_queue",
                    "celery",
                    "_kombu.binding.audio_transcriber_queue",
                    "_kombu.binding.audio_transcription_queue",
                    "_kombu.binding.celery",
                    "unacked",
                    "unacked_index",
                ]

                tasks_purged = 0
                for queue_key in queue_keys:
                    try:
                        queue_len = redis_celery.llen(queue_key)
                        if queue_len > 0:
                            logger.info(f"   Fila '{queue_key}': {queue_len} tasks")
                            tasks_purged += queue_len
                    except Exception as err:
                        logger.debug(f"Queue {queue_key} not a list: {err}")
                        pass

                    deleted = redis_celery.delete(queue_key)
                    if deleted:
                        logger.info(f"   ✓ Fila '{queue_key}' removida")

                celery_result_keys = redis_celery.keys("celery-task-meta-*")
                if celery_result_keys:
                    redis_celery.delete(*celery_result_keys)
                    logger.info(f"   ✓ {len(celery_result_keys)} resultados Celery removidos")

                report["celery_queue_purged"] = True
                report["celery_tasks_purged"] = tasks_purged
                logger.warning(f"🔥 Fila Celery purgada: {tasks_purged} tasks removidas")

            except Exception as e:
                logger.error(f"❌ Erro ao limpar fila Celery: {e}")
                report["errors"].append(f"Celery: {str(e)}")
        else:
            logger.info("⏭️  Fila Celery NÃO será limpa (purge_celery_queue=false)")

        upload_dir = Path(settings.get('upload_dir', './data/uploads'))
        if upload_dir.exists():
            deleted_count = 0
            for file_path in upload_dir.iterdir():
                if not file_path.is_file():
                    continue

                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover upload {file_path.name}: {e}")
                    report["errors"].append(f"Upload/{file_path.name}: {str(e)}")

            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Uploads: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Uploads: nenhum arquivo encontrado")

        transcription_dir = Path(settings.get('transcription_dir', './data/transcriptions'))
        if transcription_dir.exists():
            deleted_count = 0
            for file_path in transcription_dir.iterdir():
                if not file_path.is_file():
                    continue

                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover transcrição {file_path.name}: {e}")
                    report["errors"].append(f"Transcription/{file_path.name}: {str(e)}")

            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Transcriptions: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Transcriptions: nenhum arquivo encontrado")

        temp_dir = Path(settings.get('temp_dir', './data/temp'))
        if temp_dir.exists():
            deleted_count = 0
            for file_path in temp_dir.iterdir():
                if not file_path.is_file():
                    continue

                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover temp {file_path.name}: {e}")
                    report["errors"].append(f"Temp/{file_path.name}: {str(e)}")

            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Temp: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Temp: nenhum arquivo encontrado")

        models_dir = Path(settings.get('model_dir', './models'))
        if models_dir.exists():
            deleted_count = 0
            for file_path in models_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                    report["models_deleted"] += 1
                except Exception as e:
                    logger.error(f"❌ Erro ao remover modelo {file_path.name}: {e}")
                    report["errors"].append(f"Models/{file_path.name}: {str(e)}")

            if deleted_count > 0:
                logger.warning(f"🗑️  Models: {deleted_count} arquivos de modelo removidos ({size_mb:.2f}MB)")
            else:
                logger.info("✓ Models: nenhum modelo encontrado")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)

        try:
            keys_after = store.redis.keys("transcription_job:*")
            if keys_after:
                logger.warning(f"⚠️ {len(keys_after)} jobs foram salvos DURANTE a limpeza! Executando FLUSHDB novamente...")
                store.redis.flushdb()
                report["jobs_removed"] += len(keys_after)
                logger.info(f"✅ SEGUNDO FLUSHDB executado: {len(keys_after)} jobs adicionais removidos")
            else:
                logger.info("✓ Nenhum job novo detectado após limpeza")

        except Exception as e:
            logger.error(f"❌ Erro no segundo FLUSHDB: {e}")
            report["errors"].append(f"Segundo FLUSHDB: {str(e)}")

        report["message"] = (
            f"🔥 LIMPEZA TOTAL CONCLUÍDA: "
            f"{report['jobs_removed']} jobs do Redis + "
            f"{report['files_deleted']} arquivos + "
            f"{report['models_deleted']} modelos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )

        if report["errors"]:
            report["message"] += f" ⚠️ com {len(report['errors'])} erros"

        logger.warning(report["message"])
        return report

    except Exception as e:
        logger.error(f"❌ Erro na limpeza total: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0, "models_deleted": 0}


@router.post(
    "/cleanup",
    summary="Manual cleanup",
    description=(
        "Executa limpeza administrativa do serviço. Use `deep=true` para limpeza total "
        "(factory reset de Redis, arquivos temporários e modelos locais) e "
        "`purge_celery_queue=true` para remover também tasks pendentes da fila do Celery."
    ),
    response_model=AdminCleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def manual_cleanup(
    deep: bool = Query(
        False,
        description="Quando true, executa limpeza profunda com FLUSHDB, remoção de artefatos e modelos locais.",
        examples=[False, True],
    ),
    purge_celery_queue: bool = Query(
        False,
        description="Quando true, remove também tasks pendentes e resultados armazenados do Celery.",
        examples=[False, True],
    ),
    job_store: RedisJobStore = Depends(get_job_store_override),
):
    """Perform system cleanup: basic (expired jobs only) or total (factory reset)."""
    cleanup_type = "TOTAL" if deep else "básica"
    logger.warning(f"🔥 Iniciando limpeza {cleanup_type} SÍNCRONA (purge_celery={purge_celery_queue})")

    try:
        if deep:
            result = await _perform_cleanup(job_store, purge_celery_queue)
        else:
            result = await _perform_basic_cleanup(job_store)

        logger.info(f"✅ Limpeza {cleanup_type} CONCLUÍDA com sucesso")
        return result

    except Exception as e:
        logger.error(f"❌ ERRO na limpeza {cleanup_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


@router.get(
    "/stats",
    summary="Get stats",
    description="Retorna estatísticas agregadas do Redis e métricas de cache/artefatos locais do serviço.",
    response_model=AdminStatsResponse,
)
async def get_stats(job_store: RedisJobStore = Depends(get_job_store_override)):
    """Retrieve transcription service statistics including job counts and disk usage."""
    stats = job_store.get_stats()

    upload_path = Path(settings.get('upload_dir', './data/uploads'))
    transcription_path = Path(settings.get('transcription_dir', './data/transcriptions'))

    total_files = 0
    total_size = 0

    for path in [upload_path, transcription_path]:
        if path.exists():
            files = list(path.iterdir())
            total_files += len(files)
            total_size += sum(f.stat().st_size for f in files if f.is_file())

    stats["cache"] = {
        "files_count": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }

    return stats


@router.get(
    "/queue",
    summary="Get queue info",
    description="Inspeciona a fila do Celery e retorna estado resumido de processamento assíncrono.",
    response_model=QueueInfoResponse,
    responses={500: {"description": "Internal server error"}},
)
async def get_queue_info_endpoint(job_store: RedisJobStore = Depends(get_job_store_override)):
    """Retrieve Celery queue information for the transcription service."""
    try:
        queue_info = await job_store.get_queue_info()

        return {
            "status": "success",
            "queue": queue_info
        }

    except Exception as e:
        logger.error(f"Error getting queue info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue info: {str(e)}")


@router.post(
    "/cleanup-orphans",
    summary="Cleanup orphan jobs",
    description="Procura jobs órfãos e remove artefatos inconsistentes gerados por execuções interrompidas.",
    response_model=AdminOrphanCleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def cleanup_orphan_jobs_endpoint(job_store: RedisJobStore = Depends(get_job_store_override)):
    """Clean up orphaned transcription jobs using the OrphanJobCleaner."""
    try:
        from app.shared.orphan_cleaner import OrphanJobCleaner

        cleaner = OrphanJobCleaner(job_store)
        stats = await cleaner.cleanup_orphans()

        return JSONResponse(content={
            "success": True,
            "stats": stats,
            "timestamp": now_brazil().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Erro na limpeza de órfãos: {e}")
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )