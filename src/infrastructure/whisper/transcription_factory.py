"""
Factory para criar instâncias de serviços de transcrição.
Escolhe entre transcrição normal ou paralela baseado nas configurações.
Inclui fallback automático para modo normal se paralelo falhar.
"""
import subprocess
from pathlib import Path
from loguru import logger

from src.config.settings import settings
from src.domain.interfaces import ITranscriptionService
from src.domain.entities import VideoFile, Transcription
from src.infrastructure.whisper.transcription_service import WhisperTranscriptionService
from src.infrastructure.whisper.parallel_transcription_service import WhisperParallelTranscriptionService


def _get_audio_duration(audio_path: Path | str) -> float:
    """
    Obtém a duração do áudio em segundos usando FFprobe.
    
    Args:
        audio_path: Caminho do arquivo de áudio
        
    Returns:
        float: Duração em segundos
        
    Raises:
        RuntimeError: Se não conseguir obter a duração
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to get audio duration: {e}") from e


class FallbackTranscriptionService(ITranscriptionService):
    """
    Serviço com seleção inteligente e fallback automático:
    - Áudios curtos (< AUDIO_LIMIT_SINGLE_CORE): usa single-core (mais eficiente)
    - Áudios longos: usa paralelo (mais rápido)
    - Se paralelo falhar: fallback automático para normal
    """
    
    def __init__(
        self,
        parallel_service: WhisperParallelTranscriptionService,
        fallback_service: WhisperTranscriptionService,
        audio_limit_seconds: int = 300  # 5 minutos padrão
    ):
        self.parallel_service = parallel_service
        self.fallback_service = fallback_service
        self.audio_limit_seconds = audio_limit_seconds
        self._use_parallel = True  # Flag global de fallback
        
    async def transcribe(self, video_file: VideoFile, language: str = "auto") -> Transcription:
        """
        Seleciona modo baseado na duração do áudio:
        - < audio_limit_seconds: single-core (mais eficiente para áudios curtos)
        - >= audio_limit_seconds: paralelo (mais rápido para áudios longos)
        """
        # Obtém duração do áudio
        try:
            duration = _get_audio_duration(video_file.file_path)
        except (RuntimeError, subprocess.SubprocessError) as e:
            logger.warning(f"Could not get audio duration: {e}. Using fallback service.")
            return await self.fallback_service.transcribe(video_file, language)
        
        # Decisão inteligente baseada na duração
        if duration < self.audio_limit_seconds:
            logger.info(
                f"📊 Audio duration: {duration:.1f}s < {self.audio_limit_seconds}s limit. "
                "Using SINGLE-CORE mode (more efficient for short audio)"
            )
            return await self.fallback_service.transcribe(video_file, language)
        
        # Áudio longo: tenta paralelo se ainda não falhou
        if self._use_parallel:
            logger.info(
                f"📊 Audio duration: {duration:.1f}s >= {self.audio_limit_seconds}s limit. "
                "Using PARALLEL mode (faster for long audio)"
            )
            try:
                return await self.parallel_service.transcribe(video_file, language)
            except (RuntimeError, OSError, MemoryError) as e:
                # Se erro de processo do pool, desabilita paralelo e usa fallback
                error_msg = str(e).lower()
                if "process pool" in error_msg or "abruptly" in error_msg or "terminated" in error_msg or "memory" in error_msg:
                    logger.error(f"[PARALLEL] Process pool error: {e}")
                    logger.warning("[PARALLEL] Disabling parallel mode and falling back to normal transcription")
                    self._use_parallel = False  # Desabilita para próximas chamadas
                    return await self.fallback_service.transcribe(video_file, language)
                else:
                    # Outros erros: propaga
                    raise
        else:
            # Paralelo já foi desabilitado, usa normal mesmo para áudios longos
            logger.info(
                f"📊 Audio duration: {duration:.1f}s >= {self.audio_limit_seconds}s limit. "
                "Using NORMAL mode (parallel disabled due to previous error)"
            )
            return await self.fallback_service.transcribe(video_file, language)
    
    async def detect_language(self, video_file: VideoFile) -> str:
        """Usa serviço normal para detecção de idioma."""
        return await self.fallback_service.detect_language(video_file)


def create_transcription_service() -> ITranscriptionService:
    """
    Cria e retorna uma instância do serviço de transcrição apropriado.
    
    Returns:
        ITranscriptionService: Serviço de transcrição com fallback automático
    """
    # Sempre cria serviço normal como fallback
    normal_service = WhisperTranscriptionService(
        model_name=settings.whisper_model,
        device=settings.whisper_device
    )
    
    if settings.enable_parallel_transcription:
        audio_limit = getattr(settings, 'audio_limit_single_core', 300)  # 5 min padrão
        
        logger.info(
            "🚀 Creating INTELLIGENT transcription service with automatic mode selection:\n"
            f"   - Audio < {audio_limit}s: SINGLE-CORE (more efficient)\n"
            f"   - Audio >= {audio_limit}s: PARALLEL mode (workers={settings.parallel_workers}, "
            f"chunk_duration={settings.parallel_chunk_duration}s)\n"
            "   - Automatic fallback on errors"
        )
        
        parallel_service = WhisperParallelTranscriptionService(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            num_workers=settings.parallel_workers if settings.parallel_workers > 0 else None,
            chunk_duration_seconds=settings.parallel_chunk_duration
        )
        
        # Retorna serviço com seleção inteligente e fallback automático
        return FallbackTranscriptionService(
            parallel_service=parallel_service,
            fallback_service=normal_service,
            audio_limit_seconds=audio_limit
        )
    else:
        logger.info("Creating standard transcription service")
        return normal_service
