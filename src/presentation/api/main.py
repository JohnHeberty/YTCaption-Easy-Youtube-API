"""
FastAPI Application - Main Entry Point
Configuração principal da API seguindo Clean Architecture e SOLID.
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.config import settings
from src.presentation.api.routes import transcription, system, video_info
from src.presentation.api.middlewares import LoggingMiddleware
from src.presentation.api.dependencies import get_cleanup_use_case, get_storage_service

# Import worker pool para iniciar no startup
from src.infrastructure.whisper.persistent_worker_pool import PersistentWorkerPool
from src.infrastructure.whisper.temp_session_manager import TempSessionManager
from src.infrastructure.whisper.chunk_preparation_service import ChunkPreparationService

# Variáveis globais para worker pool e gerenciadores
worker_pool: PersistentWorkerPool = None
temp_session_manager: TempSessionManager = None
chunk_prep_service: ChunkPreparationService = None


def get_worker_pool() -> PersistentWorkerPool:
    """Retorna instância global do worker pool."""
    return worker_pool


def get_temp_session_manager() -> TempSessionManager:
    """Retorna instância global do session manager."""
    return temp_session_manager


def get_chunk_prep_service() -> ChunkPreparationService:
    """Retorna instância global do chunk preparation service."""
    return chunk_prep_service


# Configurar logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)

# Criar diretório de logs antes de configurar o arquivo de log
if settings.log_file:
    log_path = Path(settings.log_file)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Log directory ensured: {log_path.parent}")
    except Exception as e:
        logger.warning(f"Could not create log directory: {e}")

if settings.log_file:
    try:
        logger.add(
            settings.log_file,
            rotation="100 MB",
            retention="10 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )
        logger.info(f"File logging configured: {settings.log_file}")
    except Exception as e:
        logger.error(f"Failed to configure file logging: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Executado no startup e shutdown.
    """
    global worker_pool, temp_session_manager, chunk_prep_service
    
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_environment}")
    logger.info(f"Whisper Model: {settings.whisper_model}")
    logger.info(f"Device: {settings.whisper_device}")
    logger.info(f"Temp Directory: {settings.temp_dir}")
    logger.info(f"Parallel Transcription: {settings.enable_parallel_transcription}")
    
    # Inicializar serviços de sessão e chunks
    logger.info("Initializing session manager and chunk preparation service...")
    temp_session_manager = TempSessionManager(base_temp_dir=Path(settings.temp_dir))
    chunk_prep_service = ChunkPreparationService(
        chunk_duration_seconds=settings.parallel_chunk_duration
    )
    
    # Inicializar worker pool SE modo paralelo estiver habilitado
    if settings.enable_parallel_transcription:
        logger.info("=" * 60)
        logger.info("PARALLEL MODE ENABLED - Initializing persistent worker pool...")
        logger.info(f"Workers: {settings.parallel_workers}")
        logger.info(f"Chunk Duration: {settings.parallel_chunk_duration}s")
        logger.info("=" * 60)
        
        worker_pool = PersistentWorkerPool(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            num_workers=settings.parallel_workers
        )
        
        # Iniciar workers (carrega modelos na RAM)
        logger.info("Starting worker pool (this may take a few moments)...")
        worker_pool.start()
        
        # Exibir estatísticas do pool
        stats = worker_pool.get_stats()
        logger.info(f"Worker pool started successfully: {stats}")
    else:
        logger.info("Parallel transcription disabled - using single-core mode")
    
    logger.info("=" * 60)
    
    # Limpar arquivos antigos no startup se configurado
    if settings.cleanup_on_startup:
        try:
            logger.info("Performing startup cleanup...")
            cleanup_use_case = get_cleanup_use_case()
            result = await cleanup_use_case.execute()
            logger.info(f"Startup cleanup completed: {result}")
            
            # Também limpar sessões antigas
            if temp_session_manager:
                cleaned = temp_session_manager.cleanup_old_sessions(
                    max_age_hours=settings.max_temp_age_hours
                )
                logger.info(f"Cleaned {cleaned} old sessions")
        except Exception as e:
            logger.warning(f"Startup cleanup failed: {str(e)}")
    
    logger.info("Application startup complete!")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down application...")
    
    # Parar worker pool se estiver rodando
    if worker_pool and worker_pool.running:
        logger.info("Stopping persistent worker pool...")
        worker_pool.stop()
        logger.info("Worker pool stopped")
    
    logger.info("Application shutdown complete")
    logger.info("=" * 60)


# Criar aplicação FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    API REST para transcrição de vídeos do YouTube usando OpenAI Whisper.
    
    ## Características
    
    * 🎥 Download automático de vídeos do YouTube (menor qualidade para otimizar)
    * 🎙️ Transcrição de áudio usando Whisper
    * ⏱️ Segmentos com timestamps precisos
    * 🌍 Suporte multilíngue com detecção automática
    * 🧹 Limpeza automática de arquivos temporários
    * 📊 Monitoramento de saúde e métricas
    
    ## Arquitetura
    
    Implementada seguindo princípios de:
    - Clean Architecture
    - SOLID
    - Dependency Inversion
    - Single Responsibility
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    responses={
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "InternalServerError",
                        "message": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)

# Configurar CORS
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled: {settings.get_cors_origins()}")

# Adicionar middleware de logging
app.add_middleware(LoggingMiddleware)

# Registrar rotas
app.include_router(system.router)
app.include_router(transcription.router)
app.include_router(video_info.router)

logger.info("Routes registered successfully")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handler global para exceções não tratadas."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.presentation.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_environment == "development",
        log_level=settings.log_level.lower()
    )
