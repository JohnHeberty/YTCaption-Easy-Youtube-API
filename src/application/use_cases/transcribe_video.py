"""
Use Case: Transcribe YouTube Video
Orquestra o processo completo de transcrição de vídeos do YouTube.
Segue o princípio de Single Responsibility (SOLID).
"""
import time
from typing import Optional
from loguru import logger

from src.domain.interfaces import (
    IVideoDownloader,
    ITranscriptionService,
    IStorageService
)
from src.domain.value_objects import YouTubeURL
from src.domain.entities import Transcription, TranscriptionSegment
from src.domain.exceptions import (
    VideoDownloadError,
    TranscriptionError,
    ValidationError
)
from src.application.dtos import (
    TranscribeRequestDTO,
    TranscribeResponseDTO,
    TranscriptionSegmentDTO
)
from src.infrastructure.youtube.transcript_service import YouTubeTranscriptService


class TranscribeYouTubeVideoUseCase:
    """
    Use Case para transcrever vídeos do YouTube.
    Coordena download, transcrição e limpeza de arquivos.
    """
    
    def __init__(
        self,
        video_downloader: IVideoDownloader,
        transcription_service: ITranscriptionService,
        storage_service: IStorageService,
        cleanup_after_processing: bool = True,
        max_video_duration: int = 10800  # 3 horas por padrão
    ):
        """
        Inicializa o use case.
        
        Args:
            video_downloader: Serviço de download de vídeos
            transcription_service: Serviço de transcrição
            storage_service: Serviço de armazenamento
            cleanup_after_processing: Se deve limpar arquivos após processar
            max_video_duration: Duração máxima permitida em segundos
        """
        self.video_downloader = video_downloader
        self.transcription_service = transcription_service
        self.storage_service = storage_service
        self.cleanup_after_processing = cleanup_after_processing
        self.max_video_duration = max_video_duration
        self.youtube_transcript_service = YouTubeTranscriptService()
    
    async def execute(
        self,
        request: TranscribeRequestDTO
    ) -> TranscribeResponseDTO:
        """
        Executa o processo de transcrição.
        
        Args:
            request: Requisição com URL e parâmetros
            
        Returns:
            TranscribeResponseDTO: Resposta com transcrição completa
            
        Raises:
            ValidationError: Se a URL for inválida
            VideoDownloadError: Se falhar o download
            TranscriptionError: Se falhar a transcrição
        """
        start_time = time.time()
        temp_dir = None
        
        try:
            # 1. Validar URL do YouTube
            logger.info(f"Starting transcription process: {request.youtube_url}")
            
            try:
                youtube_url = YouTubeURL.create(request.youtube_url)
            except ValueError as e:
                raise ValidationError(f"Invalid YouTube URL: {str(e)}")
            
            # 2. Verificar se deve usar transcrição do YouTube
            if request.use_youtube_transcript:
                logger.info("Using YouTube transcript instead of Whisper")
                return await self._transcribe_from_youtube(
                    youtube_url,
                    request.language if request.language != "auto" else None,
                    request.prefer_manual_subtitles,
                    start_time
                )
            
            # 3. Criar diretório temporário
            temp_dir = await self.storage_service.create_temp_directory()
            logger.debug(f"Created temp directory: {temp_dir}")
            
            # 4. Baixar vídeo (com validação de duração)
            logger.info(f"Downloading video: {youtube_url.video_id}")
            video_file = await self.video_downloader.download(
                youtube_url, 
                temp_dir,
                validate_duration=True,
                max_duration=self.max_video_duration
            )
            logger.info(
                f"Video downloaded: {video_file.file_size_mb:.2f} MB"
            )
            
            # 5. Transcrever vídeo com Whisper
            logger.info("Starting Whisper transcription")
            transcription = await self.transcription_service.transcribe(
                video_file,
                language=request.language if request.language != "auto" else None
            )
            
            # Adicionar informações adicionais
            transcription.youtube_url = youtube_url
            transcription.processing_time = time.time() - start_time
            
            logger.info(
                f"Transcription completed: {len(transcription.segments)} segments, "
                f"language={transcription.language}, "
                f"time={transcription.processing_time:.2f}s"
            )
            
            # 6. Criar DTO de resposta
            response = self._create_response_dto(transcription, source="whisper")
            
            return response
            
        except (ValidationError, VideoDownloadError, TranscriptionError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transcription process: {str(e)}")
            raise TranscriptionError(f"Unexpected error: {str(e)}")
        
        finally:
            # 7. Limpar arquivos temporários
            if temp_dir and self.cleanup_after_processing:
                try:
                    await self.storage_service.cleanup_directory(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {str(e)}")
    
    async def _transcribe_from_youtube(
        self,
        youtube_url: YouTubeURL,
        language: Optional[str],
        prefer_manual: bool,
        start_time: float
    ) -> TranscribeResponseDTO:
        """
        Obtém transcrição diretamente do YouTube.
        
        Args:
            youtube_url: URL do YouTube
            language: Idioma desejado
            prefer_manual: Preferir legendas manuais
            start_time: Timestamp de início
            
        Returns:
            TranscribeResponseDTO: Resposta com transcrição
        """
        try:
            transcript_data = await self.youtube_transcript_service.get_transcript(
                youtube_url,
                language=language,
                prefer_manual=prefer_manual
            )
            
            # Converter para formato da aplicação
            segments = []
            for seg in transcript_data['segments']:
                segments.append(
                    TranscriptionSegment(
                        text=seg['text'],
                        start=seg['start'],
                        end=seg['start'] + seg['duration']
                    )
                )
            
            # Criar entidade Transcription
            transcription = Transcription(
                segments=segments,
                language=transcript_data['language'],
                duration=segments[-1].end if segments else 0
            )
            transcription.youtube_url = youtube_url
            transcription.processing_time = time.time() - start_time
            
            logger.info(
                f"YouTube transcript fetched: {len(segments)} segments, "
                f"language={transcript_data['language']}, "
                f"type={transcript_data['type']}, "
                f"time={transcription.processing_time:.2f}s"
            )
            
            # Criar DTO de resposta
            response = self._create_response_dto(
                transcription,
                source="youtube_transcript",
                transcript_type=transcript_data['type']
            )
            
            return response
            
        except VideoDownloadError:
            raise
        except Exception as e:
            logger.error(f"Failed to get YouTube transcript: {str(e)}")
            raise VideoDownloadError(
                f"Failed to get YouTube transcript: {str(e)}. "
                "Try using Whisper transcription instead (set use_youtube_transcript=false)"
            )
    
    def _create_response_dto(
        self,
        transcription: Transcription,
        source: str = "whisper",
        transcript_type: Optional[str] = None
    ) -> TranscribeResponseDTO:
        """
        Cria DTO de resposta a partir da entidade Transcription.
        
        Args:
            transcription: Entidade de transcrição
            source: Fonte da transcrição (whisper ou youtube_transcript)
            transcript_type: Tipo de transcrição do YouTube (manual/auto)
            
        Returns:
            TranscribeResponseDTO: DTO de resposta
        """
        segments_dto = [
            TranscriptionSegmentDTO(
                text=seg.text,
                start=seg.start,
                end=seg.end,
                duration=seg.duration
            )
            for seg in transcription.segments
        ]
        
        return TranscribeResponseDTO(
            transcription_id=transcription.id,
            youtube_url=str(transcription.youtube_url),
            video_id=transcription.youtube_url.video_id,
            language=transcription.language or "unknown",
            full_text=transcription.get_full_text(),
            segments=segments_dto,
            total_segments=len(transcription.segments),
            duration=transcription.duration,
            processing_time=transcription.processing_time,
            source=source,
            transcript_type=transcript_type
        )
