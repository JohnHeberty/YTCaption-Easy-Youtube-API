"""
Gerenciamento de recursos para Audio Transcriber Service
Monitoramento de sistema, gestão de arquivos temporários e limitação de processamento
"""
import asyncio
import os
import psutil
import tempfile
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass

from app.logging_config import get_logger
from app.exceptions import ResourceError

logger = get_logger(__name__)


@dataclass
class SystemHealth:
    """Informações de saúde do sistema"""
    healthy: bool
    timestamp: datetime
    checks: Dict[str, Any]
    warnings: List[str]


@dataclass
class ResourceUsage:
    """Informações de uso de recursos"""
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_percent: float
    disk_free_gb: float
    load_average: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None


class ResourceMonitor:
    """Monitor de recursos do sistema"""
    
    def __init__(self):
        self.cpu_threshold = 85.0
        self.memory_threshold = 85.0
        self.disk_threshold = 90.0
        self.gpu_memory_threshold = 90.0
        
        # Cache para evitar chamadas frequentes ao sistema
        self._last_check = 0
        self._cached_usage: Optional[ResourceUsage] = None
        self._cache_ttl = 5.0  # 5 segundos
    
    def get_resource_usage(self) -> ResourceUsage:
        """Obtém uso atual de recursos com cache"""
        now = time.time()
        
        if self._cached_usage and (now - self._last_check) < self._cache_ttl:
            return self._cached_usage
        
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memória
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Load average (apenas Unix)
            load_avg = None
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()[0]
            
            # GPU (se disponível)
            gpu_memory_percent = None
            gpu_memory_used_mb = None
            
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_memory_used = torch.cuda.memory_allocated(0)
                    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory
                    gpu_memory_percent = (gpu_memory_used / gpu_memory_total) * 100
                    gpu_memory_used_mb = gpu_memory_used / (1024**2)
            except ImportError:
                pass  # PyTorch não disponível
            
            usage = ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_percent=disk_percent,
                disk_free_gb=disk_free_gb,
                load_average=load_avg,
                gpu_memory_percent=gpu_memory_percent,
                gpu_memory_used_mb=gpu_memory_used_mb
            )
            
            self._cached_usage = usage
            self._last_check = now
            
            return usage
            
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            raise ResourceError(f"Failed to get resource usage: {e}")
    
    async def check_system_health(self) -> SystemHealth:
        """Verifica saúde geral do sistema"""
        try:
            usage = self.get_resource_usage()
            warnings = []
            checks = {}
            
            # Verifica CPU
            cpu_ok = usage.cpu_percent < self.cpu_threshold
            checks['cpu'] = {
                'status': 'ok' if cpu_ok else 'warning',
                'usage_percent': usage.cpu_percent,
                'threshold': self.cpu_threshold
            }
            if not cpu_ok:
                warnings.append(f"High CPU usage: {usage.cpu_percent:.1f}%")
            
            # Verifica memória
            memory_ok = usage.memory_percent < self.memory_threshold
            checks['memory'] = {
                'status': 'ok' if memory_ok else 'warning',
                'usage_percent': usage.memory_percent,
                'available_gb': usage.memory_available_gb,
                'threshold': self.memory_threshold
            }
            if not memory_ok:
                warnings.append(f"High memory usage: {usage.memory_percent:.1f}%")
            
            # Verifica disco
            disk_ok = usage.disk_percent < self.disk_threshold
            checks['disk'] = {
                'status': 'ok' if disk_ok else 'warning',
                'usage_percent': usage.disk_percent,
                'free_gb': usage.disk_free_gb,
                'threshold': self.disk_threshold
            }
            if not disk_ok:
                warnings.append(f"High disk usage: {usage.disk_percent:.1f}%")
            
            # Verifica GPU se disponível
            if usage.gpu_memory_percent is not None:
                gpu_ok = usage.gpu_memory_percent < self.gpu_memory_threshold
                checks['gpu'] = {
                    'status': 'ok' if gpu_ok else 'warning',
                    'memory_percent': usage.gpu_memory_percent,
                    'memory_used_mb': usage.gpu_memory_used_mb,
                    'threshold': self.gpu_memory_threshold
                }
                if not gpu_ok:
                    warnings.append(f"High GPU memory usage: {usage.gpu_memory_percent:.1f}%")
            
            # Load average (se disponível)
            if usage.load_average is not None:
                cpu_count = psutil.cpu_count()
                load_ok = usage.load_average < cpu_count * 0.8
                checks['load_average'] = {
                    'status': 'ok' if load_ok else 'warning',
                    'current': usage.load_average,
                    'cpu_count': cpu_count
                }
                if not load_ok:
                    warnings.append(f"High load average: {usage.load_average:.2f}")
            
            overall_healthy = len(warnings) == 0
            
            return SystemHealth(
                healthy=overall_healthy,
                timestamp=datetime.now(),
                checks=checks,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return SystemHealth(
                healthy=False,
                timestamp=datetime.now(),
                checks={},
                warnings=[f"Health check failed: {e}"]
            )
    
    def can_process_file(self, file_size_mb: float) -> bool:
        """Verifica se o sistema pode processar arquivo do tamanho especificado"""
        try:
            usage = self.get_resource_usage()
            
            # Estima memória necessária (aproximadamente 5x o tamanho do arquivo para Whisper)
            estimated_memory_gb = (file_size_mb * 5) / 1024
            
            # Verifica se há memória suficiente
            memory_available = usage.memory_available_gb
            
            # Mantém pelo menos 1GB livre
            return memory_available > (estimated_memory_gb + 1.0)
            
        except Exception as e:
            logger.warning(f"Could not determine processing capacity: {e}")
            return True  # Permite processamento se não conseguir determinar


class TempFileManager:
    """Gerenciador de arquivos temporários com cleanup automático"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "audio_transcriber"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Registro de arquivos criados para cleanup
        self._created_files: List[Path] = []
        self._created_dirs: List[Path] = []
    
    @contextmanager
    def temp_file(self, suffix: str = '', prefix: str = 'transcriber_'):
        """Context manager para arquivo temporário"""
        temp_path = None
        try:
            # Cria arquivo temporário
            fd, temp_path_str = tempfile.mkstemp(
                suffix=suffix,
                prefix=prefix,
                dir=self.base_dir
            )
            os.close(fd)  # Fecha file descriptor
            
            temp_path = Path(temp_path_str)
            self._created_files.append(temp_path)
            
            logger.debug(f"Created temp file: {temp_path}")
            yield temp_path
            
        finally:
            # Cleanup automático
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
    
    @contextmanager
    def temp_directory(self, prefix: str = 'transcriber_'):
        """Context manager para diretório temporário"""
        temp_dir = None
        try:
            # Cria diretório temporário
            temp_dir = Path(tempfile.mkdtemp(
                prefix=prefix,
                dir=self.base_dir
            ))
            self._created_dirs.append(temp_dir)
            
            logger.debug(f"Created temp directory: {temp_dir}")
            yield temp_dir
            
        finally:
            # Cleanup automático
            if temp_dir and temp_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")
    
    def cleanup_all(self):
        """Limpa todos os arquivos temporários criados"""
        import shutil
        
        # Limpa arquivos
        for file_path in self._created_files[:]:
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Cleaned up file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup file {file_path}: {e}")
        
        # Limpa diretórios
        for dir_path in self._created_dirs[:]:
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    logger.debug(f"Cleaned up directory: {dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup directory {dir_path}: {e}")
        
        self._created_files.clear()
        self._created_dirs.clear()
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Limpa arquivos temporários antigos"""
        import time
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0
        
        try:
            for file_path in self.base_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup old file {file_path}: {e}")
                
                elif file_path.is_dir() and file_path != self.base_dir:
                    try:
                        if file_path.stat().st_mtime < cutoff_time and not any(file_path.iterdir()):
                            file_path.rmdir()
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old directory: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup old directory {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old temporary files/directories")
                
        except Exception as e:
            logger.error(f"Error during old file cleanup: {e}")


class ProcessingLimiter:
    """Limitador de processamento concorrente"""
    
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_jobs: Dict[str, datetime] = {}
    
    @asynccontextmanager
    async def acquire_slot(self, job_id: str) -> AsyncGenerator[None, None]:
        """Adquire slot de processamento"""
        async with self._semaphore:
            self._active_jobs[job_id] = datetime.now()
            logger.debug(f"Acquired processing slot for job {job_id}")
            
            try:
                yield
            finally:
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
                    logger.debug(f"Released processing slot for job {job_id}")
    
    def get_active_jobs(self) -> Dict[str, datetime]:
        """Retorna jobs ativos"""
        return self._active_jobs.copy()
    
    def is_at_capacity(self) -> bool:
        """Verifica se está na capacidade máxima"""
        return len(self._active_jobs) >= self.max_concurrent
    
    async def wait_for_slot(self, timeout: Optional[float] = None) -> bool:
        """Aguarda slot disponível"""
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            self._semaphore.release()
            return True
        except asyncio.TimeoutError:
            return False


# Instâncias globais
_resource_monitor: Optional[ResourceMonitor] = None
_temp_file_manager: Optional[TempFileManager] = None
_processing_limiter: Optional[ProcessingLimiter] = None


def get_resource_monitor() -> ResourceMonitor:
    """Obtém instância global do resource monitor"""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def get_temp_file_manager() -> TempFileManager:
    """Obtém instância global do temp file manager"""
    global _temp_file_manager
    if _temp_file_manager is None:
        _temp_file_manager = TempFileManager()
    return _temp_file_manager


def get_processing_limiter() -> ProcessingLimiter:
    """Obtém instância global do processing limiter"""
    global _processing_limiter
    if _processing_limiter is None:
        from app.config import get_settings
        settings = get_settings()
        max_concurrent = getattr(settings.transcription, 'max_concurrent_jobs', 2)
        _processing_limiter = ProcessingLimiter(max_concurrent)
    return _processing_limiter