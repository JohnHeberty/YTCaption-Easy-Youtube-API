"""
Armazenamento de jobs usando Redis
"""
import json
import logging
from typing import Optional, List
import redis
from datetime import datetime

from .models import PipelineJob
from .config import get_orchestrator_settings

logger = logging.getLogger(__name__)


class RedisStore:
    """Store para persistência de jobs no Redis"""
    
    def __init__(self):
        settings = get_orchestrator_settings()
        self.redis_url = settings["redis_url"]
        self.ttl_hours = settings["cache_ttl_hours"]
        self.ttl_seconds = self.ttl_hours * 3600
        
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Testa conexão
            self.client.ping()
            logger.info(f"Connected to Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    def _job_key(self, job_id: str) -> str:
        """Gera chave do job"""
        return f"orchestrator:job:{job_id}"
    
    def _jobs_list_key(self) -> str:
        """Chave da lista de jobs"""
        return "orchestrator:jobs:list"
    
    def save_job(self, job: PipelineJob) -> bool:
        """Salva job no Redis"""
        try:
            key = self._job_key(job.id)
            
            # Serializa job para JSON
            job_dict = job.model_dump(mode='json')
            
            # Converte datetimes para ISO format
            for field in ['created_at', 'updated_at', 'completed_at']:
                if job_dict.get(field):
                    if isinstance(job_dict[field], datetime):
                        job_dict[field] = job_dict[field].isoformat()
            
            # Converte estágios
            for stage_key in ['download_stage', 'normalization_stage', 'transcription_stage']:
                stage = job_dict.get(stage_key, {})
                for field in ['started_at', 'completed_at']:
                    if stage.get(field):
                        if isinstance(stage[field], datetime):
                            stage[field] = stage[field].isoformat()
            
            job_json = json.dumps(job_dict)
            
            # Salva com TTL
            self.client.setex(key, self.ttl_seconds, job_json)
            
            # Adiciona à lista de jobs
            self.client.zadd(
                self._jobs_list_key(),
                {job.id: datetime.now().timestamp()}
            )
            
            logger.debug(f"Job {job.id} saved to Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {str(e)}")
            return False
    
    def get_job(self, job_id: str) -> Optional[PipelineJob]:
        """Recupera job do Redis"""
        try:
            key = self._job_key(job_id)
            job_json = self.client.get(key)
            
            if not job_json:
                return None
            
            job_dict = json.loads(job_json)
            
            # Parse job
            job = PipelineJob(**job_dict)
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {str(e)}")
            return None
    
    def delete_job(self, job_id: str) -> bool:
        """Remove job do Redis"""
        try:
            key = self._job_key(job_id)
            
            # Remove job
            self.client.delete(key)
            
            # Remove da lista
            self.client.zrem(self._jobs_list_key(), job_id)
            
            logger.debug(f"Job {job_id} deleted from Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {str(e)}")
            return False
    
    def list_jobs(self, limit: int = 100) -> List[str]:
        """Lista IDs dos jobs mais recentes"""
        try:
            # Pega jobs ordenados por timestamp (mais recentes primeiro)
            job_ids = self.client.zrevrange(
                self._jobs_list_key(),
                0,
                limit - 1
            )
            return job_ids
            
        except Exception as e:
            logger.error(f"Failed to list jobs: {str(e)}")
            return []
    
    def cleanup_old_jobs(self, max_age_hours: int = None) -> int:
        """Remove jobs antigos"""
        if max_age_hours is None:
            max_age_hours = self.ttl_hours
        
        try:
            cutoff_timestamp = datetime.now().timestamp() - (max_age_hours * 3600)
            
            # Remove jobs antigos da lista
            removed = self.client.zremrangebyscore(
                self._jobs_list_key(),
                0,
                cutoff_timestamp
            )
            
            logger.info(f"Cleaned up {removed} old jobs")
            return removed
            
        except Exception as e:
            logger.error(f"Failed to cleanup jobs: {str(e)}")
            return 0
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do store"""
        try:
            total_jobs = self.client.zcard(self._jobs_list_key())
            
            # Pega alguns jobs recentes para estatísticas
            recent_job_ids = self.list_jobs(limit=50)
            
            status_counts = {}
            for job_id in recent_job_ids:
                job = self.get_job(job_id)
                if job:
                    status = job.status.value
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "total_jobs": total_jobs,
                "recent_jobs_analyzed": len(recent_job_ids),
                "status_distribution": status_counts,
                "ttl_hours": self.ttl_hours
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {}
    
    def ping(self) -> bool:
        """Verifica conexão com Redis"""
        try:
            return self.client.ping()
        except:
            return False


# Singleton
_store_instance = None

def get_store() -> RedisStore:
    """Retorna instância singleton do store"""
    global _store_instance
    if _store_instance is None:
        _store_instance = RedisStore()
    return _store_instance
