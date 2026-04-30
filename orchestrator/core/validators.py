"""
Validadores para entidades do orquestrador.
"""
import re
from typing import Optional

from core.constants import ValidationConstants

JOB_ID_MAX_LENGTH = ValidationConstants.JOB_ID_MAX_LENGTH
JOB_ID_PATTERN = ValidationConstants.JOB_ID_PATTERN


class JobIdValidator:
    """
    Validador de job IDs para prevenir path traversal e injeção.

    Regras de validação:
    - Apenas letras, números, underscore (_) e hífen (-)
    - Tamanho máximo: 64 caracteres
    - Não pode ser vazio
    """

    PATTERN = re.compile(JOB_ID_PATTERN)
    MAX_LENGTH = JOB_ID_MAX_LENGTH

    @classmethod
    def validate(cls, job_id: str) -> bool:
        """
        Valida se job_id é seguro para uso em Redis keys e URLs.

        Args:
            job_id: ID do job a ser validado

        Returns:
            bool: True se válido, False caso contrário

        Example:
            >>> JobIdValidator.validate("valid-job-123")
            True
            >>> JobIdValidator.validate("../etc/passwd")
            False
        """
        if not job_id or not isinstance(job_id, str):
            return False
        if len(job_id) > cls.MAX_LENGTH:
            return False
        return bool(cls.PATTERN.match(job_id))

    @classmethod
    def sanitize(cls, job_id: str) -> Optional[str]:
        """
        Sanitiza job_id, retornando None se inválido.

        Args:
            job_id: ID do job a ser sanitizado

        Returns:
            Optional[str]: job_id se válido, None se inválido
        """
        if not cls.validate(job_id):
            return None
        return job_id[: cls.MAX_LENGTH]

    @classmethod
    def validate_or_raise(cls, job_id: str) -> str:
        """
        Valida job_id e levanta exceção se inválido.

        Args:
            job_id: ID do job a ser validado

        Returns:
            str: job_id validado

        Raises:
            ValueError: Se job_id for inválido
        """
        if not cls.validate(job_id):
            raise ValueError(f"Invalid job_id format: {job_id}")
        return job_id


class URLValidator:
    """Validador de URLs."""

    URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

    @classmethod
    def validate(cls, url: str) -> bool:
        """
        Valida se URL é válida.

        Args:
            url: URL a ser validada

        Returns:
            bool: True se válida, False caso contrário
        """
        if not url or not isinstance(url, str):
            return False
        return bool(cls.URL_PATTERN.match(url))


class YouTubeURLValidator:
    """Validador específico para URLs do YouTube."""

    YOUTUBE_PATTERNS = [
        re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
        re.compile(r"^https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})"),
        re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    ]

    @classmethod
    def validate(cls, url: str) -> bool:
        """
        Valida se URL é um link válido do YouTube.

        Args:
            url: URL a ser validada

        Returns:
            bool: True se é URL do YouTube válida, False caso contrário
        """
        if not url or not isinstance(url, str):
            return False
        return any(pattern.match(url) for pattern in cls.YOUTUBE_PATTERNS)

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        Extrai o ID do vídeo da URL do YouTube.

        Args:
            url: URL do YouTube

        Returns:
            Optional[str]: ID do vídeo ou None se não encontrado
        """
        for pattern in cls.YOUTUBE_PATTERNS:
            match = pattern.match(url)
            if match:
                return match.group(1)
        return None
