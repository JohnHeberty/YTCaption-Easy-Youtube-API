from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import hashlib
from common.job_utils.models import StandardJob, JobStatus
from common.datetime_utils import now_brazil
from app.domain.models import PipelineStatus


class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float
    duration: float


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

    # json_encoders removed — Pydantic v2 handles datetime natively

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
