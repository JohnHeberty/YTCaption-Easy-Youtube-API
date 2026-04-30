"""
Testes unitários para Validators.
"""
import pytest

from core.validators import JobIdValidator, URLValidator, YouTubeURLValidator


class TestJobIdValidator:
    """Testes para JobIdValidator."""

    def test_valid_job_id(self):
        """Deve aceitar IDs válidos."""
        valid_ids = [
            "job-123",
            "abc123_def",
            "JOB_ID",
            "123456",
            "a-b-c-123",
            "x" * 64,  # Máximo
        ]
        for job_id in valid_ids:
            assert JobIdValidator.validate(job_id) is True, f"Failed for {job_id}"

    def test_invalid_job_id(self):
        """Deve rejeitar IDs inválidos."""
        invalid_ids = [
            "",  # Vazio
            "../etc/passwd",  # Path traversal
            "job id",  # Espaço
            "job@id",  # Caractere especial
            "a" * 65,  # Muito longo
            None,
            123,  # Não é string
        ]
        for job_id in invalid_ids:
            assert JobIdValidator.validate(job_id) is False, f"Should fail for {job_id}"

    def test_sanitize_valid(self):
        """Sanitize deve retornar ID se válido."""
        assert JobIdValidator.sanitize("valid-id") == "valid-id"

    def test_sanitize_invalid(self):
        """Sanitize deve retornar None se inválido."""
        assert JobIdValidator.sanitize("../etc/passwd") is None
        assert JobIdValidator.sanitize("") is None
        assert JobIdValidator.sanitize(None) is None

    def test_validate_or_raise_valid(self):
        """Não deve lançar exceção para ID válido."""
        result = JobIdValidator.validate_or_raise("valid-id")
        assert result == "valid-id"

    def test_validate_or_raise_invalid(self):
        """Deve lançar ValueError para ID inválido."""
        with pytest.raises(ValueError, match="Invalid job_id"):
            JobIdValidator.validate_or_raise("../etc/passwd")

    def test_max_length(self):
        """Deve respeitar comprimento máximo."""
        long_id = "a" * 64
        assert JobIdValidator.validate(long_id) is True

        too_long = "a" * 65
        assert JobIdValidator.validate(too_long) is False


class TestURLValidator:
    """Testes para URLValidator."""

    def test_valid_urls(self):
        """Deve aceitar URLs válidas."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "http://localhost:8000",
            "https://api.example.com/path",
        ]
        for url in valid_urls:
            assert URLValidator.validate(url) is True, f"Failed for {url}"

    def test_invalid_urls(self):
        """Deve rejeitar URLs inválidas."""
        invalid_urls = [
            "",
            "ftp://example.com",
            "not-a-url",
            "http://",
        ]
        for url in invalid_urls:
            assert URLValidator.validate(url) is False, f"Should fail for {url}"


class TestYouTubeURLValidator:
    """Testes para YouTubeURLValidator."""

    def test_valid_youtube_urls(self):
        """Deve aceitar URLs do YouTube."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ]
        for url in valid_urls:
            assert YouTubeURLValidator.validate(url) is True, f"Failed for {url}"

    def test_invalid_youtube_urls(self):
        """Deve rejeitar URLs que não são do YouTube."""
        invalid_urls = [
            "https://example.com",
            "https://vimeo.com/123456",
            "not-a-url",
            "",
        ]
        for url in invalid_urls:
            assert YouTubeURLValidator.validate(url) is False, f"Should fail for {url}"

    def test_extract_video_id(self):
        """Deve extrair ID do vídeo."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        for url, expected_id in test_cases:
            result = YouTubeURLValidator.extract_video_id(url)
            assert result == expected_id, f"Failed for {url}"

    def test_extract_video_id_invalid(self):
        """Deve retornar None para URLs inválidas."""
        assert YouTubeURLValidator.extract_video_id("https://example.com") is None
        assert YouTubeURLValidator.extract_video_id("") is None
