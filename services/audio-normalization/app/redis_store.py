import os
import json
import asyncio
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path
import time
from redis import Redis
from .models import Job

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=LOG_LEVEL)
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
import os
import json
import asyncio
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path
import time
from redis import Redis
from .models import Job

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=LOG_LEVEL)
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
    async def cleanup_expired(self) -> int:
        """
        Limpa jobs expirados manualmente.
        Returns:
            int: Quantidade de jobs expirados removidos.
        """
    # Limpa jobs expirados manualmente.
    # Path já importado no topo
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
            except (OSError, RuntimeError) as exc:
                logger.error("Erro ao processar %s: %s", key, exc)
        if expired_count > 0:
            logger.info("🧹 Removidos %d jobs expirados", expired_count)
        return expired_count
    
    def __init__(self, redis_url: str = None) -> None:
        """
        Inicializa o JobStore com Redis.
        Args:
            redis_url (str, opcional): URL do Redis.
        """
        from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
        redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self._cleanup_task: Optional[asyncio.Task] = None
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
        min_memory_bytes = int(os.getenv('REDIS_MIN_MEMORY_BYTES', '10485760'))  # 10MB padrão
        @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
        def connect_redis():
            redis = Redis.from_url(redis_url, decode_responses=True)
            redis.ping()
            info = redis.info('memory')
            used_memory = info.get('used_memory', 0)
            if used_memory < min_memory_bytes:
                logger.error("Redis está usando apenas %d bytes, mínimo exigido: %d bytes", used_memory, min_memory_bytes)  # pylint: disable=line-too-long
                raise ConnectionError(f"Redis precisa de pelo menos {min_memory_bytes} bytes de memória disponível para iniciar.")  # pylint: disable=line-too-long
            return redis
        try:
            self.redis = connect_redis()
            logger.info("✅ Redis conectado: %s", redis_url)
            logger.info("⏰ Cache TTL: %dh, Cleanup: %dmin", self.cache_ttl_hours, self.cleanup_interval_minutes)
        except RetryError as err:
            logger.error("Falha ao conectar Redis após múltiplas tentativas: %s", err)
            raise
            logger.error("❌ Erro ao conectar Redis após múltiplas tentativas ou memória insuficiente")
            raise ConnectionError("Redis não está pronto ou não possui memória mínima após múltiplas tentativas")
    
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
    # Path já importado no topo
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
                    except (OSError, RuntimeError) as exc:
                        logger.error("Erro ao processar %s: %s", key, exc)
                if expired_count > 0:
                    logger.info("🧹 Removidos %d jobs expirados", expired_count)
            except asyncio.CancelledError:
                break
            except (OSError, RuntimeError) as exc:
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
        except (RuntimeError, ValueError, OSError) as exc:
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
            except (RuntimeError, ValueError, OSError) as exc:
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
            except (RuntimeError, ValueError, OSError):
                continue
        
        return {
            "total_jobs": total,
            "by_status": by_status,
            "cleanup_active": self._cleanup_task is not None,
            "redis_connected": True
        }
