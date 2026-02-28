"""
Event System - Event-Driven Architecture

Sistema de eventos baseado em CloudEvents specification.
Pattern: Publisher-Subscriber / Observer
"""

from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from typing import Dict, Any, Optional, Callable, Coroutine
import json
import logging
import asyncio
import shortuuid

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Tipos de eventos do sistema"""
    # Job Lifecycle
    JOB_CREATED = "job.created"
    JOB_STARTED = "job.started"
    JOB_STAGE_STARTED = "job.stage.started"
    JOB_STAGE_COMPLETED = "job.stage.completed"
    JOB_STAGE_FAILED = "job.stage.failed"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_RECOVERED = "job.recovered"
    JOB_CANCELLED = "job.cancelled"
    
    # Video Processing
    VIDEO_DOWNLOADING = "video.downloading"
    VIDEO_DOWNLOADED = "video.downloaded"
    VIDEO_DOWNLOAD_FAILED = "video.download.failed"
    VIDEO_VALIDATING = "video.validating"
    VIDEO_VALIDATED = "video.validated"
    VIDEO_REJECTED = "video.rejected"
    VIDEO_BLACKLISTED = "video.blacklisted"
    
    # Audio Processing
    AUDIO_ANALYZING = "audio.analyzing"
    AUDIO_ANALYZED = "audio.analyzed"
    AUDIO_TRANSCRIBING = "audio.transcribing"
    AUDIO_TRANSCRIBED = "audio.transcribed"
    
    # System Events
    SYSTEM_HEALTH_DEGRADED = "system.health.degraded"
    SYSTEM_HEALTH_RESTORED = "system.health.restored"
    SYSTEM_RESOURCE_WARNING = "system.resource.warning"
    SYSTEM_ERROR = "system.error"
    
    # Cache Events
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"
    CACHE_CLEANUP = "cache.cleanup"


@dataclass
class Event:
    """
    Evento padronizado do sistema
    
    Baseado em CloudEvents specification (CNCF standard)
    https://cloudevents.io/
    """
    id: str                           # UUID único do evento
    type: EventType                   # Tipo do evento
    source: str                       # Origem (ex: "make-video/celery-worker")
    timestamp: datetime               # Quando ocorreu
    data: Dict[str, Any]             # Payload do evento
    subject: Optional[str] = None    # Recurso afetado (ex: job_id)
    datacontenttype: str = "application/json"
    specversion: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa para CloudEvents format"""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "source": self.source,
            "specversion": self.specversion,
            "datacontenttype": self.datacontenttype,
            "time": self.timestamp.isoformat(),
            "subject": self.subject,
            "data": self.data
        }
    
    def to_json(self) -> str:
        """Serializa evento para JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Deserializa de dicionário"""
        return cls(
            id=data['id'],
            type=EventType(data['type']),
            source=data['source'],
            timestamp=datetime.fromisoformat(data['time']),
            data=data['data'],
            subject=data.get('subject'),
            datacontenttype=data.get('datacontenttype', 'application/json'),
            specversion=data.get('specversion', '1.0')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        """Deserializa de JSON"""
        return cls.from_dict(json.loads(json_str))


class EventPublisher:
    """
    Publisher de eventos usando Redis Pub/Sub
    
    Pattern: Observer/Publisher-Subscriber
    """
    
    def __init__(self, redis_client, enabled: bool = True):
        """
        Args:
            redis_client: Cliente Redis (aioredis)
            enabled: Se False, eventos não são publicados (útil para testes)
        """
        self.redis = redis_client
        self.enabled = enabled
    
    async def publish(self, event: Event) -> bool:
        """
        Publica evento no canal apropriado
        
        Args:
            event: Evento a ser publicado
        
        Returns:
            True se publicado com sucesso
        """
        if not self.enabled:
            logger.debug(f"Event publishing disabled: {event.type.value}")
            return False
        
        try:
            # Canal baseado no tipo de evento
            channel = f"events:{event.type.value}"
            
            # Publish no canal (Redis Pub/Sub)
            await self.redis.publish(channel, event.to_json())
            
            # Também salvar em stream para histórico (Redis Streams)
            # Streams são persistentes e podem ser consumidos com offset
            stream_name = f"event_stream:{event.type.value.split('.')[0]}"
            await self.redis.xadd(
                stream_name,
                event.to_dict(),
                maxlen=10000  # Manter últimos 10k eventos
            )
            
            logger.debug(f"📡 Event published: {event.type.value} (subject: {event.subject})")
            return True
        
        except Exception as e:
            logger.error(f"Failed to publish event {event.type.value}: {e}")
            return False
    
    async def publish_job_event(
        self,
        event_type: EventType,
        job_id: str,
        data: Dict[str, Any],
        source: str = "make-video/celery-worker"
    ):
        """
        Helper para publicar eventos de job
        
        Args:
            event_type: Tipo do evento
            job_id: ID do job
            data: Dados adicionais
            source: Origem do evento
        """
        event = Event(
            id=shortuuid.uuid(),
            type=event_type,
            source=source,
            timestamp=now_brazil(),
            subject=job_id,
            data={
                "job_id": job_id,
                **data
            }
        )
        
        await self.publish(event)


class EventSubscriber:
    """
    Subscriber de eventos usando Redis Pub/Sub
    
    Usado por dashboards, alertas, analytics, etc.
    """
    
    def __init__(self, redis_client):
        """
        Args:
            redis_client: Cliente Redis (aioredis)
        """
        self.redis = redis_client
        self.handlers: Dict[EventType, Callable] = {}
        self._running = False
        self._task = None
    
    def on(self, event_type: EventType, handler: Callable[[Event], Coroutine]):
        """
        Registra handler para tipo de evento
        
        Args:
            event_type: Tipo de evento a escutar
            handler: Função async que processa o evento
        
        Example:
            async def on_job_completed(event: Event):
                print(f"Job {event.subject} completed!")
            
            subscriber.on(EventType.JOB_COMPLETED, on_job_completed)
        """
        self.handlers[event_type] = handler
        logger.info(f"Handler registered for: {event_type.value}")
    
    async def start(self):
        """
        Inicia listening de eventos (blocking)
        
        Roda em loop infinito consumindo eventos.
        Use com asyncio.create_task() para rodar em background.
        """
        if self._running:
            logger.warning("EventSubscriber already running")
            return
        
        self._running = True
        
        try:
            pubsub = self.redis.pubsub()
            
            # Subscribe em todos os eventos registrados
            channels = [f"events:{et.value}" for et in self.handlers.keys()]
            
            if not channels:
                logger.warning("No event handlers registered")
                return
            
            await pubsub.subscribe(*channels)
            logger.info(f"📡 Subscribed to {len(channels)} event channels")
            
            # Loop de consumo
            async for message in pubsub.listen():
                if not self._running:
                    break
                
                if message['type'] == 'message':
                    await self._handle_message(message)
        
        except Exception as e:
            logger.error(f"EventSubscriber error: {e}")
            raise
        
        finally:
            self._running = False
            logger.info("EventSubscriber stopped")
    
    async def stop(self):
        """Para o subscriber"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def start_background(self):
        """Inicia subscriber em background task"""
        if self._running:
            logger.warning("EventSubscriber already running")
            return
        
        self._task = asyncio.create_task(self.start())
        return self._task
    
    async def _handle_message(self, message: Dict):
        """Processa mensagem recebida"""
        try:
            # Parse evento
            event = Event.from_json(message['data'])
            
            # Buscar handler
            handler = self.handlers.get(event.type)
            
            if handler:
                # Executar handler
                await handler(event)
                logger.debug(f"✅ Event handled: {event.type.value}")
            else:
                logger.warning(f"No handler for event type: {event.type.value}")
        
        except Exception as e:
            logger.error(f"Error handling event: {e}")


# Global event publisher instance (lazy initialization)
_event_publisher = None


def get_event_publisher(redis_client=None) -> EventPublisher:
    """
    Retorna instância singleton do event publisher
    
    Args:
        redis_client: Cliente Redis (necessário na primeira chamada)
    
    Returns:
        EventPublisher instance
    """
    global _event_publisher
    
    if _event_publisher is None:
        if redis_client is None:
            raise ValueError("redis_client required for first initialization")
        
        _event_publisher = EventPublisher(redis_client)
    
    return _event_publisher


# Helper functions para facilitar uso

async def publish_job_started(job_id: str, **kwargs):
    """Helper: Publica evento de job iniciado"""
    publisher = get_event_publisher()
    await publisher.publish_job_event(
        EventType.JOB_STARTED,
        job_id,
        kwargs
    )


async def publish_job_completed(job_id: str, duration_seconds: float, **kwargs):
    """Helper: Publica evento de job completado"""
    publisher = get_event_publisher()
    await publisher.publish_job_event(
        EventType.JOB_COMPLETED,
        job_id,
        {
            "duration_seconds": duration_seconds,
            **kwargs
        }
    )


async def publish_job_failed(job_id: str, error: str, **kwargs):
    """Helper: Publica evento de job falhado"""
    publisher = get_event_publisher()
    await publisher.publish_job_event(
        EventType.JOB_FAILED,
        job_id,
        {
            "error": error,
            **kwargs
        }
    )


async def publish_video_rejected(video_id: str, reason: str, **kwargs):
    """Helper: Publica evento de vídeo rejeitado"""
    publisher = get_event_publisher()
    
    event = Event(
        id=shortuuid.uuid(),
        type=EventType.VIDEO_REJECTED,
        source="make-video/validator",
        timestamp=now_brazil(),
        subject=video_id,
        data={
            "video_id": video_id,
            "reason": reason,
            **kwargs
        }
    )
    
    await publisher.publish(event)
