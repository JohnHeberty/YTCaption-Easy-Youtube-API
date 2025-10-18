"""
FastAPI Application - Main Entry Point
Configuração principal da API seguindo Clean Architecture e SOLID.
"""
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.config import settings
from src.presentation.api.routes import transcription, system, video_info
from src.presentation.api.middlewares import LoggingMiddleware
from src.presentation.api.dependencies import get_cleanup_use_case, get_storage_service


# Configurar logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)

if settings.log_file:
    logger.add(
        settings.log_file,
        rotation="100 MB",
        retention="10 days",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Executado no startup e shutdown.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_environment}")
    logger.info(f"Whisper Model: {settings.whisper_model}")
    logger.info(f"Device: {settings.whisper_device}")
    logger.info(f"Temp Directory: {settings.temp_dir}")
    logger.info("=" * 60)
    
    # Limpar arquivos antigos no startup se configurado
    if settings.cleanup_on_startup:
        try:
            logger.info("Performing startup cleanup...")
            cleanup_use_case = get_cleanup_use_case()
            result = await cleanup_use_case.execute()
            logger.info(f"Startup cleanup completed: {result}")
        except Exception as e:
            logger.warning(f"Startup cleanup failed: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


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
