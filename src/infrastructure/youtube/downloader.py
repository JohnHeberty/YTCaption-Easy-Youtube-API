"""
YouTube Downloader Implementation using yt-dlp.
Implementação concreta da interface IVideoDownloader.

v2.1: Retry logic com exponential backoff.
v2.2: Circuit breaker próprio integrado.
v3.0: YouTube Download Resilience System
      - Multi-strategy download (7 fallback strategies)
      - Rate limiting (sliding window + exponential backoff)
      - User-Agent rotation (17 UAs + fake-useragent)
      - Tor proxy support (free, anonymous)
      - Enhanced network diagnostics
      - Prometheus metrics integration
"""
import asyncio
import re
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
import yt_dlp
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from src.domain.interfaces import IVideoDownloader
from src.domain.value_objects import YouTubeURL
from src.domain.entities import VideoFile
from src.domain.exceptions import VideoDownloadError, NetworkError, AudioTooLongError
from src.infrastructure.utils import CircuitBreaker, CircuitBreakerOpenError

# v3.0: Import resilience system modules
from .download_config import get_youtube_config
from .download_strategies import get_strategy_manager
from .user_agent_rotator import get_ua_rotator
from .rate_limiter import get_rate_limiter
from .proxy_manager import get_proxy_manager
from .metrics import (
    record_download_attempt,
    record_download_error,
    record_rate_limit_wait,
    update_rate_limit_gauges,
    record_user_agent_rotation,
    record_proxy_request,
    set_tor_status,
    record_info_request,
    set_resilience_config
)


