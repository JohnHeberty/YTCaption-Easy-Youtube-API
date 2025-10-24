"""
Factory para criar instâncias de serviços de transcrição.
Escolhe entre transcrição normal ou paralela baseado APENAS no .env (ENABLE_PARALLEL_TRANSCRIPTION).

IMPORTANTE: Este factory é chamado UMA VEZ no Container (singleton).
A instância retornada é reutilizada em TODAS as requisições.
"""
from loguru import logger

from src.config.settings import settings
from src.domain.interfaces import ITranscriptionService
from src.infrastructure.whisper.transcription_service import WhisperTranscriptionService
from src.infrastructure.whisper.parallel_transcription_service import WhisperParallelTranscriptionService


def create_transcription_service() -> ITranscriptionService:
    """
    Cria e retorna instância SINGLETON do serviço de transcrição.
    
    IMPORTANTE: Esta função é chamada UMA VEZ pelo Container.
    A instância retornada é reutilizada em TODAS as requisições.
    
    Comportamento SIMPLIFICADO:
    - ENABLE_PARALLEL_TRANSCRIPTION=true: SEMPRE usa modo paralelo (para todos os áudios)
    - ENABLE_PARALLEL_TRANSCRIPTION=false: SEMPRE usa single-core (para todos os áudios)
    
    Returns:
        ITranscriptionService: Serviço de transcrição singleton
    """
    logger.info("[FACTORY] create_transcription_service() called - creating SINGLETON instance")
    
    if settings.enable_parallel_transcription:
        logger.info(
            "🚀 [FACTORY] PARALLEL MODE ENABLED - Creating parallel transcription service:\n"
            f"   - ALL audio files will use parallel mode\n"
            f"   - Workers: {settings.parallel_workers}\n"
            f"   - Chunk duration: {settings.parallel_chunk_duration}s\n"
            f"   - Workers load model ONCE at startup (persistent pool)\n"
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
                logger.error(
                    "[FACTORY] Worker pool is None! This usually means:\n"
                    "  1. Worker pool not yet started (app still initializing)\n"
                    "  2. ENABLE_PARALLEL_TRANSCRIPTION=true but pool failed to start\n"
                    "  3. Worker pool was stopped/crashed"
                )
                logger.warning("[FACTORY] Falling back to single-core service")
                normal_service = WhisperTranscriptionService(
                    model_name=settings.whisper_model,
                    device=settings.whisper_device
                )
                return normal_service
            
            if temp_manager is None or chunk_prep is None:
                logger.error(
                    "[FACTORY] Session manager or chunk prep service is None!\n"
                    f"  temp_manager={temp_manager is not None}\n"
                    f"  chunk_prep={chunk_prep is not None}"
                )
                logger.warning("[FACTORY] Falling back to single-core service")
                normal_service = WhisperTranscriptionService(
                    model_name=settings.whisper_model,
                    device=settings.whisper_device
                )
                return normal_service
            
            parallel_service = WhisperParallelTranscriptionService(
                worker_pool=worker_pool,
                temp_manager=temp_manager,
                chunk_prep_service=chunk_prep,
                model_name=settings.whisper_model
            )
            logger.info(f"[FACTORY] Parallel service created: {type(parallel_service).__name__}")
            logger.info(
                f"[FACTORY] Returning SINGLETON WhisperParallelTranscriptionService (id={id(parallel_service)}). "
                "This instance will be reused for ALL requests."
            )
            
            return parallel_service
            
        except (ImportError, AttributeError) as e:
            logger.warning(f"[FACTORY] Could not initialize parallel service: {e}. Using single-core only.")
            normal_service = WhisperTranscriptionService(
                model_name=settings.whisper_model,
                device=settings.whisper_device
            )
            return normal_service
    else:
        logger.info(
            "📌 [FACTORY] SINGLE-CORE MODE - Creating standard transcription service:\n"
            "   - ALL audio files will use single-core mode\n"
            "   - No worker pool, no chunks\n"
            "   - Processes entire audio file at once"
        )
        normal_service = WhisperTranscriptionService(
            model_name=settings.whisper_model,
            device=settings.whisper_device
        )
        logger.info(f"[FACTORY] Single-core service created: {type(normal_service).__name__}")
        logger.info(
            f"[FACTORY] Returning SINGLETON WhisperTranscriptionService (id={id(normal_service)}). "
            "This instance will be reused for ALL requests."
        )
        return normal_service
