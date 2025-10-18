"""
YouTube Transcript Service.
Serviço para baixar transcrições/legendas do YouTube com múltiplos fallbacks.
"""
from typing import Optional, List, Dict
import asyncio
import yt_dlp
from loguru import logger
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)

from src.domain.value_objects import YouTubeURL
from src.domain.exceptions import VideoDownloadError


class YouTubeTranscriptService:
    """
    Serviço para obter transcrições do YouTube com fallbacks.
    """
    
    def __init__(self):
        """Inicializa o serviço de transcrições."""
        pass
    
    async def get_transcript(
        self,
        url: YouTubeURL,
        language: Optional[str] = None,
        prefer_manual: bool = True
    ) -> Dict:
        """
        Obtém transcrição do YouTube com tratamento robusto de erros.
        
        Args:
            url: URL do YouTube
            language: Código do idioma desejado (ex: 'pt', 'en')
            prefer_manual: Preferir legendas manuais sobre automáticas
            
        Returns:
            Dict: Transcrição formatada
            
        Raises:
            VideoDownloadError: Se não conseguir obter transcrição
        """
        video_id = url.video_id
        logger.info(f"Fetching transcript for video: {video_id}")
        
        # Método 1: youtube-transcript-api (principal)
        try:
            result = await self._fetch_with_transcript_api(
                video_id, language, prefer_manual
            )
            logger.info(f"Successfully fetched transcript using Method 1")
            return result
        except TranscriptsDisabled:
            raise VideoDownloadError("Transcripts are disabled for this video")
        except VideoUnavailable:
            raise VideoDownloadError("Video is unavailable")
        except NoTranscriptFound as e:
            raise VideoDownloadError(f"No transcripts found: {str(e)}")
        except Exception as e:
            logger.warning(f"Method 1 failed: {str(e)}")
            # Fallback para método 2
            pass
        
        # Método 2: Tentativa alternativa com configurações mais permissivas
        try:
            logger.info("Trying alternative fetch method...")
            result = await self._fetch_alternative(video_id, language)
            logger.info(f"Successfully fetched transcript using Method 2")
            return result
        except Exception as e:
            logger.error(f"Method 2 also failed: {str(e)}")
        
        # Método 3: Usar yt-dlp para baixar legendas diretamente
        try:
            logger.info("Trying yt-dlp method...")
            result = await self._fetch_with_ytdlp(video_id, language)
            logger.info(f"Successfully fetched transcript using Method 3 (yt-dlp)")
            return result
        except Exception as e:
            logger.error(f"Method 3 also failed: {str(e)}")
        
        # Se todos os métodos falharam
        raise VideoDownloadError(
            f"Failed to fetch transcript after trying all methods. "
            f"Video may not have subtitles available or they are restricted."
        )
    
    async def _fetch_with_transcript_api(
        self,
        video_id: str,
        language: Optional[str],
        prefer_manual: bool
    ) -> Dict:
        """
        Método 1: Usar youtube-transcript-api (principal).
        """
        # Executar em thread separada para não bloquear
        loop = asyncio.get_event_loop()
        
        def _fetch():
            # Listar transcrições disponíveis
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            transcript = None
            transcript_info = None
            
            # Tentar obter no idioma específico
            if language:
                try:
                    if prefer_manual:
                        try:
                            transcript = transcript_list.find_manually_created_transcript([language])
                            transcript_info = {
                                'language': language,
                                'type': 'manual',
                                'auto_generated': False
                            }
                        except NoTranscriptFound:
                            transcript = transcript_list.find_generated_transcript([language])
                            transcript_info = {
                                'language': language,
                                'type': 'auto',
                                'auto_generated': True
                            }
                    else:
                        transcript = transcript_list.find_transcript([language])
                        transcript_info = {
                            'language': language,
                            'type': 'available',
                            'auto_generated': transcript.is_generated
                        }
                except NoTranscriptFound:
                    logger.warning(f"Transcript not found for language: {language}")
                    transcript = None
            
            # Fallback: tentar inglês
            if transcript is None:
                try:
                    transcript = transcript_list.find_transcript(['en'])
                    transcript_info = {
                        'language': 'en',
                        'type': 'fallback_en',
                        'auto_generated': transcript.is_generated
                    }
                except NoTranscriptFound:
                    # Fallback: pegar a primeira disponível
                    for t in transcript_list:
                        transcript = t
                        transcript_info = {
                            'language': t.language_code,
                            'type': 'first_available',
                            'auto_generated': t.is_generated
                        }
                        break
            
            if transcript is None:
                raise NoTranscriptFound(video_id, [])
            
            # Baixar transcrição
            transcript_data = transcript.fetch()
            
            return transcript_data, transcript_info
        
        # Executar de forma assíncrona
        transcript_data, transcript_info = await loop.run_in_executor(None, _fetch)
        
        # Formatar resultado
        full_text = ' '.join([item['text'] for item in transcript_data])
        
        segments = []
        for item in transcript_data:
            segments.append({
                'start': item['start'],
                'duration': item['duration'],
                'text': item['text']
            })
        
        result = {
            'text': full_text,
            'segments': segments,
            'language': transcript_info['language'],
            'type': transcript_info['type'],
            'auto_generated': transcript_info['auto_generated'],
            'source': 'youtube_transcript',
            'video_id': video_id
        }
        
        logger.info(
            f"Transcript fetched: {video_id} "
            f"(lang: {transcript_info['language']}, "
            f"type: {transcript_info['type']}, "
            f"segments: {len(segments)})"
        )
        
        return result
    
    async def _fetch_alternative(
        self,
        video_id: str,
        language: Optional[str]
    ) -> Dict:
        """
        Método 2: Tentativa alternativa com diferentes parâmetros.
        """
        loop = asyncio.get_event_loop()
        
        def _fetch():
            # Tentar sem preferências específicas
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Pegar qualquer transcrição disponível
            transcript = None
            for t in transcript_list:
                transcript = t
                break
            
            if transcript is None:
                raise NoTranscriptFound(video_id, [])
            
            # Baixar
            transcript_data = transcript.fetch()
            
            return transcript_data, {
                'language': transcript.language_code,
                'type': 'alternative_method',
                'auto_generated': transcript.is_generated
            }
        
        transcript_data, transcript_info = await loop.run_in_executor(None, _fetch)
        
        # Formatar
        full_text = ' '.join([item['text'] for item in transcript_data])
        
        segments = []
        for item in transcript_data:
            segments.append({
                'start': item['start'],
                'duration': item['duration'],
                'text': item['text']
            })
        
        return {
            'text': full_text,
            'segments': segments,
            'language': transcript_info['language'],
            'type': transcript_info['type'],
            'auto_generated': transcript_info['auto_generated'],
            'source': 'youtube_transcript',
            'video_id': video_id
        }
    
    async def _fetch_with_ytdlp(
        self,
        video_id: str,
        language: Optional[str]
    ) -> Dict:
        """
        Método 3: Usar yt-dlp para baixar legendas (mais robusto).
        """
        loop = asyncio.get_event_loop()
        
        def _fetch():
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': [language] if language else ['en'],
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Tentar pegar legendas
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})
                
                # Priorizar legendas manuais
                selected_lang = None
                is_auto = False
                
                if language:
                    if language in subtitles:
                        selected_lang = language
                        is_auto = False
                    elif language in automatic_captions:
                        selected_lang = language
                        is_auto = True
                
                # Fallback para inglês
                if not selected_lang:
                    if 'en' in subtitles:
                        selected_lang = 'en'
                        is_auto = False
                    elif 'en' in automatic_captions:
                        selected_lang = 'en'
                        is_auto = True
                
                # Pegar primeira disponível
                if not selected_lang:
                    if subtitles:
                        selected_lang = list(subtitles.keys())[0]
                        is_auto = False
                    elif automatic_captions:
                        selected_lang = list(automatic_captions.keys())[0]
                        is_auto = True
                
                if not selected_lang:
                    raise NoTranscriptFound(video_id, [])
                
                # Obter URL da legenda
                caption_source = automatic_captions if is_auto else subtitles
                caption_formats = caption_source[selected_lang]
                
                # Pegar formato JSON3 (tem timestamps)
                caption_url = None
                for fmt in caption_formats:
                    if fmt['ext'] == 'json3':
                        caption_url = fmt['url']
                        break
                
                if not caption_url:
                    # Fallback para primeiro formato
                    caption_url = caption_formats[0]['url']
                
                # Baixar legenda
                import urllib.request
                import json
                
                with urllib.request.urlopen(caption_url) as response:
                    caption_data = json.loads(response.read().decode('utf-8'))
                
                # Parsear formato JSON3 do YouTube
                segments = []
                full_text_parts = []
                
                if 'events' in caption_data:
                    for event in caption_data['events']:
                        if 'segs' in event:
                            start_time = event.get('tStartMs', 0) / 1000.0
                            duration = event.get('dDurationMs', 0) / 1000.0
                            
                            text_parts = []
                            for seg in event['segs']:
                                if 'utf8' in seg:
                                    text_parts.append(seg['utf8'])
                            
                            if text_parts:
                                text = ''.join(text_parts).strip()
                                if text:
                                    segments.append({
                                        'start': start_time,
                                        'duration': duration,
                                        'text': text
                                    })
                                    full_text_parts.append(text)
                
                return {
                    'segments': segments,
                    'full_text': ' '.join(full_text_parts),
                    'language': selected_lang,
                    'is_auto': is_auto
                }
        
        result = await loop.run_in_executor(None, _fetch)
        
        return {
            'text': result['full_text'],
            'segments': result['segments'],
            'language': result['language'],
            'type': 'auto' if result['is_auto'] else 'manual',
            'auto_generated': result['is_auto'],
            'source': 'youtube_transcript_ytdlp',
            'video_id': video_id
        }
    
    async def list_available_transcripts(self, url: YouTubeURL) -> List[Dict]:
        """
        Lista todas as transcrições disponíveis.
        
        Args:
            url: URL do YouTube
            
        Returns:
            List[Dict]: Lista de transcrições disponíveis
        """
        try:
            video_id = url.video_id
            
            loop = asyncio.get_event_loop()
            
            def _list():
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcripts = []
                
                for transcript in transcript_list:
                    transcripts.append({
                        'language': transcript.language_code,
                        'language_name': transcript.language,
                        'auto_generated': transcript.is_generated,
                        'translatable': transcript.is_translatable
                    })
                
                return transcripts
            
            return await loop.run_in_executor(None, _list)
            
        except Exception as e:
            logger.error(f"Error listing transcripts: {str(e)}")
            return []
    
    async def check_transcript_availability(
        self,
        url: YouTubeURL,
        language: Optional[str] = None
    ) -> Dict:
        """
        Verifica disponibilidade de transcrições.
        
        Args:
            url: URL do YouTube
            language: Código do idioma opcional
            
        Returns:
            Dict: Informações sobre disponibilidade
        """
        try:
            video_id = url.video_id
            
            loop = asyncio.get_event_loop()
            
            def _check():
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                available_languages = []
                manual_languages = []
                auto_languages = []
                
                for transcript in transcript_list:
                    lang = transcript.language_code
                    available_languages.append(lang)
                    
                    if transcript.is_generated:
                        auto_languages.append(lang)
                    else:
                        manual_languages.append(lang)
                
                return {
                    'available': len(available_languages) > 0,
                    'total_transcripts': len(available_languages),
                    'available_languages': available_languages,
                    'manual_languages': manual_languages,
                    'auto_languages': auto_languages
                }
            
            result = await loop.run_in_executor(None, _check)
            
            if language:
                result['requested_language_available'] = language in result['available_languages']
                result['requested_language_manual'] = language in result['manual_languages']
                result['requested_language_auto'] = language in result['auto_languages']
            
            return result
            
        except TranscriptsDisabled:
            return {
                'available': False,
                'reason': 'transcripts_disabled'
            }
        except VideoUnavailable:
            return {
                'available': False,
                'reason': 'video_unavailable'
            }
        except Exception as e:
            logger.error(f"Error checking transcript availability: {str(e)}")
            return {
                'available': False,
                'reason': str(e)
            }
