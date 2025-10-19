"""
Exceções customizadas para a aplicação.
Segue boas práticas de tratamento de erros.
"""


class DomainException(Exception):
    """Exceção base para erros de domínio."""


class VideoDownloadError(DomainException):
    """Erro ao baixar vídeo."""


class TranscriptionError(DomainException):
    """Erro ao transcrever áudio."""

class StorageError(DomainException):
    """Erro de armazenamento."""


class ValidationError(DomainException):
    """Erro de validação."""

class ResourceNotFoundError(DomainException):
    """Recurso não encontrado."""

class ServiceUnavailableError(DomainException):
    """Serviço indisponível."""
