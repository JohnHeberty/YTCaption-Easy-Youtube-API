"""
Sistema robusto de gestão de recursos e context managers
"""
import os
import psutil
import asyncio
import tempfile
import shutil
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Dict, Any, Generator, AsyncGenerator
from dataclasses import dataclass
from threading import Lock
import time
import weakref
import logging
from concurrent.futures import ThreadPoolExecutor
import signal

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Definição de limites de recursos"""
    max_memory_mb: float = 512  # MB
    max_cpu_percent: float = 80  # %
    max_disk_usage_mb: float = 1024  # MB
    max_file_size_mb: float = 100  # MB
    max_processing_time_minutes: float = 30  # minutos
    max_concurrent_jobs: int = 3


@dataclass
class ResourceUsage:
    """Uso atual de recursos"""
    memory_mb: float
    cpu_percent: float
    disk_usage_mb: float
    active_jobs: int
    timestamp: float
    
    def exceeds_limits(self, limits: ResourceLimits) -> Dict[str, bool]:
        """Verifica quais limites estão sendo excedidos"""
        return {
            "memory": self.memory_mb > limits.max_memory_mb,
            "cpu": self.cpu_percent > limits.max_cpu_percent,
            "disk": self.disk_usage_mb > limits.max_disk_usage_mb,
            "jobs": self.active_jobs > limits.max_concurrent_jobs
        }


class ResourceMonitor:
    """Monitor de recursos do sistema"""
    
    def __init__(self, limits: ResourceLimits = None):
        self.limits = limits or ResourceLimits()
        self.process = psutil.Process()
        self._monitoring = False
        self._monitor_task = None
        self._callbacks = []
        
    def add_callback(self, callback):
        """Adiciona callback para alertas de recurso"""
        self._callbacks.append(callback)
    
    def get_current_usage(self) -> ResourceUsage:
        """Obtém uso atual de recursos"""
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        try:
            cpu_percent = self.process.cpu_percent()
        except psutil.NoSuchProcess:
            cpu_percent = 0.0
        
        # Uso de disco dos diretórios de trabalho
        disk_usage_mb = 0
        for directory in ['./uploads', './processed', './temp']:
            if Path(directory).exists():
                disk_usage_mb += sum(
                    f.stat().st_size for f in Path(directory).rglob('*') if f.is_file()
                ) / 1024 / 1024
        
        # Número de jobs ativos (placeholder - deve ser implementado conforme o sistema)
        active_jobs = getattr(self, '_active_jobs', 0)
        
        return ResourceUsage(
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            disk_usage_mb=disk_usage_mb,
            active_jobs=active_jobs,
            timestamp=time.time()
        )
    
    async def start_monitoring(self, interval_seconds: float = 30):
        """Inicia monitoramento contínuo"""
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval_seconds))
        logger.info("Resource monitoring started")
    
    async def stop_monitoring(self):
        """Para monitoramento"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")
    
    async def _monitor_loop(self, interval_seconds: float):
        """Loop de monitoramento"""
        while self._monitoring:
            try:
                usage = self.get_current_usage()
                exceeded = usage.exceeds_limits(self.limits)
                
                if any(exceeded.values()):
                    logger.warning(
                        "Resource limits exceeded",
                        extra={
                            "extra_fields": {
                                "usage": usage.__dict__,
                                "limits": self.limits.__dict__,
                                "exceeded": exceeded
                            }
                        }
                    )
                    
                    # Chama callbacks
                    for callback in self._callbacks:
                        try:
                            await callback(usage, exceeded)
                        except Exception as e:
                            logger.error(f"Error in resource callback: {e}")
                
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(interval_seconds)
    
    def set_active_jobs(self, count: int):
        """Define número de jobs ativos"""
        self._active_jobs = count


