"""
FastAPI Application - Main Entry Point
Configuração principal da API seguindo Clean Architecture e SOLID.

v2.1: Logging melhorado, rate limiting, circuit breakers, timeout global.
"""
import sys
import uuid
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import time

# Rate Limiting (v2.1)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Prometheus Metrics (v2.2)
from prometheus_client import make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import settings
from src.presentation.api.routes import transcription, system, video_info, upload_transcription
from src.presentation.api.middlewares import LoggingMiddleware
from src.presentation.api.dependencies import get_cleanup_use_case, get_storage_service

# Import worker pool para iniciar no startup
from src.infrastructure.whisper.persistent_worker_pool import PersistentWorkerPool
from src.infrastructure.whisper.temp_session_manager import TempSessionManager
from src.infrastructure.whisper.chunk_preparation_service import ChunkPreparationService

# NOVO: Imports das otimizações v2.0
from src.infrastructure.whisper.model_cache import get_model_cache
from src.infrastructure.storage.file_cleanup_manager import FileCleanupManager
from src.infrastructure.cache import get_transcription_cache
from src.infrastructure.validators import AudioValidator
from src.infrastructure.utils import get_ffmpeg_optimizer

# Variáveis globais para worker pool e gerenciadores
worker_pool: PersistentWorkerPool = None
temp_session_manager: TempSessionManager = None
chunk_prep_service: ChunkPreparationService = None

# NOVO: Variáveis globais para serviços otimizados
model_cache = None
file_cleanup_manager = None
transcription_cache = None
audio_validator = None
ffmpeg_optimizer = None

# ============= RATE LIMITER (v2.1) =============
# Inicializar rate limiter ANTES da criação do app
limiter = Limiter(key_func=get_remote_address)
logger.info("Rate limiter initialized (key=IP address)")


def get_worker_pool() -> PersistentWorkerPool:
    """Retorna instância global do worker pool."""
    return worker_pool


def get_temp_session_manager() -> TempSessionManager:
    """Retorna instância global do session manager."""
    return temp_session_manager


def get_chunk_prep_service() -> ChunkPreparationService:
    """Retorna instância global do chunk preparation service."""
    return chunk_prep_service


# NOVO: Funções getter para serviços otimizados
def get_model_cache_service():
    """Retorna cache global de modelos Whisper."""
    return model_cache


def get_file_cleanup_manager_service():
    """Retorna gerenciador de cleanup de arquivos."""
    return file_cleanup_manager


def get_transcription_cache_service():
    """Retorna cache de transcrições."""
    return transcription_cache


def get_audio_validator_service():
    """Retorna validador de áudio."""
    return audio_validator


def get_ffmpeg_optimizer_service():
    """Retorna otimizador FFmpeg."""
    return ffmpeg_optimizer


# ============= LOGGING ESTRUTURADO MELHORADO (v2.1) =============
logger.remove()

# Formato estruturado para debugging detalhado
detailed_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<yellow>PID:{process}</yellow> | "
    "<level>{message}</level> | "
    "{extra}"
)

# Console logging (stderr)
logger.add(
    sys.stderr,
    format=detailed_format,
    level=settings.log_level,
    colorize=True,
    backtrace=True,  # Mostra stack trace completo
    diagnose=True    # Mostra variáveis locais em erros
)

# Criar diretório de logs antes de configurar o arquivo de log
if settings.log_file:
    log_path = Path(settings.log_file)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Log directory ensured: {log_path.parent}")
    except Exception as e:
        logger.warning(f"Could not create log directory: {e}")

