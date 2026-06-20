"""Admin cleanup service — SRP: orquestra limpeza do sistema (básica e profunda)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)


def _admin_default_now() -> datetime:
    return now_brazil()


class AdminCleanupService:
    """Serviço dedicado para operações de limpeza administrativa."""

    def __init__(self, settings: dict[str, Any], time_fn: Callable[[], datetime] | None = None) -> None:
        self._settings = settings
        self._time_fn = time_fn or _admin_default_now

    async def basic_cleanup(self, redis_client: Any) -> dict[str, Any]:
        """Limpeza básica: remove jobs expirados do Redis e arquivos órfãos (>24h)."""
        report = {"jobs_removed": 0, "files_deleted": 0, "space_freed_mb": 0.0, "errors": []}

        logger.info("🧹 Iniciando limpeza básica (jobs expirados)...")

        try:
            keys = redis_client.keys("transcription_job:*")
            now = self._time_fn()
            expired_count = 0
            for key in keys:
                job_data = redis_client.get(key)
                if job_data:
                    try:
                        import json as _json

                        job = _json.loads(job_data)
                        created_at = datetime.fromisoformat(
                            job.get("created_at", "")
                        )
                        if (now - created_at) > timedelta(hours=24):
                            redis_client.delete(key)
                            expired_count += 1
                    except (ValueError, TypeError, AttributeError, KeyError):
                        pass

            report["jobs_removed"] = expired_count
            logger.info(f"🗑️  Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")

        for dir_name, dir_key in [
            ("uploads", "upload_dir"),
            ("transcriptions", "transcription_dir"),
            ("temp", "temp_dir"),
        ]:
            deleted = self._cleanup_directory(
                Path(self._settings.get(dir_key, f"./{dir_name}")),
                max_age_hours=24,
                dir_label=dir_name.capitalize(),
            )
            report["files_deleted"] += deleted[0]
            report["space_freed_mb"] += deleted[1]

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        logger.info(
            f"✓ Limpeza básica: {report['jobs_removed']} jobs + "
            f"{report['files_deleted']} arquivos ({report['space_freed_mb']}MB)"
        )
        return report

    async def deep_cleanup(
        self, redis_client: Any, purge_celery_queue: bool = False
    ) -> dict[str, Any]:
        """Limpeza profunda (factory reset): flush Redis, limpa tudo."""
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "models_deleted": 0,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": [],
        }

        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")

        try:
            redis_url = (
                redis_client.connection_pool.connection_kwargs.get("host") or "localhost"
            )
            redis_port = (
                redis_client.connection_pool.connection_kwargs.get("port") or 6379
            )
            redis_db = (
                redis_client.connection_pool.connection_kwargs.get("db") or 0
            )

            logger.warning(
                f"🔥 Executando FLUSHDB no Redis {redis_url}:{redis_port} DB={redis_db}"
            )

            keys_before = redis_client.keys("transcription_job:*")
            report["jobs_removed"] = len(keys_before)

            redis_client.flushdb()
            report["redis_flushed"] = True

            logger.info(
                f"✅ Redis FLUSHDB executado: {len(keys_before)} jobs + "
                f"todas as outras keys removidas"
            )
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis FLUSHDB: {str(e)}")

        if purge_celery_queue:
            celery_report = await self._purge_celery_queue(redis_client)
            report.update(celery_report)
        else:
            logger.info("⏭️  Fila Celery NÃO será limpa (purge_celery_queue=false)")

        upload_dir = Path(self._settings.get("upload_dir", "./data/uploads"))
        deleted, freed_mb = self._delete_all_files(upload_dir, "Uploads")
        report["files_deleted"] += deleted
        report["space_freed_mb"] += freed_mb

        transcription_dir = Path(
            self._settings.get("transcription_dir", "./data/transcriptions")
        )
        deleted, freed_mb = self._delete_all_files(transcription_dir, "Transcriptions")
        report["files_deleted"] += deleted
        report["space_freed_mb"] += freed_mb

        temp_dir = Path(self._settings.get("temp_dir", "./data/temp"))
        deleted, freed_mb = self._delete_all_files(temp_dir, "Temp")
        report["files_deleted"] += deleted
        report["space_freed_mb"] += freed_mb

        models_dir = Path(self._settings.get("model_dir", "./models"))
        if models_dir.exists():
            md_count, md_size = 0, 0.0
            for file_path in models_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    md_count += 1
                    md_size += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover modelo {file_path.name}: {e}")
                    report["errors"].append(
                        f"Models/{file_path.name}: {str(e)}"
                    )

            if md_count > 0:
                logger.warning(f"🗑️  Models: {md_count} arquivos de modelo removidos")
            else:
                logger.info("✓ Models: nenhum modelo encontrado")

            report["models_deleted"] = md_count
            report["space_freed_mb"] += md_size

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)

        try:
            keys_after = redis_client.keys("transcription_job:*")
            if keys_after:
                logger.warning(
                    f"⚠️ {len(keys_after)} jobs salvos DURANTE a limpeza! "
                    f"Executando FLUSHDB novamente..."
                )
                redis_client.flushdb()
                report["jobs_removed"] += len(keys_after)
            else:
                logger.info("✓ Nenhum job novo detectado após limpeza")
        except Exception as e:
            logger.error(f"❌ Erro no segundo FLUSHDB: {e}")
            report["errors"].append(f"Segundo FLUSHDB: {str(e)}")

        message = (
            f"🔥 LIMPEZA TOTAL CONCLUÍDA: "
            f"{report['jobs_removed']} jobs do Redis + "
            f"{report['files_deleted']} arquivos + "
            f"{report['models_deleted']} modelos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )

        if report["errors"]:
            message += f" ⚠️ com {len(report['errors'])} erros"

        logger.warning(message)
        return report

    def _cleanup_directory(
        self, dir_path: Path, max_age_hours: int = 24, dir_label: str = ""
    ) -> tuple[int, float]:
        """Remove arquivos com idade > max_age_hours. Retorna (count, freed_mb)."""
        if not dir_path.exists():
            return (0, 0.0)

        deleted_count = 0
        freed_mb = 0.0
        now = self._time_fn()

        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue
            try:
                age = now - datetime.fromtimestamp(file_path.stat().st_mtime)
                if age > timedelta(hours=max_age_hours):
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    file_path.unlink()
                    deleted_count += 1
                    freed_mb += size_mb
            except Exception:
                pass

        if deleted_count > 0:
            logger.info(f"🗑️  {dir_label}: {deleted_count} arquivos órfãos removidos")

        return (deleted_count, freed_mb)

    def _delete_all_files(
        self, dir_path: Path, label: str = ""
    ) -> tuple[int, float]:
        """Remove todos os arquivos de um diretório. Retorna (count, freed_mb)."""
        if not dir_path.exists():
            return (0, 0.0)

        deleted_count = 0
        freed_mb = 0.0

        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                file_path.unlink()
                deleted_count += 1
                freed_mb += size_mb
            except Exception as e:
                logger.error(f"❌ Erro ao remover {label} {file_path.name}: {e}")

        if deleted_count > 0:
            logger.info(f"🗑️  {label}: {deleted_count} arquivos removidos")
        else:
            logger.info(f"✓ {label}: nenhum arquivo encontrado")

        return (deleted_count, freed_mb)

    async def _purge_celery_queue(self, redis_client: Any) -> dict[str, Any]:
        """Remove tasks e resultados da fila Celery."""
        report = {
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
        }

        try:
            logger.warning("🔥 Limpando fila Celery 'audio_transcriber_queue'...")

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
                    queue_len = redis_client.llen(queue_key)
                    if queue_len > 0:
                        logger.info(f"   Fila '{queue_key}': {queue_len} tasks")
                        tasks_purged += queue_len
                except Exception:
                    pass

                deleted = redis_client.delete(queue_key)
                if deleted:
                    logger.info(f"   ✓ Fila '{queue_key}' removida")

            celery_result_keys = redis_client.keys("celery-task-meta-*")
            if celery_result_keys:
                redis_client.delete(*celery_result_keys)
                logger.info(
                    f"   ✓ {len(celery_result_keys)} resultados Celery removidos"
                )

            report["celery_queue_purged"] = True
            report["celery_tasks_purged"] = tasks_purged
            logger.warning(f"🔥 Fila Celery purgada: {tasks_purged} tasks removidas")

        except Exception as e:
            logger.error(f"❌ Erro ao limpar fila Celery: {e}")

        return report