class TempFileManager:
    """Gerenciador seguro de arquivos temporários"""
    
    def __init__(self, base_dir: Path = None, max_age_minutes: float = 60):
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "audio_normalization"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_minutes = max_age_minutes
        self._temp_files = weakref.WeakSet()
        self._cleanup_lock = Lock()
    
    @contextmanager
    def create_temp_file(
        self,
        suffix: str = ".tmp",
        prefix: str = "audio_",
        auto_cleanup: bool = True
    ) -> Generator[Path, None, None]:
        """Context manager para arquivo temporário"""
        temp_path = None
        try:
            # Cria arquivo temporário
            fd, temp_path_str = tempfile.mkstemp(
                suffix=suffix,
                prefix=prefix,
                dir=str(self.base_dir)
            )
            os.close(fd)  # Fecha o file descriptor
            
            temp_path = Path(temp_path_str)
            self._temp_files.add(temp_path)
            
            logger.debug(f"Created temp file: {temp_path}")
            yield temp_path
            
        finally:
            # Cleanup automático
            if auto_cleanup and temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
    
    @contextmanager
    def create_temp_dir(
        self,
        suffix: str = "_tmp",
        prefix: str = "audio_",
        auto_cleanup: bool = True
    ) -> Generator[Path, None, None]:
        """Context manager para diretório temporário"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(
                suffix=suffix,
                prefix=prefix,
                dir=str(self.base_dir)
            ))
            
            logger.debug(f"Created temp dir: {temp_dir}")
            yield temp_dir
            
        finally:
            # Cleanup automático
            if auto_cleanup and temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp dir: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")
    
    def cleanup_old_files(self):
        """Remove arquivos antigos"""
        with self._cleanup_lock:
            cutoff_time = time.time() - (self.max_age_minutes * 60)
            removed_count = 0
            
            for file_path in self.base_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            removed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove old file {file_path}: {e}")
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old temporary files")


class ProcessingLimiter:
    """Limitador de processamento para controlar recursos"""
    
    def __init__(
        self,
        max_concurrent: int = 3,
        max_memory_mb: float = 512,
        max_processing_time_minutes: float = 30
    ):
        self.max_concurrent = max_concurrent
        self.max_memory_mb = max_memory_mb
        self.max_processing_time_seconds = max_processing_time_minutes * 60
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_processes = {}
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def acquire_processing_slot(
        self,
        job_id: str,
        estimated_memory_mb: float = None
    ) -> AsyncGenerator[None, None]:
        """Adquire slot de processamento com verificação de recursos"""
        
        # Verifica memória disponível
        if estimated_memory_mb:
            current_usage = psutil.virtual_memory().used / 1024 / 1024
            if current_usage + estimated_memory_mb > self.max_memory_mb:
                raise ResourceError(
                    f"Insufficient memory for processing: need {estimated_memory_mb}MB, "
                    f"available {self.max_memory_mb - current_usage}MB",
                    resource_type="memory"
                )
        
        # Adquire semáforo
        await self.semaphore.acquire()
        
        try:
            async with self._lock:
                self.active_processes[job_id] = {
                    "start_time": time.time(),
                    "estimated_memory_mb": estimated_memory_mb
                }
            
            logger.info(
                f"Processing slot acquired for job {job_id}",
                extra={
                    "extra_fields": {
                        "job_id": job_id,
                        "active_slots": len(self.active_processes),
                        "max_slots": self.max_concurrent
                    }
                }
            )
            
            yield
            
        finally:
            # Libera slot
            async with self._lock:
                self.active_processes.pop(job_id, None)
            
            self.semaphore.release()
            
            logger.info(f"Processing slot released for job {job_id}")
    
    async def check_timeouts(self):
        """Verifica e cancela processamentos que excederam timeout"""
        current_time = time.time()
        timed_out_jobs = []
        
        async with self._lock:
            for job_id, info in self.active_processes.items():
                if current_time - info["start_time"] > self.max_processing_time_seconds:
                    timed_out_jobs.append(job_id)
        
        for job_id in timed_out_jobs:
            logger.warning(f"Job {job_id} timed out after {self.max_processing_time_seconds}s")
            # Aqui você implementaria a lógica de cancelamento do job
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do limitador"""
        return {
            "active_processes": len(self.active_processes),
            "max_concurrent": self.max_concurrent,
            "available_slots": self.semaphore._value,
            "active_jobs": list(self.active_processes.keys())
        }


