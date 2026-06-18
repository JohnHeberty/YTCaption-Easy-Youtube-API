"""
Job Manager for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Gerencia ciclo de vida de jobs
- Interface Segregation: Implementa JobManagerInterface
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from common.datetime_utils import now_brazil
from common.log_utils import get_logger
from ..core.models import Job, JobStatus, JobResult, StageInfo
from ..infrastructure.redis_store import MakeVideoJobStore as RedisJobStore

logger = get_logger(__name__)

class JobManager:
    """
    Gerencia ciclo de vida de jobs de processamento de vídeo.

    Responsabilidades:
    - Criar novos jobs
    - Atualizar progresso e status
    - Marcar como completado/falho
    - Listar e buscar jobs
    """

    def __init__(self, redis_store: RedisJobStore):
        """
        Initialize job manager.

        Args:
            redis_store: Store Redis para persistência
        """
        self.redis_store = redis_store
        logger.info("JobManager initialized")

    async def create_job(
        self,
        job_id: str,
        max_shorts: int,
        subtitle_language: str = "pt",
        subtitle_style: str = "static",
        aspect_ratio: str = "9:16",
        crop_position: str = "center",
        audio_path: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Job:
        """
        Cria um novo job.

        Args:
            job_id: ID único do job
            max_shorts: Máximo de shorts a usar
            subtitle_language: Idioma das legendas
            subtitle_style: Estilo das legendas
            aspect_ratio: Proporção do vídeo
            crop_position: Posição do crop
            audio_path: Path do arquivo de áudio
            query: Query de busca (para pipeline de download)

        Returns:
            Job criado
        """
        now = now_brazil()

        job = Job(
            job_id=job_id,
            status=JobStatus.QUEUED,
            progress=0.0,
            max_shorts=max_shorts,
            subtitle_language=subtitle_language,
            subtitle_style=subtitle_style,
            aspect_ratio=aspect_ratio,
            crop_position=crop_position,
            audio_path=audio_path,
            query=query,
            created_at=now,
            updated_at=now,
            stages={},
        )

        await self.redis_store.save_job(job)
        logger.info(f"Job created: {job_id} (max_shorts={max_shorts})")

        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Obtém job por ID.

        Args:
            job_id: ID do job

        Returns:
            Job ou None se não encontrado
        """
        return await self.redis_store.get_job(job_id)

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float,
        stage_name: Optional[str] = None,
        stage_status: Optional[str] = None,
        stage_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Atualiza status e progresso de job.

        Args:
            job_id: ID do job
            status: Novo status
            progress: Progresso (0-100)
            stage_name: Nome do estágio atual
            stage_status: Status do estágio
            stage_metadata: Metadata do estágio

        Returns:
            True se sucesso, False caso contrário
        """
        try:
            job = await self.redis_store.get_job(job_id)
            if not job:
                logger.error(f"Job not found for update: {job_id}")
                return False

            job.status = status
            job.progress = progress
            job.updated_at = now_brazil()

            # Atualizar estágio se fornecido
            if stage_name:
                if stage_name not in job.stages:
                    job.stages[stage_name] = StageInfo(
                        status=stage_status or "in_progress",
                        progress=progress,
                        metadata=stage_metadata or {},
                    )
                else:
                    stage = job.stages[stage_name]
                    if stage_status:
                        stage.status = stage_status
                    if stage_metadata:
                        stage.metadata.update(stage_metadata)
                    stage.progress = progress

            await self.redis_store.save_job(job)
            return True

        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False

    async def complete_job(
        self,
        job_id: str,
        video_url: str,
        video_file: str,
        file_size: int,
        duration: float,
        resolution: str,
        fps: int,
        shorts_used: int,
        subtitle_segments: int,
    ) -> bool:
        """
        Marca job como completado.

        Args:
            job_id: ID do job
            video_url: URL do vídeo gerado
            video_file: Nome do arquivo do vídeo
            file_size: Tamanho em bytes
            duration: Duração em segundos
            resolution: Resolução (ex: "1080x1920")
            fps: Frames por segundo
            shorts_used: Número de shorts usados
            subtitle_segments: Número de segmentos de legenda

        Returns:
            True se sucesso, False caso contrário
        """
        try:
            job = await self.redis_store.get_job(job_id)
            if not job:
                logger.error(f"Job not found for completion: {job_id}")
                return False

            now = now_brazil()

            result = JobResult(
                video_url=video_url,
                video_file=video_file,
                file_size=file_size,
                file_size_mb=round(file_size / (1024 * 1024), 2),
                duration=duration,
                resolution=resolution,
                aspect_ratio=job.aspect_ratio,
                fps=fps,
                shorts_used=shorts_used,
                subtitle_segments=subtitle_segments,
                processing_time=(now - job.created_at).total_seconds(),
            )

            job.result = result
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.completed_at = now
            job.expires_at = now + timedelta(hours=24)

            await self.redis_store.save_job(job)
            logger.info(f"Job completed: {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")
            return False

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_code: str = "UNKNOWN",
        error_details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Marca job como falho.

        Args:
            job_id: ID do job
            error_message: Mensagem de erro
            error_code: Código do erro
            error_details: Detalhes adicionais do erro

        Returns:
            True se sucesso, False caso contrário
        """
        try:
            job = await self.redis_store.get_job(job_id)
            if not job:
                logger.error(f"Job not found for failure: {job_id}")
                return False

            job.status = JobStatus.FAILED
            job.progress = 100.0
            job.updated_at = now_brazil()
            job.error = {
                "message": error_message,
                "code": error_code,
                "details": error_details or {},
                "timestamp": now_brazil().isoformat(),
            }

            await self.redis_store.save_job(job)
            logger.error(f"Job failed: {job_id} - {error_message}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return False

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> List[Job]:
        """
        Lista jobs.

        Args:
            status: Filtrar por status
            limit: Limite de resultados

        Returns:
            Lista de jobs
        """
        jobs = await self.redis_store.list_jobs(limit=limit)

        if status:
            jobs = [j for j in jobs if j.status == status]

        return jobs

    async def delete_job(self, job_id: str) -> bool:
        """
        Deleta job.

        Args:
            job_id: ID do job

        Returns:
            True se sucesso, False caso contrário
        """
        return await self.redis_store.delete_job(job_id)

    async def find_orphaned_jobs(
        self,
        max_age_minutes: int = 30,
    ) -> List[Job]:
        """
        Encontra jobs órfãos (presos em processamento).

        Args:
            max_age_minutes: Idade máxima em minutos

        Returns:
            Lista de jobs órfãos
        """
        return await self.redis_store.find_orphaned_jobs(max_age_minutes)

    def get_stats(self) -> Dict[str, int]:
        """
        Retorna estatísticas de jobs.

        Returns:
            Dict com contagens por status
        """
        return self.redis_store.get_stats()

    async def cleanup_expired(self) -> int:
        """
        Limpa jobs expirados.

        Returns:
            Número de jobs removidos
        """
        return await self.redis_store.cleanup_expired()

    async def get_queue_info(self) -> Dict[str, Any]:
        """
        Retorna informações da fila.

        Returns:
            Dict com informações da fila
        """
        return await self.redis_store.get_queue_info()
