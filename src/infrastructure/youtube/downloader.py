"""
YouTube Downloader Implementation using yt-dlp.
Implementação concreta da interface IVideoDownloader.
"""
import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
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
    
    # Palavras-chave para detecção de idioma
    LANGUAGE_KEYWORDS = {
        'pt': [
            'brasil', 'portuguese', 'português', 'pt-br', 'legendado',
            'dublado', 'notícias', 'reportagem', 'entrevista', 'programa',
            'episódio', 'temporada', 'série'
        ],
        'en': [
            'english', 'subtitle', 'official', 'trailer', 'interview',
            'news', 'episode', 'season', 'series', 'documentary'
        ],
        'es': [
            'español', 'spanish', 'latino', 'castellano', 'noticias',
            'entrevista', 'capítulo', 'temporada'
        ],
        'fr': [
            'français', 'french', 'sous-titres', 'épisode', 'saison'
        ],
        'de': [
            'deutsch', 'german', 'untertitel', 'folge', 'staffel'
        ],
        'it': [
            'italiano', 'italian', 'sottotitoli', 'episodio', 'stagione'
        ],
        'ja': [
            'japanese', '日本語', 'nihongo', 'anime', 'manga'
        ],
        'ko': [
            'korean', '한국어', 'hangul', 'k-pop', 'kdrama'
        ],
        'ru': [
            'russian', 'русский', 'russkiy', 'субтитры'
        ],
        'zh': [
            'chinese', '中文', 'mandarin', 'cantonese'
        ]
    }
    
    # Caracteres especiais por idioma
    SPECIAL_CHARS = {
        'pt': 'àáâãäçèéêëìíîïòóôõöùúûüñ',
        'es': 'áéíóúüñ¿¡',
        'fr': 'àâæçéèêëïîôùûüÿœ',
        'de': 'äöüßẞ',
        'it': 'àèéìíîòóùú',
        'ja': 'ぁ-ゔァ-ヴー々〆〤一-龥',
        'ko': 'ㄱ-ㅎㅏ-ㅣ가-힣',
        'ru': 'а-яА-ЯёЁ',
        'zh': '一-龥'
    }
    
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
    
    def detect_language_from_text(self, text: str) -> Tuple[str, float]:
        """
        Detecta o idioma baseado em análise de texto.
        
        Args:
            text: Texto para análise (título, descrição, etc.)
            
        Returns:
            Tuple[str, float]: (código do idioma, confiança 0-1)
        """
        if not text:
            return 'unknown', 0.0
        
        text_lower = text.lower()
        scores = {}
        
        # Pontuação por palavras-chave
        for lang, keywords in self.LANGUAGE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[lang] = score
        
        # Pontuação por caracteres especiais
        for lang, chars in self.SPECIAL_CHARS.items():
            pattern = f'[{chars}]'
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                scores[lang] = scores.get(lang, 0) + (matches * 0.5)
        
        if not scores:
            return 'unknown', 0.0
        
        # Calcular idioma com maior pontuação
        max_lang = max(scores, key=scores.get)
        max_score = scores[max_lang]
        total_score = sum(scores.values())
        
        # Confiança normalizada
        confidence = min(max_score / (total_score + 1), 1.0)
        
        return max_lang, round(confidence, 2)
    
    async def get_video_info_with_language(self, url: YouTubeURL) -> Dict:
        """
        Obtém informações do vídeo incluindo detecção de idioma e legendas.
        
        Args:
            url: URL do YouTube
            
        Returns:
            Dict: Informações completas do vídeo
        """
        try:
            logger.info(f"Fetching detailed video info: {url.video_id}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'listsubtitles': True,
            }
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._get_info_sync,
                str(url),
                ydl_opts
            )
            
            # Detectar idioma do texto
            text_to_analyze = f"{info.get('title', '')} {info.get('description', '')}"
            detected_lang, confidence = self.detect_language_from_text(text_to_analyze)
            
            # Extrair legendas disponíveis
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            # Formatar legendas
            available_subtitles = []
            for lang in subtitles.keys():
                available_subtitles.append({
                    'language': lang,
                    'type': 'manual',
                    'auto_generated': False
                })
            
            for lang in automatic_captions.keys():
                if lang not in subtitles:  # Evitar duplicatas
                    available_subtitles.append({
                        'language': lang,
                        'type': 'auto',
                        'auto_generated': True
                    })
            
            # Recomendação de modelo Whisper baseado na duração
            duration = info.get('duration', 0)
            whisper_recommendation = self._get_whisper_recommendation(duration)
            
            return {
                'video_id': info.get('id'),
                'title': info.get('title'),
                'duration': duration,
                'description': info.get('description'),
                'uploader': info.get('uploader'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count'),
                'formats_available': len(info.get('formats', [])),
                'language_detection': {
                    'detected_language': detected_lang,
                    'confidence': confidence,
                    'method': 'text_analysis'
                },
                'available_subtitles': available_subtitles,
                'subtitle_languages': list(subtitles.keys()),
                'auto_caption_languages': list(automatic_captions.keys()),
                'whisper_recommendation': whisper_recommendation
            }
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Failed to get video info: {str(e)}")
            raise VideoDownloadError(f"Failed to get video info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting video info: {str(e)}")
            raise VideoDownloadError(f"Unexpected error: {str(e)}")
    
    def _get_whisper_recommendation(self, duration: int) -> Dict:
        """
        Recomenda modelo Whisper baseado na duração do vídeo.
        
        Args:
            duration: Duração em segundos
            
        Returns:
            Dict: Recomendações por modelo
        """
        models = {
            'tiny': {'speed': 32, 'quality': 'lowest'},
            'base': {'speed': 16, 'quality': 'low'},
            'small': {'speed': 6, 'quality': 'medium'},
            'medium': {'speed': 2, 'quality': 'high'},
            'large': {'speed': 1, 'quality': 'highest'}
        }
        
        recommendations = {}
        for model, config in models.items():
            estimated_time = duration / config['speed']
            recommendations[model] = {
                'estimated_time_seconds': int(estimated_time),
                'estimated_time_formatted': self._format_duration(int(estimated_time)),
                'quality': config['quality'],
                'recommended': model == 'base'  # Base como padrão
            }
        
        return recommendations
    
    def _format_duration(self, seconds: int) -> str:
        """Formata duração em formato legível."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

