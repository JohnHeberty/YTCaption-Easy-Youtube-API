"""
Job Manager - Responsável por gerenciar jobs de processamento
Princípio: Single Responsibility + Dependency Inversion
"""
from pathlib import Path
from typing import Optional
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from ..core.models import AudioNormJob
from common.job_utils.models import JobStatus
from common.log_utils import get_logger
from ..infrastructure.redis_store import RedisJobStore
from .file_validator import FileValidator
from .audio_extractor import AudioExtractor
from .audio_normalizer import AudioNormalizer
from ..shared.exceptions import AudioNormalizationException

logger = get_logger(__name__)

class JobManager:
    """Gerencia processamento completo de jobs de normalização"""
    
    def __init__(
        self,
        job_store: RedisJobStore,
        file_validator: FileValidator,
        audio_extractor: AudioExtractor,
        audio_normalizer: AudioNormalizer,
        config: dict
    ):
        self.job_store = job_store
        self.file_validator = file_validator
        self.audio_extractor = audio_extractor
        self.audio_normalizer = audio_normalizer
        self.config = config
        
        self.temp_dir = Path(config.get('temp_dir', './temp'))
        self.processed_dir = Path(config.get('processed_dir', './processed'))
        
        # Create directories
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_job(self, job: AudioNormJob) -> AudioNormJob:
        """
        Processa um job de normalização de áudio
        
        Args:
            job: AudioNormJob a ser processado
            
        Returns:
            Job atualizado com resultado do processamento
        """
        try:
            logger.info(f"🚀 Starting job processing: {job.id}")
            
            # Update job status
            job.status = JobStatus.PROCESSING
            job.started_at = now_brazil()
            job.progress = 0.0
            self.job_store.update_job(job)
            
            # Validate input file
            await self._validate_input_file(job)
            job.progress = 10.0
            self.job_store.update_job(job)
            
            # Extract audio if video file
            audio_file = await self._handle_video_extraction(job)
            job.progress = 20.0
            self.job_store.update_job(job)
            
            # Prepare output path
            output_file = self._prepare_output_path(job)
            
            # Progress callback
            async def update_progress(progress: float, message: str):
                # Map 20-90% for normalization process
                job.progress = 20.0 + (progress / 100.0 * 70.0)
                logger.info(f"   Progress: {job.progress:.1f}% - {message}")
                self.job_store.update_job(job)
            
            # Normalize audio
            normalized_file = await self.audio_normalizer.normalize_audio(
                input_path=audio_file,
                output_path=str(output_file),
                remove_noise=job.remove_noise or False,
                convert_to_mono=job.convert_to_mono or False,
                apply_highpass=job.apply_highpass_filter or False,
                set_sample_rate_16k=job.set_sample_rate_16k or False,
                isolate_vocals=job.isolate_vocals or False,
                progress_callback=update_progress
            )
            
            job.progress = 95.0
            self.job_store.update_job(job)
            
            # Update job with results
            job.output_file = normalized_file
            job.file_size_output = Path(normalized_file).stat().st_size
            job.progress = 100.0
            job.status = JobStatus.COMPLETED
            job.completed_at = now_brazil()
            
            self.job_store.update_job(job)
            
            logger.info(f"✅ Job completed successfully: {job.id}")
            return job
            
        except Exception as e:
            logger.error(f"❌ Job processing failed: {job.id} - {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = now_brazil()
            self.job_store.update_job(job)
            return job
    
    async def _validate_input_file(self, job: AudioNormJob) -> None:
        """Valida arquivo de entrada do job"""
        if not job.input_file:
            raise AudioNormalizationException("No input file specified")
        
        await self.file_validator.validate_file_exists(job.input_file)
        await self.file_validator.validate_file_size(job.input_file)
        
        # Get and log audio info
        try:
            info = await self.file_validator.get_audio_info(job.input_file)
            logger.info(f"📊 Audio info:")
            logger.info(f"   Duration: {info['duration']:.2f}s")
            logger.info(f"   Sample rate: {info['sample_rate']}Hz")
            logger.info(f"   Channels: {info['channels']}")
            logger.info(f"   Codec: {info['codec']}")
        except Exception as e:
            logger.warning(f"⚠️ Could not get audio info: {e}")
    
    async def _handle_video_extraction(self, job: AudioNormJob) -> str:
        """Extrai áudio de vídeo se necessário"""
        if not job.input_file:
            raise AudioNormalizationException("No input file")
        
        is_video = await self.file_validator.is_video_file(job.input_file)
        
        if is_video:
            logger.info("🎬 Video file detected, extracting audio...")
            
            # Create job-specific temp directory
            job_temp_dir = self.temp_dir / f"job_{job.id}"
            job_temp_dir.mkdir(parents=True, exist_ok=True)
            
            audio_file = await self.audio_extractor.extract_audio_from_video(
                video_path=job.input_file,
                output_dir=job_temp_dir
            )
            
            return audio_file
        else:
            logger.info("🎵 Audio file detected, proceeding with normalization")
            return job.input_file
    
    def _prepare_output_path(self, job: AudioNormJob) -> Path:
        """Prepara caminho do arquivo de saída"""
        # Use job ID for output filename to avoid conflicts
        output_filename = f"{job.id}.webm"
        output_path = self.processed_dir / output_filename
        
        logger.info(f"📁 Output path: {output_path}")
        return output_path
    
    def cleanup_job_files(self, job: AudioNormJob) -> None:
        """Limpa arquivos temporários do job"""
        try:
            # Clean job-specific temp directory
            job_temp_dir = self.temp_dir / f"job_{job.id}"
            if job_temp_dir.exists():
                import shutil
                shutil.rmtree(job_temp_dir)
                logger.info(f"🧹 Cleaned temp directory for job {job.id}")
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning job files: {e}")
