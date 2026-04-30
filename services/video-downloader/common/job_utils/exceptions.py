"""
Standard exception hierarchy for job operations.

Extends the common exception_handlers with job-specific exceptions
that produce consistent error responses across all services.
"""
from fastapi import status

from common.exception_handlers import BaseServiceException


class JobNotFoundError(BaseServiceException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job not found: {job_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
            details={"job_id": job_id},
        )


class JobExpiredError(BaseServiceException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job expired: {job_id}",
            status_code=status.HTTP_410_GONE,
            error_code="JOB_EXPIRED",
            details={"job_id": job_id},
        )


class JobAlreadyExistsError(BaseServiceException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job already exists: {job_id}",
            status_code=status.HTTP_409_CONFLICT,
            error_code="JOB_ALREADY_EXISTS",
            details={"job_id": job_id},
        )


class JobCreationError(BaseServiceException):
    def __init__(self, reason: str, details: dict = None):
        super().__init__(
            message=f"Failed to create job: {reason}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="JOB_CREATION_ERROR",
            details=details or {},
        )


class JobSubmissionError(BaseServiceException):
    def __init__(self, reason: str, details: dict = None):
        super().__init__(
            message=f"Failed to submit job: {reason}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="JOB_SUBMISSION_ERROR",
            details=details or {},
        )


class JobProcessingError(BaseServiceException):
    def __init__(self, job_id: str, reason: str, details: dict = None):
        full_details = {"job_id": job_id}
        if details:
            full_details.update(details)
        super().__init__(
            message=f"Processing failed for job {job_id}: {reason}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="JOB_PROCESSING_ERROR",
            details=full_details,
        )


class JobValidationError(BaseServiceException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="JOB_VALIDATION_ERROR",
            details=details or {},
        )


class WorkerUnavailableError(BaseServiceException):
    def __init__(self, worker_type: str = "celery"):
        super().__init__(
            message=f"{worker_type} worker unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="WORKER_UNAVAILABLE",
            details={"worker_type": worker_type},
        )