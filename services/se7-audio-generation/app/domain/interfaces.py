from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import AudioGenerationJob, VoiceProfile


class IModelManager(ABC):
    """Manages TTS model lifecycle and generation."""

    @abstractmethod
    def load_model(self) -> None:
        pass

    @abstractmethod
    def unload_model(self) -> None:
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        pass

    @abstractmethod
    def generate(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        temperature: float = 0.8,
        cfg_weight: float = 0.5,
    ) -> Any:
        pass


class IJobStore(ABC):
    """Persistence for audio generation jobs."""

    @abstractmethod
    def save_job(self, job: AudioGenerationJob) -> None:
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> AudioGenerationJob | None:
        pass

    @abstractmethod
    def update_job(self, job: AudioGenerationJob) -> None:
        pass

    @abstractmethod
    def list_jobs(self, limit: int = 20) -> list[AudioGenerationJob]:
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        pass


class IVoiceStore(ABC):
    """Persistence for voice profiles."""

    @abstractmethod
    def save_profile(self, profile: VoiceProfile) -> None:
        pass

    @abstractmethod
    def get_profile(self, voice_id: str) -> VoiceProfile | None:
        pass

    @abstractmethod
    def list_profiles(self) -> list[VoiceProfile]:
        pass

    @abstractmethod
    def delete_profile(self, voice_id: str) -> bool:
        pass


class ITTSGenerator(ABC):
    """Orchestrates TTS audio generation."""

    @abstractmethod
    def generate(
        self, job: AudioGenerationJob, audio_prompt_path: str | None = None
    ) -> AudioGenerationJob:
        pass