@contextmanager
def timeout_context(timeout_seconds: float, operation_name: str = "operation"):
    """Context manager para timeout de operações"""
    def timeout_handler(signum, frame):
        raise ProcessingTimeoutError(
            timeout_seconds=timeout_seconds,
            operation=operation_name
        )
    
    # Configura signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout_seconds))
    
    try:
        yield
    finally:
        # Restaura handler anterior
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@asynccontextmanager
async def async_timeout_context(timeout_seconds: float, operation_name: str = "operation"):
    """Context manager assíncrono para timeout"""
    try:
        async with asyncio.timeout(timeout_seconds):
            yield
    except asyncio.TimeoutError:
        raise ProcessingTimeoutError(
            timeout_seconds=timeout_seconds,
            operation=operation_name
        )


class FileManager:
    """Gerenciador seguro de arquivos com limpeza automática"""
    
    def __init__(self, base_dirs: Dict[str, Path]):
        self.base_dirs = {name: Path(path) for name, path in base_dirs.items()}
        self._ensure_directories()
        self._tracked_files = weakref.WeakSet()
    
    def _ensure_directories(self):
        """Garante que os diretórios existam"""
        for name, path in self.base_dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {name} -> {path}")
    
    @contextmanager
    def managed_file(
        self,
        directory_name: str,
        filename: str,
        auto_cleanup: bool = False
    ) -> Generator[Path, None, None]:
        """Context manager para arquivo gerenciado"""
        if directory_name not in self.base_dirs:
            raise ValueError(f"Unknown directory: {directory_name}")
        
        file_path = self.base_dirs[directory_name] / filename
        
        try:
            self._tracked_files.add(file_path)
            logger.debug(f"Managing file: {file_path}")
            yield file_path
            
        finally:
            if auto_cleanup and file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Auto-cleaned file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to auto-clean file {file_path}: {e}")
    
    def cleanup_directory(self, directory_name: str, max_age_hours: float = 24):
        """Limpa arquivos antigos de um diretório"""
        if directory_name not in self.base_dirs:
            return
        
        directory = self.base_dirs[directory_name]
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0
        
        for file_path in directory.iterdir():
            if file_path.is_file():
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        removed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove old file {file_path}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned {removed_count} old files from {directory_name}")
    
    def get_directory_size(self, directory_name: str) -> float:
        """Retorna tamanho do diretório em MB"""
        if directory_name not in self.base_dirs:
            return 0.0
        
        directory = self.base_dirs[directory_name]
        total_size = sum(
            f.stat().st_size for f in directory.rglob('*') if f.is_file()
        )
        return total_size / 1024 / 1024


class ResourcePool:
    """Pool de recursos com limite e timeout"""
    
    def __init__(self, max_size: int = 10, timeout_seconds: float = 30):
        self.max_size = max_size
        self.timeout_seconds = timeout_seconds
        self._pool = asyncio.Queue(maxsize=max_size)
        self._created_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> Any:
        """Adquire recurso do pool"""
        try:
            return await asyncio.wait_for(
                self._pool.get(),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise ResourceError(
                f"Timeout waiting for resource from pool ({self.timeout_seconds}s)",
                resource_type="pool"
            )
    
    async def release(self, resource: Any):
        """Libera recurso de volta ao pool"""
        try:
            self._pool.put_nowait(resource)
        except asyncio.QueueFull:
            logger.warning("Resource pool full, discarding resource")
    
    async def create_resource(self) -> Any:
        """Cria novo recurso (deve ser implementado por subclasses)"""
        raise NotImplementedError
    
    async def destroy_resource(self, resource: Any):
        """Destrói recurso (deve ser implementado por subclasses)"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do pool"""
        return {
            "pool_size": self._pool.qsize(),
            "max_size": self.max_size,
            "created_count": self._created_count
        }


# Importações necessárias para as exceções
from .exceptions import ResourceError, ProcessingTimeoutError