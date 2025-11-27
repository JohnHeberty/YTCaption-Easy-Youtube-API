"""
Processor para jobs de dublagem e clonagem de voz (XTTS ONLY)
Sprint 4: Adicionado suporte RVC
"""
import logging
from pathlib import Path
from typing import Optional

from .models import Job, VoiceProfile, JobMode, JobStatus, RvcModel, RvcParameters
from .config import get_settings
from .exceptions import DubbingException, VoiceCloneException
from .resilience import CircuitBreaker

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """Processa jobs de dublagem e clonagem de voz usando XTTS"""
    
    def __init__(self, lazy_load: bool = False):
        """
        Inicializa o processador
        
        Args:
            lazy_load: Se True, não carrega modelo XTTS imediatamente.
                      Usado pela API para economizar VRAM (~2GB).
                      Worker deve usar lazy_load=False para carregar modelo.
        """
        self.settings = get_settings()
        self.engine = None
        self.lazy_load = lazy_load
        
        # Circuit breaker para proteção contra falhas em cascata
        resilience_config = self.settings.get('resilience', {})
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=resilience_config.get('circuit_breaker_threshold', 5),
            timeout_seconds=resilience_config.get('circuit_breaker_timeout', 60)
        )
        
        # Só carrega modelo se não for lazy_load (worker)
        if not lazy_load:
            self._load_engine()
        
        self.job_store = None  # Será injetado no main.py
        
        # Sprint 6: RVC Model Manager
        self.rvc_model_manager = None  # Será injetado no main.py ou inicializado lazy
    
    def _load_engine(self):
        """Carrega modelo XTTS (lazy initialization)"""
        if self.engine is not None:
            return  # Já carregado
        
        from .xtts_client import XTTSClient
        logger.info("Initializing XTTS engine")
        
        self.engine = XTTSClient(
            device=self.settings['xtts'].get('device'),
            fallback_to_cpu=self.settings['xtts'].get('fallback_to_cpu', True),
            model_name=self.settings['xtts']['model_name']
        )
    
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
            # Garante que engine esteja carregado (lazy load)
            if self.engine is None:
                self._load_engine()
            
            job.status = JobStatus.PROCESSING
            job.progress = 10.0
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info("Processing dubbing job %s: mode=%s", job.id, job.mode)
            
            # === SPRINT 4: Preparar parâmetros RVC ===
            rvc_model = None
            rvc_params = None
            
            if job.enable_rvc:
                # Busca modelo RVC se habilitado
                if job.rvc_model_id and self.rvc_model_manager:
                    try:
                        rvc_model = self.rvc_model_manager.get_model(job.rvc_model_id)
                        logger.info("Loaded RVC model: %s", rvc_model.name)
                    except Exception as e:
                        logger.warning("Failed to load RVC model %s: %s", job.rvc_model_id, e)
                        # Continua sem RVC
                
                # Constrói parâmetros RVC a partir do job
                if rvc_model:
                    rvc_params = RvcParameters(
                        pitch=job.rvc_pitch or 0,
                        index_rate=job.rvc_index_rate or 0.75,
                        protect=job.rvc_protect or 0.33,
                        rms_mix_rate=job.rvc_rms_mix_rate or 0.25,
                        filter_radius=job.rvc_filter_radius or 3,
                        f0_method=job.rvc_f0_method or 'rmvpe',
                        hop_length=job.rvc_hop_length or 128
                    )
                    logger.info("RVC parameters: pitch=%d, f0_method=%s", rvc_params.pitch, rvc_params.f0_method)
            
            # Gera áudio dublado com perfil de qualidade usando XTTS (+ RVC se habilitado)
            # Retry automático já aplicado via decorator em xtts_client.generate_dubbing
            audio_bytes, duration = await self.engine.generate_dubbing(
                text=job.text,
                language=job.source_language or job.target_language or 'en',
                voice_preset=job.voice_preset,
                voice_profile=voice_profile,
                quality_profile=job.quality_profile,
                speed=1.0,
                # Parâmetros RVC (Sprint 4)
                enable_rvc=job.enable_rvc or False,
                rvc_model=rvc_model,
                rvc_params=rvc_params
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
            
            logger.info("Dubbing job %s completed: %.2fs", job.id, duration)
            
            return job
            
        except Exception as e:
            logger.error("Dubbing job %s failed: %s", job.id, e, exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            if self.job_store:
                self.job_store.update_job(job)
            raise DubbingException(str(e)) from e
    
    async def process_clone_job(self, job: Job) -> VoiceProfile:
        """
        Processa job de clonagem de voz
        
        Returns:
            VoiceProfile criado
        """
        try:
            # Garante que engine esteja carregado (lazy load)
            if self.engine is None:
                self._load_engine()
            
            # Validação
            logger.info("Starting clone job %s", job.id)
            logger.debug("  - input_file: %s", job.input_file)
            logger.debug("  - voice_name: %s", job.voice_name)
            logger.debug("  - language: %s", job.source_language)
            
            if not job.input_file:
                error_msg = (
                    f"Job {job.id} is missing input_file. "
                    f"This should have been set during upload. "
                    f"Job data: {job.model_dump()}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            job.status = JobStatus.PROCESSING
            job.progress = 20.0
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info("Processing voice clone job %s: %s", job.id, job.voice_name)
            
            # Clona voz usando XTTS
            voice_profile = await self.engine.clone_voice(
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
            job.voice_id = voice_profile.id
            
            import datetime
            job.completed_at = datetime.datetime.now()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info("Voice clone job %s completed: %s", job.id, voice_profile.id)
            
            return voice_profile
            
        except Exception as e:
            logger.error("Voice clone job %s failed: %s", job.id, e, exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            if self.job_store:
                self.job_store.update_job(job)
            raise VoiceCloneException(str(e)) from e
