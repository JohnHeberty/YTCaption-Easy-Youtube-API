"""
Exceções customizadas para a aplicação.
Segue boas práticas de tratamento de erros.
"""


class DomainException(Exception):
    """Exceção base para erros de domínio."""
    ...


class VideoDownloadError(DomainException):
    """Erro ao baixar vídeo."""
    pass


class TranscriptionError(DomainException):
    """Erro ao transcrever áudio."""
    ...


class StorageError(DomainException):
    """Erro de armazenamento."""
    pass


class ValidationError(DomainException):
    """Erro de validação."""
    ...


class ResourceNotFoundError(DomainException):
    """Recurso não encontrado."""
    pass


class ServiceUnavailableError(DomainException):
    """Serviço indisponível."""
    ...
