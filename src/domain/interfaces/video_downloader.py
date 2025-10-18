"""
Interface: IVideoDownloader
Define o contrato para downloaders de vídeo.
Segue o princípio de Dependency Inversion (SOLID).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from src.domain.value_objects import YouTubeURL
from src.domain.entities import VideoFile


class IVideoDownloader(ABC):
    """Interface para download de vídeos."""
    
    @abstractmethod
    async def download(self, url: YouTubeURL, output_path: Path) -> VideoFile:
        """
        Baixa um vídeo do YouTube.
        
        Args:
            url: URL do vídeo
            output_path: Caminho onde o vídeo será salvo
            
        Returns:
            VideoFile: Entidade representando o arquivo baixado
            
        Raises:
            VideoDownloadError: Se houver erro no download
        """
        pass
    
    @abstractmethod
    async def get_video_info(self, url: YouTubeURL) -> dict:
        """
        Obtém informações sobre o vídeo sem baixá-lo.
        
        Args:
            url: URL do vídeo
            
        Returns:
            dict: Informações do vídeo
            
        Raises:
            VideoDownloadError: Se houver erro ao obter informações
        """
        pass
