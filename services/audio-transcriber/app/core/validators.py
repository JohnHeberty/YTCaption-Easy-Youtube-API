"""
Módulo de validação para o serviço de transcrição de áudio.

Fornece validadores centralizados para:
- job_id (formato e existência)
- Linguagens suportadas
- Parâmetros de entrada
- Configurações de engine

Regras:
- job_id: string alfanumérica com underscore e hífen, 3-100 caracteres
- language_in/language_out: códigos ISO 639-1 ou 'auto'
- engine: valores válidos do enum WhisperEngine
"""

import re
from typing import Optional, Tuple
from pathlib import Path

from ..domain.models import WhisperEngine, JobStatus
from .config import get_supported_languages


class ValidationError(Exception):
    """Exceção para erros de validação."""

    def __init__(self, field: str, message: str, code: str = "INVALID"):
        self.field = field
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {field}: {message}")


class JobIdValidator:
    """
    Validação de job_id seguindo padrões consistentes.

    Regras:
    - Apenas caracteres alfanuméricos, underscore e hífen
    - Tamanho entre 3 e 100 caracteres
    - Não pode começar ou terminar com underscore/hífen
    - Case-insensitive (normalizado para lowercase)
    """

    # Regex: começa com alfanumérico, pode ter alfanumérico, underscore, hífen
    # e deve terminar com alfanumérico
    JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]{3,}$")
    MIN_LENGTH = 3
    MAX_LENGTH = 100

    @classmethod
    def validate(cls, job_id: Optional[str]) -> str:
        """
        Valida e normaliza um job_id.

        Args:
            job_id: ID do job a validar

        Returns:
            str: job_id normalizado (lowercase)

        Raises:
            ValidationError: Se job_id for inválido
        """
        if job_id is None:
            raise ValidationError(
                field="job_id",
                message="job_id é obrigatório",
                code="REQUIRED"
            )

        if not isinstance(job_id, str):
            raise ValidationError(
                field="job_id",
                message=f"job_id deve ser string, recebido {type(job_id).__name__}",
                code="TYPE_ERROR"
            )

        stripped = job_id.strip()

        if not stripped:
            raise ValidationError(
                field="job_id",
                message="job_id não pode ser vazio",
                code="EMPTY"
            )

        if len(stripped) < cls.MIN_LENGTH:
            raise ValidationError(
                field="job_id",
                message=f"job_id muito curto (mínimo {cls.MIN_LENGTH} caracteres)",
                code="TOO_SHORT"
            )

        if len(stripped) > cls.MAX_LENGTH:
            raise ValidationError(
                field="job_id",
                message=f"job_id muito longo (máximo {cls.MAX_LENGTH} caracteres)",
                code="TOO_LONG"
            )

        if not cls.JOB_ID_PATTERN.match(stripped):
            raise ValidationError(
                field="job_id",
                message="job_id contém caracteres inválidos. Use apenas letras, números, underscore e hífen",
                code="INVALID_FORMAT"
            )

        return stripped.lower()

    @classmethod
    def is_valid(cls, job_id: Optional[str]) -> bool:
        """Retorna True se job_id é válido sem lançar exceção."""
        try:
            cls.validate(job_id)
            return True
        except ValidationError:
            return False


class LanguageValidator:
    """
    Validação de códigos de linguagem.

    Suporta códigos ISO 639-1 e 'auto' para detecção automática.
    """

    _supported_languages: Optional[list[str]] = None

    @classmethod
    def _get_supported(cls) -> list[str]:
        """Cache de linguagens suportadas."""
        if cls._supported_languages is None:
            cls._supported_languages = get_supported_languages()
        return cls._supported_languages

    @classmethod
    def validate(cls, language: Optional[str], field_name: str = "language") -> str:
        """
        Valida um código de linguagem.

        Args:
            language: Código a validar (ex: 'pt', 'en', 'auto')
            field_name: Nome do campo para mensagens de erro

        Returns:
            str: código normalizado (lowercase)

        Raises:
            ValidationError: Se linguagem não for suportada
        """
        if language is None:
            raise ValidationError(
                field=field_name,
                message=f"{field_name} é obrigatório",
                code="REQUIRED"
            )

        if not isinstance(language, str):
            raise ValidationError(
                field=field_name,
                message=f"{field_name} deve ser string, recebido {type(language).__name__}",
                code="TYPE_ERROR"
            )

        normalized = language.strip().lower()

        if not normalized:
            raise ValidationError(
                field=field_name,
                message=f"{field_name} não pode ser vazio",
                code="EMPTY"
            )

        supported = cls._get_supported()

        if normalized not in [lang.lower() for lang in supported]:
            raise ValidationError(
                field=field_name,
                message=f"Linguagem '{language}' não suportada. Use 'auto' ou código ISO 639-1 válido",
                code="UNSUPPORTED_LANGUAGE"
            )

        return normalized

    @classmethod
    def is_supported(cls, language: Optional[str]) -> bool:
        """Retorna True se linguagem é suportada."""
        try:
            cls.validate(language)
            return True
        except ValidationError:
            return False


