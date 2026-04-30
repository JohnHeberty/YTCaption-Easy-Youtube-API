"""
Tests for validators module.
"""
import pytest

from app.core.validators import (
    ValidationError,
    JobIdValidator,
    MaxResultsValidator,
    TimeoutValidator,
    QueryValidator,
)


class TestJobIdValidator:
    """Tests for JobIdValidator."""

    def test_valid_job_id_simple(self):
        """Test simple valid job ID."""
        assert JobIdValidator.validate("abc123") == "abc123"

    def test_valid_job_id_with_hyphen(self):
        """Test job ID with hyphen."""
        assert JobIdValidator.validate("job-123") == "job-123"

    def test_valid_job_id_with_underscore(self):
        """Test job ID with underscore."""
        assert JobIdValidator.validate("job_123") == "job_123"

    def test_valid_job_id_mixed(self):
        """Test job ID with mixed characters."""
        assert JobIdValidator.validate("Job-123_test") == "Job-123_test"

    def test_valid_job_id_max_length(self):
        """Test job ID at max length (64 chars)."""
        long_id = "a" * 64
        assert JobIdValidator.validate(long_id) == long_id

    def test_invalid_job_id_none(self):
        """Test None job ID raises error."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate(None)
        assert "cannot be None" in str(exc_info.value)
        assert exc_info.value.field == "job_id"

    def test_invalid_job_id_empty(self):
        """Test empty job ID raises error."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate("")
        assert "at least" in str(exc_info.value)

    def test_invalid_job_id_too_long(self):
        """Test job ID exceeding max length raises error."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate("a" * 65)
        assert "not exceed" in str(exc_info.value)

    def test_invalid_job_id_invalid_chars(self):
        """Test job ID with invalid characters raises error."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate("job@123")
        assert "invalid characters" in str(exc_info.value)

    def test_invalid_job_id_non_string(self):
        """Test non-string job ID raises error."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate(12345)
        assert "must be a string" in str(exc_info.value)

    def test_invalid_job_id_spaces(self):
        """Test job ID with spaces raises error."""
        with pytest.raises(ValidationError):
            JobIdValidator.validate("job 123")


class TestMaxResultsValidator:
    """Tests for MaxResultsValidator."""

    def test_valid_max_results_min(self):
        """Test minimum valid max_results."""
        assert MaxResultsValidator.validate(1) == 1

    def test_valid_max_results_max(self):
        """Test maximum valid max_results (50)."""
        assert MaxResultsValidator.validate(50) == 50

    def test_valid_max_results_middle(self):
        """Test middle value."""
        assert MaxResultsValidator.validate(25) == 25

    def test_valid_max_results_string_number(self):
        """Test string number conversion."""
        assert MaxResultsValidator.validate("10") == 10

    def test_invalid_max_results_none(self):
        """Test None raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MaxResultsValidator.validate(None)
        assert "cannot be None" in str(exc_info.value)

    def test_invalid_max_results_zero(self):
        """Test zero raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MaxResultsValidator.validate(0)
        assert "at least" in str(exc_info.value)

    def test_invalid_max_results_negative(self):
        """Test negative number raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MaxResultsValidator.validate(-1)
        assert "at least" in str(exc_info.value)

    def test_invalid_max_results_too_high(self):
        """Test value above 50 raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MaxResultsValidator.validate(51)
        assert "not exceed" in str(exc_info.value)

    def test_invalid_max_results_string_non_number(self):
        """Test non-numeric string raises error."""
        with pytest.raises(ValidationError):
            MaxResultsValidator.validate("abc")


class TestTimeoutValidator:
    """Tests for TimeoutValidator."""

    def test_valid_timeout_min(self):
        """Test minimum valid timeout."""
        assert TimeoutValidator.validate(1) == 1

    def test_valid_timeout_default(self):
        """Test default timeout."""
        assert TimeoutValidator.validate(600) == 600

    def test_valid_timeout_max(self):
        """Test maximum valid timeout (3600)."""
        assert TimeoutValidator.validate(3600) == 3600

    def test_valid_timeout_none_returns_default(self):
        """Test None returns default."""
        assert TimeoutValidator.validate(None) == TimeoutValidator.DEFAULT_TIMEOUT

    def test_valid_timeout_string_number(self):
        """Test string number conversion."""
        assert TimeoutValidator.validate("300") == 300

    def test_invalid_timeout_zero(self):
        """Test zero raises error."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutValidator.validate(0)
        assert "at least" in str(exc_info.value)

    def test_invalid_timeout_negative(self):
        """Test negative raises error."""
        with pytest.raises(ValidationError):
            TimeoutValidator.validate(-1)

    def test_invalid_timeout_too_high(self):
        """Test value above 3600 raises error."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutValidator.validate(3601)
        assert "not exceed" in str(exc_info.value)

    def test_invalid_timeout_string_non_number(self):
        """Test non-numeric string raises error."""
        with pytest.raises(ValidationError):
            TimeoutValidator.validate("abc")


class TestQueryValidator:
    """Tests for QueryValidator."""

    def test_valid_query_simple(self):
        """Test simple valid query."""
        assert QueryValidator.validate("hello") == "hello"

    def test_valid_query_with_spaces(self):
        """Test query with spaces gets stripped."""
        assert QueryValidator.validate("  hello world  ") == "hello world"

    def test_valid_query_long(self):
        """Test query at max length (500)."""
        long_query = "a" * 500
        assert QueryValidator.validate(long_query) == long_query

    def test_invalid_query_none(self):
        """Test None raises error."""
        with pytest.raises(ValidationError):
            QueryValidator.validate(None)

    def test_invalid_query_empty(self):
        """Test empty string raises error."""
        with pytest.raises(ValidationError):
            QueryValidator.validate("")

    def test_invalid_query_whitespace_only(self):
        """Test whitespace-only string raises error."""
        with pytest.raises(ValidationError):
            QueryValidator.validate("   ")

    def test_invalid_query_too_long(self):
        """Test query exceeding max length raises error."""
        with pytest.raises(ValidationError) as exc_info:
            QueryValidator.validate("a" * 501)
        assert "not exceed" in str(exc_info.value)

    def test_invalid_query_non_string(self):
        """Test non-string raises error."""
        with pytest.raises(ValidationError):
            QueryValidator.validate(123)
