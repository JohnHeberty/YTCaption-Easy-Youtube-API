"""
Rotas de sistema.
Health check e informações da API.
"""
import time
from fastapi import APIRouter, Depends
from src.config import settings
from src.domain.interfaces import IStorageService
from src.application.dtos import HealthCheckDTO
from src.presentation.api.dependencies import get_storage_service

router = APIRouter(tags=["System"])

# Tempo de início da aplicação
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthCheckDTO,
    summary="Health check",
    description="Returns the API health status and system information"
)
async def health_check(
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
    storage_usage = await storage.get_storage_usage()
    
    return HealthCheckDTO(
        status="healthy",
        version=settings.app_version,
        whisper_model=settings.whisper_model,
        storage_usage=storage_usage,
        uptime_seconds=round(time.time() - _start_time, 2)
    )


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