# Circuit Breaker global para YouTube API
_youtube_circuit_breaker = CircuitBreaker(
    name="youtube_api",
    failure_threshold=5,
    timeout_seconds=60,
    half_open_max_calls=3
)


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
        
        # v3.0: Inicializar resilience system
        self.config = get_youtube_config()
        self.strategy_manager = get_strategy_manager()
        self.ua_rotator = get_ua_rotator()
        self.rate_limiter = get_rate_limiter()
        self.proxy_manager = get_proxy_manager()
        
        # v3.0: Configurar métricas do Prometheus
        set_resilience_config({
            'max_retries': str(self.config.max_retries),
            'requests_per_minute': str(self.config.requests_per_minute),
            'requests_per_hour': str(self.config.requests_per_hour),
            'tor_enabled': str(self.config.enable_tor_proxy),
            'multi_strategy_enabled': str(self.config.enable_multi_strategy),
            'user_agent_rotation_enabled': str(self.config.enable_user_agent_rotation)
        })
        set_tor_status(self.config.enable_tor_proxy)
        
        logger.info("✅ YouTubeDownloader initialized with v3.0 Resilience System + Prometheus metrics")
    
    async def download(
        self, 
        url: YouTubeURL, 
        output_path: Path,
        validate_duration: bool = True,
        max_duration: Optional[int] = None
    ) -> VideoFile:
        """
        Baixa vídeo do YouTube na pior qualidade (focado em áudio).
        
        v2.2: Circuit breaker custom + retry com exponential backoff.
        
        Args:
            url: URL do YouTube
            output_path: Diretório de saída
            validate_duration: Se deve validar a duração antes do download
            max_duration: Duração máxima permitida em segundos
            
        Returns:
            VideoFile: Arquivo de vídeo baixado
            
        Raises:
            VideoDownloadError: Se houver erro no download
            AudioTooLongError: Se vídeo exceder duração máxima
            CircuitBreakerOpenError: Se circuit breaker estiver aberto
        """
        # Envolve a lógica de download com Circuit Breaker (versão async)
        return await _youtube_circuit_breaker.acall(self._download_internal, url, output_path, validate_duration, max_duration)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=retry_if_exception_type((yt_dlp.utils.DownloadError, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no),
        reraise=True
    )
    async def _download_internal(
        self,
        url: YouTubeURL,
        output_path: Path,
        validate_duration: bool,
        max_duration: Optional[int]
    ) -> VideoFile:
        """
        Método interno com retry logic - chamado pelo Circuit Breaker.
        v3.0: Multi-strategy download com rate limiting e proxy support.
        """
        try:
            logger.info(f"🔽 Starting download (v3.0): {url.video_id}")
            
            # v3.0: Rate limiting ANTES de qualquer tentativa
            await self.rate_limiter.wait_if_needed()
            
            # Validar duração antes de baixar (para vídeos longos)
            if validate_duration:
                info = await self.get_video_info(url)
                duration = info.get('duration', 0)
                
                if duration > 0:
                    duration_formatted = f"{duration//3600}h {(duration%3600)//60}m {duration%60}s"
                    logger.info(f"📹 Video duration: {duration}s (~{duration_formatted})")
                    
                    if max_duration and duration > max_duration:
                        max_formatted = f"{max_duration//3600}h {(max_duration%3600)//60}m"
                        logger.error(
                            f"❌ Video too long: {duration}s > {max_duration}s"
                        )
                        raise AudioTooLongError(duration, max_duration)
                    
                    # Estimar tempo de processamento
                    estimated_processing = duration * 0.5  # Base model ~0.5x realtime
                    est_formatted = f"{int(estimated_processing//60)}m {int(estimated_processing%60)}s"
                    logger.info(f"⏱️  Estimated processing time: ~{est_formatted}")
            
            # Garantir que o diretório existe
            output_path.mkdir(parents=True, exist_ok=True)
            
            # v3.0: Multi-strategy fallback loop
            strategies = self.strategy_manager.get_strategies()
            last_error = None
            
            for strategy in strategies:
                try:
                    logger.info(f"🎯 Trying strategy: {strategy.name} (priority {strategy.priority})")
                    
                    # v3.0: Track tempo de download
                    download_start_time = time.time()
                    
                    # Configurações base do yt-dlp
                    ydl_opts = {
                        'format': 'worstaudio/worst',  # Pior qualidade de áudio/vídeo
                        'outtmpl': str(output_path / self.output_template),
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'socket_timeout': self.config.download_timeout,
                        'nocheckcertificate': True,
                        'prefer_insecure': True,
                    }
                    
                    if self.max_filesize:
                        ydl_opts['max_filesize'] = self.max_filesize
                    
                    # v3.0: Merge strategy-specific options
                    if strategy.extra_opts:
                        ydl_opts.update(strategy.extra_opts)
                    
                    # v3.0: User-Agent rotation
                    if self.config.enable_user_agent_rotation:
                        user_agent = self.ua_rotator.get_random()
                        logger.debug(f"🔄 Using User-Agent: {user_agent[:50]}...")
                        record_user_agent_rotation('random')
                    else:
                        user_agent = strategy.user_agent
                    
                    ydl_opts['http_headers'] = {
                        'User-Agent': user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                        'Sec-Fetch-Mode': 'navigate',
                    }
                    
                    # v3.0: Tor proxy support
                    proxy_type = 'none'
                    if self.config.enable_tor_proxy:
                        proxy_url = self.proxy_manager.get_tor_proxy()
                        if proxy_url:
                            ydl_opts['proxy'] = proxy_url
                            proxy_type = 'tor'
                            logger.info(f"🧅 Using Tor proxy: {proxy_url}")
                    
                    # Executar download em thread separada
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
                    
                    # v3.0: Report success
                    self.rate_limiter.report_success()
                    self.strategy_manager.log_strategy_success(strategy)
                    
                    # v3.0: Record metrics
                    download_duration = time.time() - download_start_time
                    record_download_attempt(
                        strategy=strategy.name,
                        success=True,
                        duration=download_duration,
                        size_bytes=video_file.file_size_bytes
                    )
                    record_proxy_request(proxy_type, success=True)
                    
                    logger.info(
                        f"✅ Download completed with strategy '{strategy.name}': {url.video_id} "
                        f"({video_file.file_size_mb:.2f} MB, {download_duration:.1f}s)"
                    )
                    
                    return video_file
                    
                except (yt_dlp.utils.DownloadError, ConnectionError, TimeoutError) as e:
                    last_error = e
                    self.strategy_manager.log_strategy_failure(strategy, str(e))
                    
                    # v3.0: Record metrics
                    download_duration = time.time() - download_start_time
                    record_download_attempt(
                        strategy=strategy.name,
                        success=False,
                        duration=download_duration
                    )
                    record_proxy_request(proxy_type, success=False)
                    
                    # Detectar tipo de erro
                    error_str = str(e).lower()
                    if '403' in error_str:
                        error_type = '403_forbidden'
                    elif '404' in error_str:
                        error_type = '404_not_found'
                    elif 'timeout' in error_str:
                        error_type = 'timeout'
                    elif 'network' in error_str or 'unreachable' in error_str:
                        error_type = 'network'
                    else:
                        error_type = 'other'
                    
                    record_download_error(error_type, strategy.name)
                    
                    logger.warning(f"⚠️ Strategy '{strategy.name}' failed: {str(e)}")
                    
                    # Se não for a última estratégia, continuar
                    if strategy != strategies[-1]:
                        logger.info("🔄 Trying next strategy...")
                        continue
                    else:
                        # Última estratégia falhou - propagar erro
                        raise
            
            # Se chegou aqui, todas as estratégias falharam
            if last_error:
                self.rate_limiter.report_error()
                raise last_error
            else:
                raise VideoDownloadError("All download strategies failed")
            
        except AudioTooLongError:
            # Re-raise sem wrapper
            raise
        except yt_dlp.utils.DownloadError as e:
            self.rate_limiter.report_error()
            logger.error(f"🔥 yt-dlp download error: {str(e)}", exc_info=True)
            raise VideoDownloadError(f"Failed to download video: {str(e)}") from e
        except (ConnectionError, TimeoutError) as e:
            self.rate_limiter.report_error()
            logger.error(f"🔥 Network error during download: {str(e)}", exc_info=True)
            raise NetworkError("YouTube", str(e)) from e
        except Exception as e:
            self.rate_limiter.report_error()
            logger.error(f"🔥 Unexpected download error: {type(e).__name__}: {str(e)}", exc_info=True)
            raise VideoDownloadError(f"Unexpected error during download: {str(e)}") from e
    
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
        
        v2.2: Circuit breaker custom + retry logic.
        
        Args:
            url: URL do YouTube
            
        Returns:
            dict: Informações do vídeo
            
        Raises:
            VideoDownloadError: Se houver erro ao obter informações
            CircuitBreakerOpenError: Se circuit breaker estiver aberto
        """
        # Envolve a lógica de info com Circuit Breaker (versão async)
        return await _youtube_circuit_breaker.acall(self._get_video_info_internal, url)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((yt_dlp.utils.DownloadError, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no),
        reraise=True
    )
    async def _get_video_info_internal(self, url: YouTubeURL) -> dict:
        """
        Método interno com retry logic - chamado pelo Circuit Breaker.
        v3.0: User-Agent rotation e proxy support.
        """
        try:
            logger.info(f"📄 Fetching video info (v3.0): {url.video_id}")
            
            # v3.0: Track tempo
            info_start_time = time.time()
            
            # v3.0: Rate limiting
            await self.rate_limiter.wait_if_needed()
            
            # v3.0: Usar primeira estratégia (mais confiável)
            strategy = self.strategy_manager.get_strategies()[0]
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
            }
            
            # v3.0: Merge strategy options
            if strategy.extra_opts:
                ydl_opts.update(strategy.extra_opts)
            
            # v3.0: User-Agent rotation
            if self.config.enable_user_agent_rotation:
                user_agent = self.ua_rotator.get_random()
            else:
                user_agent = strategy.user_agent
            
            ydl_opts['http_headers'] = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
            
            # v3.0: Tor proxy support
            if self.config.enable_tor_proxy:
                proxy_url = self.proxy_manager.get_tor_proxy()
                if proxy_url:
                    ydl_opts['proxy'] = proxy_url
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._get_info_sync,
                str(url),
                ydl_opts
            )
            
            # v3.0: Report success
            self.rate_limiter.report_success()
            
            # v3.0: Record metrics
            info_duration = time.time() - info_start_time
            record_info_request(success=True, duration=info_duration)
            
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
            self.rate_limiter.report_error()
            
            # v3.0: Record metrics
            info_duration = time.time() - info_start_time
            record_info_request(success=False, duration=info_duration)
            
            logger.error(f"🔥 Failed to get video info: {str(e)}")
            raise VideoDownloadError(f"Failed to get video info: {str(e)}")
        except Exception as e:
            self.rate_limiter.report_error()
            
            # v3.0: Record metrics
            info_duration = time.time() - info_start_time
            record_info_request(success=False, duration=info_duration)
            
            logger.error(f"🔥 Unexpected error getting video info: {str(e)}")
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

