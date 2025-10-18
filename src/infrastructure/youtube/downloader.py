"""
YouTube Downloader Implementation using yt-dlp.
Implementação concreta da interface IVideoDownloader.
"""
import asyncio
from pathlib import Path
from typing import Optional
import yt_dlp
from loguru import logger

from src.domain.interfaces import IVideoDownloader
from src.domain.value_objects import YouTubeURL
from src.domain.entities import VideoFile
from src.domain.exceptions import VideoDownloadError


class YouTubeDownloader(IVideoDownloader):
    """
    Implementação de downloader do YouTube usando yt-dlp.
    Baixa vídeos na pior qualidade para otimizar extração de áudio.
    """
    
    def __init__(
        self,
        output_template: str = "%(id)s.%(ext)s",
        max_filesize: Optional[int] = None,
        timeout: int = 300
    ):
        """
        Inicializa o downloader.
        
        Args:
            output_template: Template para nome do arquivo
            max_filesize: Tamanho máximo do arquivo em bytes
            timeout: Timeout para download em segundos
        """
        self.output_template = output_template
        self.max_filesize = max_filesize
        self.timeout = timeout
    
    async def download(
        self, 
        url: YouTubeURL, 
        output_path: Path,
        validate_duration: bool = True,
        max_duration: Optional[int] = None
    ) -> VideoFile:
        """
        Baixa vídeo do YouTube na pior qualidade (focado em áudio).
        
        Args:
            url: URL do YouTube
            output_path: Diretório de saída
            validate_duration: Se deve validar a duração antes do download
            max_duration: Duração máxima permitida em segundos
            
        Returns:
            VideoFile: Arquivo de vídeo baixado
            
        Raises:
            VideoDownloadError: Se houver erro no download
        """
        try:
            logger.info(f"Starting download: {url.video_id}")
            
            # Validar duração antes de baixar (para vídeos longos)
            if validate_duration:
                info = await self.get_video_info(url)
                duration = info.get('duration', 0)
                
                if duration > 0:
                    duration_formatted = f"{duration//3600}h {(duration%3600)//60}m {duration%60}s"
                    logger.info(f"Video duration: {duration}s (~{duration_formatted})")
                    
                    if max_duration and duration > max_duration:
                        max_formatted = f"{max_duration//3600}h {(max_duration%3600)//60}m"
                        raise VideoDownloadError(
                            f"Video too long: {duration_formatted} "
                            f"(maximum allowed: {max_formatted})"
                        )
                    
                    # Estimar tempo de processamento
                    estimated_processing = duration * 0.5  # Base model ~0.5x realtime
                    est_formatted = f"{int(estimated_processing//60)}m {int(estimated_processing%60)}s"
                    logger.info(f"Estimated processing time: ~{est_formatted}")
            
            # Garantir que o diretório existe
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Configurações do yt-dlp para baixar pior qualidade (menor arquivo)
            ydl_opts = {
                'format': 'worstaudio/worst',  # Pior qualidade de áudio/vídeo
                'outtmpl': str(output_path / self.output_template),
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': self.timeout,
                'nocheckcertificate': True,
                'prefer_insecure': True,
            }
            
            if self.max_filesize:
                ydl_opts['max_filesize'] = self.max_filesize
            
            # Executar download em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(
                None,
                self._download_sync,
                str(url),
                ydl_opts
            )
            
            # Criar entidade VideoFile
            file_path = Path(info_dict['filepath'])
            
            if not file_path.exists():
                raise VideoDownloadError(f"Downloaded file not found: {file_path}")
            
            video_file = VideoFile(
                file_path=file_path,
                original_url=str(url),
                file_size_bytes=file_path.stat().st_size,
                format=info_dict.get('ext', 'unknown')
            )
            
            logger.info(
                f"Download completed: {url.video_id} "
                f"({video_file.file_size_mb:.2f} MB)"
            )
            
            return video_file
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            raise VideoDownloadError(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected download error: {str(e)}")
            raise VideoDownloadError(f"Unexpected error during download: {str(e)}")
    
    def _download_sync(self, url: str, ydl_opts: dict) -> dict:
        """
        Executa download síncrono.
        
        Args:
            url: URL do vídeo
            ydl_opts: Opções do yt-dlp
            
        Returns:
            dict: Informações do vídeo baixado
        """
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Obter caminho do arquivo baixado
            if 'requested_downloads' in info and info['requested_downloads']:
                filepath = info['requested_downloads'][0]['filepath']
            else:
                filepath = ydl.prepare_filename(info)
            
            return {
                'filepath': filepath,
                'ext': info.get('ext', 'unknown'),
                'title': info.get('title', 'unknown'),
                'duration': info.get('duration', 0)
            }
    
    async def get_video_info(self, url: YouTubeURL) -> dict:
        """
        Obtém informações do vídeo sem baixar.
        
        Args:
            url: URL do YouTube
            
        Returns:
            dict: Informações do vídeo
            
        Raises:
            VideoDownloadError: Se houver erro ao obter informações
        """
        try:
            logger.info(f"Fetching video info: {url.video_id}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
            }
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._get_info_sync,
                str(url),
                ydl_opts
            )
            
            return {
                'video_id': info.get('id'),
                'title': info.get('title'),
                'duration': info.get('duration'),
                'description': info.get('description'),
                'uploader': info.get('uploader'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count'),
                'formats_available': len(info.get('formats', []))
            }
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Failed to get video info: {str(e)}")
            raise VideoDownloadError(f"Failed to get video info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting video info: {str(e)}")
            raise VideoDownloadError(f"Unexpected error: {str(e)}")
    
    def _get_info_sync(self, url: str, ydl_opts: dict) -> dict:
        """
        Obtém informações síncronas do vídeo.
        
        Args:
            url: URL do vídeo
            ydl_opts: Opções do yt-dlp
            
        Returns:
            dict: Informações do vídeo
        """
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
