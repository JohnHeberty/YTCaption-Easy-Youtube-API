"""
Interface: IStorageService
Define o contrato para serviços de armazenamento.
Segue o princípio de Dependency Inversion (SOLID).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class IStorageService(ABC):
    """Interface para gerenciamento de armazenamento temporário."""
    
    @abstractmethod
    async def create_temp_directory(self) -> Path:
        """
        Cria um diretório temporário.
        
        Returns:
            Path: Caminho do diretório criado
        """
        pass
    
    @abstractmethod
    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Remove arquivos antigos do armazenamento temporário.
        
        Args:
            max_age_hours: Idade máxima dos arquivos em horas
            
        Returns:
            int: Número de arquivos removidos
        """
        pass
    
    @abstractmethod
    async def cleanup_directory(self, directory: Path) -> bool:
        """
        Remove um diretório e todo seu conteúdo.
        
        Args:
            directory: Diretório a ser removido
            
        Returns:
            bool: True se removido com sucesso
        """
        pass
    
    @abstractmethod
    async def get_temp_files(self) -> List[Path]:
        """
        Lista todos os arquivos temporários.
        
        Returns:
            List[Path]: Lista de caminhos dos arquivos
        """
        pass
    
    @abstractmethod
    async def get_storage_usage(self) -> dict:
        """
        Obtém informações sobre uso de armazenamento.
        
        Returns:
            dict: Informações de uso (total, usado, livre)
        """
        pass
