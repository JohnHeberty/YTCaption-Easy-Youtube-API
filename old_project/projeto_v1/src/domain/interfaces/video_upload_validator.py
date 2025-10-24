"""
Interface para validação de vídeos enviados.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any


class IVideoUploadValidator(ABC):
    """Interface para validação de uploads de vídeo."""
    
    @abstractmethod
    async def validate_file(
        self,
        file_path: Path,
        max_size_mb: int,
        max_duration_seconds: int
    ) -> Dict[str, Any]:
        """
        Valida arquivo de vídeo/áudio.
        
        Args:
            file_path: Caminho do arquivo
            max_size_mb: Tamanho máximo em MB
            max_duration_seconds: Duração máxima em segundos
            
        Returns:
            Dict com metadata: duration, codec, bitrate, etc.
            
        Raises:
            ValidationError: Se validação falhar
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list:
        """Retorna lista de formatos suportados."""
        pass
