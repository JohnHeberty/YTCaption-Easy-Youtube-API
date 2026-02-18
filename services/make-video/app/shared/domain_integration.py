"""  Domain Integration Layer

Conecta a camada de domínio (DDD) com as dependências concretas
do serviço make-video (Celery, Redis, VideoBuilder, etc.).

Este módulo adapta os stages abstratos para usarem as implementações
reais dos serviços.
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ..domain.job_processor import JobProcessor
from ..domain.job_stage import StageContext, JobStage
from ..domain.stages.analyze_audio_stage import AnalyzeAudioStage
from ..domain.stages.fetch_shorts_stage import FetchShortsStage
from ..domain.stages.download_shorts_stage import DownloadShortsStage
from ..domain.stages.select_shorts_stage import SelectShortsStage
from ..domain.stages.assemble_video_stage import AssembleVideoStage
from ..domain.stages.generate_subtitles_stage import GenerateSubtitlesStage
from ..domain.stages.final_composition_stage import FinalCompositionStage
from ..domain.stages.trim_video_stage import TrimVideoStage

from ..core.models import Job, JobStatus, JobResult, ShortInfo
from ..infrastructure.redis_store import RedisJobStore
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

logger = logging.getLogger(__name__)


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
        settings: Dict[str, Any],
        event_publisher: Optional[EventPublisher] = None
    ):
        self.redis_store = redis_store
        self.api_client = api_client
        self.video_builder = video_builder
        self.shorts_cache = shorts_cache
        self.subtitle_gen = subtitle_gen
        self.video_validator = video_validator
        self.blacklist = blacklist
        self.settings = settings
        self.event_publisher = event_publisher
        
        # Criar stages com dependências
        self.stages = self._create_stages()
        
        # Criar processor
        self.processor = JobProcessor(stages=self.stages)
    
    def _create_stages(self) -> List[JobStage]:
        """Cria e configura todos os stages com dependências concretas"""
        
        # Cada stage recebe as dependências que precisa
        return [
            AnalyzeAudioStage(
                video_builder=self.video_builder
            ),
            FetchShortsStage(
                api_client=self.api_client
            ),
            DownloadShortsStage(
                api_client=self.api_client,
                shorts_cache=self.shorts_cache,
                video_validator=self.video_validator,
                blacklist=self.blacklist
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
            )
        ]
    
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
        
        # Criar logger específico para este job
        job_logger = FileLogger.get_job_logger(job_id)
        job_logger.info("=" * 80)
        job_logger.info(f"🎬 STARTING MAKE-VIDEO JOB (Domain-Driven): {job_id}")
        job_logger.info("=" * 80)
        
        # Carregar job do Redis
        job = await self.redis_store.get_job(job_id)
        if not job:
            job_logger.error(f"❌ Job {job_id} not found in Redis")
            raise MakeVideoException(f"Job {job_id} not found")
        
        job_logger.info(f"Job loaded: max_shorts={job.max_shorts} (no query - uses approved videos)")
        
        # Atualizar status inicial
        job.status = JobStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        await self.redis_store.save_job(job)
        
        try:
            # Criar contexto compartilhado para todos os stages
            context = StageContext(
                job_id=job_id,
                query=job.query if job.query else "approved_videos",  # Opcional: make-video não usa query
                max_shorts=job.max_shorts,
                aspect_ratio=job.aspect_ratio,
                crop_position=getattr(job, 'crop_position', 'center'),
                subtitle_language=getattr(job, 'subtitle_language', 'pt-BR'),
                subtitle_style=job.subtitle_style,
                settings=self.settings,
                event_publisher=self.event_publisher
            )
            
            # Publicar evento de início
            if self.event_publisher:
                await self.event_publisher.publish_job_started(
                    job_id=job_id,
                    query=job.query if job.query else "approved_videos"  # Opcional
                )
            
            # Executar processamento através dos stages
            logger.info(f"🚀 Starting domain-driven processing for job {job_id}")
            final_context = await self.processor.process(context)
            
            # Extrair resultados do contexto final
            result = self._build_job_result(job, final_context)
            
            # Atualizar job como completo
            job.result = result
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.completed_at = datetime.utcnow()
            job.expires_at = job.completed_at + timedelta(hours=24)
            await self.redis_store.save_job(job)
            
            # Publicar evento de sucesso
            if self.event_publisher:
                await self.event_publisher.publish_job_completed(
                    job_id=job_id,
                    result=result.dict()
                )
            
            logger.info(f"🎉 Job {job_id} completed successfully (Domain-Driven)!")
            logger.info(f"   ├─ Duration: {result.duration:.1f}s")
            logger.info(f"   ├─ Size: {result.file_size_mb}MB")
            logger.info(f"   ├─ Shorts used: {result.shorts_used}")
            logger.info(f"   └─ Processing time: {result.processing_time:.1f}s")
            
            job_logger.info("=" * 80)
            job_logger.info(f"✅ JOB COMPLETED SUCCESSFULLY")
            job_logger.info("=" * 80)
            
            return result
            
        except Exception as e:
            # Atualizar job com erro
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
            
            job.updated_at = datetime.utcnow()
            await self.redis_store.save_job(job)
            
            # Publicar evento de erro
            if self.event_publisher:
                await self.event_publisher.publish_job_failed(
                    job_id=job_id,
                    error=job.error
                )
            
            logger.error(f"❌ Job {job_id} failed (Domain-Driven): {e}", exc_info=True)
            job_logger.error(f"❌ JOB FAILED: {e}")
            
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
        
        # Extrair dados do contexto
        audio_duration = context.data.get('audio_duration', 0.0)
        selected_shorts = context.data.get('selected_shorts', [])
        final_video_path = Path(context.data.get('final_video_path', ''))
        video_info = context.data.get('video_info', {})
        segments = context.data.get('segments', [])
        
        # Calcular tamanho do arquivo
        file_size = final_video_path.stat().st_size if final_video_path.exists() else 0
        
        # Criar resultado
        result = JobResult(
            video_url=f"/download/{job.id}",
            video_file=final_video_path.name,
            file_size=file_size,
            file_size_mb=round(file_size / (1024 * 1024), 2),
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
            processing_time=(datetime.utcnow() - job.created_at).total_seconds()
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
    settings: Dict[str, Any],
    event_publisher: Optional[EventPublisher] = None
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
