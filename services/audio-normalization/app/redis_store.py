import json
import asyncio
import os
import logging
from typing import Optional, List
from datetime import datetime
from redis import Redis
from .models import Job

logger = logging.getLogger(__name__)


class RedisJobStore:
    """Store compartilhado de jobs usando Redis"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Inicializa store com Redis
        
        Args:
            redis_url: URL de conexão do Redis
        """
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Lê configurações de cache das variáveis de ambiente
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
        
        # Testa conexão
        try:
            self.redis.ping()
            logger.info("✅ Redis conectado: %s", redis_url)
            logger.info("⏰ Cache TTL: %sh, Cleanup: %smin", 
                       self.cache_ttl_hours, self.cleanup_interval_minutes)
        except Exception as exc:
            logger.error("❌ Erro ao conectar Redis: %s", exc)
            raise
    
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
            job_dict['created_at'] = datetime.fromisoformat(job_dict['created_at'])
        if 'completed_at' in job_dict and job_dict['completed_at']:
            job_dict['completed_at'] = datetime.fromisoformat(job_dict['completed_at'])
        if 'expires_at' in job_dict:
            job_dict['expires_at'] = datetime.fromisoformat(job_dict['expires_at'])
        
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
        """Atualiza job existente"""
        self.save_job(job)  # Redis permite sobrescrever
    
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
                except:
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
                except:
                    self.redis.delete(key)  # Remove corrompido
                    removed += 1
        
        return removed