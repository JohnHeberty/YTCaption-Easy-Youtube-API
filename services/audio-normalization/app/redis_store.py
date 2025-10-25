"""
Redis Job Store refatorado com alta resiliência e boas práticas
"""
import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from redis import Redis
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Job, JobStatus
from .config import get_settings
from .exceptions import RedisConnectionError, JobNotFoundError, JobExpiredError
from .logging_config import log_function_call, get_performance_logger

logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()


class RedisJobStore:
    """
    Store robusto de jobs no Redis com retry automático e circuit breaker
    """
    
    def __init__(self, redis_url: str = None):
        self.settings = get_settings()
        self.redis_url = redis_url or self.settings.get_redis_url()
        
        # Estado interno
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_connected = False
        
        # Configurações
        self.cache_ttl_seconds = self.settings.cache.ttl_hours * 3600
        self.cleanup_interval_seconds = self.settings.cache.cleanup_interval_minutes * 60
        
        # Inicializa conexão
        self._initialize_connection()
        
        logger.info(
            "RedisJobStore initialized",
            extra={
                "extra_fields": {
                    "redis_url": self._mask_redis_url(self.redis_url),
                    "cache_ttl_hours": self.settings.cache.ttl_hours,
                    "cleanup_interval_minutes": self.settings.cache.cleanup_interval_minutes
                }
            }
        )
    
    def _mask_redis_url(self, url: str) -> str:
        """Mascara credenciais da URL do Redis para logs"""
        if '@' in url:
            parts = url.split('@')
            if len(parts) == 2:
                return f"{parts[0].split(':')[0]}://***@{parts[1]}"
        return url
    
    @retry(
        stop=stop_after_attempt(5), 
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _initialize_connection(self):
        """Inicializa conexão com Redis com retry automático"""
        try:
            self.redis = Redis.from_url(
                self.redis_url, 
                decode_responses=True,
                socket_connect_timeout=self.settings.database.connection_timeout,
                socket_timeout=self.settings.database.connection_timeout,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Testa conexão
            self.redis.ping()
            self._validate_redis_memory()
            
            self._is_connected = True
            logger.info("✅ Redis connection established")
            
        except Exception as e:
            self._is_connected = False
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise RedisConnectionError(self.redis_url) from e
    
    def _validate_redis_memory(self):
        """Valida se Redis tem memória suficiente"""
        try:
            info = self.redis.info('memory')
            used_memory = info.get('used_memory', 0)
            min_memory = self.settings.database.min_memory_bytes
            
            if used_memory < min_memory:
                raise RedisConnectionError(
                    self.redis_url,
                    details={
                        "reason": "insufficient_memory",
                        "used_memory": used_memory,
                        "min_required": min_memory
                    }
                )
                
        except Exception as e:
            logger.warning(f"Could not validate Redis memory: {e}")
    
    def _job_key(self, job_id: str) -> str:
        """Gera chave Redis para job"""
        return f"audio_job:{job_id}"
    
    def _serialize_job(self, job: Job) -> str:
        """Serializa job para JSON com tratamento de datetime"""
        try:
            job_dict = job.model_dump()
            
            # Serializa campos datetime
            datetime_fields = ['created_at', 'completed_at', 'expires_at']
            for field in datetime_fields:
                if job_dict.get(field):
                    job_dict[field] = job_dict[field].isoformat()
            
            return json.dumps(job_dict, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to serialize job {job.id}: {e}")
            raise
    
    def _deserialize_job(self, data: str) -> Job:
        """Deserializa job do JSON com validação"""
        try:
            job_dict = json.loads(data)
            
            # Deserializa campos datetime
            datetime_fields = ['created_at', 'completed_at', 'expires_at']
            for field in datetime_fields:
                if job_dict.get(field):
                    job_dict[field] = datetime.fromisoformat(job_dict[field])
            
            # Compatibilidade com versões antigas (campos opcionais)
            optional_fields = {
                'apply_highpass_filter': False,
                'set_sample_rate_16k': False,
                'file_size_input': None,
                'file_size_output': None,
                'progress': 0.0
            }
            
            for field, default_value in optional_fields.items():
                if field not in job_dict:
                    job_dict[field] = default_value
            
            return Job(**job_dict)
            
        except Exception as e:
            logger.error(f"Failed to deserialize job data: {e}")
            raise
    
    @log_function_call()
    def save_job(self, job: Job) -> Job:
        """Salva job no Redis com TTL"""
        self._ensure_connection()
        
        try:
            key = self._job_key(job.id)
            data = self._serialize_job(job)
            
            # Salva com TTL
            self.redis.setex(key, self.cache_ttl_seconds, data)
            
            logger.debug(
                f"Job saved: {job.id}",
                extra={
                    "extra_fields": {
                        "job_id": job.id,
                        "status": job.status,
                        "ttl_hours": self.settings.cache.ttl_hours
                    }
                }
            )
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {e}")
            raise
    
    @log_function_call()
    def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do Redis"""
        self._ensure_connection()
        
        try:
            key = self._job_key(job_id)
            data = self.redis.get(key)
            
            if not data:
                logger.debug(f"Job not found: {job_id}")
                return None
            
            job = self._deserialize_job(data)
            
            # Verifica expiração
            if job.is_expired:
                logger.debug(f"Job expired: {job_id}")
                self.redis.delete(key)  # Remove job expirado
                return None
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    @log_function_call()
    def update_job(self, job: Job) -> Job:
        """Atualiza job existente"""
        return self.save_job(job)
    
    @log_function_call()
    def delete_job(self, job_id: str) -> bool:
        """Deleta job do Redis"""
        self._ensure_connection()
        
        try:
            key = self._job_key(job_id)
            result = self.redis.delete(key)
            
            logger.debug(
                f"Job deletion: {job_id}",
                extra={
                    "extra_fields": {
                        "job_id": job_id,
                        "deleted": bool(result)
                    }
                }
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False
    
    def list_jobs(self, limit: int = 100) -> List[Job]:
        """Lista jobs recentes com paginação"""
        self._ensure_connection()
        
        jobs = []
        try:
            # Busca chaves com padrão
            keys = self.redis.keys(f"audio_job:*")
            
            # Processa em batches para evitar sobrecarga
            batch_size = 50
            for i in range(0, min(len(keys), limit * 2), batch_size):
                batch_keys = keys[i:i+batch_size]
                
                for key in batch_keys:
                    try:
                        data = self.redis.get(key)
                        if data:
                            job = self._deserialize_job(data)
                            if not job.is_expired:
                                jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize job from key {key}: {e}")
                        continue
                
                # Para se atingiu o limite
                if len(jobs) >= limit:
                    break
            
            # Ordena por data de criação (mais recente primeiro)
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]
            
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do store"""
        self._ensure_connection()
        
        try:
            # Estatísticas básicas
            keys = self.redis.keys("audio_job:*")
            total_jobs = len(keys)
            
            # Conta por status
            status_counts = {}
            expired_count = 0
            
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        if job.is_expired:
                            expired_count += 1
                        else:
                            status = job.status.value
                            status_counts[status] = status_counts.get(status, 0) + 1
                except Exception:
                    continue
            
            # Info do Redis
            redis_info = self.redis.info()
            
            return {
                "total_jobs": total_jobs,
                "active_jobs": total_jobs - expired_count,
                "expired_jobs": expired_count,
                "by_status": status_counts,
                "redis_info": {
                    "used_memory_mb": redis_info.get('used_memory', 0) / 1024 / 1024,
                    "connected_clients": redis_info.get('connected_clients', 0),
                    "total_commands_processed": redis_info.get('total_commands_processed', 0)
                },
                "cleanup_active": self._cleanup_task is not None and not self._cleanup_task.done(),
                "cache_config": {
                    "ttl_hours": self.settings.cache.ttl_hours,
                    "cleanup_interval_minutes": self.settings.cache.cleanup_interval_minutes
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    async def start_cleanup_task(self):
        """Inicia tarefa de limpeza automática"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("🧹 Cleanup task started")
    
    async def stop_cleanup_task(self):
        """Para tarefa de limpeza"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Cleanup task stopped")
    
    async def _cleanup_loop(self):
        """Loop principal de limpeza"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                removed_count = await self.cleanup_expired()
                
                if removed_count > 0:
                    logger.info(f"🧹 Automatic cleanup: {removed_count} expired jobs removed")
                    
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Continua o loop mesmo com erro
    
    async def cleanup_expired(self) -> int:
        """Remove jobs expirados e arquivos associados"""
        if not self._is_connected:
            logger.warning("Cannot cleanup: Redis not connected")
            return 0
        
        try:
            current_time = datetime.now()
            removed_count = 0
            
            # Busca todas as chaves de jobs
            keys = self.redis.keys("audio_job:*")
            
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if not data:
                        continue
                    
                    job = self._deserialize_job(data)
                    
                    if job.expires_at < current_time:
                        # Remove arquivos associados
                        await self._cleanup_job_files(job)
                        
                        # Remove do Redis
                        self.redis.delete(key)
                        removed_count += 1
                        
                        logger.debug(
                            f"Cleaned up expired job: {job.id}",
                            extra={
                                "extra_fields": {
                                    "job_id": job.id,
                                    "expired_at": job.expires_at.isoformat()
                                }
                            }
                        )
                        
                except Exception as e:
                    logger.warning(f"Error processing job key {key} during cleanup: {e}")
                    continue
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0
    
    async def _cleanup_job_files(self, job: Job):
        """Remove arquivos associados ao job"""
        files_to_remove = []
        
        if job.input_file:
            files_to_remove.append(Path(job.input_file))
        if job.output_file:
            files_to_remove.append(Path(job.output_file))
        
        for file_path in files_to_remove:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Removed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")
    
    def backup_jobs(self, backup_dir: str = None) -> int:
        """Realiza backup dos jobs ativos"""
        backup_path = Path(backup_dir or self.settings.backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        try:
            keys = self.redis.keys("audio_job:*")
            backup_count = 0
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if not data:
                        continue
                    
                    job = self._deserialize_job(data)
                    if job.is_expired:
                        continue
                    
                    # Salva job em arquivo JSON
                    backup_file = backup_path / f"job_{job.id}_{timestamp}.json"
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        f.write(data)
                    
                    backup_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to backup job from key {key}: {e}")
                    continue
            
            logger.info(
                f"Backup completed: {backup_count} jobs saved to {backup_path}",
                extra={
                    "extra_fields": {
                        "backup_count": backup_count,
                        "backup_path": str(backup_path)
                    }
                }
            )
            
            return backup_count
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return 0
    
    def _ensure_connection(self):
        """Garante que a conexão Redis está ativa"""
        if not self._is_connected:
            logger.warning("Redis connection lost, attempting to reconnect...")
            self._initialize_connection()
        
        try:
            self.redis.ping()
        except Exception as e:
            self._is_connected = False
            logger.error(f"Redis connection check failed: {e}")
            raise RedisConnectionError(self.redis_url) from e
    
    def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do Redis store"""
        try:
            start_time = time.time()
            self.redis.ping()
            ping_time = (time.time() - start_time) * 1000
            
            info = self.redis.info()
            
            return {
                "status": "healthy",
                "connected": True,
                "ping_time_ms": ping_time,
                "redis_version": info.get('redis_version', 'unknown'),
                "used_memory_mb": info.get('used_memory', 0) / 1024 / 1024,
                "connected_clients": info.get('connected_clients', 0)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }