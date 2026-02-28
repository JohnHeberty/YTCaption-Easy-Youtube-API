"""Domain models, schemas and interfaces."""

from .models import (
    WhisperEngine,
    TranscriptionWord,
    TranscriptionSegment,
    JobRequest,
    Job,
    JobStatus,
    TranscriptionResponse,
)
from .exceptions import (
    AudioTranscriptionException,
    AudioProcessingError,
    ServiceException,
    ResourceError,
    ProcessingTimeoutError,
)
from .interfaces import (
    IModelManager,
    IAudioProcessor,
    IProgressTracker,
    IStorageManager,
    IDeviceManager,
    IJobStore,
    IHealthChecker,
)

__all__ = [
    "WhisperEngine",
    "TranscriptionWord",
    "TranscriptionSegment",
    "JobRequest",
    "Job",
    "JobStatus",
    "TranscriptionResponse",
    "AudioTranscriptionException",
    "AudioProcessingError",
    "ServiceException",
    "ResourceError",
    "ProcessingTimeoutError",
    "IModelManager",
    "IAudioProcessor",
    "IProgressTracker",
    "IStorageManager",
    "IDeviceManager",
    "IJobStore",
    "IHealthChecker",
]
