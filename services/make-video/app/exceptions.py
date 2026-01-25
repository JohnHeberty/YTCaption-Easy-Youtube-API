"""
Custom Exceptions for Make-Video Service
"""


class MakeVideoException(Exception):
    """Base exception para Make-Video Service"""
    def __init__(self, message: str, code: str = "MAKE_VIDEO_ERROR", details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AudioProcessingException(MakeVideoException):
    """Erro no processamento de áudio"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "AUDIO_PROCESSING_ERROR", details)


class VideoProcessingException(MakeVideoException):
    """Erro no processamento de vídeo"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "VIDEO_PROCESSING_ERROR", details)


class MicroserviceException(MakeVideoException):
    """Erro ao chamar microserviço externo"""
    def __init__(self, service: str, message: str, details: dict = None):
        details = details or {}
        details["service"] = service
        super().__init__(message, "MICROSERVICE_ERROR", details)


class InvalidRequestException(MakeVideoException):
    """Request inválido"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "INVALID_REQUEST", details)


class StorageException(MakeVideoException):
    """Erro de storage"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "STORAGE_ERROR", details)


class JobNotFoundException(MakeVideoException):
    """Job não encontrado"""
    def __init__(self, job_id: str):
        super().__init__(
            f"Job {job_id} not found",
            "JOB_NOT_FOUND",
            {"job_id": job_id}
        )
