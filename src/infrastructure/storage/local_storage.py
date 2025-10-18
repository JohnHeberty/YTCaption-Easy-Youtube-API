"""
Storage Service Implementation.
Gerencia armazenamento temporário de arquivos com limpeza automática.
"""
import asyncio
import shutil
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
from loguru import logger

from src.domain.interfaces import IStorageService
from src.domain.exceptions import StorageError


class LocalStorageService(IStorageService):
    """
    Serviço de armazenamento local para arquivos temporários.
    Implementa limpeza automática de arquivos antigos.
    """
    
    def __init__(self, base_temp_dir: str = "./temp"):
        """
        Inicializa o serviço de storage.
        
        Args:
            base_temp_dir: Diretório base para arquivos temporários
        """
        self.base_temp_dir = Path(base_temp_dir)
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage service initialized: {self.base_temp_dir}")
    
    async def create_temp_directory(self) -> Path:
        """
        Cria um diretório temporário único.
        
        Returns:
            Path: Caminho do diretório criado
            
        Raises:
            StorageError: Se não conseguir criar o diretório
        """
        try:
            # Criar subdiretório com timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            temp_dir = self.base_temp_dir / timestamp
            
            loop = asyncio.get_event_loop()
            # Criar diretório com permissões 0o755
            await loop.run_in_executor(
                None, 
                lambda: temp_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            )
            
            logger.debug(f"Created temp directory: {temp_dir}")
            return temp_dir
            
        except Exception as e:
            logger.error(f"Failed to create temp directory: {str(e)}")
            raise StorageError(f"Failed to create temp directory: {str(e)}")
    
    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Remove arquivos mais antigos que max_age_hours.
        
        Args:
            max_age_hours: Idade máxima dos arquivos em horas
            
        Returns:
            int: Número de arquivos/diretórios removidos
        """
        try:
            logger.info(f"Starting cleanup: max_age={max_age_hours}h")
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            removed_count = 0
            
            if not self.base_temp_dir.exists():
                return 0
            
            # Iterar sobre diretórios temporários
            for item in self.base_temp_dir.iterdir():
                try:
                    # Verificar idade do arquivo/diretório
                    item_time = datetime.fromtimestamp(item.stat().st_mtime)
                    
                    if item_time < cutoff_time:
                        if item.is_dir():
                            shutil.rmtree(item)
                            logger.debug(f"Removed old directory: {item.name}")
                        else:
                            item.unlink()
                            logger.debug(f"Removed old file: {item.name}")
                        
                        removed_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to remove {item}: {str(e)}")
                    continue
            
            logger.info(f"Cleanup completed: {removed_count} items removed")
            return removed_count
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            raise StorageError(f"Failed to cleanup old files: {str(e)}")
    
    async def cleanup_directory(self, directory: Path) -> bool:
        """
        Remove um diretório específico e todo seu conteúdo.
        
        Args:
            directory: Diretório a ser removido
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            if not directory.exists():
                logger.debug(f"Directory does not exist: {directory}")
                return True
            
            if not directory.is_dir():
                logger.warning(f"Path is not a directory: {directory}")
                return False
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, directory)
            
            logger.debug(f"Removed directory: {directory}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove directory {directory}: {str(e)}")
            return False
    
    async def get_temp_files(self) -> List[Path]:
        """
        Lista todos os arquivos e diretórios temporários.
        
        Returns:
            List[Path]: Lista de caminhos
        """
        try:
            if not self.base_temp_dir.exists():
                return []
            
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: list(self.base_temp_dir.rglob("*"))
            )
            
            return [item for item in items if item.is_file()]
            
        except Exception as e:
            logger.error(f"Failed to list temp files: {str(e)}")
            return []
    
    async def get_storage_usage(self) -> dict:
        """
        Obtém informações sobre uso de armazenamento.
        
        Returns:
            dict: Informações de uso
        """
        try:
            if not self.base_temp_dir.exists():
                return {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "total_size_mb": 0.0,
                    "oldest_file": None,
                    "newest_file": None
                }
            
            files = await self.get_temp_files()
            
            if not files:
                return {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "total_size_mb": 0.0,
                    "oldest_file": None,
                    "newest_file": None
                }
            
            # Calcular tamanho total
            total_size = sum(f.stat().st_size for f in files if f.exists())
            
            # Encontrar arquivos mais antigos e mais novos
            file_times = [(f, f.stat().st_mtime) for f in files if f.exists()]
            oldest = min(file_times, key=lambda x: x[1]) if file_times else None
            newest = max(file_times, key=lambda x: x[1]) if file_times else None
            
            return {
                "total_files": len(files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_file": {
                    "path": str(oldest[0]),
                    "age_hours": round((datetime.utcnow().timestamp() - oldest[1]) / 3600, 2)
                } if oldest else None,
                "newest_file": {
                    "path": str(newest[0]),
                    "age_hours": round((datetime.utcnow().timestamp() - newest[1]) / 3600, 2)
                } if newest else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage usage: {str(e)}")
            return {
                "error": str(e)
            }
