import json
import asyncio
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta
try:
    from common.datetime_utils import now_brazil, ensure_timezone_aware
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)


# Use resilient Redis from common library
from common.redis_utils import ResilientRedisStore

from ..core.models import Job

logger = logging.getLogger(__name__)


class RedisJobStore:
    """Store compartilhado de jobs usando Redis (com resiliência)"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Inicializa store com Redis resiliente
        
        Args:
            redis_url: URL de conexão do Redis
        """
        # Usa ResilientRedisStore da biblioteca comum
        self.redis_client = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
            circuit_breaker_max_failures=int(os.getenv('REDIS_CIRCUIT_BREAKER_MAX_FAILURES', '5')),
            circuit_breaker_timeout=int(os.getenv('REDIS_CIRCUIT_BREAKER_TIMEOUT', '60'))
        )
        
        # Mantém interface compatível
        self.redis = self.redis_client.redis
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Lê configurações de cache das variáveis de ambiente
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
        
        logger.info("✅ Redis conectado com resiliência: %s", redis_url)
        logger.info("⏰ Cache TTL: %sh, Cleanup: %smin", 
                   self.cache_ttl_hours, self.cleanup_interval_minutes)
    
    def _job_key(self, job_id: str) -> str:
        """Gera chave Redis para job"""
        return f"audio_job:{job_id}"
    
    def _serialize_job(self, job: Job) -> str:
        """Serializa Job para JSON"""
        job_dict = job.model_dump(mode='json')
        return json.dumps(job_dict)
    
    def _deserialize_job(self, data: str) -> Job:
        """Deserializa Job de JSON"""
        job_dict = json.loads(data)
        # Converte strings de datetime de volta para datetime objects
        if 'created_at' in job_dict:
            dt = datetime.fromisoformat(job_dict['created_at'])
            job_dict['created_at'] = ensure_timezone_aware(dt)
        if 'completed_at' in job_dict and job_dict['completed_at']:
            dt = datetime.fromisoformat(job_dict['completed_at'])
            job_dict['completed_at'] = ensure_timezone_aware(dt)
        if 'expires_at' in job_dict:
            dt = datetime.fromisoformat(job_dict['expires_at'])
            job_dict['expires_at'] = ensure_timezone_aware(dt)
        
        return Job(**job_dict)
    
    def save_job(self, job: Job) -> None:
        """Salva job no Redis"""
        key = self._job_key(job.id)
        data = self._serialize_job(job)
        
        # Define TTL em segundos
        ttl_seconds = self.cache_ttl_hours * 3600
        
        self.redis.setex(key, ttl_seconds, data)
        logger.debug("📝 Job salvo: %s", job.id)
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do Redis"""
        key = self._job_key(job_id)
        data = self.redis.get(key)
        
        if not data:
            return None
        
        try:
            job = self._deserialize_job(data)
            
            # Verifica se expirou
            if job.is_expired:
                self.redis.delete(key)
                logger.debug("🗑️  Job expirado removido: %s", job_id)
                return None
            
            return job
        except Exception as exc:
            logger.error("❌ Erro ao deserializar job %s: %s", job_id, exc)
            self.redis.delete(key)  # Remove job corrompido
            return None
    
    def update_job(self, job: Job) -> None:
        """Atualiza job existente de forma atômica"""
        # CORREÇÃO: Usa pipeline para operação atômica
        key = self._job_key(job.id)
        data = self._serialize_job(job)
        ttl_seconds = self.cache_ttl_hours * 3600
        
        # Pipeline garante atomicidade
        pipe = self.redis.pipeline()
        pipe.setex(key, ttl_seconds, data)
        pipe.execute()
        logger.debug(f"📝 Job atualizado atomicamente: {job.id}")
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete job from Redis
        
        Args:
            job_id: Job ID
        
        Returns:
            True if deleted, False if not found
        """
        key = self._job_key(job_id)
        result = self.redis.delete(key)  # Operação síncrona
        return result > 0
    
    def list_jobs(self, limit: int = 50) -> List[Job]:
        """Lista jobs recentes"""
        keys = self.redis.keys(f"audio_job:*")
        jobs = []
        
        for key in keys[:limit]:
            data = self.redis.get(key)
            if data:
                try:
                    job = self._deserialize_job(data)
                    if not job.is_expired:
                        jobs.append(job)
                    else:
                        self.redis.delete(key)  # Remove expirado
                except Exception as exc:
                    logger.error("❌ Erro ao deserializar job: %s", exc)
                    self.redis.delete(key)  # Remove corrompido
        
        # Ordena por data de criação (mais recente primeiro)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs
    
    def get_stats(self) -> dict:
        """Estatísticas básicas do store"""
        keys = self.redis.keys(f"audio_job:*")
        total_jobs = len(keys)
        
        status_count = {"queued": 0, "processing": 0, "completed": 0, "failed": 0}
        
        for key in keys:
            data = self.redis.get(key)
            if data:
                try:
                    job = self._deserialize_job(data)
                    if not job.is_expired:
                        status_count[job.status] += 1
                    else:
                        self.redis.delete(key)
                        total_jobs -= 1
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Failed to deserialize job {key}: {e}")
                    self.redis.delete(key)
                    total_jobs -= 1
        
        return {
            "total_jobs": total_jobs,
            "by_status": status_count,
            "cache_ttl_hours": self.cache_ttl_hours,
            "timestamp": datetime.now().isoformat()
        }
    
    async def start_cleanup_task(self):
        """Inicia tarefa de limpeza automática"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("🧹 Limpeza automática iniciada")
    
    async def stop_cleanup_task(self):
        """Para tarefa de limpeza"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("🛑 Limpeza automática parada")
    
    async def _cleanup_loop(self):
        """Loop de limpeza de jobs expirados"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                removed = await self.cleanup_expired()
                if removed > 0:
                    logger.info("🧹 Limpeza automática: %d jobs removidos", removed)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("❌ Erro na limpeza automática: %s", exc)
    
    async def cleanup_expired(self) -> int:
        """Remove jobs expirados"""
        keys = self.redis.keys(f"audio_job:*")
        removed = 0
        
        for key in keys:
            data = self.redis.get(key)
            if data:
                try:
                    job = self._deserialize_job(data)
                    if job.is_expired:
                        self.redis.delete(key)
                        removed += 1
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Failed to deserialize job {key}: {e}")
                    self.redis.delete(key)  # Remove corrompido
                    removed += 1
        
        return removed
    
    async def find_orphaned_jobs(self, max_age_minutes: int = 30) -> List[Job]:
        """
        Find jobs that are stuck in processing state for too long
        
        Args:
            max_age_minutes: Maximum time a job can be processing
        
        Returns:
            List of orphaned jobs
        """
        orphaned = []
        now = now_brazil()
        max_age = timedelta(minutes=max_age_minutes)
        
        try:
            for key in self.redis.scan_iter(match="audio_job:*"):
                try:
                    data = self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        
                        # Check if processing for too long
                        if job.status == "processing":
                            age = now - job.updated_at
                            if age > max_age:
                                orphaned.append(job)
                                logger.warning(
                                    f"⚠️ Orphaned job found: {job.id} "
                                    f"(processing for {age.total_seconds()/60:.1f} minutes)"
                                )
                except Exception as e:
                    logger.debug(f"Error processing key {key}: {e}")
        except Exception as e:
            logger.error(f"Error finding orphaned jobs: {e}")
        
        return orphaned
    
    async def get_queue_info(self) -> dict:
        """
        Get information about the job queue
        
        Returns:
            Dictionary with queue statistics
        """
        queue_info = {
            "total_jobs": 0,
            "by_status": {
                "queued": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0
            },
            "oldest_job": None,
            "newest_job": None
        }
        
        try:
            jobs = await self.list_jobs(limit=10000)  # Get all jobs
            queue_info["total_jobs"] = len(jobs)
            
            # Count by status
            for job in jobs:
                status_str = job.status.value if hasattr(job.status, 'value') else str(job.status)
                if status_str in queue_info["by_status"]:
                    queue_info["by_status"][status_str] += 1
            
            # Find oldest and newest
            if jobs:
                # Jobs are already sorted by created_at descending
                newest_status = jobs[0].status.value if hasattr(jobs[0].status, 'value') else str(jobs[0].status)
                oldest_status = jobs[-1].status.value if hasattr(jobs[-1].status, 'value') else str(jobs[-1].status)
                
                queue_info["newest_job"] = {
                    "job_id": jobs[0].id,
                    "created_at": jobs[0].created_at.isoformat(),
                    "status": newest_status
                }
                queue_info["oldest_job"] = {
                    "job_id": jobs[-1].id,
                    "created_at": jobs[-1].created_at.isoformat(),
                    "status": oldest_status
                }
        
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
        
        return queue_info