"""
Domain exceptions for the Audio Normalization service.
All exceptions carry an HTTP status_code and a machine-readable error_code so
FastAPI exception handlers can return consistent JSON responses without any
try/except boilerplate in the route handlers.

Backward-compatible: existing ``raise AudioNormalizationException("msg")``
calls continue to work unchanged.
"""
from fastapi import status


class AudioNormalizationException(Exception):
    """Base domain exception — carries HTTP context.

    Args:
        message:     Human-readable error description.
        status_code: HTTP status to return (default 500).
        error_code:  Machine-readable code for clients (default 'AUDIO_NORMALIZATION_ERROR').
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "AUDIO_NORMALIZATION_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "detail": self.message,
            "error_code": self.error_code,
            "status_code": self.status_code,
        }


# ── Specialised subclasses ────────────────────────────────────────────────────

class AudioProcessingError(AudioNormalizationException):
    """Generic audio processing failure (500)."""

    def __init__(self, message: str = "Audio processing failed"):
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="AUDIO_PROCESSING_ERROR",
        )


class FileValidationError(AudioNormalizationException):
    """Input-file validation failure (422)."""

    def __init__(self, message: str = "File validation failed"):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="FILE_VALIDATION_ERROR",
        )


class ResourceNotFoundError(AudioNormalizationException):
    """Requested resource not found (404)."""

    def __init__(self, resource_id: str):
        super().__init__(
            f"Resource not found: {resource_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
        )


class ProcessingTimeoutError(AudioNormalizationException):
    """Processing exceeded time limit (408)."""

    def __init__(self, message: str = "Processing timed out"):
        super().__init__(
            message,
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            error_code="PROCESSING_TIMEOUT",
        )


class ResourceError(AudioNormalizationException):
    """Resource/infrastructure failure (503)."""

    def __init__(self, message: str = "Resource unavailable"):
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="RESOURCE_ERROR",
        )
