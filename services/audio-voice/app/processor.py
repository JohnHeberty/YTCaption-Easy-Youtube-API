"""
Processor para jobs de dublagem e clonagem de voz
"""
import logging
from pathlib import Path
from typing import Optional

from .models import Job, VoiceProfile, JobMode, JobStatus
from .openvoice_client import OpenVoiceClient
from .config import get_settings
from .exceptions import DubbingException, VoiceCloneException

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """Processa jobs de dublagem e clonagem de voz"""
    
    def __init__(self):
        self.settings = get_settings()
        self.openvoice_client = OpenVoiceClient()
        self.job_store = None  # Será injetado no main.py
    
    async def process_dubbing_job(self, job: Job, voice_profile: Optional[VoiceProfile] = None) -> Job:
        """
        Processa job de dublagem
        
        Args:
            job: Job a processar
            voice_profile: Perfil de voz clonada (se mode=dubbing_with_clone)
        
        Returns:
            Job atualizado
        """
        try:
            job.status = JobStatus.PROCESSING
            job.progress = 10.0
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"Processing dubbing job {job.id}: mode={job.mode}")
            
            # Gera áudio dublado
            audio_bytes, duration = await self.openvoice_client.generate_dubbing(
                text=job.text,
                language=job.source_language or job.target_language or 'en',
                voice_preset=job.voice_preset,
                voice_profile=voice_profile,
                speed=1.0,  # TODO: pegar de job params
                pitch=1.0
            )
            
            job.progress = 80.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Salva áudio
            processed_dir = Path(self.settings['processed_dir'])
            processed_dir.mkdir(exist_ok=True, parents=True)
            
            output_path = processed_dir / f"{job.id}.wav"
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
            
            job.output_file = str(output_path)
            job.duration = duration
            job.file_size_output = len(audio_bytes)
            job.audio_url = f"/jobs/{job.id}/download"
            job.progress = 100.0
            job.status = JobStatus.COMPLETED
            
            import datetime
            job.completed_at = datetime.datetime.now()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"✅ Dubbing job {job.id} completed: {duration:.2f}s")
            
            return job
            
        except Exception as e:
            logger.error(f"❌ Dubbing job {job.id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            if self.job_store:
                self.job_store.update_job(job)
            raise DubbingException(str(e))
    
    async def process_clone_job(self, job: Job) -> VoiceProfile:
        """
        Processa job de clonagem de voz
        
        Returns:
            VoiceProfile criado
        """
        try:
            job.status = JobStatus.PROCESSING
            job.progress = 20.0
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"Processing voice clone job {job.id}: {job.voice_name}")
            
            # Clona voz
            voice_profile = await self.openvoice_client.clone_voice(
                audio_path=job.input_file,
                language=job.source_language or 'en',
                voice_name=job.voice_name,
                description=job.voice_description
            )
            
            job.progress = 90.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Salva perfil no store
            if self.job_store:
                self.job_store.save_voice_profile(voice_profile)
            
            job.progress = 100.0
            job.status = JobStatus.COMPLETED
            job.output_file = voice_profile.profile_path
            
            import datetime
            job.completed_at = datetime.datetime.now()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"✅ Voice clone job {job.id} completed: {voice_profile.id}")
            
            return voice_profile
            
        except Exception as e:
            logger.error(f"❌ Voice clone job {job.id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            if self.job_store:
                self.job_store.update_job(job)
            raise VoiceCloneException(str(e))
