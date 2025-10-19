"""
Factory para criar instâncias de serviços de transcrição.
Escolhe entre transcrição normal ou paralela baseado nas configurações.
Inclui fallback automático para modo normal se paralelo falhar.

IMPORTANTE: Este factory é chamado UMA VEZ no Container (singleton).
A instância retornada é reutilizada em TODAS as requisições.
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
    Serviço SINGLETON com seleção inteligente e fallback automático:
    - Áudios curtos (< AUDIO_LIMIT_SINGLE_CORE): usa single-core (mais eficiente)
    - Áudios longos: usa paralelo (workers persistentes, mais rápido)
    - Se paralelo falhar: fallback automático para normal
    
    CRÍTICO: Esta instância é criada UMA VEZ e compartilhada entre TODAS as requisições.
    O worker pool é compartilhado, então múltiplas requisições usam os mesmos 2 workers.
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
        
        logger.info(
            f"[FACTORY] FallbackTranscriptionService created (SINGLETON): "
            f"audio_limit={audio_limit_seconds}s"
        )
        
    async def transcribe(self, video_file: VideoFile, language: str = "auto") -> Transcription:
        """
        Seleciona modo baseado na duração do áudio:
        - < audio_limit_seconds: single-core (mais eficiente para áudios curtos)
        - >= audio_limit_seconds: paralelo (mais rápido para áudios longos)
        
        IMPORTANTE: Este método é chamado por múltiplas requisições concorrentes.
        Todas usam a MESMA instância do serviço (singleton) e o MESMO worker pool.
        """
        logger.info(
            f"[FALLBACK SERVICE] transcribe() called on instance id={id(self)}. "
            f"This is a SINGLETON shared across all requests."
        )
        
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
                "Using PARALLEL mode (persistent workers, faster for long audio)"
            )
            try:
                # Aceita request_ip opcional (None aqui pois não temos contexto da request)
                return await self.parallel_service.transcribe(video_file, language, request_ip=None)
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
    Cria e retorna instância SINGLETON do serviço de transcrição.
    
    IMPORTANTE: Esta função é chamada UMA VEZ pelo Container.
    A instância retornada é reutilizada em TODAS as requisições,
    garantindo que o worker pool persistente seja compartilhado corretamente.
    
    Returns:
        ITranscriptionService: Serviço de transcrição singleton com fallback automático
    """
    logger.info("[FACTORY] create_transcription_service() called - creating SINGLETON instance")
    
    # Sempre cria serviço normal como fallback
    normal_service = WhisperTranscriptionService(
        model_name=settings.whisper_model,
        device=settings.whisper_device
    )
    logger.info(f"[FACTORY] Normal service created: {type(normal_service).__name__}")
    
    if settings.enable_parallel_transcription:
        audio_limit = getattr(settings, 'audio_limit_single_core', 300)  # 5 min padrão
        
        logger.info(
            "🚀 [FACTORY] Creating INTELLIGENT transcription service with persistent worker pool:\n"
            f"   - Audio < {audio_limit}s: SINGLE-CORE (more efficient)\n"
            f"   - Audio >= {audio_limit}s: PARALLEL mode (workers={settings.parallel_workers}, "
            f"chunk_duration={settings.parallel_chunk_duration}s)\n"
            "   - Workers load model ONCE at startup (no reload per chunk)\n"
            "   - Automatic fallback on errors\n"
            "   - SINGLETON: Same instance shared across ALL requests"
        )
        
        # Importa getters da main.py para acessar worker pool global
        try:
            from src.presentation.api.main import (
                get_worker_pool,
                get_temp_session_manager,
                get_chunk_prep_service
            )
            
            worker_pool = get_worker_pool()
            temp_manager = get_temp_session_manager()
            chunk_prep = get_chunk_prep_service()
            
            logger.info(
                f"[FACTORY] Retrieved global instances: "
                f"worker_pool={worker_pool is not None}, "
                f"temp_manager={temp_manager is not None}, "
                f"chunk_prep={chunk_prep is not None}"
            )
            
            if worker_pool is None:
                logger.error("[FACTORY] Worker pool is None! Cannot create parallel service.")
                logger.warning("[FACTORY] Falling back to single-core service")
                return normal_service
            
            parallel_service = WhisperParallelTranscriptionService(
                worker_pool=worker_pool,
                temp_manager=temp_manager,
                chunk_prep_service=chunk_prep,
                model_name=settings.whisper_model
            )
            logger.info(f"[FACTORY] Parallel service created: {type(parallel_service).__name__}")
            
            # Retorna serviço com seleção inteligente e fallback automático
            fallback_service = FallbackTranscriptionService(
                parallel_service=parallel_service,
                fallback_service=normal_service,
                audio_limit_seconds=audio_limit
            )
            
            logger.info(
                f"[FACTORY] Returning SINGLETON FallbackTranscriptionService (id={id(fallback_service)}). "
                "This instance will be reused for ALL requests."
            )
            
            return fallback_service
            
        except (ImportError, AttributeError) as e:
            logger.warning(f"[FACTORY] Could not initialize parallel service: {e}. Using single-core only.")
            return normal_service
    else:
        logger.info("[FACTORY] Creating standard transcription service (parallel disabled)")
        return normal_service
