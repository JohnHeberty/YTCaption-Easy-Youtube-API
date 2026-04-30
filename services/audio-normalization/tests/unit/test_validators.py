"""
Unit tests for validators module.
"""
import pytest
from pathlib import Path

from app.core.validators import (
    JobIdValidator,
    BooleanValidator,
    FileValidator,
    ProcessingParamsValidator,
    PathValidator,
    ValidationError,
    FileTooLargeError,
)


class TestJobIdValidator:
    """Testes para JobIdValidator."""

    def test_validate_valid_id(self):
        """Deve aceitar ID válido."""
        result = JobIdValidator.validate("job_123-abc")
        assert result == "job_123-abc"

    def test_validate_trims_whitespace(self):
        """Deve remover espaços em branco."""
        result = JobIdValidator.validate("  job_123  ")
        assert result == "job_123"

    def test_validate_empty_id_raises_error(self):
        """Deve rejeitar ID vazio."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("")
        assert exc.value.status_code == 400

    def test_validate_none_id_raises_error(self):
        """Deve rejeitar ID None."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate(None)
        assert exc.value.status_code == 400

    def test_validate_invalid_chars_raises_error(self):
        """Deve rejeitar ID com caracteres inválidos."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("job@123")
        assert "caracteres inválidos" in str(exc.value.detail).lower()

    def test_validate_long_id_raises_error(self):
        """Deve rejeitar ID muito longo."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("a" * 300)
        assert exc.value.status_code == 400

    def test_sanitize_removes_invalid_chars(self):
        """Deve remover caracteres inválidos ao sanitizar."""
        result = JobIdValidator.sanitize("job@123#abc")
        assert result == "job123abc"

    def test_sanitize_truncates_long_id(self):
        """Deve truncar ID muito longo."""
        result = JobIdValidator.sanitize("a" * 300)
        assert len(result) == 255


class TestBooleanValidator:
    """Testes para BooleanValidator."""

    @pytest.mark.parametrize("value,expected", [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
    ])
    def test_validate_true_values(self, value, expected):
        """Deve converter valores true corretamente."""
        result = BooleanValidator.validate(value)
        assert result is expected

    @pytest.mark.parametrize("value,expected", [
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
    ])
    def test_validate_false_values(self, value, expected):
        """Deve converter valores false corretamente."""
        result = BooleanValidator.validate(value)
        assert result is expected

    def test_validate_none_returns_false(self):
        """Deve retornar False para None."""
        result = BooleanValidator.validate(None)
        assert result is False

    def test_validate_invalid_raises_error(self):
        """Deve rejeitar valor inválido."""
        with pytest.raises(ValidationError) as exc:
            BooleanValidator.validate("invalid")
        assert exc.value.status_code == 400

    def test_validate_non_string_raises_error(self):
        """Deve rejeitar tipo não-string."""
        with pytest.raises(ValidationError) as exc:
            BooleanValidator.validate(123)
        assert "Tipo inválido" in str(exc.value.detail)


class TestProcessingParamsValidator:
    """Testes para ProcessingParamsValidator."""

    def test_validate_all_false_by_default(self):
        """Deve retornar False para todos os parâmetros não fornecidos."""
        result = ProcessingParamsValidator.validate()
        assert all(v is False for v in result.values())

    def test_validate_converts_params(self):
        """Deve converter todos os parâmetros."""
        result = ProcessingParamsValidator.validate(
            remove_noise="true",
            convert_to_mono="1",
            apply_highpass_filter="yes",
            set_sample_rate_16k="on",
            isolate_vocals="false"
        )
        assert result["remove_noise"] is True
        assert result["convert_to_mono"] is True
        assert result["apply_highpass_filter"] is True
        assert result["set_sample_rate_16k"] is True
        assert result["isolate_vocals"] is False


class TestPathValidator:
    """Testes para PathValidator."""

    def test_validate_safe_path(self):
        """Deve criar caminho seguro."""
        base_dir = Path("/tmp/uploads")
        result = PathValidator.validate_safe_path(
            base_dir, "test.wav", "job_123"
        )
        assert result == Path("/tmp/uploads/job_123.wav")

    def test_validate_prevents_path_traversal(self):
        """Deve prevenir path traversal."""
        base_dir = Path("/tmp/uploads")
        with pytest.raises(ValidationError) as exc:
            PathValidator.validate_safe_path(
                base_dir, "../../../etc/passwd", "job_123"
            )
        assert "traversal" in str(exc.value.detail).lower()

    def test_validate_invalid_job_id(self):
        """Deve rejeitar job_id vazio após sanitização."""
        base_dir = Path("/tmp/uploads")
        with pytest.raises(ValidationError) as exc:
            PathValidator.validate_safe_path(base_dir, "test.wav", "@#$%")
        assert exc.value.status_code == 500


class TestFileValidator:
    """Testes para FileValidator."""

    def test_validate_file_content_empty_raises_error(self):
        """Deve rejeitar conteúdo vazio."""
        with pytest.raises(ValidationError) as exc:
            FileValidator.validate_file_content(b"")
        assert "vazio" in str(exc.value.detail).lower()

    def test_validate_file_content_too_large_raises_error(self):
        """Deve rejeitar arquivo muito grande."""
        large_content = b"x" * (3 * 1024 * 1024)  # 3MB
        with pytest.raises(FileTooLargeError) as exc:
            FileValidator.validate_file_content(large_content, max_size_mb=1)
        assert exc.value.status_code == 413

    def test_validate_file_content_valid(self):
        """Deve aceitar conteúdo válido."""
        # Não deve lançar exceção
        FileValidator.validate_file_content(b"valid content", max_size_mb=10)
