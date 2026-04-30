"""
Serviço de limpeza do sistema.

Responsável por limpar jobs expirados e arquivos órfãos.
"""
import asyncio
import shutil
from pathlib import Path
from typing import List, Dict, Any
from datetime import timedelta

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from common.log_utils import get_logger

from ..core.config import get_settings
from ..domain.interfaces import IJobStore

logger = get_logger(__name__)


class CleanupService:
    """Serviço para limpeza do sistema."""

    def __init__(self, job_store: IJobStore):
        self.job_store = job_store
        self.settings = get_settings()
        self.upload_dir = Path(self.settings.get('upload_dir', './uploads'))
        self.processed_dir = Path(self.settings.get('processed_dir', './processed'))
        self.temp_dir = Path(self.settings.get('temp_dir', './temp'))

    async def perform_basic_cleanup(self) -> Dict[str, Any]:
        """
        Executa limpeza básica: jobs expirados e arquivos órfãos.

        Returns:
            Relatório da limpeza
        """
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "errors": []
        }

        logger.info("🧹 Iniciando limpeza básica...")

        # Limpa jobs expirados
        try:
            removed = await self._cleanup_expired_jobs()
            report["jobs_removed"] = removed
            logger.info(f"🗑️ Jobs expirados removidos: {removed}")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar jobs: {e}")
            report["errors"].append(f"jobs: {str(e)}")

        # Limpa arquivos órfãos
        try:
            for dir_path in [self.upload_dir, self.processed_dir, self.temp_dir]:
                if not dir_path.exists():
                    continue

                deleted, freed = await self._cleanup_orphaned_files(dir_path)
                report["files_deleted"] += deleted
                report["space_freed_mb"] += freed

        except Exception as e:
            logger.error(f"❌ Erro ao limpar arquivos: {e}")
            report["errors"].append(f"files: {str(e)}")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        logger.info(
            f"✅ Limpeza básica: {report['jobs_removed']} jobs + "
            f"{report['files_deleted']} arquivos ({report['space_freed_mb']}MB)"
        )

        return report

    async def perform_deep_cleanup(self) -> Dict[str, Any]:
        """
        Executa limpeza profunda: TUDO é removido.

        Returns:
            Relatório da limpeza
        """
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "errors": []
        }

        logger.warning("🔥 INICIANDO LIMPEZA PROFUNDA - TUDO SERÁ REMOVIDO!")

        # 1. Flush Redis
        try:
            keys_before = self.job_store.redis.keys("audio_job:*")
            report["jobs_removed"] = len(keys_before)
            self.job_store.redis.flushdb()
            report["redis_flushed"] = True
            logger.info(f"✅ Redis FLUSHDB: {len(keys_before)} jobs removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"redis: {str(e)}")

        # 2. Limpa todos os diretórios
        for dir_name, dir_path in [
            ("uploads", self.upload_dir),
            ("processed", self.processed_dir),
            ("temp", self.temp_dir)
        ]:
            try:
                if not dir_path.exists():
                    continue

                deleted, freed = await self._cleanup_all_files(dir_path)
                report["files_deleted"] += deleted
                report["space_freed_mb"] += freed
                logger.info(f"🗑️ {dir_name}: {deleted} arquivos removidos")

            except Exception as e:
                logger.error(f"❌ Erro ao limpar {dir_name}: {e}")
                report["errors"].append(f"{dir_name}: {str(e)}")

        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        report["message"] = (
            f"🔥 LIMPEZA PROFUNDA: {report['jobs_removed']} jobs + "
            f"{report['files_deleted']} arquivos ({report['space_freed_mb']}MB)"
        )

        if report["errors"]:
            report["message"] += f" ⚠️ com {len(report['errors'])} erros"

        logger.warning(report["message"])
        return report

    async def _cleanup_expired_jobs(self) -> int:
        """Remove jobs expirados do Redis."""
        return await self.job_store.cleanup_expired()

    async def _cleanup_orphaned_files(self, dir_path: Path) -> tuple:
        """
        Remove arquivos órfãos (mais de 24h).

        Returns:
            (quantidade_deletada, espaço_liberado_mb)
        """
        deleted = 0
        space_freed = 0.0
        max_age = timedelta(hours=24)

        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue

            try:
                age = now_brazil() - datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=now_brazil().tzinfo
                )

                if age > max_age:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted += 1
                    space_freed += size_mb

            except Exception as e:
                logger.warning(f"Erro ao remover {file_path}: {e}")

        return deleted, space_freed

    async def _cleanup_all_files(self, dir_path: Path) -> tuple:
        """
        Remove TODOS os arquivos do diretório.

        Returns:
            (quantidade_deletada, espaço_liberado_mb)
        """
        deleted = 0
        space_freed = 0.0

        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue

            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                await asyncio.to_thread(file_path.unlink)
                deleted += 1
                space_freed += size_mb

            except Exception as e:
                logger.warning(f"Erro ao remover {file_path}: {e}")

        return deleted, space_freed
