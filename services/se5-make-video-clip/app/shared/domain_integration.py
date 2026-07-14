"""  Domain Integration Layer

Conecta a camada de domínio (DDD) com as dependências concretas
do serviço make-video (Celery, Redis, VideoBuilder, etc.).

Este módulo adapta os stages abstratos para usarem as implementações
reais dos serviços.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
from common.datetime_utils import now_brazil

from typing import Any

from ..domain.job_processor import JobProcessor
from ..core.constants import BYTES_PER_MB
from ..domain.job_stage import StageContext, JobStage
from ..domain.stages.analyze_audio_stage import AnalyzeAudioStage
from ..domain.stages.load_approved_stage import LoadApprovedVideosStage
from ..domain.stages.select_shorts_stage import SelectShortsStage
from ..domain.stages.assemble_video_stage import AssembleVideoStage
from ..domain.stages.generate_subtitles_stage import GenerateSubtitlesStage
from ..domain.stages.final_composition_stage import FinalCompositionStage
from ..domain.stages.trim_video_stage import TrimVideoStage
from ..domain.stages.validate_av_sync_stage import ValidateAVSyncStage

from ..core.models import Job, JobStatus, JobResult, ShortInfo
from ..infrastructure.redis_store import MakeVideoJobStore as RedisJobStore
from ..infrastructure.checkpoint import save_checkpoint, delete_checkpoint
from ..infrastructure.base import update_job_status
from ..infrastructure.simple_metrics import simple_metrics
from ..api.api_client import MicroservicesClient
from ..services.video_builder import VideoBuilder
from ..services.shorts_manager import ShortsCache
from ..services.subtitle_generator import SubtitleGenerator
from ..services.subtitle_postprocessor import process_subtitles_with_vad
from ..video_processing.video_validator import VideoValidator
from ..services.blacklist_factory import get_blacklist
from ..infrastructure.file_logger import FileLogger
from .events import EventPublisher, EventType
from .exceptions import MakeVideoException
from ..core.models import StageInfo
from common.log_utils import get_logger

logger = get_logger(__name__)

class DomainJobProcessor:
    """
    Wrapper que integra o JobProcessor do domínio com as
    dependências concretas do serviço make-video.
    
    Responsabilidades:
    - Inicializar stages com dependências concretas
    - Adaptar contexto entre domínio e infraestrutura
    - Publicar eventos durante processamento
    - Persistir resultados no Redis
    """
    
    def __init__(
        self,
        redis_store: RedisJobStore,
        api_client: MicroservicesClient,
        video_builder: VideoBuilder,
        shorts_cache: ShortsCache,
        subtitle_gen: SubtitleGenerator,
        video_validator: VideoValidator,
        blacklist: Any,
        settings: dict[str, Any],
        event_publisher: EventPublisher | None = None
    ) -> None:
        self.redis_store = redis_store
        self.api_client = api_client
        self.video_builder = video_builder
        self.shorts_cache = shorts_cache
        self.subtitle_gen = subtitle_gen
        self.video_validator = video_validator
        self.blacklist = blacklist
        self.settings = settings
        self.event_publisher = event_publisher
        self._current_job: Job | None = None

        # Criar stages com dependências
        self.stages = self._create_stages()

        # Criar processor com callback para atualizar Job.stages em tempo real
        self.processor = JobProcessor(
            stages=self.stages,
            stage_callback=self._on_stage_update,
        )

    async def _on_stage_update(
        self,
        stage_name: str,
        status: str,
        progress: float,
        duration: float,
        error_msg: str | None,
    ) -> None:
        """Callback called by JobProcessor after each stage to update Job.stages."""
        job = self._current_job
        if not job:
            return

        try:
            # Map DDD stage names to API display names
            display_names = {
                'analyze_audio': 'Analyzing audio',
                'load_approved': 'Loading approved videos',
                'select_shorts': 'Selecting shorts',
                'assemble_video': 'Assembling video',
                'generate_subtitles': 'Generating subtitles',
                'final_composition': 'Final composition',
                'trim_video': 'Trimming video',
                'validate_av_sync': 'Validating A/V sync',
            }

            if stage_name not in job.stages:
                job.stages[stage_name] = StageInfo(
                    name=stage_name,
                    display_name=display_names.get(stage_name, stage_name),
                )

            stage_info = job.stages[stage_name]

            if status == 'processing':
                stage_info.start()
            elif status == 'completed':
                stage_info.complete()
            elif status == 'failed':
                stage_info.fail(error_msg or 'Unknown error')

            stage_info.update_progress(progress)

            # Persist to Redis so API can read updated stages
            self.redis_store.save_job(job)

        except Exception as exc:
            logger.debug("Failed to update stage %s: %s", stage_name, exc)
    
    def _create_stages(self) -> list[JobStage]:
        """Cria e configura todos os stages com dependências concretas"""

        # Cada stage recebe as dependências que precisa
        return [
            AnalyzeAudioStage(
                video_builder=self.video_builder
            ),
            LoadApprovedVideosStage(
                video_builder=self.video_builder
            ),
            SelectShortsStage(),
            AssembleVideoStage(
                video_builder=self.video_builder
            ),
            GenerateSubtitlesStage(
                api_client=self.api_client,
                subtitle_generator=self.subtitle_gen,
                vad_processor=process_subtitles_with_vad
            ),
            FinalCompositionStage(
                video_builder=self.video_builder
            ),
            TrimVideoStage(
                video_builder=self.video_builder
            ),
            ValidateAVSyncStage(
                video_builder=self.video_builder
            ),
        ]
    
    async def _setup_job_context(self, job: Job) -> StageContext:
        """Create and configure the StageContext for processing."""
        return StageContext(
            job_id=job.id,
            query=job.query if job.query else "approved_videos",
            max_shorts=job.max_shorts,
            aspect_ratio=job.aspect_ratio,
            crop_position=getattr(job, 'crop_position', 'center'),
            subtitle_language=getattr(job, 'subtitle_language', 'pt-BR'),
            subtitle_style=job.subtitle_style,
            settings=self.settings,
            event_publisher=self.event_publisher,
            hook_text=getattr(job, 'hook_text', None),
            burn_subtitles=getattr(job, 'burn_subtitles', True),
        )

    def _finalize_completed_job(self, job: Job, result: JobResult) -> None:
        """Update job with completed result and persist."""
        job.result = result
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = now_brazil()
        job.expires_at = job.completed_at + timedelta(hours=24)
        self.redis_store.save_job(job)

    async def _publish_job_event(self, event_type: str, job_id: str, **kwargs: Any) -> None:
        """Publish a job lifecycle event (started/completed/failed)."""
        try:
            if event_type == 'started':
                from ..shared.events import publish_job_started
                await publish_job_started(job_id=job_id, **kwargs)
            elif event_type == 'completed':
                from ..shared.events import publish_job_completed
                await publish_job_completed(job_id=job_id, **kwargs)
            elif event_type == 'failed':
                from ..shared.events import publish_job_failed
                await publish_job_failed(job_id=job_id, **kwargs)
        except Exception as exc:
            logger.debug("Failed to publish job_%s event: %s", event_type, exc)

    def _handle_job_error(self, job: Job, job_id: str, e: Exception) -> None:
        """Update job with failure info and persist."""
        job.status = JobStatus.FAILED
        job.error = {
            "message": str(e),
            "type": type(e).__name__
        }
        if isinstance(e, MakeVideoException):
            job.error = {
                "message": str(e),
                "code": getattr(e, 'error_code', 'UNKNOWN'),
                "details": getattr(e, 'context', {})
            }
        self.redis_store.save_job(job)

    async def process_job(self, job_id: str) -> JobResult:
        """
        Processa um job usando Domain-Driven Design.

        Args:
            job_id: ID do job a ser processado

        Returns:
            JobResult com informações do vídeo final

        Raises:
            MakeVideoException: Se houver erro no processamento
        """
        job_logger = FileLogger.get_job_logger(job_id)
        job_logger.info("=" * 80)
        job_logger.info(f"🎬 STARTING MAKE-VIDEO JOB (Domain-Driven): {job_id}")
        job_logger.info("=" * 80)

        job = self.redis_store.get_job(job_id)
        if not job:
            job_logger.error(f"❌ Job {job_id} not found in Redis")
            raise MakeVideoException(f"Job {job_id} not found")

        job_logger.info(f"Job loaded: max_shorts={job.max_shorts} (no query - uses approved videos)")

        job.status = JobStatus.PROCESSING
        self.redis_store.save_job(job)

        try:
            context = await self._setup_job_context(job)

            await self._publish_job_event('started', job_id, query=job.query or "approved_videos")

            logger.info(f"🚀 Starting domain-driven processing for job {job_id}")
            self._current_job = job
            final_context = await self.processor.process(context)
            self._current_job = None

            try:
                from ..pipeline.cleanup import PipelineCleanup
                PipelineCleanup(settings=self.settings).cleanup_stale_validations()
            except Exception:
                pass

            try:
                await delete_checkpoint(job_id)
            except Exception:
                pass

            result = self._build_job_result(job, final_context)
            self._finalize_completed_job(job, result)

            await self._publish_job_event('completed', job_id, duration_seconds=result.processing_time)

            logger.info(f"🎉 Job {job_id} completed successfully (Domain-Driven)!")
            logger.info(f"   ├─ Duration: {result.duration:.1f}s")
            logger.info(f"   ├─ Size: {result.file_size_mb}MB")
            logger.info(f"   ├─ Shorts used: {result.shorts_used}")
            logger.info(f"   └─ Processing time: {result.processing_time:.1f}s")

            simple_metrics.jobs_completed += 1

            job_logger.info("=" * 80)
            job_logger.info(f"✅ JOB COMPLETED SUCCESSFULLY")
            job_logger.info("=" * 80)

            return result

        except Exception as e:
            self._handle_job_error(job, job_id, e)
            await self._publish_job_event('failed', job_id, error=str(job.error))

            logger.error(f"❌ Job {job_id} failed (Domain-Driven): {e}", exc_info=True)
            job_logger.error(f"❌ JOB FAILED: {e}")

            simple_metrics.jobs_failed += 1

            raise
    
    def _build_job_result(self, job: Job, context: StageContext) -> JobResult:
        """
        Constrói JobResult a partir do contexto final dos stages.
        
        Args:
            job: Job original
            context: Contexto final após todos os stages
            
        Returns:
            JobResult com informações do vídeo final
        """
        
        # Extrair dados do contexto via resultados dos stages
        audio_result = context.get_result('analyze_audio')
        audio_duration = audio_result.data.get('audio_duration', 0.0) if audio_result else 0.0
        selected_shorts = context.selected_shorts or []
        final_video_path = context.final_video_path or Path('')
        video_info = context.video_info or {}
        segments_result = context.get_result('generate_subtitles')
        segments = segments_result.data.get('segments', []) if segments_result else []
        
        # Calcular tamanho do arquivo
        file_size = final_video_path.stat().st_size if final_video_path.exists() else 0
        
        # Criar resultado
        result = JobResult(
            video_url=f"/download/{job.id}",
            video_file=final_video_path.name,
            file_size=file_size,
            file_size_mb=round(file_size / BYTES_PER_MB, 2),
            duration=video_info.get('duration', audio_duration),
            resolution=video_info.get('resolution', '1920x1080'),
            aspect_ratio=job.aspect_ratio,
            fps=int(video_info.get('fps', 30)),
            shorts_used=len(selected_shorts),
            shorts_list=[
                ShortInfo(
                    video_id=s['video_id'],
                    duration_seconds=s['duration_seconds'],
                    file_path=s['file_path'],
                    position_in_video=sum(selected_shorts[j]['duration_seconds']
                                        for j in range(i))
                )
                for i, s in enumerate(selected_shorts)
            ],
            subtitle_segments=len(segments),
            processing_time=(now_brazil() - job.created_at).total_seconds()
        )
        
        return result

async def process_job_with_domain(
    job_id: str,
    redis_store: RedisJobStore,
    api_client: MicroservicesClient,
    video_builder: VideoBuilder,
    shorts_cache: ShortsCache,
    subtitle_gen: SubtitleGenerator,
    video_validator: VideoValidator,
    blacklist: Any,
    settings: dict[str, Any],
    event_publisher: EventPublisher | None = None
) -> JobResult:
    """
    Função helper para processar job usando Domain-Driven Design.
    
    Esta é a interface pública que celery_tasks.py deve usar para
    processar jobs com a nova arquitetura.
    
    Args:
        job_id: ID do job
        redis_store: Store Redis para persistência
        api_client: Cliente para microserviços
        video_builder: Builder FFmpeg
        shorts_cache: Cache de shorts
        subtitle_gen: Gerador de legendas
        video_validator: Validador OCR
        blacklist: Blacklist de vídeos
        settings: Configurações do serviço
        event_publisher: Publicador de eventos (opcional)
        
    Returns:
        JobResult com informações do vídeo processado
        
    Raises:
        MakeVideoException: Se houver erro no processamento
    """
    
    processor = DomainJobProcessor(
        redis_store=redis_store,
        api_client=api_client,
        video_builder=video_builder,
        shorts_cache=shorts_cache,
        subtitle_gen=subtitle_gen,
        video_validator=video_validator,
        blacklist=blacklist,
        settings=settings,
        event_publisher=event_publisher
    )
    
    return await processor.process_job(job_id)
