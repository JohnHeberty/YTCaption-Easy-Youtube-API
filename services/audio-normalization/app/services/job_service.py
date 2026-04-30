"""
Serviço de gerenciamento de jobs.

Responsável por orquestrar criação, validação e submissão de jobs.
Segue SRP (Single Responsibility Principle).
"""
import asyncio
from pathlib import Path
from typing import Optional, Tuple

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from common.log_utils import get_logger
from fastapi import UploadFile

from ..core.models import AudioNormJob
from common.job_utils.models import JobStatus
from ..core.validators import (
    JobIdValidator,
    FileValidator,
    ProcessingParamsValidator,
    ValidationError,
    FileTooLargeError,
)
from ..core.constants import JOB_CONSTANTS, FILE_CONSTANTS
from ..core.exceptions import (
    JobNotFoundError,
    RedisError,
    CeleryTaskError,
)
from ..domain.interfaces import IJobStore

logger = get_logger(__name__)


class JobValidationResult:
    """Resultado da validação de job."""

    def __init__(
        self,
        content: bytes,
        extension: str,
        processing_params: dict,
        original_filename: str
    ):
        self.content = content
        self.extension = extension
        self.processing_params = processing_params
        self.original_filename = original_filename


class JobCreationService:
    """
    Serviço para criação de jobs.

    Responsabilidades:
    - Validar arquivos enviados
    - Criar entidades Job
    - Salvar arquivos de forma segura
    """

    def __init__(
        self,
        job_store: IJobStore,
        upload_dir: Path,
        max_file_size_mb: int = FILE_CONSTANTS.DEFAULT_MAX_FILE_SIZE_MB
    ):
        self.job_store = job_store
        self.upload_dir = upload_dir
        self.max_file_size_mb = max_file_size_mb
        self.file_validator = FileValidator()

    async def validate_input(
        self,
        file: UploadFile,
        **processing_params_raw
    ) -> JobValidationResult:
        """
        Valida entrada do usuário.

        Args:
            file: Arquivo enviado
            **processing_params_raw: Parâmetros de processamento em string

        Returns:
            JobValidationResult com dados validados

        Raises:
            ValidationError: Se validação falhar
            FileTooLargeError: Se arquivo for muito grande
        """
        # Valida arquivo
        extension = self.file_validator.validate_uploaded_file(file, self.max_file_size_mb)

        # Lê conteúdo
        try:
            content = await file.read()
        except Exception as e:
            raise ValidationError(f"Erro ao ler arquivo: {e}", status_code=400)

        # Valida conteúdo
        self.file_validator.validate_file_content(content, self.max_file_size_mb)

        # Valida parâmetros
        processing_params = ProcessingParamsValidator.validate(**processing_params_raw)

        return JobValidationResult(
            content=content,
            extension=extension,
            processing_params=processing_params,
            original_filename=file.filename
        )

    def create_job_entity(
        self,
        filename: str,
        processing_params: dict
    ) -> AudioNormJob:
        """
        Cria nova entidade Job.

        Args:
            filename: Nome do arquivo original
            processing_params: Parâmetros de processamento validados

        Returns:
            Nova instância de Job
        """
        return AudioNormJob.create_new(
            filename=filename,
            **processing_params
        )

    def save_file(self, job: AudioNormJob, content: bytes, extension: str) -> Path:
        """
        Salva arquivo de forma segura.

        Args:
            job: AudioNormJob associado
            content: Conteúdo do arquivo
            extension: Extensão do arquivo

        Returns:
            Path do arquivo salvo

        Raises:
            ValidationError: Se não conseguir salvar
        """
        # Sanitiza job_id
        safe_job_id = JobIdValidator.sanitize(job.id)
        if not safe_job_id:
            raise ValidationError("Job ID inválido", status_code=500)

        # Cria diretório
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValidationError(f"Erro ao criar diretório: {e}", status_code=500)

        # Salva arquivo
        file_path = self.upload_dir / f"{safe_job_id}{extension}"
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise ValidationError(f"Erro ao salvar arquivo: {e}", status_code=500)

        return file_path