# File logging (persistente)
if settings.log_file:
    try:
        logger.add(
            settings.log_file,
            rotation="100 MB",
            retention="30 days",  # Aumentado de 10 para 30 dias
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | PID:{process} | {message}", # pylint: disable=line-too-long
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe async logging
            serialize=False  # JSON format para parsing
        )
        logger.info(f"File logging configured: {settings.log_file}")
    except Exception as e:
        logger.error(f"Failed to configure file logging: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Executado no startup e shutdown.
    """
    global worker_pool, temp_session_manager, chunk_prep_service
    global model_cache, file_cleanup_manager, transcription_cache, audio_validator, ffmpeg_optimizer
    
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version} (OPTIMIZED v2.0)")
    logger.info(f"Environment: {settings.app_environment}")
    logger.info(f"Whisper Model: {settings.whisper_model}")
    logger.info(f"Device: {settings.whisper_device}")
    logger.info(f"Temp Directory: {settings.temp_dir}")
    logger.info(f"Parallel Transcription: {settings.enable_parallel_transcription}")
    logger.info("=" * 60)
    
    # ========== OTIMIZAÇÕES v2.0 ==========
    
    # 1. Inicializar cache de modelos Whisper
    logger.info("🚀 [v2.0] Initializing Whisper model cache (singleton)...")
    model_cache = get_model_cache()
    model_cache.set_unload_timeout(settings.whisper_model_cache_timeout_minutes)
    logger.info(f"✅ Model cache initialized (timeout: {settings.whisper_model_cache_timeout_minutes}min)")
    
    # 2. Inicializar cache de transcrições
    if settings.enable_transcription_cache:
        logger.info("🚀 [v2.0] Initializing transcription cache (LRU)...")
        transcription_cache = get_transcription_cache(
            max_size=settings.cache_max_size,
            ttl_hours=settings.cache_ttl_hours
        )
        logger.info(f"✅ Transcription cache initialized (size: {settings.cache_max_size}, TTL: {settings.cache_ttl_hours}h)") # pylint: disable=line-too-long
    else:
        logger.info("⚠️  Transcription cache disabled")
    
    # 3. Inicializar gerenciador de cleanup
    logger.info("🚀 [v2.0] Initializing file cleanup manager...")
    file_cleanup_manager = FileCleanupManager(
        base_temp_dir=Path(settings.temp_dir),
        default_ttl_hours=settings.max_temp_age_hours,
        cleanup_interval_minutes=settings.cleanup_interval_minutes
    )
    
    # Iniciar limpeza periódica
    if settings.enable_periodic_cleanup:
        file_cleanup_manager.start_periodic_cleanup()
        logger.info(f"✅ Periodic cleanup started (interval: {settings.cleanup_interval_minutes}min)")
    else:
        logger.info("⚠️  Periodic cleanup disabled")
    
    # 4. Inicializar validador de áudio
    logger.info("🚀 [v2.0] Initializing audio validator...")
    audio_validator = AudioValidator()
    logger.info("✅ Audio validator initialized")
    
    # 5. Inicializar otimizador FFmpeg
    logger.info("🚀 [v2.0] Initializing FFmpeg optimizer...")
    ffmpeg_optimizer = get_ffmpeg_optimizer()
    capabilities = ffmpeg_optimizer.get_capabilities()
    logger.info(
        f"✅ FFmpeg optimizer initialized: "
        f"version={capabilities.version}, "
        f"hw_accel={capabilities.has_hw_acceleration}, "
        f"cuda={capabilities.has_cuda}, "
        f"nvenc={capabilities.has_nvenc}"
    )
    
    logger.info("=" * 60)
    
    # ========== SERVIÇOS EXISTENTES ==========
    
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
    logger.info("Shutting down application (OPTIMIZED v2.0)...")
    
    # ========== SHUTDOWN OTIMIZAÇÕES v2.0 ==========
    
    # 1. Parar cleanup periódico
    if file_cleanup_manager:
        logger.info("Stopping file cleanup manager...")
        await file_cleanup_manager.stop_periodic_cleanup()
        logger.info("✅ File cleanup manager stopped")
    
    # 2. Limpar cache de modelos
    if model_cache:
        logger.info("Clearing model cache...")
        stats = model_cache.get_cache_stats()
        logger.info(f"Model cache stats: {stats}")
        model_cache.clear_all()
        logger.info("✅ Model cache cleared")
    
    # 3. Limpar cache de transcrições
    if transcription_cache:
        logger.info("Clearing transcription cache...")
        stats = transcription_cache.get_stats()
        logger.info(f"Transcription cache stats: {stats}")
        transcription_cache.clear()
        logger.info("✅ Transcription cache cleared")
    
    # ========== SHUTDOWN SERVIÇOS EXISTENTES ==========
    
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

# ============= RATE LIMITER CONFIGURATION (v2.1) =============
# Adicionar rate limiter state ao app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
logger.info("✅ Rate limiter configured and exception handler registered")

# ============= MIDDLEWARES (v2.1 com melhorias) =============

# 1. GZip Compression Middleware (comprime respostas >1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("GZip compression enabled (minimum_size=1KB)")

# 2. CORS Middleware
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled: {settings.get_cors_origins()}")

# 3. Request ID + Enhanced Logging Middleware
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    """
    Adiciona request_id único e logging detalhado para cada requisição.
    CRÍTICO para debugging de erros 500.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    
    # Log inicial da request
    logger.info(
        f"⬇️  INCOMING REQUEST",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )
    
    try:
        # Processar request
        response = await call_next(request)
        
        # Calcular tempo de processamento
        process_time = time.time() - start_time
        
        # Adicionar headers customizados
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.3f}s"
        
        # Log de resposta
        logger.info(
            f"⬆️  OUTGOING RESPONSE",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "process_time": f"{process_time:.3f}s",
                "path": request.url.path
            }
        )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        
        # Log CRÍTICO de exceção não capturada
        logger.error(
            f"❌ UNHANDLED EXCEPTION IN MIDDLEWARE",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "process_time": f"{process_time:.3f}s",
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )
        
        # Retornar erro 500 estruturado
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": f"An unexpected error occurred: {type(e).__name__}",
                "request_id": request_id,
                "details": str(e) if settings.app_environment == "development" else None
            },
            headers={"X-Request-ID": request_id}
        )

# 4. Legacy Logging Middleware (manter compatibilidade)
app.add_middleware(LoggingMiddleware)

# ============= PROMETHEUS METRICS INSTRUMENTATION (v2.2) =============
logger.info("Configuring Prometheus metrics instrumentation...")

# Instrumentador padrão (métricas automáticas: latency, requests, etc.)
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=False,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health", "/health/ready"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True
)

# Ativar instrumentação (adiciona middleware automaticamente)
instrumentator.instrument(app)

# Criar endpoint /metrics para Prometheus scraping
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

logger.info("✅ Prometheus metrics configured at /metrics")

# Registrar rotas
app.include_router(system.router)
app.include_router(transcription.router)
app.include_router(video_info.router)
app.include_router(upload_transcription.router)

logger.info("Routes registered successfully")


# ============= EXCEPTION HANDLERS MELHORADOS (v2.1) =============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handler global MELHORADO para exceções não tratadas.
    Captura TODAS as exceptions e loga com contexto completo.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Log CRÍTICO com stack trace completo
    logger.critical(
        f"🔥 GLOBAL EXCEPTION HANDLER TRIGGERED",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown",
            "traceback": traceback.format_exc(),
            "request_headers": dict(request.headers),
            "query_params": str(request.query_params)
        },
        exc_info=True
    )
    
    # Retornar resposta estruturada
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": type(exc).__name__,
            "message": "An unexpected error occurred. Please check server logs.",
            "request_id": request_id,
            "details": str(exc) if settings.app_environment == "development" else None,
            "path": request.url.path
        },
        headers={"X-Request-ID": request_id}
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
