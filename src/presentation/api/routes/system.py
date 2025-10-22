"""
Rotas de sistema.
Health check e informações da API.

v2.1: Rate limiting e melhorias de logging.
"""
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from src.config import settings
from src.domain.interfaces import IStorageService
from src.application.dtos import HealthCheckDTO
from src.presentation.api.dependencies import get_storage_service

router = APIRouter(tags=["System"])

# Tempo de início da aplicação
_start_time = time.time()

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/health",
    response_model=HealthCheckDTO,
    summary="Health check",
    description="Returns the API health status and system information"
)
@limiter.limit("30/minute")  # v2.1: Rate limiting para health check
async def health_check(
    request: Request,
    storage: IStorageService = Depends(get_storage_service)
) -> HealthCheckDTO:
    """
    Verifica o status de saúde da API.
    
    Retorna informações sobre:
    - Status da API
    - Versão
    - Modelo Whisper em uso
    - Uso de armazenamento
    - Tempo de atividade
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        storage_usage = await storage.get_storage_usage()
        
        logger.debug(
            "Health check performed",
            extra={
                "request_id": request_id,
                "uptime": round(time.time() - _start_time, 2),
                "storage_usage": storage_usage
            }
        )
        
        return HealthCheckDTO(
            status="healthy",
            version=settings.app_version,
            whisper_model=settings.whisper_model,
            storage_usage=storage_usage,
            uptime_seconds=round(time.time() - _start_time, 2)
        )
    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "request_id": request_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "HealthCheckError",
                "message": "Health check failed",
                "request_id": request_id
            }
        ) from e


@router.get(
    "/",
    summary="API root",
    description="Returns basic API information"
)
async def root():
    """Endpoint raiz da API."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "API para transcrição de vídeos do YouTube usando Whisper",
        "docs": "/docs",
        "health": "/health"
    }


# ========== NOVOS ENDPOINTS v2.0 ==========

@router.get(
    "/metrics",
    summary="Sistema metrics",
    description="Retorna métricas detalhadas do sistema (cache, performance, etc)"
)
@limiter.limit("20/minute")  # v2.1: Rate limiting para metrics
async def get_metrics(request: Request):
    """
    Retorna métricas completas do sistema.
    
    **Informações retornadas**:
    - Cache de modelos Whisper
    - Cache de transcrições
    - Gerenciador de cleanup de arquivos
    - Capacidades do FFmpeg
    - Worker pool (se habilitado)
    """
    from src.presentation.api.main import (
        model_cache,
        transcription_cache,
        file_cleanup_manager,
        ffmpeg_optimizer,
        worker_pool
    )
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "uptime_seconds": round(time.time() - _start_time, 2),
            "optimizations_version": "2.0",
            "model_cache": None,
            "transcription_cache": None,
            "file_cleanup": None,
            "ffmpeg": None,
            "worker_pool": None
        }
        
        # Cache de modelos Whisper
        if model_cache:
            try:
                metrics["model_cache"] = model_cache.get_cache_stats()
            except Exception as e:
                logger.error(f"Failed to get model cache stats: {e}", exc_info=True)
                metrics["model_cache"] = {"error": str(e)}
        
        # Cache de transcrições
        if transcription_cache:
            try:
                metrics["transcription_cache"] = transcription_cache.get_stats()
            except Exception as e:
                logger.error(f"Failed to get transcription cache stats: {e}", exc_info=True)
                metrics["transcription_cache"] = {"error": str(e)}
        
        # Cleanup manager
        if file_cleanup_manager:
            try:
                metrics["file_cleanup"] = file_cleanup_manager.get_stats()
            except Exception as e:
                logger.error(f"Failed to get cleanup stats: {e}", exc_info=True)
                metrics["file_cleanup"] = {"error": str(e)}
        
        # FFmpeg capabilities
        if ffmpeg_optimizer:
            try:
                capabilities = ffmpeg_optimizer.get_capabilities()
                metrics["ffmpeg"] = {
                    "version": capabilities.version,
                    "has_hw_acceleration": capabilities.has_hw_acceleration,
                    "has_cuda": capabilities.has_cuda,
                    "has_nvenc": capabilities.has_nvenc,
                    "has_nvdec": capabilities.has_nvdec,
                    "has_vaapi": capabilities.has_vaapi,
                    "has_videotoolbox": capabilities.has_videotoolbox,
                    "has_amf": capabilities.has_amf
                }
            except Exception as e:
                logger.error(f"Failed to get ffmpeg capabilities: {e}", exc_info=True)
                metrics["ffmpeg"] = {"error": str(e)}
        
        # Worker pool
        if worker_pool:
            try:
                metrics["worker_pool"] = worker_pool.get_stats()
            except Exception as e:
                logger.error(f"Failed to get worker pool stats: {e}", exc_info=True)
                metrics["worker_pool"] = {"error": str(e)}
        
        logger.debug("Metrics retrieved", extra={"request_id": request_id})
        
        return metrics
    
    except Exception as e:
        logger.error(
            "Failed to get metrics",
            extra={"request_id": request_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "MetricsError",
                "message": "Failed to retrieve metrics",
                "request_id": request_id
            }
        ) from e


