"""
Standardized exception hierarchy for YTCaption microservices.

All services should extend these base classes for service-specific exceptions.
Common exceptions cover: job lifecycle, validation, Redis, HTTP, and processing errors.
"""
from typing import Optional


class ServiceError(Exception):
    """Base exception for all service errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code (e.g., 'JOB_NOT_FOUND')
        status_code: HTTP status code to return
        details: Optional dict with additional error context
    """

    message: str = "An error occurred"
    error_code: str = "SERVICE_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        if message is not None:
            self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Serialize exception to dict for API responses."""
        result = {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
        }
        if self.details:
            result["details"] = self.details
        return result


# ----- Job Lifecycle Errors -----

class JobError(ServiceError):
    """Base error for job operations."""
    message = "Job operation failed"
    error_code = "JOB_ERROR"
    status_code = 500


class JobNotFoundError(JobError):
    """Job not found in the store."""
    message = "Job not found"
    error_code = "JOB_NOT_FOUND"
    status_code = 404


class JobExpiredError(JobError):
    """Job has expired and is no longer available."""
    message = "Job has expired"
    error_code = "JOB_EXPIRED"
    status_code = 410


class JobCreationError(JobError):
    """Failed to create a job."""
    message = "Failed to create job"
    error_code = "JOB_CREATION_ERROR"
    status_code = 500


class JobProcessingError(JobError):
    """Error during job processing."""
    message = "Job processing failed"
    error_code = "JOB_PROCESSING_ERROR"
    status_code = 500


# ----- Validation Errors -----

class ValidationError(ServiceError):
    """Request or data validation failed."""
    message = "Validation failed"
    error_code = "VALIDATION_ERROR"
    status_code = 422


class FileValidationError(ValidationError):
    """File validation failed (wrong type, too large, etc)."""
    message = "File validation failed"
    error_code = "FILE_VALIDATION_ERROR"
    status_code = 400


# ----- Infrastructure Errors -----

class RedisConnectionError(ServiceError):
    """Failed to connect to Redis."""
    message = "Redis connection failed"
    error_code = "REDIS_CONNECTION_ERROR"
    status_code = 503


class ResourceNotFoundError(ServiceError):
    """Requested resource not found."""
    message = "Resource not found"
    error_code = "RESOURCE_NOT_FOUND"
    status_code = 404


class ResourceError(ServiceError):
    """General resource error."""
    message = "Resource error"
    error_code = "RESOURCE_ERROR"
    status_code = 500


class ProcessingTimeoutError(ServiceError):
    """Processing operation timed out."""
    message = "Processing timed out"
    error_code = "PROCESSING_TIMEOUT"
    status_code = 408


# ----- Microservice Communication Errors -----

class MicroserviceError(ServiceError):
    """Error communicating with another microservice."""
    message = "Microservice communication error"
    error_code = "MICROSERVICE_ERROR"
    status_code = 502


class CircuitBreakerOpenError(MicroserviceError):
    """Circuit breaker is open, refusing requests."""
    message = "Circuit breaker is open"
    error_code = "CIRCUIT_BREAKER_OPEN"
    status_code = 503