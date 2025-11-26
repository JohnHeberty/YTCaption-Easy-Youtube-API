"""
Processor para jobs de dublagem e clonagem de voz
"""
import logging
import os
from pathlib import Path
from typing import Optional

from .models import Job, VoiceProfile, JobMode, JobStatus
from .openvoice_client import OpenVoiceClient
from .f5tts_client import F5TTSClient
from .tts_interface import TTSEngine
from .config import get_settings
from .exceptions import DubbingException, VoiceCloneException

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """Processa jobs de dublagem e clonagem de voz"""
    
    def __init__(self, use_xtts: bool = None):
        """
        Inicializa o processador de voz
        
        Args:
            use_xtts: Se True, usa XTTS. Se False, usa engine de TTS_ENGINE env var.
                     Se None, lê de config (padrão)
        """
        self.settings = get_settings()
        
        # Determina engine: parâmetro > config > padrão (True)
        if use_xtts is None:
            self.use_xtts = self.settings.get('use_xtts', True)
        else:
            self.use_xtts = use_xtts
        
        self._engine = None
        self.job_store = None  # Será injetado no main.py
    
    def _get_tts_engine(self) -> TTSEngine:
        """
        Retorna engine TTS apropriada (factory method)
        
        Returns:
            TTSEngine: XTTSClient, F5TTSClient ou OpenVoiceClient
        """
        if self._engine is None:
            if self.use_xtts:
                # Usa XTTS (novo motor padrão)
                try:
                    from .xtts_client import XTTSClient
                    logger.info("Initializing XTTS engine (new default)")
                    self._engine = XTTSClient(
                        device=self.settings.get('xtts', {}).get('device'),
                        fallback_to_cpu=True
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize XTTS: {e}")
                    raise RuntimeError(f"XTTS initialization failed: {str(e)}")
            else:
                # Fallback para engine anterior via env var
                engine = os.getenv('TTS_ENGINE', 'openvoice')
                logger.info(f"Initializing TTS engine from TTS_ENGINE: {engine}")
                
                if engine == 'f5tts':
                    self._engine = F5TTSClient()
                elif engine == 'openvoice':
                    self._engine = OpenVoiceClient()
                else:
                    raise ValueError(f"Unknown TTS_ENGINE: {engine}")
        
        return self._engine
    
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
            
            # Obtém engine TTS apropriada
            engine = self._get_tts_engine()
            
            # Gera áudio dublado
            audio_bytes, duration = await engine.generate_dubbing(
                text=job.text,
                language=job.source_language or job.target_language or 'en',
                voice_preset=job.voice_preset,
                voice_profile=voice_profile,
                speed=1.0
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
            # LOG DETALHADO
            logger.info(f"🔍 Starting clone job {job.id}")
            logger.debug(f"  - input_file: {job.input_file}")
            logger.debug(f"  - voice_name: {job.voice_name}")
            logger.debug(f"  - language: {job.source_language}")
            
            # Validar antes de processar
            if not job.input_file:
                error_msg = (
                    f"Job {job.id} is missing input_file. "
                    f"This should have been set during upload. "
                    f"Job data: {job.model_dump()}"
                )
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            job.status = JobStatus.PROCESSING
            job.progress = 20.0
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"Processing voice clone job {job.id}: {job.voice_name}")
            
            # Obtém engine TTS apropriada
            engine = self._get_tts_engine()
            
            # Clona voz
            voice_profile = await engine.clone_voice(
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
            job.voice_id = voice_profile.id  # 🔥 FIX: Armazena voice_id no job para que o teste possa obter
            
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
