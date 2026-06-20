from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from common.job_utils.models import StandardJob, JobStatus, generate_job_id
from common.datetime_utils import now_brazil


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
    voice_id: str | None = None
    has_voice_cloning: bool = False
    exaggeration: float = Field(default=DEFAULT_EXAGGERATION, ge=0.0, le=2.0)
    cfg_weight: float = Field(default=DEFAULT_CFG_WEIGHT, ge=0.0, le=1.0)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    normalize_text: bool = True
    output_file: str | None = None
    output_duration_seconds: float | None = None
    audio_format: str = "wav"

    @classmethod
    def create_new(cls, text: str, voice_id: str | None = None,
                   exaggeration: float = DEFAULT_EXAGGERATION,
                   cfg_weight: float = DEFAULT_CFG_WEIGHT,
                   temperature: float = DEFAULT_TEMPERATURE,
                   normalize_text: bool = True) -> AudioGenerationJob:
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

    # json_encoders removed — Pydantic v2 handles datetime natively
