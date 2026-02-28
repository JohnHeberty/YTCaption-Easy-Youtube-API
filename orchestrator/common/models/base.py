"""
Base models shared across all microservices
"""
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timedelta
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

from typing import Optional
import uuid


class JobStatus(str, Enum):
    """Status padrão para todos os jobs do sistema"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HealthStatus(str, Enum):
    """Status de health check"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BaseJob(BaseModel):
    """
    Modelo base para todos os jobs do sistema.
    
    Fornece funcionalidade comum como:
    - Geração automática de IDs
    - Tracking de timestamps
    - Progress tracking
    - Expiração automática
    - Correlation IDs para tracing distribuído
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: datetime = Field(
        default_factory=lambda: now_brazil() + timedelta(hours=24)
    )
    
    # Progress tracking
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    
    # Error handling
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    
    # Observability
    correlation_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    retry_count: int = 0
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o job expirou"""
        return now_brazil() > self.expires_at
    
    @property
    def is_terminal(self) -> bool:
        """Verifica se o job está em estado terminal"""
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED
        ]
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Retorna duração do job em segundos"""
        if not self.started_at:
            return None
        end_time = self.completed_at or now_brazil()
        return (end_time - self.started_at).total_seconds()
    
    def mark_as_queued(self):
        """Marca job como enfileirado"""
        self.status = JobStatus.QUEUED
    
    def mark_as_processing(self, message: Optional[str] = None):
        """Marca job como em processamento"""
        self.status = JobStatus.PROCESSING
        if not self.started_at:
            self.started_at = now_brazil()
        if message:
            self.progress_message = message
    
    def mark_as_completed(self, message: Optional[str] = None):
        """Marca job como completado"""
        self.status = JobStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0
        if message:
            self.progress_message = message
    
    def mark_as_failed(self, error: str, error_type: Optional[str] = None):
        """Marca job como falho"""
        self.status = JobStatus.FAILED
        self.completed_at = now_brazil()
        self.error_message = error
        self.error_type = error_type or "UnknownError"
    
    def mark_as_cancelled(self, reason: Optional[str] = None):
        """Marca job como cancelado"""
        self.status = JobStatus.CANCELLED
        self.completed_at = now_brazil()
        if reason:
            self.error_message = f"Cancelled: {reason}"
    
    def update_progress(self, progress: float, message: Optional[str] = None):
        """Atualiza progresso do job"""
        self.progress = max(0.0, min(100.0, progress))
        if message:
            self.progress_message = message
    
    def increment_retry(self):
        """Incrementa contador de retries"""
        self.retry_count += 1


class BaseHealthResponse(BaseModel):
    """Resposta padrão de health check"""
    status: HealthStatus
    service: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.now)
    uptime_seconds: Optional[float] = None
    
    # Dependências
    redis_connected: bool = False
    celery_available: bool = False
    
    # Métricas
    active_jobs: int = 0
    total_processed: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