class JobSubmissionService:
    """
    Serviço para submissão de jobs para processamento.

    Responsabilidades:
    - Verificar jobs existentes (cache)
    - Submeter para Celery
    - Fallback para processamento direto
    """

    def __init__(self, job_store: IJobStore):
        self.job_store = job_store

    def check_existing_job(self, job: AudioNormJob) -> Optional[AudioNormJob]:
        """
        Verifica se job já existe no cache.

        Args:
            job: Novo job a ser verificado

        Returns:
            Job existente se encontrado, None caso contrário
        """
        existing = self.job_store.get_job(job.id)

        if not existing:
            return None

        # Verifica status
        if existing.status == JobStatus.COMPLETED:
            logger.info(f"Job {job.id} já completado - retornando do cache")
            return existing

        # Verifica se é órfão (processando há muito tempo)
        if existing.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
            from datetime import timedelta
            processing_timeout = timedelta(minutes=JOB_CONSTANTS.DEFAULT_JOB_TIMEOUT_MINUTES)
            job_age = now_brazil() - existing.created_at

            if job_age > processing_timeout:
                logger.warning(f"⚠️ Job {job.id} órfão detectado, reprocessando...")
                existing.status = JobStatus.QUEUED
                existing.error_message = f"Job órfão detectado após {job_age}, reiniciando"
                existing.progress = 0.0
                self.job_store.update_job(existing)
                return existing

            logger.info(f"Job {job.id} em processamento (idade: {job_age})")
            return existing

        # Job falhou - tenta novamente
        if existing.status == JobStatus.FAILED:
            logger.info(f"Reprocessando job falhado: {job.id}")
            existing.status = JobStatus.QUEUED
            existing.error_message = None
            existing.progress = 0.0
            self.job_store.update_job(existing)
            return existing

        return existing

    async def submit_for_processing(self, job: AudioNormJob) -> None:
        """
        Submete job para processamento.

        Args:
            job: AudioNormJob a ser processado

        Raises:
            CeleryTaskError: Se falhar ao enviar para Celery
        """
        try:
            from ..infrastructure.celery_config import celery_app
            from ..infrastructure.celery_tasks import normalize_audio_task

            task_result = normalize_audio_task.apply_async(
                args=[job.model_dump()],
                task_id=job.id
            )
            logger.info(f"📤 Job {job.id} enviado para Celery: {task_result.id}")

        except Exception as e:
            logger.error(f"❌ Erro ao enviar para Celery: {e}")
            raise CeleryTaskError(f"Falha ao enviar para Celery: {e}")

    async def submit_with_fallback(self, job: AudioNormJob, processor) -> None:
        """
        Submete job com fallback para processamento direto.

        Args:
            job: AudioNormJob a ser processado
            processor: Instância do processador de áudio
        """
        try:
            await self.submit_for_processing(job)
        except CeleryTaskError:
            logger.warning(f"Fallback: processando diretamente job {job.id}")
            asyncio.create_task(processor.process_audio_job(job))


class JobRetrievalService:
    """
    Serviço para recuperação de jobs.

    Responsabilidades:
    - Buscar jobs por ID
    - Verificar expiração
    - Formatar resposta
    """

    def __init__(self, job_store: IJobStore):
        self.job_store = job_store

    def get_job(self, job_id: str) -> AudioNormJob:
        """
        Recupera job por ID.

        Args:
            job_id: ID do job

        Returns:
            Job encontrado

        Raises:
            JobNotFoundError: Se job não existir
        """
        try:
            job = self.job_store.get_job(job_id)
        except Exception as e:
            logger.error(f"Erro ao buscar job {job_id}: {e}")
            raise RedisError(f"Erro ao buscar job: {e}")

        if not job:
            raise JobNotFoundError(job_id)

        return job

    def get_job_with_expiration_check(self, job_id: str) -> AudioNormJob:
        """
        Recupera job verificando expiração.

        Args:
            job_id: ID do job

        Returns:
            Job encontrado

        Raises:
            JobNotFoundError: Se job não existir
            JobExpiredError: Se job expirou
        """
        job = self.get_job(job_id)

        if job.is_expired:
            from ..core.exceptions import JobExpiredError
            raise JobExpiredError(job_id)

        return job

    def list_recent_jobs(self, limit: int = 20) -> list:
        """
        Lista jobs recentes.

        Args:
            limit: Limite de jobs a retornar

        Returns:
            Lista de jobs
        """
        try:
            return self.job_store.list_jobs(limit)
        except Exception as e:
            logger.error(f"Erro ao listar jobs: {e}")
            raise RedisError(f"Erro ao listar jobs: {e}")
