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
    def backup_jobs(self, backup_dir: str = './backup') -> int:
        """
        Realiza backup dos jobs e arquivos processados.
        Args:
            backup_dir (str): Diretório de backup.
        Returns:
            int: Quantidade de jobs salvos.
        """
        from pathlib import Path
        import shutil
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        count = 0
        for key in self.redis.keys("audio_job:*"):
            data = self.redis.get(key)
            if not data:
                continue
            job = self._deserialize_job(data)
            # Salva job em JSON
            job_file = backup_path / f"{job.id}.json"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(data)
            # Copia arquivo processado se existir
            if getattr(job, 'output_file', None):
                src = Path(job.output_file)
                if src.exists():
                    shutil.copy2(src, backup_path / src.name)
            count += 1
        logger.info(f"Backup realizado: {count} jobs salvos em {backup_path}")
        return count
    """Store compartilhado de jobs usando Redis"""
    
    def __init__(self, redis_url: str = None):
        from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self._cleanup_task: Optional[asyncio.Task] = None
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
        min_memory_bytes = int(os.getenv('REDIS_MIN_MEMORY_BYTES', '52428800'))  # 50MB padrão
        @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
        def connect_redis():
            redis = Redis.from_url(self.redis_url, decode_responses=True, socket_timeout=5)
            redis.ping()
            info = redis.info('memory')
            used_memory = info.get('used_memory', 0)
            if used_memory < min_memory_bytes:
                logger.error("Redis está usando apenas %d bytes, mínimo exigido: %d bytes", used_memory, min_memory_bytes)  # pylint: disable=line-too-long
                raise ConnectionError(f"Redis precisa de pelo menos {min_memory_bytes} bytes de memória disponível para iniciar.")  # pylint: disable=line-too-long
            return redis
        try:
            self.redis = connect_redis()
            logger.info("✅ Redis conectado: %s", self.redis_url)
            logger.info("⏰ Cache TTL: %dh, Cleanup: %dmin", self.cache_ttl_hours, self.cleanup_interval_minutes)
        except RetryError as e:
            logger.error("❌ Falha ao conectar Redis após múltiplas tentativas: %s", e)
            raise
        except Exception as e:
            logger.error("❌ Erro ao conectar Redis: %s", e)
            raise
    
    def _job_key(self, job_id: str) -> str:
        return f"audio_job:{job_id}"
    
    def _serialize_job(self, job: Job) -> str:
        job_dict = job.model_dump(mode='json')
        return json.dumps(job_dict)
    
    def _deserialize_job(self, data: str) -> Job:
        job_dict = json.loads(data)
        for field in ['created_at', 'completed_at', 'expires_at']:
            if job_dict.get(field):
                job_dict[field] = datetime.fromisoformat(job_dict[field])
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
        while True:
            try:
                await asyncio.sleep(cleanup_interval_seconds)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except (json.JSONDecodeError, TypeError, ValueError, ConnectionError, TimeoutError) as e:
                logger.error("Erro na limpeza: %s", e)
    
    async def cleanup_expired(self) -> int:
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
            except (json.JSONDecodeError, TypeError, ValueError, ConnectionError, TimeoutError) as e:
                logger.error("Erro ao processar %s: %s", key, e)
        
        if expired_count > 0:
            logger.info("� Removidos %d jobs expirados", expired_count)
        
        return expired_count
    
    def save_job(self, job: Job) -> Job:
        from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
        key = self._job_key(job.id)
        data = self._serialize_job(job)
        ttl_seconds = self.cache_ttl_hours * 3600  # Converte horas para segundos
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def set_job():
            self.redis.setex(key, ttl_seconds, data)
        try:
            set_job()
            logger.debug("💾 Job salvo: %s (TTL: %dh)", job.id, self.cache_ttl_hours)
        except RetryError as e:
            logger.error("❌ Falha ao salvar job no Redis: %s", e)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
        key = self._job_key(job_id)
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def get_data():
            return self.redis.get(key)
        try:
            data = get_data()
        except RetryError as e:
            logger.error("❌ Falha ao buscar job no Redis: %s", e)
            return None
        if not data:
            return None
        try:
            return self._deserialize_job(data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Erro ao deserializar job %s: %s", job_id, e)
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
            except (json.JSONDecodeError, TypeError, ValueError, ConnectionError, TimeoutError) as e:
                logger.error("Erro ao deserializar %s: %s", key, e)
        
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
            except (json.JSONDecodeError, TypeError, ValueError, ConnectionError, TimeoutError):
                pass
        
        return {
            "total_jobs": total,
            "by_status": by_status,
            "cleanup_active": self._cleanup_task is not None,
            "redis_connected": True
        }
