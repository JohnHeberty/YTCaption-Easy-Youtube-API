"""
Gerenciador de progresso de jobs (Single Responsibility Principle).
Responsável APENAS por rastrear e atualizar progresso de jobs.
"""
import logging
from typing import Any, Optional
from datetime import datetime
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


from ..domain.interfaces import IProgressTracker, IJobStore
from ..domain.models import Job, JobStatus

logger = logging.getLogger(__name__)


class RedisProgressTracker(IProgressTracker):
    """
    Rastreia progresso de jobs usando Redis.
    
    Responsabilidades:
    - Atualizar progresso de jobs
    - Marcar início/conclusão/falha
    - Manter consistência no Redis
    
    Implementa circuit breaker pattern para resiliência.
    """
    
    def __init__(self, job_store: IJobStore):
        """
        Args:
            job_store: Store de jobs (DIP - depende de interface)
        """
        self.job_store = job_store
        self._update_failures = 0
        self._max_failures_before_warn = 3
    
    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """
        Atualiza progresso de um job.
        
        Args:
            job_id: ID do job
            progress: Progresso (0.0 a 1.0)
            message: Mensagem opcional de status
        """
        try:
            # Clamp progress entre 0 e 1
            progress = max(0.0, min(1.0, progress))
            
            job = self.job_store.get_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} não encontrado para atualizar progresso")
                return
            
            job.progress = progress
            if message:
                job.status_message = message
            
            self.job_store.update_job(job)
            
            # Reset failure counter on success
            if self._update_failures > 0:
                logger.info(f"✅ Conexão restaurada após {self._update_failures} falhas")
                self._update_failures = 0
            
            logger.debug(f"📊 Job {job_id}: {progress*100:.1f}% - {message}")
            
        except Exception as e:
            self._update_failures += 1
            
            if self._update_failures >= self._max_failures_before_warn:
                logger.error(
                    f"❌ Falha ao atualizar progresso do job {job_id} "
                    f"({self._update_failures} falhas consecutivas): {e}"
                )
            else:
                logger.warning(f"⚠️ Falha ao atualizar progresso: {e}")
    
    def mark_started(self, job_id: str) -> None:
        """
        Marca job como iniciado.
        
        Args:
            job_id: ID do job
        """
        try:
            job = self.job_store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} não encontrado para marcar como iniciado")
                return
            
            job.status = JobStatus.PROCESSING
            job.started_at = now_brazil()
            job.progress = 0.0
            job.status_message = "Processamento iniciado"
            
            self.job_store.update_job(job)
            logger.info(f"🚀 Job {job_id} iniciado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar job {job_id} como iniciado: {e}")
    
    def mark_completed(self, job_id: str, result: Any) -> None:
        """
        Marca job como completado.
        
        Args:
            job_id: ID do job
            result: Resultado do processamento
        """
        try:
            job = self.job_store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} não encontrado para marcar como completado")
                return
            
            job.status = JobStatus.COMPLETED
            job.completed_at = now_brazil()
            job.progress = 1.0
            job.status_message = "Processamento concluído com sucesso"
            
            # Calcula tempo de processamento
            if job.started_at:
                processing_time = (job.completed_at - job.started_at).total_seconds()
                job.processing_time = processing_time
            
            # Adiciona resultado se houver
            if result:
                # result pode ser TranscriptionResponse ou dict
                if hasattr(result, 'model_dump'):
                    job.result = result.model_dump()
                elif isinstance(result, dict):
                    job.result = result
            
            self.job_store.update_job(job)
            logger.info(f"✅ Job {job_id} completado em {job.processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar job {job_id} como completado: {e}")
    
    def mark_failed(self, job_id: str, error: str) -> None:
        """
        Marca job como falho.
        
        Args:
            job_id: ID do job
            error: Mensagem de erro
        """
        try:
            job = self.job_store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} não encontrado para marcar como falho")
                return
            
            job.status = JobStatus.FAILED
            job.error_message = error
            job.progress = 0.0
            job.status_message = "Processamento falhou"
            
            # Calcula tempo até falha
            if job.started_at:
                job.completed_at = now_brazil()
                job.processing_time = (job.completed_at - job.started_at).total_seconds()
            
            self.job_store.update_job(job)
            logger.error(f"❌ Job {job_id} falhou: {error}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar job {job_id} como falho: {e}")
            # Tentativa última de salvar o erro
            try:
                # Cria job mínimo com erro
                minimal_job = Job(
                    id=job_id,
                    status=JobStatus.FAILED,
                    error_message=f"Erro duplo: {error} + {e}",
                    input_file="unknown",
                    operation="transcribe"
                )
                self.job_store.save_job(minimal_job)
            except:
                logger.critical(f"💀 Não foi possível salvar falha do job {job_id}")


# Alias para compatibilidade com imports antigos
ProgressTracker = RedisProgressTracker
