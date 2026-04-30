"""
Testes para módulo de validação.
"""
import sys
from pathlib import Path

# Adiciona app ao path sem importar app/__init__.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.validators import (
    ValidationError,
    JobIdValidator,
    LanguageValidator,
    EngineValidator,
    FileValidator,
    TranscriptionRequestValidator,
)
from domain.models import WhisperEngine


class TestJobIdValidator:
    """Testes para validação de job_id."""
    
    def test_valid_job_id(self):
        """Aceita job_id válido."""
        assert JobIdValidator.validate("job123") == "job123"
        assert JobIdValidator.validate("JOB_456") == "job_456"
        assert JobIdValidator.validate("job-with-dash") == "job-with-dash"
        assert JobIdValidator.validate("ABC123XYZ789") == "abc123xyz789"
    
    def test_job_id_normalizes_to_lowercase(self):
        """Normaliza para lowercase."""
        assert JobIdValidator.validate("ABC") == "abc"
        assert JobIdValidator.validate("MixedCase123") == "mixedcase123"
    
    def test_job_id_strips_whitespace(self):
        """Remove espaços."""
        assert JobIdValidator.validate("  job123  ") == "job123"
    
    def test_job_id_none_raises_error(self):
        """None gera erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate(None)
        assert exc.value.field == "job_id"
        assert exc.value.code == "REQUIRED"
    
    def test_job_id_empty_raises_error(self):
        """Vazio gera erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("")
        assert exc.value.code == "EMPTY"
    
    def test_job_id_too_short_raises_error(self):
        """Muito curto gera erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("ab")
        assert exc.value.code == "TOO_SHORT"
    
    def test_job_id_too_long_raises_error(self):
        """Muito longo gera erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("a" * 101)
        assert exc.value.code == "TOO_LONG"
    
    def test_job_id_invalid_characters(self):
        """Caracteres inválidos geram erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("job@123")
        assert exc.value.code == "INVALID_FORMAT"
    
    def test_job_id_starts_with_invalid_char(self):
        """Início inválido gera erro."""
        with pytest.raises(ValidationError) as exc:
            JobIdValidator.validate("_job123")
        assert exc.value.code == "INVALID_FORMAT"
    
    def test_is_valid_returns_bool(self):
        """is_valid retorna booleano."""
        assert JobIdValidator.is_valid("valid123") is True
        assert JobIdValidator.is_valid(None) is False
        assert JobIdValidator.is_valid("") is False
        assert JobIdValidator.is_valid("ab") is False


class TestLanguageValidator:
    """Testes para validação de linguagem."""
    
    def test_valid_languages(self):
        """Aceita linguagens válidas."""
        assert LanguageValidator.validate("pt") == "pt"
        assert LanguageValidator.validate("en") == "en"
        assert LanguageValidator.validate("auto") == "auto"
        assert LanguageValidator.validate("PT") == "pt"  # Case insensitive
        assert LanguageValidator.validate("  pt  ") == "pt"  # Strips
    
    def test_invalid_language(self):
        """Linguagem inválida gera erro."""
        with pytest.raises(ValidationError) as exc:
            LanguageValidator.validate("invalid")
        assert exc.value.code == "UNSUPPORTED_LANGUAGE"
    
    def test_language_none_raises_error(self):
        """None gera erro."""
        with pytest.raises(ValidationError) as exc:
            LanguageValidator.validate(None)
        assert exc.value.code == "REQUIRED"


class TestEngineValidator:
    """Testes para validação de engine."""
    
    def test_valid_engine(self):
        """Aceita engine válido."""
        result = EngineValidator.validate(WhisperEngine.FASTER_WHISPER)
        assert result == WhisperEngine.FASTER_WHISPER
    
    def test_none_raises_error(self):
        """None gera erro."""
        with pytest.raises(ValidationError) as exc:
            EngineValidator.validate(None)
        assert exc.value.code == "REQUIRED"
    
    def test_invalid_type_raises_error(self):
        """Tipo inválido gera erro."""
        with pytest.raises(ValidationError) as exc:
            EngineValidator.validate("faster-whisper")
        assert exc.value.code == "TYPE_ERROR"


class TestFileValidator:
    """Testes para validação de arquivo."""
    
    def test_valid_audio_file(self, tmp_path):
        """Aceita arquivo válido."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")
        
        valid, error = FileValidator.validate_audio_file(test_file)
        assert valid is True
        assert error is None
    
    def test_missing_file(self, tmp_path):
        """Arquivo inexistente gera erro."""
        test_file = tmp_path / "missing.mp3"
        
        valid, error = FileValidator.validate_audio_file(test_file)
        assert valid is False
        assert "não encontrado" in error
    
    def test_empty_file(self, tmp_path):
        """Arquivo vazio gera erro."""
        test_file = tmp_path / "empty.mp3"
        test_file.write_bytes(b"")
        
        valid, error = FileValidator.validate_audio_file(test_file)
        assert valid is False
        assert "vazio" in error
    
    def test_invalid_extension(self, tmp_path):
        """Extensão inválida gera erro."""
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"content")
        
        valid, error = FileValidator.validate_audio_file(test_file)
        assert valid is False
        assert "Formato não suportado" in error
    
    def test_validate_content_empty(self):
        """Conteúdo vazio gera erro."""
        valid, error = FileValidator.validate_file_content(b"")
        assert valid is False
        assert "vazio" in error
    
    def test_validate_content_valid(self):
        """Conteúdo válido aceito."""
        valid, error = FileValidator.validate_file_content(b"some content")
        assert valid is True
        assert error is None


class TestTranscriptionRequestValidator:
    """Testes para validação de requisição completa."""
    
    def test_valid_request(self):
        """Aceita requisição válida."""
        result = TranscriptionRequestValidator.validate(
            job_id="valid123",
            language_in="pt",
            engine=WhisperEngine.FASTER_WHISPER
        )
        assert result["job_id"] == "valid123"
        assert result["language_in"] == "pt"
        assert result["language_out"] is None
    
    def test_valid_request_with_optional(self):
        """Aceita requisição com opcionais."""
        result = TranscriptionRequestValidator.validate(
            job_id="valid123",
            language_in="pt",
            language_out="en",
            engine=WhisperEngine.FASTER_WHISPER
        )
        assert result["language_out"] == "en"
    
    def test_invalid_job_id(self):
        """job_id inválido gera erro."""
        with pytest.raises(ValidationError) as exc:
            TranscriptionRequestValidator.validate(
                job_id="ab",
                language_in="pt"
            )
        assert "job_id" in exc.value.message
    
    def test_invalid_language(self):
        """language inválida gera erro."""
        with pytest.raises(ValidationError) as exc:
            TranscriptionRequestValidator.validate(
                language_in="invalid"
            )
        assert "language_in" in exc.value.message
    
    def test_multiple_errors(self):
        """Múltiplos erros combinados."""
        with pytest.raises(ValidationError) as exc:
            TranscriptionRequestValidator.validate(
                job_id="ab",
                language_in="invalid"
            )
        assert exc.value.code == "MULTIPLE_ERRORS"
        assert "job_id" in exc.value.message
        assert "language_in" in exc.value.message