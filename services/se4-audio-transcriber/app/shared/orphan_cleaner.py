"""
Sistema de limpeza de jobs órfãos e gerenciamento de Dead Letter Queue.
Implementa resiliência automática e recuperação de falhas.
"""
import asyncio
from datetime import datetime, timedelta
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

from typing import List, Dict, Any
from celery import Celery

from ..domain.interfaces import IJobStore
from ..domain.models import Job, JobStatus
from common.log_utils import get_logger

logger = get_logger(__name__)

class OrphanJobCleaner:
    """
    Limpa jobs órfãos automaticamente.
    
    Jobs órfãos são aqueles que:
    - Estão em PROCESSING há muito tempo (> timeout)
    - Estão em QUEUED mas nunca foram processados
    - Tem worker que morreu durante processamento
    """
    
    def __init__(
        self,
        job_store: IJobStore,
        processing_timeout_minutes: int = 10,
        queued_timeout_minutes: int = 30
    ):
        """
        Args:
            job_store: Store de jobs
            processing_timeout_minutes: Timeout para jobs em PROCESSING
            queued_timeout_minutes: Timeout para jobs em QUEUED
        """
        self.job_store = job_store
        self.processing_timeout = timedelta(minutes=processing_timeout_minutes)
        self.queued_timeout = timedelta(minutes=queued_timeout_minutes)
    
    async def cleanup_orphans(self) -> Dict[str, Any]:
        """
        Executa limpeza de jobs órfãos.
        
        Returns:
            Dict com estatísticas da limpeza
        """
        logger.info("🧹 Iniciando limpeza de jobs órfãos...")
        
        stats = {
            "checked": 0,
            "orphans_found": 0,
            "requeued": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            # Busca jobs em PROCESSING
            processing_jobs = self.job_store.list_jobs(status=JobStatus.PROCESSING)
            stats["checked"] += len(processing_jobs)
            
            for job in processing_jobs:
                try:
                    if self._is_orphan_processing(job):
                        stats["orphans_found"] += 1
                        await self._handle_orphan_job(job, stats)
                except Exception as e:
                    logger.error(f"Erro ao processar job órfão {job.id}: {e}")
                    stats["errors"].append(f"{job.id}: {str(e)}")
            
            # Busca jobs em QUEUED muito antigos
            queued_jobs = self.job_store.list_jobs(status=JobStatus.QUEUED)
            stats["checked"] += len(queued_jobs)
            
            for job in queued_jobs:
                try:
                    if self._is_orphan_queued(job):
                        stats["orphans_found"] += 1
                        await self._handle_stale_queued_job(job, stats)
                except Exception as e:
                    logger.error(f"Erro ao processar job enfileirado órfão {job.id}: {e}")
                    stats["errors"].append(f"{job.id}: {str(e)}")
            
            logger.info(
                f"✅ Limpeza concluída: {stats['orphans_found']} órfãos encontrados, "
                f"{stats['requeued']} reenfileirados, {stats['failed']} falhados"
            )
            
        except Exception as e:
            logger.error(f"❌ Erro durante limpeza de órfãos: {e}")
            stats["errors"].append(f"cleanup_error: {str(e)}")
        
        return stats
    
    def _is_orphan_processing(self, job: Job) -> bool:
        """Verifica se job em PROCESSING é órfão"""
        if not job.started_at:
            # Job em PROCESSING sem started_at é definitivamente órfão
            return True
        
        age = now_brazil() - job.started_at
        return age > self.processing_timeout
    
    def _is_orphan_queued(self, job: Job) -> bool:
        """Verifica se job em QUEUED é órfão"""
        age = now_brazil() - job.created_at
        return age > self.queued_timeout
    
    async def _handle_orphan_job(self, job: Job, stats: Dict) -> None:
        """
        Trata job órfão em PROCESSING.
        
        Estratégia:
        - Se retry_count < max_retries: reenfileira
        - Senão: marca como FAILED
        """
        retry_count = getattr(job, 'retry_count', 0)
        max_retries = 2
        
        if retry_count < max_retries:
            # Reenfileira job
            job.status = JobStatus.QUEUED
            job.retry_count = retry_count + 1
            job.error_message = f"Job órfão detectado e reenfileirado (tentativa {retry_count + 1})"
            job.progress = 0.0
            job.started_at = None
            
            self.job_store.update_job(job)
            stats["requeued"] += 1
            
            logger.warning(f"♻️ Job órfão {job.id} reenfileirado (tentativa {retry_count + 1})")
        else:
            # Excedeu retries, marca como falho
            job.status = JobStatus.FAILED
            job.error_message = f"Job órfão após {retry_count} tentativas. Possível crash de worker ou timeout."
            job.progress = 0.0
            
            self.job_store.update_job(job)
            stats["failed"] += 1
            
            logger.error(f"❌ Job órfão {job.id} marcado como FAILED após {retry_count} tentativas")
    
    async def _handle_stale_queued_job(self, job: Job, stats: Dict) -> None:
        """Trata job muito antigo em QUEUED"""
        age = now_brazil() - job.created_at
        
        job.status = JobStatus.FAILED
        job.error_message = f"Job permaneceu em fila por {age} sem ser processado. Possível problema no worker."
        job.progress = 0.0
        
        self.job_store.update_job(job)
        stats["failed"] += 1
        
        logger.error(f"❌ Job em fila órfão {job.id} marcado como FAILED (idade: {age})")

class DeadLetterQueueManager:
    """
    Gerencia Dead Letter Queue (DLQ) para jobs que falharam permanentemente.
    """
    
    def __init__(self, job_store: IJobStore):
        self.job_store = job_store
        self.dlq_prefix = "dlq:"
    
    def send_to_dlq(self, job: Job, reason: str) -> None:
        """
        Envia job para Dead Letter Queue.
        
        Args:
            job: Job que falhou
            reason: Motivo da falha permanente
        """
        try:
            job.status = JobStatus.FAILED
            job.error_message = f"[DLQ] {reason}"
            job.dlq_at = now_brazil()
            
            # Salva com prefixo DLQ
            dlq_job_id = f"{self.dlq_prefix}{job.id}"
            
            # TODO: Implementar store separado para DLQ
            # Por enquanto, usa mesmo store com prefixo
            self.job_store.save_job(job)
            
            logger.warning(f"📪 Job {job.id} enviado para DLQ: {reason}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar job {job.id} para DLQ: {e}")
    
    def list_dlq_jobs(self, limit: int = 100) -> List[Job]:
        """
        Lista jobs na Dead Letter Queue.
        
        Args:
            limit: Número máximo de jobs a retornar
        
        Returns:
            Lista de jobs na DLQ
        """
        try:
            # TODO: Implementar busca específica de DLQ
            failed_jobs = self.job_store.list_jobs(status=JobStatus.FAILED)
            return failed_jobs[:limit]
        except Exception as e:
            logger.error(f"❌ Erro ao listar DLQ: {e}")
            return []
    
    def retry_dlq_job(self, job_id: str) -> bool:
        """
        Retenta processar job da DLQ.
        
        Args:
            job_id: ID do job na DLQ
        
        Returns:
            True se job foi reenfileirado
        """
        try:
            job = self.job_store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} não encontrado na DLQ")
                return False
            
            # Reseta job para QUEUED
            job.status = JobStatus.QUEUED
            job.error_message = None
            job.retry_count = getattr(job, 'retry_count', 0) + 1
            job.progress = 0.0
            
            self.job_store.update_job(job)
            
            logger.info(f"♻️ Job {job_id} da DLQ reenfileirado manualmente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao retentar job {job_id} da DLQ: {e}")
            return False

async def run_orphan_cleanup_loop(
    job_store: IJobStore,
    interval_minutes: int = 5,
    celery_app: Celery = None
):
    """
    Loop contínuo de limpeza de órfãos (para rodar como background task).
    
    Args:
        job_store: Store de jobs
        interval_minutes: Intervalo entre limpezas
        celery_app: App Celery (opcional, para agendar com Beat)
    """
    cleaner = OrphanJobCleaner(job_store)
    
    logger.info(f"🧹 Iniciando loop de limpeza de órfãos (intervalo: {interval_minutes}min)")
    
    while True:
        try:
            stats = await cleaner.cleanup_orphans()
            
            # Log estatísticas
            if stats["orphans_found"] > 0:
                logger.warning(
                    f"⚠️ Órfãos detectados: {stats['orphans_found']} "
                    f"(reenfileirados: {stats['requeued']}, falhados: {stats['failed']})"
                )
            
        except Exception as e:
            logger.error(f"❌ Erro no loop de limpeza de órfãos: {e}")
        
        # Aguarda próxima iteração
        await asyncio.sleep(interval_minutes * 60)

# Alias para compatibilidade com imports antigos
OrphanCleaner = OrphanJobCleaner
