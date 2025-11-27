"""
Exceções customizadas para o serviço de dublagem e clonagem de voz
"""
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class VoiceServiceException(Exception):
    """Exceção base do serviço"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DubbingException(VoiceServiceException):
    """Exceção durante dublagem de texto"""
    def __init__(self, message: str):
        super().__init__(f"Dubbing error: {message}", status_code=500)


class VoiceCloneException(VoiceServiceException):
    """Exceção durante clonagem de voz"""
    def __init__(self, message: str):
        super().__init__(f"Voice cloning error: {message}", status_code=500)


class VoiceProfileNotFoundException(VoiceServiceException):
    """Perfil de voz não encontrado"""
    def __init__(self, voice_id: str):
        super().__init__(f"Voice profile not found: {voice_id}", status_code=404)


class InvalidAudioException(VoiceServiceException):
    """Áudio inválido para processamento"""
    def __init__(self, message: str):
        super().__init__(f"Invalid audio: {message}", status_code=400)


class TTSEngineException(VoiceServiceException):
    """Exceção relacionada ao motor TTS (XTTS)"""
    def __init__(self, message: str):
        super().__init__(f"TTS engine error: {message}", status_code=500)


class InvalidLanguageException(VoiceServiceException):
    """Idioma não suportado"""
    def __init__(self, language: str):
        super().__init__(f"Language not supported: {language}", status_code=400)


class TextTooLongException(VoiceServiceException):
    """Texto excede limite máximo"""
    def __init__(self, length: int, max_length: int):
        super().__init__(f"Text too long: {length} chars (max: {max_length})", status_code=400)


class FileTooLargeException(VoiceServiceException):
    """Arquivo excede limite de tamanho"""
    def __init__(self, size_mb: float, max_size_mb: int):
        super().__init__(f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)", status_code=413)


class ServiceException(VoiceServiceException):
    """Exceção genérica de serviço"""
    pass


# === RVC EXCEPTIONS (Sprint 3) ===

class RvcException(VoiceServiceException):
    """Exceção base para RVC"""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(f"RVC error: {message}", status_code=status_code)


class RvcConversionException(RvcException):
    """Exceção durante conversão RVC"""
    def __init__(self, message: str):
        super().__init__(f"Conversion failed: {message}", status_code=500)


class RvcModelException(RvcException):
    """Exceção relacionada a modelos RVC"""
    def __init__(self, message: str):
        super().__init__(f"Model error: {message}", status_code=400)


class RvcDeviceException(RvcException):
    """Exceção relacionada a device (GPU/CPU)"""
    def __init__(self, message: str):
        super().__init__(f"Device error: {message}", status_code=500)


class RvcModelNotFoundException(RvcModelException):
    """Modelo RVC não encontrado"""
    def __init__(self, model_id: str):
        message = f"Model not found: {model_id}"
        super().__init__(message)
        self.status_code = 404


async def exception_handler(request: Request, exc: VoiceServiceException):
    """Handler global de exceções para FastAPI"""
    logger.error(f"Exception handling request {request.url}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "type": exc.__class__.__name__,
            "path": str(request.url)
        }
    )
