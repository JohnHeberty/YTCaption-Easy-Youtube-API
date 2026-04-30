"""
Unit tests for exceptions module.
"""
import pytest
from fastapi import status

from app.core.exceptions import (
    AudioNormalizationError,
    InvalidAudioFormat,
    FileTooLarge,
    ProcessingError,
    RedisError,
    JobNotFoundError,
    JobExpiredError,
)


class TestAudioNormalizationError:
    """Testes para exceção base."""

    def test_base_exception_has_default_values(self):
        """Deve ter valores padrão."""
        exc = AudioNormalizationError("Test error")
        assert exc.message == "Test error"
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == "AUDIO_NORMALIZATION_ERROR"

    def test_to_dict_returns_correct_structure(self):
        """Deve retornar dicionário com estrutura correta."""
        exc = AudioNormalizationError("Test", status_code=400, error_code="TEST_ERROR")
        result = exc.to_dict()
        assert result == {
            "detail": "Test",
            "error_code": "TEST_ERROR",
            "status_code": 400,
        }

    def test_exception_is_catchable(self):
        """Deve ser capturável como Exception."""
        try:
            raise AudioNormalizationError("Test")
        except AudioNormalizationError as e:
            assert e.message == "Test"


class TestSpecificExceptions:
    """Testes para exceções específicas."""

    def test_invalid_audio_format_defaults(self):
        """Deve ter valores padrão para formato inválido."""
        exc = InvalidAudioFormat()
        assert exc.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert exc.error_code == "INVALID_AUDIO_FORMAT"

    def test_invalid_audio_format_custom_message(self):
        """Deve aceitar mensagem customizada."""
        exc = InvalidAudioFormat("Formato não suportado: MP4")
        assert "MP4" in exc.message

    def test_file_too_large_has_correct_values(self):
        """Deve ter valores corretos para arquivo grande."""
        exc = FileTooLarge(100.5, 50)
        assert exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "100.5MB" in exc.message
        assert "50MB" in exc.message

    def test_processing_error_has_correct_values(self):
        """Deve ter valores corretos para erro de processamento."""
        exc = ProcessingError("Falha no processamento")
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == "PROCESSING_ERROR"
        assert "Falha no processamento" in exc.message

    def test_redis_error_has_correct_values(self):
        """Deve ter valores corretos para erro do Redis."""
        exc = RedisError()
        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error_code == "REDIS_ERROR"

    def test_job_not_found_error_includes_job_id(self):
        """Deve incluir ID do job na mensagem."""
        exc = JobNotFoundError("abc123")
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert "abc123" in exc.message

    def test_job_expired_error_includes_job_id(self):
        """Deve incluir ID do job na mensagem."""
        exc = JobExpiredError("expired_job")
        assert exc.status_code == status.HTTP_410_GONE
        assert "expired_job" in exc.message


class TestExceptionHierarchy:
    """Testes para hierarquia de exceções."""

    def test_all_exceptions_inherit_from_base(self):
        """Todas as exceções devem herdar de AudioNormalizationError."""
        exceptions = [
            InvalidAudioFormat(),
            FileTooLarge(1, 0),
            ProcessingError(),
            RedisError(),
            JobNotFoundError("test"),
            JobExpiredError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, AudioNormalizationError)

    def test_all_exceptions_are_catchable_as_base(self):
        """Devem ser capturáveis como AudioNormalizationError."""
        for exc_class in [InvalidAudioFormat, FileTooLarge, ProcessingError]:
            try:
                if exc_class == FileTooLarge:
                    raise exc_class(1, 0)
                raise exc_class()
            except AudioNormalizationError:
                pass  # Expected