@router.post(
    "/cache/clear",
    summary="Limpar caches",
    description="Limpa todos os caches do sistema"
)
async def clear_caches():
    """
    Limpa todos os caches (modelos e transcrições).
    
    **Útil para**:
    - Liberar memória
    - Forçar recarregamento de modelos
    - Debugging
    """
    from src.presentation.api.main import model_cache, transcription_cache
    from loguru import logger
    
    results = {}
    
    # Limpar cache de modelos
    if model_cache:
        try:
            stats_before = model_cache.get_cache_stats()
            model_cache.clear_all()
            results["model_cache"] = {
                "status": "cleared",
                "models_removed": stats_before.get("cache_size", 0)
            }
            logger.info("Model cache cleared via API")
        except Exception as e:
            results["model_cache"] = {"status": "error", "error": str(e)}
    else:
        results["model_cache"] = {"status": "not_initialized"}
    
    # Limpar cache de transcrições
    if transcription_cache:
        try:
            stats_before = transcription_cache.get_stats()
            transcription_cache.clear()
            results["transcription_cache"] = {
                "status": "cleared",
                "entries_removed": stats_before.get("cache_size", 0),
                "size_freed_mb": stats_before.get("total_size_mb", 0)
            }
            logger.info("Transcription cache cleared via API")
        except Exception as e:
            results["transcription_cache"] = {"status": "error", "error": str(e)}
    else:
        results["transcription_cache"] = {"status": "not_initialized"}
    
    return {
        "message": "Cache clearing completed",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }


@router.post(
    "/cleanup/run",
    summary="Executar limpeza manual",
    description="Executa limpeza manual de arquivos temporários antigos"
)
async def run_cleanup():
    """
    Executa limpeza manual de arquivos temporários.
    
    **Remove**:
    - Arquivos temporários antigos (baseado em TTL)
    - Diretórios vazios
    - Sessões de transcrição expiradas
    """
    from src.presentation.api.main import file_cleanup_manager
    from loguru import logger
    
    if not file_cleanup_manager:
        raise HTTPException(status_code=503, detail="Cleanup manager not initialized")
    
    logger.info("Running manual cleanup via API...")
    
    try:
        # Limpar arquivos antigos
        cleanup_stats = await file_cleanup_manager.cleanup_old_files()
        
        logger.info(f"Manual cleanup completed: {cleanup_stats}")
        
        return {
            "message": "Cleanup completed successfully",
            "files": cleanup_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get(
    "/cache/transcriptions",
    summary="Listar transcrições em cache",
    description="Lista todas as transcrições armazenadas em cache"
)
async def list_cached_transcriptions():
    """
    Lista transcrições em cache.
    
    **Informações retornadas**:
    - Hash do arquivo
    - Modelo usado
    - Idioma
    - Idade do cache
    - Número de acessos
    - Tamanho do arquivo
    """
    from src.presentation.api.main import transcription_cache
    
    if not transcription_cache:
        raise HTTPException(status_code=503, detail="Transcription cache not initialized")
    
    try:
        entries = transcription_cache.get_cached_entries()
        stats = transcription_cache.get_stats()
        
        return {
            "total_entries": len(entries),
            "cache_stats": stats,
            "entries": entries,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list cache: {str(e)}")


@router.post(
    "/cache/cleanup-expired",
    summary="Limpar caches expirados",
    description="Remove apenas entradas expiradas do cache de transcrições"
)
async def cleanup_expired_cache():
    """
    Remove entradas expiradas do cache de transcrições.
    
    Menos agressivo que `/cache/clear` - remove apenas caches que
    ultrapassaram o TTL configurado.
    """
    from src.presentation.api.main import transcription_cache, model_cache
    from loguru import logger
    
    results = {}
    
    # Limpar cache de transcrições expiradas
    if transcription_cache:
        try:
            removed = transcription_cache.cleanup_expired()
            results["transcription_cache"] = {
                "status": "cleaned",
                "expired_entries_removed": removed
            }
            logger.info(f"Removed {removed} expired cache entries via API")
        except Exception as e:
            results["transcription_cache"] = {"status": "error", "error": str(e)}
    else:
        results["transcription_cache"] = {"status": "not_initialized"}
    
    # Limpar modelos não usados
    if model_cache:
        try:
            removed = model_cache.cleanup_unused_models()
            results["model_cache"] = {
                "status": "cleaned",
                "unused_models_removed": removed
            }
            logger.info(f"Removed {removed} unused models via API")
        except Exception as e:
            results["model_cache"] = {"status": "error", "error": str(e)}
    else:
        results["model_cache"] = {"status": "not_initialized"}
    
    return {
        "message": "Expired cache cleanup completed",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

