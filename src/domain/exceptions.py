"""
Exceções customizadas para a aplicação.
Segue boas práticas de tratamento de erros.
"""


class DomainException(Exception):
    """Exceção base para erros de domínio."""
    pass


class VideoDownloadError(DomainException):
    """Erro ao baixar vídeo."""
    pass


class TranscriptionError(DomainException):
    """Erro ao transcrever áudio."""
    pass


class StorageError(DomainException):
    """Erro de armazenamento."""
    pass


class ValidationError(DomainException):
    """Erro de validação."""
    pass


class ResourceNotFoundError(DomainException):
    """Recurso não encontrado."""
    pass


class ServiceUnavailableError(DomainException):
    """Serviço indisponível."""
    pass
