"""
Use Case: Transcribe YouTube Video
Orquestra o processo completo de transcrição de vídeos do YouTube.
Segue o princípio de Single Responsibility (SOLID).

v2.0: Integrado com cache de transcrição e validação de áudio.
v2.1: Timeout global, exceções granulares, logging melhorado.
v2.2.1: Cache reimplementado com file_hash após download.
"""
import time
import asyncio
from pathlib import Path
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
    ValidationError,
    AudioTooLongError,
    AudioCorruptedError,
    OperationTimeoutError,
    CacheError
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
        max_video_duration: int = 10800,  # 3 horas por padrão
        # v2.0: Serviços opcionais de otimização
        audio_validator=None,
        transcription_cache=None
    ):
        """
        Inicializa o use case.
        
        Args:
            video_downloader: Serviço de download de vídeos
            transcription_service: Serviço de transcrição
            storage_service: Serviço de armazenamento
            cleanup_after_processing: Se deve limpar arquivos após processar
            max_video_duration: Duração máxima permitida em segundos
            audio_validator: (v2.0) Validador de áudio (opcional)
            transcription_cache: (v2.0) Cache de transcrições (opcional)
        """
        self.video_downloader = video_downloader
        self.transcription_service = transcription_service
        self.storage_service = storage_service
        self.cleanup_after_processing = cleanup_after_processing
        self.max_video_duration = max_video_duration
        self.youtube_transcript_service = YouTubeTranscriptService()
        
        # v2.0: Otimizações opcionais
        self.audio_validator = audio_validator
        self.transcription_cache = transcription_cache
        logger.info(
            f"📋 TranscribeVideoUseCase initialized "
            f"(cache={'enabled' if transcription_cache else 'disabled'}, "
            f"validation={'enabled' if audio_validator else 'disabled'})"
        )
    
    async def execute(
        self,
        request: TranscribeRequestDTO
    ) -> TranscribeResponseDTO:
        """
        Executa o processo de transcrição.
        
        v2.0: Integra cache e validação de áudio.
        
        Args:
            request: Requisição com URL e parâmetros
            
        Returns:
            TranscribeResponseDTO: Resposta com transcrição completa
            
        Raises:
            ValidationError: Se a URL for inválida ou áudio inválido
            VideoDownloadError: Se falhar o download
            TranscriptionError: Se falhar a transcrição
        """
        start_time = time.time()
        temp_dir = None
        cache_key = None
        
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
            
            # 5. v2.2.1: Verificar cache APÓS download (usando file_hash)
            file_hash = None
            if self.transcription_cache and video_file.file_path:
                logger.info("🔍 Computing file hash for cache lookup...")
                file_hash = self.transcription_cache.compute_file_hash(
                    Path(video_file.file_path)
                )
                
                # Obter model_name e language para cache lookup
                model_name = getattr(self.transcription_service, 'model_name', 'base')
                language = request.language if request.language != "auto" else "auto"
                
                # Verificar cache
                cached_result = self.transcription_cache.get(
                    file_hash=file_hash,
                    model_name=model_name,
                    language=language
                )
                
                if cached_result:
                    logger.info(
                        f"✅ Cache HIT for {youtube_url.video_id} "
                        f"(hash={file_hash[:16]}..., model={model_name}, lang={language})"
                    )
                    
                    # Adicionar informações adicionais
                    cached_result["youtube_url"] = str(youtube_url)
                    cached_result["video_id"] = youtube_url.video_id
                    cached_result["processing_time"] = time.time() - start_time
                    
                    return TranscribeResponseDTO(**cached_result)
                else:
                    logger.info(
                        f"❌ Cache MISS for {youtube_url.video_id} "
                        f"(hash={file_hash[:16]}..., model={model_name}, lang={language})"
                    )
            
            # 6. v2.0: Validar áudio antes de processar
            if self.audio_validator and video_file.file_path:
                logger.info("🔍 Validating audio file...")
                validation_start = time.time()
                
                # validate_file() é SÍNCRONO e retorna AudioMetadata (dataclass)
                validation_result = self.audio_validator.validate_file(
                    Path(video_file.file_path)
                )
                
                if not validation_result.is_valid:
                    error_msg = f"Invalid audio file: {', '.join(validation_result.validation_errors)}"
                    logger.error(f"❌ {error_msg}")
                    
                    # v2.1: Usar exceção granular
                    raise AudioCorruptedError(
                        str(video_file.file_path),
                        error_msg
                    )
                
                validation_time = time.time() - validation_start
                audio_duration = validation_result.duration_seconds
                
                # Estimar tempo de processamento
                min_time, max_time = self.audio_validator.estimate_processing_time(
                    validation_result,
                    model_name=getattr(self.transcription_service, 'model_name', 'base'),
                    device=getattr(self.transcription_service, 'device', 'cpu')
                )
                
                logger.info(
                    f"✅ Audio validation passed in {validation_time:.2f}s "
                    f"(duration={audio_duration:.1f}s, "
                    f"estimated_processing={min_time:.1f}-{max_time:.1f}s)"
                )
            else:
                # Estimar duração do vídeo se validator não disponível
                audio_duration = getattr(video_file, 'duration', self.max_video_duration)
            
            # 7. v2.1: Transcrever vídeo com Whisper + TIMEOUT GLOBAL
            logger.info("Starting Whisper transcription with timeout protection")
            
            # Estimar timeout baseado na duração do áudio
            from src.config import settings
            estimated_timeout = self._estimate_timeout(
                audio_duration,
                settings.whisper_model
            )
            
            logger.info(f"⏱️  Transcription timeout set to {estimated_timeout:.0f}s")
            
            try:
                # Executar transcrição com timeout
                transcription = await asyncio.wait_for(
                    self.transcription_service.transcribe(
                        video_file,
                        language=request.language if request.language != "auto" else None
                    ),
                    timeout=estimated_timeout
                )
            except asyncio.TimeoutError as e:
                logger.error(
                    f"🔥 Transcription TIMED OUT after {estimated_timeout:.0f}s "
                    f"(audio_duration={audio_duration:.1f}s)"
                )
                raise OperationTimeoutError(
                    f"transcription of {youtube_url.video_id}",
                    estimated_timeout
                ) from e
            
            # Adicionar informações adicionais
            transcription.youtube_url = youtube_url
            transcription.processing_time = time.time() - start_time
            
            logger.info(
                f"✅ Transcription completed: {len(transcription.segments)} segments, "
                f"language={transcription.language}, "
                f"time={transcription.processing_time:.2f}s, "
                f"timeout_used={estimated_timeout:.0f}s"
            )
            
            # 8. Criar DTO de resposta
            response = self._create_response_dto(transcription, source="whisper")
            
            # 9. v2.2.1: Salvar no cache COM file_hash correto
            if self.transcription_cache and file_hash and video_file.file_path:
                try:
                    # Converter para dict para cachear
                    cache_data = response.model_dump()
                    
                    # Obter model_name e language
                    model_name = getattr(self.transcription_service, 'model_name', 'base')
                    language = transcription.language or request.language or "auto"
                    
                    # Obter tamanho do arquivo
                    file_size_bytes = Path(video_file.file_path).stat().st_size
                    
                    self.transcription_cache.put(
                        file_hash=file_hash,
                        transcription_data=cache_data,
                        model_name=model_name,
                        language=language,
                        file_size_bytes=file_size_bytes
                    )
                    
                    logger.info(
                        f"💾 Cached transcription for {youtube_url.video_id} "
                        f"(hash={file_hash[:16]}..., model={model_name}, lang={language})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache result: {e}")
                    # v2.1: Não lançar exceção, apenas logar
                    # Cache failure não deve quebrar o fluxo
            
            return response
            
        except (ValidationError, VideoDownloadError, TranscriptionError, OperationTimeoutError):
            raise
        except asyncio.TimeoutError as e:
            # Capturar timeout não tratado
            logger.error("Transcription timeout at top level")
            raise OperationTimeoutError("transcription", self.max_video_duration) from e
        except Exception as e:
            logger.error(
                f"🔥 Unexpected error in transcription process: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise TranscriptionError(f"Unexpected error: {str(e)}") from e
        
        finally:
            # 10. Limpar arquivos temporários
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
                language=transcript_data['language']
            )
            transcription.youtube_url = youtube_url
            transcription.processing_time = time.time() - start_time
            # Note: duration is calculated automatically via property
            
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
    
    def _estimate_timeout(self, duration_seconds: float, model_name: str = "base") -> float:
        """
        Estima timeout baseado na duração do áudio e modelo.
        
        v2.1: Timeout dinâmico para evitar travamentos.
        
        Args:
            duration_seconds: Duração do áudio
            model_name: Modelo Whisper usado
            
        Returns:
            Timeout estimado em segundos (com margem de segurança)
        """
        # Fatores de processamento (realtime factor)
        factors = {
            'tiny': 2.0,    # ~2x realtime
            'base': 1.5,    # ~1.5x realtime
            'small': 0.8,   # ~0.8x realtime
            'medium': 0.4,  # ~0.4x realtime
            'large': 0.2,   # ~0.2x realtime
            'turbo': 1.0    # ~1x realtime
        }
        
        factor = factors.get(model_name, 1.0)
        
        # Tempo base = duração / fator
        base_time = duration_seconds / factor
        
        # Adicionar overhead (download, conversão, I/O) ~20%
        overhead = base_time * 0.2
        
        # Adicionar margem de segurança (50%)
        safety_margin = base_time * 0.5
        
        # Timeout mínimo: 60s
        # Timeout máximo: 3600s (1 hora)
        timeout = max(60, min(3600, base_time + overhead + safety_margin))
        
        logger.debug(
            f"Estimated timeout: {timeout:.0f}s "
            f"(duration={duration_seconds:.0f}s, model={model_name})"
        )
        
        return timeout

