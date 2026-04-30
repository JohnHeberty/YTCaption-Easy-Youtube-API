"""
Validadores para o serviço de normalização de áudio.

Segue princípios SOLID - cada validador tem responsabilidade única.
"""
import re
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..core.constants import (
    JOB_CONSTANTS,
    VALIDATION_CONSTANTS,
    FILE_CONSTANTS,
    AUDIO_CONSTANTS,
)

logger = get_logger(__name__)


class ValidationError(HTTPException):
    """Erro de validação com código HTTP apropriado."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


class FileTooLargeError(ValidationError):
    """Arquivo excede tamanho máximo permitido."""

    def __init__(self, size_mb: float, max_size_mb: int):
        super().__init__(
            detail=f"Arquivo muito grande ({size_mb:.2f}MB). Máximo permitido: {max_size_mb}MB",
            status_code=413
        )


class InvalidFileFormatError(ValidationError):
    """Formato de arquivo não suportado."""

    def __init__(self, filename: str):
        super().__init__(
            detail=f"Formato de arquivo não suportado: {filename}",
            status_code=415
        )


class JobIdValidator:
    """Validador de IDs de job."""

    @staticmethod
    def validate(job_id: Optional[str]) -> str:
        """
        Valida e sanitiza um job_id.

        Args:
            job_id: ID a ser validado

        Returns:
            job_id sanitizado

        Raises:
            ValidationError: Se o ID for inválido
        """
        if not job_id:
            raise ValidationError("Job ID não pode estar vazio", status_code=400)

        job_id = job_id.strip()

        if len(job_id) == 0:
            raise ValidationError("Job ID não pode estar vazio", status_code=400)

        if len(job_id) > JOB_CONSTANTS.JOB_ID_MAX_LENGTH:
            raise ValidationError(
                f"Job ID muito longo (máximo {JOB_CONSTANTS.JOB_ID_MAX_LENGTH} caracteres)",
                status_code=400
            )

        if not re.match(JOB_CONSTANTS.JOB_ID_PATTERN, job_id):
            raise ValidationError(
                "Job ID contém caracteres inválidos. Use apenas letras, números, hífen e underscore",
                status_code=400
            )

        return job_id

    @staticmethod
    def sanitize(job_id: str) -> str:
        """
        Sanitiza um job_id removendo caracteres perigosos.

        Args:
            job_id: ID a ser sanitizado

        Returns:
            ID sanitizado seguro para uso em paths
        """
        # Remove caracteres não permitidos
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', job_id[:JOB_CONSTANTS.JOB_ID_MAX_LENGTH])
        return safe_id


class BooleanValidator:
    """Validador de valores booleanos em string."""

    @staticmethod
    def validate(value: Optional[str]) -> bool:
        """
        Converte string para booleano.

        Args:
            value: Valor string a ser convertido

        Returns:
            Valor booleano

        Raises:
            ValidationError: Se o valor não for reconhecido
        """
        if value is None:
            return False

        if not isinstance(value, str):
            raise ValidationError(
                f"Tipo inválido: esperado string, recebido {type(value).__name__}",
                status_code=400
            )

        value_lower = value.lower().strip()

        if value_lower in VALIDATION_CONSTANTS.TRUE_VALUES:
            return True

        if value_lower in VALIDATION_CONSTANTS.FALSE_VALUES:
            return False

        raise ValidationError(
            f"Valor booleano inválido: '{value}'. Use 'true' ou 'false'",
            status_code=400
        )


class FileValidator:
    """Validador de arquivos."""

    @staticmethod
    def validate_uploaded_file(
        file: UploadFile,
        max_size_mb: int = FILE_CONSTANTS.DEFAULT_MAX_FILE_SIZE_MB
    ) -> Tuple[bytes, str]:
        """
        Valida arquivo enviado.

        Args:
            file: Arquivo do UploadFile
            max_size_mb: Tamanho máximo permitido em MB

        Returns:
            Tupla (conteúdo em bytes, extensão do arquivo)

        Raises:
            ValidationError: Se a validação falhar
        """
        # Verifica se arquivo existe
        if not file:
            raise ValidationError("Nenhum arquivo enviado", status_code=400)

        # Verifica se tem nome
        if not file.filename:
            raise ValidationError("Arquivo sem nome", status_code=400)

        filename = file.filename
        logger.info(f"Validando arquivo: {filename}")

        # Extrai extensão
        extension = Path(filename).suffix.lower()
        if not extension:
            extension = ".tmp"

        return extension

    @staticmethod
    def validate_file_content(
        content: bytes,
        max_size_mb: int = FILE_CONSTANTS.DEFAULT_MAX_FILE_SIZE_MB
    ) -> None:
        """
        Valida conteúdo do arquivo.

        Args:
            content: Conteúdo em bytes
            max_size_mb: Tamanho máximo permitido

        Raises:
            FileTooLargeError: Se arquivo exceder limite
            ValidationError: Se conteúdo for inválido
        """
        # Verifica se não está vazio
        if not content or len(content) == 0:
            raise ValidationError("Arquivo está vazio", status_code=400)

        # Verifica tamanho
        max_size_bytes = max_size_mb * 1024 * 1024
        file_size_mb = len(content) / (1024 * 1024)

        if len(content) > max_size_bytes:
            raise FileTooLargeError(file_size_mb, max_size_mb)

        logger.info(f"✅ Validação de tamanho: {file_size_mb:.2f}MB / {max_size_mb}MB permitidos")


class ProcessingParamsValidator:
    """Validador de parâmetros de processamento."""

    @staticmethod
    def validate(
        remove_noise: Optional[str] = None,
        convert_to_mono: Optional[str] = None,
        apply_highpass_filter: Optional[str] = None,
        set_sample_rate_16k: Optional[str] = None,
        isolate_vocals: Optional[str] = None
    ) -> dict:
        """
        Valida e converte parâmetros de processamento.

        Returns:
            Dicionário com valores booleanos validados
        """
        validator = BooleanValidator()

        return {
            'remove_noise': validator.validate(remove_noise),
            'convert_to_mono': validator.validate(convert_to_mono),
            'apply_highpass_filter': validator.validate(apply_highpass_filter),
            'set_sample_rate_16k': validator.validate(set_sample_rate_16k),
            'isolate_vocals': validator.validate(isolate_vocals),
        }


class PathValidator:
    """Validador de caminhos de arquivo."""

    @staticmethod
    def validate_safe_path(
        base_dir: Path,
        filename: str,
        job_id: str
    ) -> Path:
        """
        Cria caminho seguro prevenindo path traversal.

        Args:
            base_dir: Diretório base
            filename: Nome do arquivo
            job_id: ID do job

        Returns:
            Path seguro

        Raises:
            ValidationError: Se o caminho for inseguro
        """
        # Sanitiza job_id
        safe_job_id = JobIdValidator.sanitize(job_id)

        if not safe_job_id:
            raise ValidationError("Job ID inválido para criar caminho", status_code=500)

        # Extrai extensão segura
        extension = Path(filename).suffix
        if not extension:
            extension = ".tmp"

        # Cria path
        safe_path = base_dir / f"{safe_job_id}{extension}"

        # Resolve para caminho absoluto e verifica se está dentro do base_dir
        try:
            resolved_path = safe_path.resolve()
            resolved_base = base_dir.resolve()

            if not str(resolved_path).startswith(str(resolved_base)):
                raise ValidationError("Path traversal detectado", status_code=400)
        except (OSError, ValueError) as e:
            raise ValidationError(f"Caminho inválido: {e}", status_code=400)

        return safe_path
