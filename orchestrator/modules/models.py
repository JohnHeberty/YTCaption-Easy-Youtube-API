"""
Orchestrator pipeline job model extending StandardJob.

Replaces the monolithic PipelineJob with a model that inherits
the standard lifecycle methods while preserving pipeline-specific
stage tracking.
"""
from typing import Optional, List, Dict, Any
from pydantic import Field
import hashlib

from common.job_utils.models import StandardJob, JobStatus, StageInfo, StageStatus
from common.datetime_utils import now_brazil


class TranscriptionSegment(StandardJob if False else object):
    text: str
    start: float
    end: float
    duration: float


from pydantic import BaseModel


class TranscriptionSegmentModel(BaseModel):
    text: str
    start: float
    end: float
    duration: float


class PipelineStatus(str):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    NORMALIZING = "normalizing"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineJobV2(StandardJob):
    youtube_url: str = ""
    language: str = "auto"
    language_out: Optional[str] = None
    remove_noise: bool = True
    convert_to_mono: bool = True
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = True
    isolate_vocals: bool = False
    transcription_text: Optional[str] = None
    transcription_file: Optional[str] = None
    audio_file: Optional[str] = None

    # Mapping of pipeline-specific statuses to StandardJob statuses
    _STATUS_MAP = {
        PipelineStatus.QUEUED: JobStatus.QUEUED,
        PipelineStatus.DOWNLOADING: JobStatus.PROCESSING,
        PipelineStatus.NORMALIZING: JobStatus.PROCESSING,
        PipelineStatus.TRANSCRIBING: JobStatus.PROCESSING,
        PipelineStatus.COMPLETED: JobStatus.COMPLETED,
        PipelineStatus.FAILED: JobStatus.FAILED,
        PipelineStatus.CANCELLED: JobStatus.CANCELLED,
    }

    _PIPELINE_STATUS_MAP = {
        JobStatus.QUEUED: PipelineStatus.QUEUED,
        JobStatus.PROCESSING: PipelineStatus.TRANSCRIBING,
        JobStatus.COMPLETED: PipelineStatus.COMPLETED,
        JobStatus.FAILED: PipelineStatus.FAILED,
        JobStatus.CANCELLED: PipelineStatus.CANCELLED,
    }

    class Config:
        json_encoders = {**StandardJob.Config.json_encoders}

    @classmethod
    def create_new(cls, youtube_url: str, **kwargs) -> "PipelineJobV2":
        unique_str = f"{youtube_url}_{now_brazil().isoformat()}"
        job_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]

        pipeline_stages = {
            "download": "Downloading video",
            "normalization": "Normalizing audio",
            "transcription": "Transcribing audio",
        }

        job = cls(
            id=job_id,
            youtube_url=youtube_url,
            **kwargs,
        )
        for stage_name, display_name in pipeline_stages.items():
            job.add_stage(stage_name, display_name)

        job.mark_as_queued()
        return job


class PipelineRequest(BaseModel):
    youtube_url: str = "https://www.youtube.com/watch?v=_xhulIrM6hw"
    language: Optional[str] = None
    language_out: Optional[str] = None
    remove_noise: Optional[bool] = True
    convert_to_mono: Optional[bool] = True
    apply_highpass_filter: Optional[bool] = False
    set_sample_rate_16k: Optional[bool] = True


class PipelineResponse(BaseModel):
    job_id: str
    status: str
    message: str
    youtube_url: str
    overall_progress: float = 0.0


class PipelineStatusResponse(BaseModel):
    job_id: str
    youtube_url: str
    status: str
    overall_progress: float
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    stages: Dict[str, Dict[str, Any]]
    transcription_text: Optional[str] = None
    transcription_segments: Optional[list] = None
    transcription_file: Optional[str] = None
    audio_file: Optional[str] = None
    error_message: Optional[str] = None


# Backward compatibility aliases
PipelineJob = PipelineJobV2