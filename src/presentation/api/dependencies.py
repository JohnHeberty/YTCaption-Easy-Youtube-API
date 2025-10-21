"""
Dependency Injection Container.
Gerencia a criação e injeção de dependências seguindo SOLID.

IMPORTANTE: Todos os serviços são SINGLETON para evitar recriar
instâncias a cada requisição. Especialmente crítico para o worker pool
que deve ser compartilhado entre todas as requisições.
"""
from loguru import logger
from src.config import settings
from src.domain.interfaces import (
    IVideoDownloader,
    ITranscriptionService,
    IStorageService
)
from src.infrastructure.youtube import YouTubeDownloader
from src.infrastructure.whisper.transcription_factory import create_transcription_service
from src.infrastructure.storage import LocalStorageService
from src.application.use_cases import (
    TranscribeYouTubeVideoUseCase,
    CleanupOldFilesUseCase
)


class Container:
    """
    Container de injeção de dependências com SINGLETON pattern.
    
    CRÍTICO: Serviços são criados UMA VEZ e reutilizados em todas as requisições.
    Isso garante que o worker pool persistente seja compartilhado corretamente.
    """
    
    _video_downloader: IVideoDownloader = None
    _transcription_service: ITranscriptionService = None
    _storage_service: IStorageService = None
    _transcribe_use_case: TranscribeYouTubeVideoUseCase = None
    _cleanup_use_case: CleanupOldFilesUseCase = None
    
    @classmethod
    def get_video_downloader(cls) -> IVideoDownloader:
        """
        Obtém instância SINGLETON do downloader de vídeos.
        Criado uma vez, reutilizado em todas as requisições.
        """
        if cls._video_downloader is None:
            logger.debug("[CONTAINER] Creating VideoDownloader singleton")
            cls._video_downloader = YouTubeDownloader(
                max_filesize=settings.max_video_size_mb * 1024 * 1024,
                timeout=settings.download_timeout
            )
        return cls._video_downloader
    
    @classmethod
    def get_transcription_service(cls) -> ITranscriptionService:
        """
        Obtém instância SINGLETON do serviço de transcrição.
        
        CRÍTICO: Criado UMA VEZ para garantir que o worker pool persistente
        seja compartilhado entre TODAS as requisições. Se criarmos nova instância
        a cada requisição, teremos referências duplicadas ao worker pool.
        
        IMPORTANTE: O serviço é criado de forma LAZY (preguiçosa), ou seja,
        apenas quando realmente necessário. Isso garante que o worker pool
        já esteja iniciado quando o serviço for criado.
        """
        if cls._transcription_service is None:
            logger.info("[CONTAINER] Creating TranscriptionService singleton (with persistent worker pool)")
            try:
                cls._transcription_service = create_transcription_service()
                logger.info(f"[CONTAINER] TranscriptionService created: {type(cls._transcription_service).__name__}")
            except Exception as e:
                logger.error(f"[CONTAINER] Failed to create TranscriptionService: {e}")
                # Re-raise para que o erro seja propagado corretamente
                raise
        return cls._transcription_service
    
    @classmethod
    def get_storage_service(cls) -> IStorageService:
        """
        Obtém instância SINGLETON do serviço de armazenamento.
        Criado uma vez, reutilizado em todas as requisições.
        """
        if cls._storage_service is None:
            logger.debug("[CONTAINER] Creating StorageService singleton")
            cls._storage_service = LocalStorageService(
                base_temp_dir=settings.temp_dir
            )
        return cls._storage_service
    
    @classmethod
    def get_transcribe_use_case(cls) -> TranscribeYouTubeVideoUseCase:
        """
        Obtém instância SINGLETON do use case de transcrição.
        
        CRÍTICO: Use case também é singleton para garantir que sempre
        use o MESMO serviço de transcrição (que por sua vez usa o mesmo worker pool).
        
        v2.0: Injeta serviços de otimização (cache, validação).
        """
        if cls._transcribe_use_case is None:
            logger.debug("[CONTAINER] Creating TranscribeYouTubeVideoUseCase singleton")
            
            # v2.0: Importar serviços de otimização do main.py
            from src.presentation.api.main import (
                audio_validator,
                transcription_cache
            )
            
            cls._transcribe_use_case = TranscribeYouTubeVideoUseCase(
                video_downloader=cls.get_video_downloader(),
                transcription_service=cls.get_transcription_service(),
                storage_service=cls.get_storage_service(),
                cleanup_after_processing=settings.cleanup_after_processing,
                max_video_duration=settings.max_video_duration_seconds,
                # v2.0: Otimizações opcionais
                audio_validator=audio_validator,
                transcription_cache=transcription_cache
            )
        return cls._transcribe_use_case
    
    @classmethod
    def get_cleanup_use_case(cls) -> CleanupOldFilesUseCase:
        """
        Obtém instância SINGLETON do use case de limpeza.
        Criado uma vez, reutilizado em todas as requisições.
        """
        if cls._cleanup_use_case is None:
            logger.debug("[CONTAINER] Creating CleanupOldFilesUseCase singleton")
            cls._cleanup_use_case = CleanupOldFilesUseCase(
                storage_service=cls.get_storage_service(),
                max_age_hours=settings.max_temp_age_hours
            )
        return cls._cleanup_use_case


# Funções de dependência para FastAPI
# IMPORTANTE: Sempre retornam a MESMA instância (singleton)
def get_transcribe_use_case() -> TranscribeYouTubeVideoUseCase:
    """
    Dependency para FastAPI.
    Retorna sempre a MESMA instância do use case (singleton).
    """
    return Container.get_transcribe_use_case()


def get_cleanup_use_case() -> CleanupOldFilesUseCase:
    """
    Dependency para FastAPI.
    Retorna sempre a MESMA instância do use case (singleton).
    """
    return Container.get_cleanup_use_case()


def get_storage_service() -> IStorageService:
    """
    Dependency para FastAPI.
    Retorna sempre a MESMA instância do serviço (singleton).
    """
    return Container.get_storage_service()
