"""
Use Case: Transcribe YouTube Video
Orquestra o processo completo de transcrição de vídeos do YouTube.
Segue o princípio de Single Responsibility (SOLID).
"""
import time
from loguru import logger

from src.domain.interfaces import (
    IVideoDownloader,
    ITranscriptionService,
    IStorageService
)
from src.domain.value_objects import YouTubeURL
from src.domain.entities import Transcription
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
            
            # 2. Criar diretório temporário
            temp_dir = await self.storage_service.create_temp_directory()
            logger.debug(f"Created temp directory: {temp_dir}")
            
            # 3. Baixar vídeo (com validação de duração)
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
            
            # 4. Transcrever vídeo
            logger.info("Starting transcription")
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
            
            # 5. Criar DTO de resposta
            response = self._create_response_dto(transcription)
            
            return response
            
        except (ValidationError, VideoDownloadError, TranscriptionError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transcription process: {str(e)}")
            raise TranscriptionError(f"Unexpected error: {str(e)}")
        
        finally:
            # 6. Limpar arquivos temporários
            if temp_dir and self.cleanup_after_processing:
                try:
                    await self.storage_service.cleanup_directory(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {str(e)}")
    
    def _create_response_dto(
        self,
        transcription: Transcription
    ) -> TranscribeResponseDTO:
        """
        Cria DTO de resposta a partir da entidade Transcription.
        
        Args:
            transcription: Entidade de transcrição
            
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
            processing_time=transcription.processing_time
        )
