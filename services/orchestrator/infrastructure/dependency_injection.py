"""
Injeção de Dependência para o orquestrador.

Gerencia a criação e lifecycle das dependências.
"""
from datetime import datetime
from functools import lru_cache
from typing import Optional

from core.config import get_settings
from domain.interfaces import MicroserviceClientInterface
from infrastructure.circuit_breaker import CircuitBreaker
from infrastructure.microservice_client import MicroserviceClient
from infrastructure.redis_store import RedisStore, get_store
from services.health_checker import HealthChecker
from services.pipeline_orchestrator import PipelineOrchestrator

_app_start_time: Optional[datetime] = None


def set_app_start_time(dt: datetime) -> None:
    global _app_start_time
    _app_start_time = dt


def get_app_start_time() -> Optional[datetime]:
    return _app_start_time


@lru_cache()
def get_circuit_breaker(
    failure_threshold: Optional[int] = None,
    recovery_timeout: Optional[int] = None,
    name: str = "default"
) -> CircuitBreaker:
    """
    Factory para CircuitBreaker.

    Args:
        failure_threshold: Número de falhas para abrir circuito
        recovery_timeout: Segundos até tentar reabrir
        name: Nome identificador

    Returns:
        CircuitBreaker configurado
    """
    settings = get_settings()
    return CircuitBreaker(
        failure_threshold=failure_threshold or settings.circuit_breaker_max_failures,
        recovery_timeout=recovery_timeout or settings.circuit_breaker_recovery_timeout,
        name=name,
    )


def get_microservice_client(service_name: str) -> MicroserviceClient:
    """
    Factory para MicroserviceClient.

    Args:
        service_name: Nome do serviço

    Returns:
        MicroserviceClient configurado
    """
    return MicroserviceClient(service_name)


@lru_cache()
def get_health_checker() -> HealthChecker:
    """
    Factory para HealthChecker com todos os serviços.

    Returns:
        HealthChecker configurado
    """
    clients = {
        "video-downloader": get_microservice_client("video-downloader"),
        "audio-normalization": get_microservice_client("audio-normalization"),
        "audio-transcriber": get_microservice_client("audio-transcriber"),
    }
    return HealthChecker(clients)


def get_pipeline_orchestrator(redis_store: Optional[RedisStore] = None) -> PipelineOrchestrator:
    """
    Factory para PipelineOrchestrator com todas as dependências.

    Args:
        redis_store: Store Redis opcional

    Returns:
        PipelineOrchestrator configurado
    """
    if redis_store is None:
        redis_store = get_store()

    video_client = get_microservice_client("video-downloader")
    audio_client = get_microservice_client("audio-normalization")
    transcription_client = get_microservice_client("audio-transcriber")
    health_checker = get_health_checker()

    return PipelineOrchestrator(
        video_client=video_client,
        audio_client=audio_client,
        transcription_client=transcription_client,
        health_checker=health_checker,
        redis_store=redis_store,
    )


def get_orchestrator_with_custom_clients(
    video_client: Optional[MicroserviceClientInterface] = None,
    audio_client: Optional[MicroserviceClientInterface] = None,
    transcription_client: Optional[MicroserviceClientInterface] = None,
    redis_store: Optional[RedisStore] = None,
) -> PipelineOrchestrator:
    """
    Factory para PipelineOrchestrator com clients customizáveis (útil para testes).

    Args:
        video_client: Cliente de vídeo customizado
        audio_client: Cliente de áudio customizado
        transcription_client: Cliente de transcrição customizado
        redis_store: Store Redis customizado

    Returns:
        PipelineOrchestrator configurado
    """
    if redis_store is None:
        redis_store = get_store()

    video_client = video_client or get_microservice_client("video-downloader")
    audio_client = audio_client or get_microservice_client("audio-normalization")
    transcription_client = transcription_client or get_microservice_client("audio-transcriber")

    # Cria HealthChecker com clients customizados
    clients = {
        "video-downloader": video_client,
        "audio-normalization": audio_client,
        "audio-transcriber": transcription_client,
    }
    health_checker = HealthChecker(clients)

    return PipelineOrchestrator(
        video_client=video_client,
        audio_client=audio_client,
        transcription_client=transcription_client,
        health_checker=health_checker,
        redis_store=redis_store,
    )
