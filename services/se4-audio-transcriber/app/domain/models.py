"""
Audio transcriber job model extending StandardJob.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from common.job_utils.models import StandardJob, JobStatus
except ImportError:
    raise

from common.datetime_utils import now_brazil  # noqa: F401


def _now_brazil() -> datetime:
    return now_brazil()


class WhisperEngine(str, Enum):
    FASTER_WHISPER = "faster-whisper"
    OPENAI_WHISPER = "openai-whisper"
    WHISPERX = "whisperx"


class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float
    duration: float
    words: list[TranscriptionWord] | None = None

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, value: float, info: Any) -> float:
        start = info.data.get("start")
        if start is not None and value < start:
            raise ValueError("end deve ser maior ou igual a start")
        return value

    @field_validator("duration")
    @classmethod
    def validate_duration_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("duration deve ser >= 0")
        return value


class TranscriptionWord(BaseModel):
    word: str
    start: float
    end: float
    probability: float = Field(default=1.0, ge=0.0, le=1.0)


class TranscriptionResponse(BaseModel):
    transcription_id: str | None = None
    filename: str | None = None
    language: str | None = None
    full_text: str
    segments: list[TranscriptionSegment] = Field(default_factory=list)
    total_segments: int = 0
    duration: float = 0.0
    language_detected: str | None = None
    language_out: str | None = None
    was_translated: bool = False
    processing_time: float | None = None


class AudioTranscriptionJob(StandardJob):
    received_at: datetime = Field(default_factory=_now_brazil)
    updated_at: datetime = Field(default_factory=_now_brazil)
    input_file: str | None = None
    output_file: str | None = None
    filename: str | None = None
    file_size: int | None = None
    file_size_input: int | None = None
    file_size_output: int | None = None
    operation: str = "transcribe"
    language_in: str = "auto"
    language_out: str | None = None
    language_detected: str | None = None
    engine: WhisperEngine = WhisperEngine.FASTER_WHISPER
    transcription_text: str | None = None
    transcription_segments: list[TranscriptionSegment] | None = None
    processing_time: float | None = None
    status_message: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    dlq_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_language_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "language_in" not in data and data.get("language"):
                data["language_in"] = data["language"]
        return data

    @field_validator("transcription_segments", mode="before")
    @classmethod
    def normalize_segments(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, list):
            normalized = []
            for item in value:
                if isinstance(item, TranscriptionSegment):
                    normalized.append(item)
                elif isinstance(item, dict):
                    normalized.append(TranscriptionSegment(**item))
            return normalized
        return value

    @field_validator("language_in")
    @classmethod
    def normalize_language_in(cls, value: str) -> str:
        return (value or "auto").lower()

    @field_validator("language_out")
    @classmethod
    def normalize_language_out(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @classmethod
    def create_new(
        cls,
        filename: str,
        operation: str = "transcribe",
        language_in: str = "auto",
        language_out: str | None = None,
        engine: WhisperEngine = WhisperEngine.FASTER_WHISPER,
        **kwargs: Any,
    ) -> AudioTranscriptionJob:
        from common.job_utils.models import generate_job_id

        normalized_engine = engine.value if isinstance(engine, WhisperEngine) else str(engine)
        unique_str = f"{filename}_{language_in}_{normalized_engine}"
        job_id = generate_job_id(unique_str, prefix="at_")
        job = cls(
            id=job_id,
            filename=filename,
            operation=operation,
            language_in=language_in,
            language_out=language_out,
            engine=engine,
            **kwargs,
        )
        job.add_stage("transcription", "Audio transcription")
        job.mark_as_queued()
        return job

    @property
    def needs_translation(self) -> bool:
        return self.language_out is not None and self.language_out != self.language_in

    @property
    def language(self) -> str:
        """Compatibilidade com payload legado que usa campo `language`."""
        return self.language_in

    @language.setter
    def language(self, value: str) -> None:
        self.language_in = value

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data.setdefault("language", self.language_in)
        return data


class JobRequest(BaseModel):
    operation: str = "transcribe"
    language_in: str = "auto"
    language_out: str | None = None
    engine: WhisperEngine = WhisperEngine.FASTER_WHISPER


Job = AudioTranscriptionJob