class EngineValidator:
    """Validação de engines de transcrição."""

    @classmethod
    def validate(cls, engine: WhisperEngine) -> WhisperEngine:
        """
        Valida que o engine é válido.

        Args:
            engine: Valor do enum WhisperEngine

        Returns:
            WhisperEngine: mesmo valor

        Raises:
            ValidationError: Se engine for inválido
        """
        if engine is None:
            raise ValidationError(
                field="engine",
                message="engine é obrigatório",
                code="REQUIRED"
            )

        if not isinstance(engine, WhisperEngine):
            raise ValidationError(
                field="engine",
                message=f"engine deve ser WhisperEngine, recebido {type(engine).__name__}",
                code="TYPE_ERROR"
            )

        return engine


class FileValidator:
    """Validação de arquivos de áudio."""

    MAX_FILE_SIZE_MB = 500
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.mp4', '.m4a', '.ogg', '.flac', '.aac', '.wma'}

    @classmethod
    def validate_audio_file(cls, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Valida um arquivo de áudio.

        Args:
            file_path: Caminho do arquivo

        Returns:
            Tuple[bool, Optional[str]]: (válido, mensagem_erro)
        """
        if not file_path.exists():
            return False, f"Arquivo não encontrado: {file_path}"

        if not file_path.is_file():
            return False, f"Caminho não é um arquivo: {file_path}"

        # Tamanho
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > cls.MAX_FILE_SIZE_MB:
                return False, (
                    f"Arquivo muito grande ({size_mb:.1f}MB). "
                    f"Máximo permitido: {cls.MAX_FILE_SIZE_MB}MB"
                )
            if size_mb == 0:
                return False, "Arquivo está vazio (0 bytes)"
        except OSError as e:
            return False, f"Erro ao verificar tamanho do arquivo: {e}"

        # Extensão
        ext = file_path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            return False, (
                f"Formato não suportado: {ext}. "
                f"Formatos suportados: {', '.join(cls.SUPPORTED_EXTENSIONS)}"
            )

        return True, None

    @classmethod
    def validate_file_content(cls, content: bytes, max_size_mb: int = None) -> Tuple[bool, Optional[str]]:
        """
        Valida conteúdo de arquivo em memória.

        Args:
            content: Bytes do arquivo
            max_size_mb: Tamanho máximo permitido

        Returns:
            Tuple[bool, Optional[str]]: (válido, mensagem_erro)
        """
        max_size = max_size_mb or cls.MAX_FILE_SIZE_MB

        if not content:
            return False, "Conteúdo do arquivo está vazio"

        size_mb = len(content) / (1024 * 1024)
        if size_mb > max_size:
            return False, (
                f"Arquivo muito grande ({size_mb:.1f}MB). "
                f"Máximo permitido: {max_size}MB"
            )

        return True, None


class TranscriptionRequestValidator:
    """Validador composto para requisições de transcrição."""

    @classmethod
    def validate(
        cls,
        job_id: Optional[str] = None,
        language_in: Optional[str] = None,
        language_out: Optional[str] = None,
        engine: Optional[WhisperEngine] = None,
        file_path: Optional[Path] = None,
        validate_file: bool = False
    ) -> dict:
        """
        Valida uma requisição completa de transcrição.

        Args:
            job_id: ID do job
            language_in: Idioma de entrada
            language_out: Idioma de saída (opcional)
            engine: Engine de transcrição
            file_path: Caminho do arquivo (opcional)
            validate_file: Se True, valida o arquivo também

        Returns:
            dict: Valores validados e normalizados

        Raises:
            ValidationError: Se qualquer validação falhar
        """
        errors = []
        validated = {}

        # Valida job_id
        try:
            if job_id:
                validated["job_id"] = JobIdValidator.validate(job_id)
        except ValidationError as e:
            errors.append(e)

        # Valida language_in
        try:
            validated["language_in"] = LanguageValidator.validate(language_in, "language_in")
        except ValidationError as e:
            errors.append(e)

        # Valida language_out (opcional)
        if language_out is not None:
            try:
                validated["language_out"] = LanguageValidator.validate(language_out, "language_out")
            except ValidationError as e:
                errors.append(e)
        else:
            validated["language_out"] = None

        # Valida engine
        if engine is not None:
            try:
                validated["engine"] = EngineValidator.validate(engine)
            except ValidationError as e:
                errors.append(e)

        # Valida arquivo
        if validate_file and file_path is not None:
            valid, error_msg = FileValidator.validate_audio_file(file_path)
            if not valid:
                errors.append(ValidationError(
                    field="file",
                    message=error_msg,
                    code="INVALID_FILE"
                ))

        # Se há erros, lança exceção com todos
        if errors:
            if len(errors) == 1:
                raise errors[0]

            # Múltiplos erros
            raise ValidationError(
                field="multiple",
                message="; ".join(f"{e.field}: {e.message}" for e in errors),
                code="MULTIPLE_ERRORS"
            )

        return validated


# Exporta validadores principais
__all__ = [
    "ValidationError",
    "JobIdValidator",
    "LanguageValidator",
    "EngineValidator",
    "FileValidator",
    "TranscriptionRequestValidator",
]