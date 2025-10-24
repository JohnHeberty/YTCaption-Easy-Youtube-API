"""
File Cleanup Manager - Gerenciamento automático de arquivos temporários.

Features:
- Context managers para garantir cleanup
- Background task de limpeza periódica
- Cleanup automático em caso de erro
- TTL (Time-To-Live) configurável
- Zero memory leaks
"""
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List, Set
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from loguru import logger
import threading


class TempFileContext:
    """Context manager para arquivos temporários com auto-cleanup."""
    
    def __init__(self, file_path: Path, cleanup_on_error: bool = True):
        """
        Inicializa context manager.
        
        Args:
            file_path: Caminho do arquivo temporário
            cleanup_on_error: Se True, limpa arquivo mesmo em caso de erro
        """
        self.file_path = file_path
        self.cleanup_on_error = cleanup_on_error
        self._should_cleanup = True
    
    def __enter__(self) -> Path:
        """Entra no contexto."""
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Sai do contexto e limpa arquivo.
        
        Args:
            exc_type: Tipo da exceção (se houver)
            exc_val: Valor da exceção
            exc_tb: Traceback
        """
        if self._should_cleanup and (self.cleanup_on_error or exc_type is None):
            self._cleanup()
        
        return False  # Não suprimir exceções
    
    def _cleanup(self):
        """Limpa arquivo temporário."""
        try:
            if self.file_path.exists():
                self.file_path.unlink()
                logger.debug(f"Cleaned up temp file: {self.file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {self.file_path}: {e}")
    
    def keep(self):
        """Marca arquivo para não ser limpo."""
        self._should_cleanup = False


@asynccontextmanager
async def temp_file_async(file_path: Path, cleanup_on_error: bool = True):
    """
    Context manager assíncrono para arquivos temporários.
    
    Args:
        file_path: Caminho do arquivo
        cleanup_on_error: Limpar em caso de erro
        
    Yields:
        Path do arquivo
    """
    try:
        yield file_path
    finally:
        if cleanup_on_error or not asyncio.current_task().cancelled():
            try:
                if file_path.exists():
                    await asyncio.to_thread(file_path.unlink)
                    logger.debug(f"Async cleaned up: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to async cleanup {file_path}: {e}")


class FileCleanupManager:
    """
    Gerenciador de limpeza automática de arquivos temporários.
    
    Features:
    - Tracking de arquivos criados
    - Limpeza periódica de arquivos antigos
    - Cleanup forçado ao shutdown
    - Thread-safe
    """
    
    def __init__(
        self,
        base_temp_dir: Path,
        default_ttl_hours: int = 24,
        cleanup_interval_minutes: int = 30
    ):
        """
        Inicializa gerenciador de cleanup.
        
        Args:
            base_temp_dir: Diretório base de arquivos temporários
            default_ttl_hours: TTL padrão em horas
            cleanup_interval_minutes: Intervalo de limpeza automática
        """
        self.base_temp_dir = Path(base_temp_dir)
        self.default_ttl_hours = default_ttl_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        
        # Tracking de arquivos criados
        self._tracked_files: Set[Path] = set()
        self._lock = threading.RLock()
        
        # Background task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(
            f"File cleanup manager initialized: "
            f"ttl={default_ttl_hours}h, interval={cleanup_interval_minutes}min"
        )
    
    def track_file(self, file_path: Path):
        """
        Adiciona arquivo ao tracking para limpeza futura.
        
        Args:
            file_path: Caminho do arquivo
        """
        with self._lock:
            self._tracked_files.add(file_path)
            logger.debug(f"Tracking file: {file_path} (total: {len(self._tracked_files)})")
    
    def untrack_file(self, file_path: Path):
        """
        Remove arquivo do tracking (arquivo foi movido/processado).
        
        Args:
            file_path: Caminho do arquivo
        """
        with self._lock:
            self._tracked_files.discard(file_path)
    
    async def cleanup_file(self, file_path: Path) -> bool:
        """
        Remove arquivo específico.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se removido com sucesso
        """
        try:
            if file_path.exists():
                await asyncio.to_thread(file_path.unlink)
                logger.debug(f"Cleaned up file: {file_path}")
                
                with self._lock:
                    self._tracked_files.discard(file_path)
                
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup file {file_path}: {e}")
            return False
    
    async def cleanup_directory(self, directory: Path, recursive: bool = True) -> bool:
        """
        Remove diretório e seu conteúdo.
        
        Args:
            directory: Diretório a remover
            recursive: Se True, remove recursivamente
            
        Returns:
            True se removido com sucesso
        """
        try:
            if not directory.exists():
                return True
            
            if recursive:
                await asyncio.to_thread(shutil.rmtree, directory)
            else:
                await asyncio.to_thread(directory.rmdir)
            
            logger.debug(f"Cleaned up directory: {directory}")
            
            # Remover arquivos tracked dentro do diretório
            with self._lock:
                to_remove = {f for f in self._tracked_files if directory in f.parents}
                self._tracked_files -= to_remove
            
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup directory {directory}: {e}")
            return False
    
    async def cleanup_old_files(
        self,
        max_age_hours: Optional[int] = None
    ) -> dict:
        """
        Remove arquivos mais antigos que max_age_hours.
        
        Args:
            max_age_hours: Idade máxima em horas (None = usar default)
            
        Returns:
            Dict com estatísticas de limpeza
        """
        if max_age_hours is None:
            max_age_hours = self.default_ttl_hours
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        removed_count = 0
        removed_size_bytes = 0
        errors = 0
        
        logger.info(f"Starting cleanup: max_age={max_age_hours}h")
        
        try:
            # Limpar arquivos tracked
            with self._lock:
                files_to_check = list(self._tracked_files)
            
            for file_path in files_to_check:
                try:
                    if not file_path.exists():
                        with self._lock:
                            self._tracked_files.discard(file_path)
                        continue
                    
                    # Verificar idade
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_time < cutoff_time:
                        file_size = file_path.stat().st_size
                        
                        await asyncio.to_thread(file_path.unlink)
                        
                        removed_count += 1
                        removed_size_bytes += file_size
                        
                        with self._lock:
                            self._tracked_files.discard(file_path)
                        
                        logger.debug(f"Removed old file: {file_path.name}")
                
                except Exception as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")
                    errors += 1
            
            # Limpar diretórios vazios no base_temp_dir
            if self.base_temp_dir.exists():
                for item in self.base_temp_dir.iterdir():
                    if item.is_dir():
                        try:
                            # Verificar se diretório está vazio ou antigo
                            if not any(item.iterdir()):
                                await asyncio.to_thread(item.rmdir)
                                logger.debug(f"Removed empty directory: {item.name}")
                            else:
                                # Verificar idade do diretório
                                dir_time = datetime.fromtimestamp(item.stat().st_mtime)
                                if dir_time < cutoff_time:
                                    await asyncio.to_thread(shutil.rmtree, item)
                                    removed_count += 1
                                    logger.debug(f"Removed old directory: {item.name}")
                        except Exception as e:
                            logger.warning(f"Failed to remove directory {item}: {e}")
                            errors += 1
            
            removed_size_mb = removed_size_bytes / (1024 * 1024)
            
            logger.info(
                f"Cleanup completed: removed={removed_count}, "
                f"size={removed_size_mb:.2f}MB, errors={errors}"
            )
            
            return {
                "removed_count": removed_count,
                "removed_size_bytes": removed_size_bytes,
                "removed_size_mb": round(removed_size_mb, 2),
                "errors": errors,
                "tracked_files_remaining": len(self._tracked_files)
            }
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                "error": str(e),
                "removed_count": removed_count,
                "errors": errors
            }
    
    async def _periodic_cleanup_loop(self):
        """Loop de limpeza periódica (roda em background)."""
        logger.info(
            f"Starting periodic cleanup loop: interval={self.cleanup_interval_minutes}min"
        )
        
        while self._running:
            try:
                # Aguardar intervalo
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                
                if not self._running:
                    break
                
                # Executar limpeza
                logger.info("Running periodic cleanup...")
                await self.cleanup_old_files()
            
            except asyncio.CancelledError:
                logger.info("Periodic cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup loop: {e}")
    
    def start_periodic_cleanup(self):
        """Inicia limpeza periódica em background."""
        if self._running:
            logger.warning("Periodic cleanup already running")
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())
        logger.info("Periodic cleanup started")
    
    async def stop_periodic_cleanup(self):
        """Para limpeza periódica."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Periodic cleanup stopped")
    
    async def cleanup_all_tracked(self) -> int:
        """
        Remove todos os arquivos tracked (usado em shutdown).
        
        Returns:
            Número de arquivos removidos
        """
        with self._lock:
            files_to_remove = list(self._tracked_files)
        
        removed = 0
        for file_path in files_to_remove:
            if await self.cleanup_file(file_path):
                removed += 1
        
        logger.info(f"Cleaned up all tracked files: {removed} files")
        return removed
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do gerenciador.
        
        Returns:
            Dict com estatísticas
        """
        with self._lock:
            tracked_count = len(self._tracked_files)
            
            total_size = 0
            for file_path in self._tracked_files:
                try:
                    if file_path.exists():
                        total_size += file_path.stat().st_size
                except Exception:
                    pass
        
        return {
            "tracked_files": tracked_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "periodic_cleanup_running": self._running,
            "default_ttl_hours": self.default_ttl_hours,
            "cleanup_interval_minutes": self.cleanup_interval_minutes
        }
