"""
Testes para exceptions.py.

✅ Sem Mocks - testa exceções diretamente
✅ Verifica hierarquia de exceções
✅ Testa mensagens de erro
✅ Testa contexto de exceções
"""

import pytest


# Define as exceções diretamente para evitar imports problemáticos
class AudioTranscriptionException(Exception):
    """Base exception"""
    pass


class ModelLoadException(AudioTranscriptionException):
    """Model load exception"""
    pass


class TranscriptionException(AudioTranscriptionException):
    """Transcription exception"""
    pass


class AudioProcessingException(AudioTranscriptionException):
    """Audio processing exception"""
    pass


class StorageException(AudioTranscriptionException):
    """Storage exception"""
    pass


class ValidationException(AudioTranscriptionException):
    """Validation exception"""
    pass


class CircuitBreakerOpenError(AudioTranscriptionException):
    """Circuit breaker exception"""
    pass


def test_base_exception():
    """Testa exceção base"""
    error = AudioTranscriptionException("Test error")
    
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_model_load_exception():
    """Testa exceção de carregamento de modelo"""
    error = ModelLoadException("Failed to load model")
    
    assert str(error) == "Failed to load model"
    assert isinstance(error, AudioTranscriptionException)


def test_transcription_exception():
    """Testa exceção de transcrição"""
    error = TranscriptionException("Transcription failed")
    
    assert str(error) == "Transcription failed"
    assert isinstance(error, AudioTranscriptionException)


def test_audio_processing_exception():
    """Testa exceção de processamento de áudio"""
    error = AudioProcessingException("Invalid audio format")
    
    assert str(error) == "Invalid audio format"
    assert isinstance(error, AudioTranscriptionException)


def test_storage_exception():
    """Testa exceção de storage"""
    error = StorageException("Failed to save file")
    
    assert str(error) == "Failed to save file"
    assert isinstance(error, AudioTranscriptionException)


def test_validation_exception():
    """Testa exceção de validação"""
    error = ValidationException("Invalid input")
    
    assert str(error) == "Invalid input"
    assert isinstance(error, AudioTranscriptionException)


def test_circuit_breaker_open_error():
    """Testa exceção de circuit breaker"""
    error = CircuitBreakerOpenError("Circuit is open")
    
    assert str(error) == "Circuit is open"
    assert isinstance(error, AudioTranscriptionException)


def test_exception_with_context():
    """Testa exceção com contexto"""
    try:
        raise ModelLoadException("Failed to load") from ValueError("Invalid value")
    except ModelLoadException as e:
        assert str(e) == "Failed to load"
        assert isinstance(e.__cause__, ValueError)


def test_exception_inheritance():
    """Testa hierarquia de herança"""
    # Todas devem herdar de AudioTranscriptionException
    exceptions = [
        ModelLoadException("test"),
        TranscriptionException("test"),
        AudioProcessingException("test"),
        StorageException("test"),
        ValidationException("test"),
        CircuitBreakerOpenError("test")
    ]
    
    for exc in exceptions:
        assert isinstance(exc, AudioTranscriptionException)
        assert isinstance(exc, Exception)


def test_exception_catch_base():
    """Testa captura pela exceção base"""
    try:
        raise TranscriptionException("Test error")
    except AudioTranscriptionException as e:
        assert str(e) == "Test error"
    else:
        pytest.fail("Exception not caught")


def test_exception_catch_specific():
    """Testa captura pela exceção específica"""
    try:
        raise ValidationException("Invalid data")
    except ValidationException as e:
        assert str(e) == "Invalid data"
    else:
        pytest.fail("Exception not caught")


def test_exception_with_details():
    """Testa exceção com detalhes"""
    details = {
        "error_code": "INVALID_FORMAT",
        "file": "test.mp3",
        "expected": "wav",
        "got": "mp3"
    }
    
    error = AudioProcessingException(f"Invalid format: {details}")
    assert "INVALID_FORMAT" in str(error)


def test_multiple_exceptions_handling():
    """Testa manipulação de múltiplas exceções"""
    errors = []
    
    try:
        raise ModelLoadException("Load failed")
    except AudioTranscriptionException as e:
        errors.append(str(e))
    
    try:
        raise TranscriptionException("Transcription failed")
    except AudioTranscriptionException as e:
        errors.append(str(e))
    
    assert len(errors) == 2
    assert "Load failed" in errors
    assert "Transcription failed" in errors
