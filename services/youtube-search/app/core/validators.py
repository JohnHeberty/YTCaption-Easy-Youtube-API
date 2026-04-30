"""
Core validators for YouTube Search service.

Provides input validation following SOLID principles.
"""
import re
from typing import Any, Optional

from common.datetime_utils import now_brazil


class ValidationError(ValueError):
    """Custom validation error with context."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(f"Validation error for '{field}': {message}")


class JobIdValidator:
    """
    Validator for job IDs.

    Validates that job IDs follow the pattern: ^[a-zA-Z0-9_-]{1,64}$
    """

    # Regex for valid job IDs: alphanumeric, underscore, hyphen, 1-64 chars
    PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    MIN_LENGTH = 1
    MAX_LENGTH = 64

    @classmethod
    def validate(cls, job_id: Optional[str]) -> str:
        """
        Validate job_id format.

        Args:
            job_id: The job ID to validate

        Returns:
            The validated job_id

        Raises:
            ValidationError: If job_id is invalid
        """
        if job_id is None:
            raise ValidationError("job_id", "Job ID cannot be None")

        if not isinstance(job_id, str):
            raise ValidationError(
                "job_id", f"Job ID must be a string, got {type(job_id).__name__}"
            )

        if len(job_id) < cls.MIN_LENGTH:
            raise ValidationError(
                "job_id",
                f"Job ID must be at least {cls.MIN_LENGTH} character",
                job_id,
            )

        if len(job_id) > cls.MAX_LENGTH:
            raise ValidationError(
                "job_id",
                f"Job ID must not exceed {cls.MAX_LENGTH} characters",
                job_id[:20] + "..." if len(job_id) > 20 else job_id,
            )

        if not cls.PATTERN.match(job_id):
            raise ValidationError(
                "job_id",
                "Job ID contains invalid characters. "
                "Allowed: letters, numbers, underscores, and hyphens",
                job_id,
            )

        return job_id


class MaxResultsValidator:
    """
    Validator for max_results parameter.

    Ensures max_results is within acceptable range (1-50).
    """

    MIN_VALUE = 1
    MAX_VALUE = 50

    @classmethod
    def validate(cls, value: Any) -> int:
        """
        Validate max_results value.

        Args:
            value: The value to validate

        Returns:
            The validated integer value

        Raises:
            ValidationError: If value is invalid
        """
        if value is None:
            raise ValidationError("max_results", "max_results cannot be None")

        try:
            int_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "max_results",
                f"max_results must be a valid integer, got {type(value).__name__}",
                value,
            ) from exc

        if int_value < cls.MIN_VALUE:
            raise ValidationError(
                "max_results",
                f"max_results must be at least {cls.MIN_VALUE}",
                int_value,
            )

        if int_value > cls.MAX_VALUE:
            raise ValidationError(
                "max_results",
                f"max_results must not exceed {cls.MAX_VALUE}",
                int_value,
            )

        return int_value


class TimeoutValidator:
    """
    Validator for timeout values.

    Ensures timeout is within acceptable range.
    """

    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 3600  # 1 hour max
    DEFAULT_TIMEOUT = 600  # 10 minutes

    @classmethod
    def validate(cls, value: Any) -> int:
        """
        Validate timeout value.

        Args:
            value: The value to validate

        Returns:
            The validated integer value

        Raises:
            ValidationError: If value is invalid
        """
        if value is None:
            return cls.DEFAULT_TIMEOUT

        try:
            int_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "timeout",
                f"timeout must be a valid integer, got {type(value).__name__}",
                value,
            ) from exc

        if int_value < cls.MIN_TIMEOUT:
            raise ValidationError(
                "timeout",
                f"timeout must be at least {cls.MIN_TIMEOUT} second",
                int_value,
            )

        if int_value > cls.MAX_TIMEOUT:
            raise ValidationError(
                "timeout",
                f"timeout must not exceed {cls.MAX_TIMEOUT} seconds (1 hour)",
                int_value,
            )

        return int_value


class QueryValidator:
    """
    Validator for search queries.

    Ensures queries are valid and within length limits.
    """

    MIN_LENGTH = 1
    MAX_LENGTH = 500

    @classmethod
    def validate(cls, query: Any) -> str:
        """
        Validate search query.

        Args:
            query: The query to validate

        Returns:
            The validated query string

        Raises:
            ValidationError: If query is invalid
        """
        if query is None:
            raise ValidationError("query", "Query cannot be None")

        if not isinstance(query, str):
            raise ValidationError(
                "query",
                f"Query must be a string, got {type(query).__name__}",
            )

        query = query.strip()

        if len(query) < cls.MIN_LENGTH:
            raise ValidationError(
                "query",
                f"Query must be at least {cls.MIN_LENGTH} character",
                query,
            )

        if len(query) > cls.MAX_LENGTH:
            raise ValidationError(
                "query",
                f"Query must not exceed {cls.MAX_LENGTH} characters",
                query[:50] + "..." if len(query) > 50 else query,
            )

        return query
