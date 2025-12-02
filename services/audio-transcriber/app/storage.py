"""
Sistema de armazenamento para jobs de transcrição
Implementação em memória com interface para Redis
"""
import asyncio
import time
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime

from .models import Job, JobStatus, TranscriptionStats
from .logging_config import get_logger

logger = get_logger(__name__)


class JobStorage:
    """
    Storage para jobs de transcrição
    Implementação em memória com interface preparada para Redis
    """
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
    
    async def save_job(self, job: Job) -> None:
        """
        Salva job no storage
        
        Args:
            job: Job para salvar
        """
        
        async with self._lock:
            self._jobs[job.id] = job
            logger.debug(f"Job saved: {job.id}")
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Recupera job por ID
        
        Args:
            job_id: ID do job
            
        Returns:
            Job encontrado ou None
        """
        
        async with self._lock:
            job = self._jobs.get(job_id)
            
            if job and job.is_expired:
                # Remove job expirado automaticamente
                del self._jobs[job_id]
                logger.info(f"Removed expired job: {job_id}")
                return None
                
            return job
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Remove job do storage
        
        Args:
            job_id: ID do job
            
        Returns:
            True se removido, False se não encontrado
        """
        
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Job deleted: {job_id}")
                return True
            return False
    
    async def list_jobs(
        self, 
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Job]:
        """
        Lista jobs com filtros opcionais
        
        Args:
            status: Filtro por status
            limit: Limite de resultados
            offset: Offset para paginação
            
        Returns:
            Lista de jobs
        """
        
        async with self._lock:
            jobs = list(self._jobs.values())
            
            # Remove jobs expirados
            current_time = datetime.now()
            valid_jobs = []
            expired_jobs = []
            
            for job in jobs:
                if job.expires_at <= current_time:
                    expired_jobs.append(job.id)
                else:
                    valid_jobs.append(job)
            
            # Remove jobs expirados do storage
            for job_id in expired_jobs:
                del self._jobs[job_id]
            
            # Aplica filtro de status
            if status:
                try:
                    status_enum = JobStatus(status)
                    valid_jobs = [job for job in valid_jobs if job.status == status_enum]
                except ValueError:
                    logger.warning(f"Invalid status filter: {status}")
                    return []
            
            # Ordena por data de criação (mais recentes primeiro)
            valid_jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            # Aplica paginação
            start = offset
            end = offset + limit
            
            return valid_jobs[start:end]
    
    async def get_expired_jobs(self) -> List[Job]:
        """
        Retorna jobs expirados
        
        Returns:
            Lista de jobs expirados
        """
        
        async with self._lock:
            current_time = datetime.now()
            expired_jobs = []
            
            for job in self._jobs.values():
                if job.expires_at <= current_time:
                    expired_jobs.append(job)
            
            return expired_jobs
    
    async def get_stats(self) -> TranscriptionStats:
        """
        Calcula estatísticas dos jobs
        
        Returns:
            Estatísticas de transcrição
        """
        
        async with self._lock:
            jobs = list(self._jobs.values())
            
            # Remove jobs expirados das estatísticas
            current_time = datetime.now()
            valid_jobs = [job for job in jobs if job.expires_at > current_time]
            
            total_jobs = len(valid_jobs)
            
            # Contagem por status
            jobs_by_status = defaultdict(int)
            for job in valid_jobs:
                jobs_by_status[job.status] += 1
            
            # Contagem por idioma
            jobs_by_language = defaultdict(int)
            for job in valid_jobs:
                if job.detected_language:
                    jobs_by_language[job.detected_language] += 1
                elif job.language != "auto":
                    jobs_by_language[job.language] += 1
            
            # Calcula tempo médio de processamento
            processing_times = []
            total_audio_duration = 0.0
            successful_jobs = 0
            
            for job in valid_jobs:
                if job.processing_time:
                    processing_times.append(job.processing_time)
                
                if job.audio_duration:
                    total_audio_duration += job.audio_duration
                
                if job.is_completed:
                    successful_jobs += 1
            
            average_processing_time = None
            if processing_times:
                average_processing_time = sum(processing_times) / len(processing_times)
            
            # Taxa de sucesso
            success_rate = None
            if total_jobs > 0:
                success_rate = (successful_jobs / total_jobs) * 100
            
            return TranscriptionStats(
                total_jobs=total_jobs,
                jobs_by_status=dict(jobs_by_status),
                jobs_by_language=dict(jobs_by_language),
                average_processing_time=average_processing_time,
                total_audio_duration=total_audio_duration,
                success_rate=success_rate
            )
    
    async def cleanup_expired(self) -> int:
        """
        Remove todos os jobs expirados
        
        Returns:
            Número de jobs removidos
        """
        
        async with self._lock:
            current_time = datetime.now()
            expired_job_ids = []
            
            for job_id, job in self._jobs.items():
                if job.expires_at <= current_time:
                    expired_job_ids.append(job_id)
            
            # Remove jobs expirados
            for job_id in expired_job_ids:
                del self._jobs[job_id]
            
            if expired_job_ids:
                logger.info(f"Cleaned up {len(expired_job_ids)} expired jobs")
            
            return len(expired_job_ids)
    
    async def get_job_count(self) -> Dict[str, int]:
        """
        Retorna contagem de jobs por status
        
        Returns:
            Dicionário com contagem por status
        """
        
        async with self._lock:
            # Remove jobs expirados primeiro
            await self.cleanup_expired()
            
            counts = defaultdict(int)
            for job in self._jobs.values():
                counts[job.status.value] += 1
            
            counts["total"] = len(self._jobs)
            
            return dict(counts)
    
    async def get_processing_jobs(self) -> List[Job]:
        """
        Retorna jobs que estão sendo processados
        
        Returns:
            Lista de jobs em processamento
        """
        
        async with self._lock:
            processing_jobs = []
            
            for job in self._jobs.values():
                if job.status == JobStatus.PROCESSING:
                    processing_jobs.append(job)
            
            return processing_jobs
    
    async def update_job_progress(self, job_id: str, progress: float, message: Optional[str] = None) -> bool:
        """
        Atualiza progresso de um job
        
        Args:
            job_id: ID do job
            progress: Progresso (0.0 - 100.0)
            message: Mensagem opcional
            
        Returns:
            True se atualizado, False se job não encontrado
        """
        
        async with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.update_progress(progress, message)
                return True
            return False


