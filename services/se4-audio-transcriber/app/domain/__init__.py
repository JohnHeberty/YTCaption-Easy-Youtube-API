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
    ITranscriber,
    ILifecycleManaged,
    TranscriptionEngine,
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
    "ITranscriber",
    "ILifecycleManaged",
    "TranscriptionEngine",
    "IModelManager",
    "IAudioProcessor",
    "IProgressTracker",
    "IStorageManager",
    "IDeviceManager",
    "IJobStore",
    "IHealthChecker",
]
