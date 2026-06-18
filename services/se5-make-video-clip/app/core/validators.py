"""
Input validation utilities for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Cada função valida um tipo específico de entrada
- Pure Functions: Sem side effects, retornam True/False ou sanitizam dados
"""

import re
from pathlib import Path
from typing import Optional, List


class QueryValidator:
    """Validação de queries de busca."""

    # Palavras proibidas (SQL injection, XSS)
    FORBIDDEN_PATTERNS = [
        r"[<>]",  # HTML tags
        r"['\";]",  # SQL injection chars
        r"(--|#|/\*|\*/)",  # SQL comments
        r"(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)",  # SQL keywords
    ]

    @classmethod
    def sanitize(cls, query: str) -> str:
        """
        Sanitiza query de busca removendo caracteres perigosos.

        Args:
            query: Query original

        Returns:
            Query sanitizada
        """
        if not query:
            return ""

        # Remove múltiplos espaços e trim
        sanitized = re.sub(r"\s+", " ", query.strip())

        # Remove caracteres proibidos
        for pattern in cls.FORBIDDEN_PATTERNS:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        return sanitized.strip()

    @classmethod
    def is_valid(cls, query: str, min_length: int = 3, max_length: int = 200) -> bool:
        """
        Verifica se query é válida.

        Args:
            query: Query a validar
            min_length: Tamanho mínimo
            max_length: Tamanho máximo

        Returns:
            True se válida, False caso contrário
        """
        if not query:
            return False

        sanitized = cls.sanitize(query)
        return min_length <= len(sanitized) <= max_length


class AudioFileValidator:
    """Validação de arquivos de áudio."""

    # Magic bytes para formatos suportados
    MAGIC_BYTES = {
        ".mp3": [
            (b"ID3", 0),  # ID3 tag
            (bytes([0xFF, 0xFB]), 0),  # MPEG frame sync
            (bytes([0xFF, 0xFA]), 0),
            (bytes([0xFF, 0xF3]), 0),
            (bytes([0xFF, 0xF2]), 0),
        ],
        ".wav": [(b"RIFF", 0)],  # RIFF header
        ".m4a": [(b"ftyp", 4)],  # ftyp box
        ".ogg": [(b"OggS", 0)],  # OggS header
    }

    ALLOWED_EXTENSIONS = frozenset([".mp3", ".wav", ".m4a", ".ogg"])

    @classmethod
    def is_valid_extension(cls, filename: str) -> bool:
        """Verifica se extensão é permitida."""
        ext = Path(filename).suffix.lower()
        return ext in cls.ALLOWED_EXTENSIONS

    @classmethod
    def is_valid_content(cls, content: bytes, filename: str) -> bool:
        """
        Valida magic bytes do arquivo.

        Args:
            content: Conteúdo binário do arquivo
            filename: Nome do arquivo (para determinar formato esperado)

        Returns:
            True se conteúdo é válido para o formato
        """
        ext = Path(filename).suffix.lower()

        if ext not in cls.MAGIC_BYTES:
            return False

        if len(content) < 12:
            return False

        magic_list = cls.MAGIC_BYTES[ext]

        for magic_bytes, offset in magic_list:
            end_offset = offset + len(magic_bytes)
            if len(content) >= end_offset:
                if content[offset:end_offset] == magic_bytes:
                    return True

        return False


class JobParamsValidator:
    """Validação de parâmetros de job."""

    VALID_ASPECT_RATIOS = frozenset(["9:16", "16:9", "1:1", "4:5"])
    VALID_CROP_POSITIONS = frozenset(["center", "top", "bottom"])
    VALID_SUBTITLE_STYLES = frozenset(["static", "dynamic", "minimal"])
    VALID_LANGUAGES = frozenset(["pt", "en", "es"])

    @classmethod
    def validate_max_shorts(cls, value: int, min_val: int = 10, max_val: int = 500) -> bool:
        """Valida quantidade de shorts."""
        return min_val <= value <= max_val

    @classmethod
    def validate_aspect_ratio(cls, value: str) -> bool:
        """Valida proporção de aspecto."""
        return value in cls.VALID_ASPECT_RATIOS

    @classmethod
    def validate_crop_position(cls, value: str) -> bool:
        """Valida posição do crop."""
        return value in cls.VALID_CROP_POSITIONS

    @classmethod
    def validate_subtitle_style(cls, value: str) -> bool:
        """Valida estilo de legenda."""
        return value in cls.VALID_SUBTITLE_STYLES

    @classmethod
    def validate_language(cls, value: str) -> bool:
        """Valida idioma."""
        return value in cls.VALID_LANGUAGES