class RedisJobStorage(JobStorage):
    """
    Implementação com Redis (para produção)
    Mantém mesma interface, mas persiste no Redis
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        super().__init__()
        self.redis_url = redis_url
        self._redis = None
        
        # TODO: Implementar conexão Redis
        logger.warning("RedisJobStorage not implemented yet, using in-memory storage")
    
    async def _get_redis(self):
        """Obtém conexão Redis (lazy loading)"""
        if self._redis is None:
            # TODO: Implementar conexão Redis
            # import aioredis
            # self._redis = await aioredis.from_url(self.redis_url)
            pass
        return self._redis
    
    async def save_job(self, job: Job) -> None:
        """Salva job no Redis"""
        
        # TODO: Implementar persistência Redis
        # redis = await self._get_redis()
        # job_data = job.json()
        # await redis.setex(f"job:{job.id}", job.expires_at.timestamp(), job_data)
        
        # Fallback para implementação em memória
        await super().save_job(job)
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do Redis"""
        
        # TODO: Implementar recuperação Redis
        # redis = await self._get_redis()
        # job_data = await redis.get(f"job:{job_id}")
        # if job_data:
        #     return Job.parse_raw(job_data)
        # return None
        
        # Fallback para implementação em memória
        return await super().get_job(job_id)


# Factory function para criar storage apropriado
def create_job_storage(use_redis: bool = False, redis_url: str = "redis://localhost:6379") -> JobStorage:
    """
    Cria instância de JobStorage
    
    Args:
        use_redis: Se deve usar Redis ou implementação em memória
        redis_url: URL do Redis
        
    Returns:
        Instância de JobStorage
    """
    
    if use_redis:
        return RedisJobStorage(redis_url)
    else:
        return JobStorage()