"""
Use Case: Cleanup Old Files
Remove arquivos temporários antigos.
"""
from loguru import logger

from src.domain.interfaces import IStorageService


class CleanupOldFilesUseCase:
    """Use Case para limpeza de arquivos antigos."""
    
    def __init__(
        self,
        storage_service: IStorageService,
        max_age_hours: int = 24
    ):
        """
        Inicializa o use case.
        
        Args:
            storage_service: Serviço de armazenamento
            max_age_hours: Idade máxima dos arquivos em horas
        """
        self.storage_service = storage_service
        self.max_age_hours = max_age_hours
    
    async def execute(self) -> dict:
        """
        Executa a limpeza de arquivos antigos.
        
        Returns:
            dict: Informações sobre a limpeza
        """
        logger.info(f"Starting cleanup: max_age={self.max_age_hours}h")
        
        try:
            # Obter uso antes da limpeza
            usage_before = await self.storage_service.get_storage_usage()
            
            # Limpar arquivos antigos
            removed_count = await self.storage_service.cleanup_old_files(
                self.max_age_hours
            )
            
            # Obter uso após limpeza
            usage_after = await self.storage_service.get_storage_usage()
            
            result = {
                "success": True,
                "removed_count": removed_count,
                "storage_before_mb": usage_before.get("total_size_mb", 0),
                "storage_after_mb": usage_after.get("total_size_mb", 0),
                "freed_space_mb": round(
                    usage_before.get("total_size_mb", 0) - 
                    usage_after.get("total_size_mb", 0),
                    2
                )
            }
            
            logger.info(
                f"Cleanup completed: {removed_count} items removed, "
                f"{result['freed_space_mb']} MB freed"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "removed_count": 0
            }
