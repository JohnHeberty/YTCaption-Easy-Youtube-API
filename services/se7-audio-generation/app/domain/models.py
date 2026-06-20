import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

try:
    from common.job_utils.models import StandardJob, JobStatus, generate_job_id
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo") if ZoneInfo else timezone.utc

    def now_brazil():
        return datetime.now(BRAZIL_TZ)

    class JobStatus(str, Enum):
        PENDING = "pending"
        QUEUED = "queued"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"

    class StandardJob(BaseModel):
        id: str = ""
        status: JobStatus = JobStatus.PENDING
        progress: float = 0.0
        progress_message: Optional[str] = None
        created_at: datetime = Field(default_factory=now_brazil)
        started_at: Optional[datetime] = None
        completed_at: Optional[datetime] = None
        expires_at: datetime = Field(default_factory=lambda: now_brazil())
        error_message: Optional[str] = None
        error_type: Optional[str] = None
        retry_count: int = 0
        stages: dict = Field(default_factory=dict)

        @property
        def is_expired(self) -> bool:
            return now_brazil() > self.expires_at

        def update_progress(self, progress: float, message: str = "") -> None:
            self.progress = progress
            if message:
                self.progress_message = message

        def mark_as_queued(self):
            self.status = JobStatus.QUEUED

        def mark_as_processing(self):
            self.status = JobStatus.PROCESSING
            if not self.started_at:
                self.started_at = now_brazil()

        def mark_as_completed(self, message=None):
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

        def add_stage(self, name: str, display_name: Optional[str] = None):
            class StageInfo(BaseModel):
                name: str
                display_name: str = ""
                status: str = "pending"
                progress: float = 0.0
                started_at: Optional[datetime] = None
                completed_at: Optional[datetime] = None
                error_message: Optional[str] = None

                def start(self):
                    self.status = "processing"
                    self.started_at = now_brazil()

                def complete(self):
                    self.status = "completed"
                    self.completed_at = now_brazil()
                    self.progress = 100.0

                def fail(self, error: str):
                    self.status = "failed"
                    self.completed_at = now_brazil()
                    self.error_message = error

            stage = StageInfo(name=name, display_name=display_name or name)
            self.stages[name] = stage
            return stage


from app.core.constants import (
    DEFAULT_EXAGGERATION,
    DEFAULT_CFG_WEIGHT,
    DEFAULT_TEMPERATURE,
    STAGE_MODEL_LOADING,
    STAGE_TEXT_CHUNKING,
    STAGE_AUDIO_GENERATION,
    STAGE_AUDIO_ASSEMBLY,
    JOB_ID_PREFIX,
)


class AudioGenerationJob(StandardJob):
    input_text: str = ""
    text_hash: str = ""
    voice_id: Optional[str] = None
    has_voice_cloning: bool = False
    exaggeration: float = Field(default=DEFAULT_EXAGGERATION, ge=0.0, le=2.0)
    cfg_weight: float = Field(default=DEFAULT_CFG_WEIGHT, ge=0.0, le=1.0)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    normalize_text: bool = True
    output_file: Optional[str] = None
    output_duration_seconds: Optional[float] = None
    audio_format: str = "wav"

    @classmethod
    def create_new(cls, text: str, voice_id: Optional[str] = None,
                   exaggeration: float = DEFAULT_EXAGGERATION,
                   cfg_weight: float = DEFAULT_CFG_WEIGHT,
                   temperature: float = DEFAULT_TEMPERATURE,
                   normalize_text: bool = True) -> "AudioGenerationJob":
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        job_id = f"{JOB_ID_PREFIX}{text_hash}_{uuid.uuid4().hex[:8]}"
        job = cls(
            id=job_id,
            input_text=text,
            text_hash=text_hash,
            voice_id=voice_id,
            has_voice_cloning=voice_id is not None,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            normalize_text=normalize_text,
        )
        job.add_stage(STAGE_MODEL_LOADING, "Model loading")
        job.add_stage(STAGE_TEXT_CHUNKING, "Text chunking")
        job.add_stage(STAGE_AUDIO_GENERATION, "Audio generation")
        job.add_stage(STAGE_AUDIO_ASSEMBLY, "Audio assembly")
        job.mark_as_queued()
        return job


class VoiceProfile(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=now_brazil)
    updated_at: datetime = Field(default_factory=now_brazil)
    audio_path: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    status: str = "active"

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
