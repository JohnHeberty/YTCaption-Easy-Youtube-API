import json
import asyncio
import os
from typing import Optional
from datetime import datetime
from redis import Redis
from .models import Job
import logging

logger = logging.getLogger(__name__)


class RedisJobStore:
    async def cleanup_expired(self) -> int:
        """Limpa jobs expirados manualmente."""
        from pathlib import Path
        now = datetime.now()
        expired_count = 0
        for key in self.redis.keys("audio_job:*"):
            try:
                data = self.redis.get(key)
                if not data:
                    continue
                job = self._deserialize_job(data)
                if job.expires_at < now:
                    # Remove arquivo se existir
                    if job.output_file:
                        file_path = Path(job.output_file)
                        if file_path.exists():
                            file_path.unlink()
                            logger.info("🗑️  Arquivo removido: %s", file_path)
                    self.redis.delete(key)
                    expired_count += 1
            except Exception as exc:
                logger.error("Erro ao processar %s: %s", key, exc)
        if expired_count > 0:
            logger.info("🧹 Removidos %d jobs expirados", expired_count)
        return expired_count
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Lê configurações de cache das variáveis de ambiente
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
        
        try:
            self.redis.ping()
            logger.info("✅ Redis conectado: %s", redis_url)
            logger.info("⏰ Cache TTL: %dh, Cleanup: %dmin", self.cache_ttl_hours, self.cleanup_interval_minutes)
        except Exception as exc:
            logger.error("❌ Erro ao conectar Redis: %s", exc)
            raise
    
    def _job_key(self, job_id: str) -> str:
        return f"audio_job:{job_id}"
    def _serialize_job(self, job: Job) -> str:
        job_dict = job.model_dump()
        # Serializa campos datetime para string
        for field in ['created_at', 'completed_at', 'expires_at']:
            if job_dict.get(field):
                job_dict[field] = job_dict[field].isoformat()
        return json.dumps(job_dict)
    
    def _deserialize_job(self, data: str) -> Job:
        job_dict = json.loads(data)
        for field in ['created_at', 'completed_at', 'expires_at']:
            if job_dict.get(field):
                job_dict[field] = datetime.fromisoformat(job_dict[field])
        # Preenche campos obrigatórios ausentes com False
        if 'apply_highpass_filter' not in job_dict:
            job_dict['apply_highpass_filter'] = False
        if 'set_sample_rate_16k' not in job_dict:
            job_dict['set_sample_rate_16k'] = False
        return Job(**job_dict)
    async def start_cleanup_task(self):
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("🧹 Cleanup task iniciada")
    
    async def stop_cleanup_task(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_loop(self):
        """Loop de limpeza com intervalo configurável"""
        cleanup_interval_seconds = self.cleanup_interval_minutes * 60
        from pathlib import Path
        while True:
            try:
                await asyncio.sleep(cleanup_interval_seconds)
                now = datetime.now()
                expired_count = 0
                for key in self.redis.keys("audio_job:*"):
                    try:
                        data = self.redis.get(key)
                        if not data:
                            continue
                        job = self._deserialize_job(data)
                        if job.expires_at < now:
                            # Remove arquivo se existir
                            if job.output_file:
                                file_path = Path(job.output_file)
                                if file_path.exists():
                                    file_path.unlink()
                                    logger.info("🗑️  Arquivo removido: %s", file_path)
                            self.redis.delete(key)
                            expired_count += 1
                    except Exception as exc:
                        logger.error("Erro ao processar %s: %s", key, exc)
                if expired_count > 0:
                    logger.info("🧹 Removidos %d jobs expirados", expired_count)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Erro na limpeza: %s", exc)
                    
        # Removido código duplicado e fora de escopo
    
    def save_job(self, job: Job) -> Job:
        key = self._job_key(job.id)
        data = self._serialize_job(job)
        ttl_seconds = self.cache_ttl_hours * 3600  # Converte horas para segundos
        self.redis.setex(key, ttl_seconds, data)
        logger.debug("💾 Job salvo: %s (TTL: %dh)", job.id, self.cache_ttl_hours)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        key = self._job_key(job_id)
        data = self.redis.get(key)
        if not data:
            return None
        try:
            return self._deserialize_job(data)
        except Exception as exc:
            logger.error("Erro ao deserializar job %s: %s", key, exc)
            return None
    
    def update_job(self, job: Job) -> Job:
        return self.save_job(job)
    
    def list_jobs(self, limit: int = 100) -> list[Job]:
        jobs = []
        for key in self.redis.keys("audio_job:*")[:limit * 2]:
            try:
                data = self.redis.get(key)
                if data:
                    job = self._deserialize_job(data)
                    jobs.append(job)
            except Exception as exc:
                logger.error("Erro ao deserializar %s: %s", key, exc)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
    
    def get_stats(self) -> dict:
        job_keys = self.redis.keys("audio_job:*")
        total = len(job_keys)
        by_status = {}
        
        for key in job_keys:
            try:
                data = self.redis.get(key)
                if data:
                    job = self._deserialize_job(data)
                    status = job.status.value
                    by_status[status] = by_status.get(status, 0) + 1
            except Exception:
                continue
        
        return {
            "total_jobs": total,
            "by_status": by_status,
            "cleanup_active": self._cleanup_task is not None,
            "redis_connected": True
        }
