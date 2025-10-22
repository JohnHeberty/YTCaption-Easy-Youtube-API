"""
Rotas de sistema.
Health check e informações da API.

v2.1: Rate limiting e melhorias de logging.
v2.2: Healthcheck detalhado, métricas Prometheus, Circuit Breaker.
"""
import time
import subprocess
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    "/health/ready",
    summary="Readiness check",
    description="Kubernetes/Docker readiness probe - validates all critical components"
)
@limiter.limit("60/minute")  # Mais permissivo para health checks automáticos
async def readiness_check(request: Request) -> Dict[str, Any]:
    """
    Readiness probe detalhado para Kubernetes/Docker.
    
    Valida TODOS os componentes críticos:
    - Model cache
    - Transcription cache
    - FFmpeg
    - Whisper library
    - Storage
    - File cleanup manager
    
    Returns:
        200: Todos componentes saudáveis
        503: Um ou mais componentes falharam
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    checks: Dict[str, Any] = {
        "api": {"status": "healthy", "details": "API responding"},
        "model_cache": {"status": "unknown", "details": None},
        "transcription_cache": {"status": "unknown", "details": None},
        "ffmpeg": {"status": "unknown", "details": None},
        "whisper": {"status": "unknown", "details": None},
        "storage": {"status": "unknown", "details": None},
        "file_cleanup": {"status": "unknown", "details": None}
    }
    
    # 1. Validar Model Cache
    try:
        from src.presentation.api.main import model_cache
        if model_cache:
            stats = model_cache.get_cache_stats()
            checks["model_cache"] = {
                "status": "healthy",
                "details": f"Cache size: {stats.get('cache_size', 0)}, Total usage: {stats.get('total_usage_count', 0)}"
            }
        else:
            checks["model_cache"] = {
                "status": "unhealthy",
                "details": "Model cache not initialized"
            }
    except Exception as e:
        checks["model_cache"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # 2. Validar Transcription Cache
    try:
        from src.presentation.api.main import transcription_cache
        if transcription_cache:
            stats = transcription_cache.get_stats()
            checks["transcription_cache"] = {
                "status": "healthy",
                "details": f"Size: {stats.get('cache_size', 0)}/{stats.get('max_size', 0)}, Hit rate: {stats.get('hit_rate_percent', 0)}%"
            }
        else:
            checks["transcription_cache"] = {
                "status": "unhealthy",
                "details": "Transcription cache not initialized"
            }
    except Exception as e:
        checks["transcription_cache"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # 3. Validar FFmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            checks["ffmpeg"] = {
                "status": "healthy",
                "details": version_line[:100]  # Primeiros 100 chars
            }
        else:
            checks["ffmpeg"] = {
                "status": "unhealthy",
                "details": "FFmpeg returned non-zero exit code"
            }
    except subprocess.TimeoutExpired:
        checks["ffmpeg"] = {
            "status": "unhealthy",
            "details": "FFmpeg command timed out"
        }
    except FileNotFoundError:
        checks["ffmpeg"] = {
            "status": "unhealthy",
            "details": "FFmpeg not found in PATH"
        }
    except Exception as e:
        checks["ffmpeg"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # 4. Validar Whisper
    try:
        import whisper
        checks["whisper"] = {
            "status": "healthy",
            "details": f"Whisper library loaded, version: {getattr(whisper, '__version__', 'unknown')}"
        }
    except ImportError as e:
        checks["whisper"] = {
            "status": "unhealthy",
            "details": f"Failed to import whisper: {str(e)}"
        }
    except Exception as e:
        checks["whisper"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # 5. Validar Storage
    try:
        from src.presentation.api.dependencies import get_storage_service
        storage = get_storage_service()
        # Tentar operação básica
        temp_files = await storage.get_temp_files()
        checks["storage"] = {
            "status": "healthy",
            "details": f"Storage accessible, temp files: {len(temp_files)}"
        }
    except Exception as e:
        checks["storage"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # 6. Validar File Cleanup Manager
    try:
        from src.presentation.api.main import file_cleanup_manager
        if file_cleanup_manager:
            stats = file_cleanup_manager.get_stats()
            checks["file_cleanup"] = {
                "status": "healthy",
                "details": f"Tracked files: {stats.get('tracked_files', 0)}, Running: {stats.get('periodic_cleanup_running', False)}"
            }
        else:
            checks["file_cleanup"] = {
                "status": "unhealthy",
                "details": "File cleanup manager not initialized"
            }
    except Exception as e:
        checks["file_cleanup"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # Verificar se todos estão saudáveis
    all_healthy = all(
        check.get("status") == "healthy" 
        for check in checks.values()
    )
    
    overall_status = "ready" if all_healthy else "not_ready"
    http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    logger.info(
        f"Readiness check: {overall_status}",
        extra={
            "request_id": request_id,
            "all_healthy": all_healthy,
            "checks": {k: v["status"] for k, v in checks.items()}
        }
    )
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "healthy": sum(1 for c in checks.values() if c.get("status") == "healthy"),
            "unhealthy": sum(1 for c in checks.values() if c.get("status") == "unhealthy"),
            "unknown": sum(1 for c in checks.values() if c.get("status") == "unknown")
        }
    }, http_status


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

