"""
Standard job models for all microservices.

Provides a unified job lifecycle with consistent status tracking,
progress updates, and stage-level observability.
"""
import hashlib
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from common.datetime_utils import now_brazil


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageInfo(BaseModel):
    name: str
    display_name: str = ""
    status: StageStatus = StageStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def start(self):
        self.status = StageStatus.PROCESSING
        self.started_at = now_brazil()

    def complete(self, message: Optional[str] = None):
        self.status = StageStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0
        if message:
            self.progress_message = message

    def fail(self, error: str):
        self.status = StageStatus.FAILED
        self.completed_at = now_brazil()
        self.error_message = error

    def skip(self, reason: Optional[str] = None):
        self.status = StageStatus.SKIPPED
        self.completed_at = now_brazil()
        if reason:
            self.progress_message = reason

    def update_progress(self, progress: float, message: Optional[str] = None):
        self.progress = max(0.0, min(100.0, progress))
        if message:
            self.progress_message = message

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        end = self.completed_at or now_brazil()
        return (end - self.started_at).total_seconds()


class StandardJob(BaseModel):
    id: str = Field(default="")
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    created_at: datetime = Field(default_factory=now_brazil)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: datetime = Field(default_factory=lambda: now_brazil() + timedelta(hours=24))
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    correlation_id: Optional[str] = None
    retry_count: int = 0
    stages: dict[str, StageInfo] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def mark_as_queued(self):
        self.status = JobStatus.QUEUED

    def mark_as_processing(self, message: Optional[str] = None):
        self.status = JobStatus.PROCESSING
        if not self.started_at:
            self.started_at = now_brazil()
        if message:
            self.progress_message = message

    def mark_as_completed(self, message: Optional[str] = None):
        self.status = JobStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0
        if message:
            self.progress_message = message

    def mark_as_failed(self, error: str, error_type: Optional[str] = None):
        self.status = JobStatus.FAILED
        self.completed_at = now_brazil()
        self.error_message = error
        self.error_type = error_type or "UnknownError"

    def mark_as_cancelled(self, reason: Optional[str] = None):
        self.status = JobStatus.CANCELLED
        self.completed_at = now_brazil()
        if reason:
            self.error_message = f"Cancelled: {reason}"

    def update_progress(self, progress: float, message: Optional[str] = None):
        self.progress = max(0.0, min(100.0, progress))
        if message:
            self.progress_message = message

    def increment_retry(self):
        self.retry_count += 1

    def add_stage(self, name: str, display_name: Optional[str] = None) -> StageInfo:
        stage = StageInfo(name=name, display_name=display_name or name)
        self.stages[name] = stage
        return stage

    def get_current_stage(self) -> Optional[StageInfo]:
        processing = [s for s in self.stages.values() if s.status == StageStatus.PROCESSING]
        if processing:
            return processing[0]
        return None

    def update_overall_progress(self):
        if not self.stages:
            return
        total = len(self.stages)
        completed = sum(1 for s in self.stages.values() if s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED))
        self.progress = (completed / total) * 100.0

    @property
    def is_expired(self) -> bool:
        return now_brazil() > self.expires_at

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        end = self.completed_at or now_brazil()
        return (end - self.started_at).total_seconds()


class JobResponse(BaseModel):
    success: bool
    job_id: str
    status: JobStatus
    message: str = ""
    progress: float = 0.0
    correlation_id: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class JobListResponse(BaseModel):
    jobs: list[StandardJob]
    total: int
    page: int = 1
    page_size: int = 50


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict[str, Any]] = None


def generate_job_id(*parts: str, prefix: str = "") -> str:
    if not parts:
        import uuid
        return f"{prefix}{uuid.uuid4()}" if prefix else str(uuid.uuid4())
    content = ":".join(str(p) for p in parts if p)
    hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{prefix}{hash_value}" if prefix else hash_value


def generate_random_job_id(prefix: str = "") -> str:
    import uuid
    uid = uuid.uuid4().hex[:16]
    return f"{prefix}{uid}" if prefix else uid