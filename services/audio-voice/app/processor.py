"""
Processor para jobs de dublagem e clonagem de voz
Sprint 4: Multi-Engine Support (XTTS + F5-TTS)
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
    """Processa jobs de dublagem e clonagem de voz usando múltiplos engines TTS"""
    
    def __init__(self, lazy_load: bool = False):
        """
        Inicializa o processador
        
        Args:
            lazy_load: Se True, não carrega modelos TTS imediatamente.
                      Usado pela API para economizar VRAM (~2GB).
                      Worker deve usar lazy_load=False para carregar modelo.
        """
        self.settings = get_settings()
        self.engines = {}  # Cache de engines: {engine_name: engine_instance}
        self.lazy_load = lazy_load
        
        # Circuit breaker para proteção contra falhas em cascata
        resilience_config = self.settings.get('resilience', {})
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=resilience_config.get('circuit_breaker_threshold', 5),
            timeout_seconds=resilience_config.get('circuit_breaker_timeout', 60)
        )
        
        # Só carrega engine default se não for lazy_load (worker)
        if not lazy_load:
            default_engine = self.settings.get('tts_engine_default', 'xtts')
            self._load_engine(default_engine)
        
        self.job_store = None  # Será injetado no main.py
        
        # Sprint 6: RVC Model Manager
        self.rvc_model_manager = None  # Será injetado no main.py ou inicializado lazy
    
    def _load_engine(self, engine_type: str):
        """
        Carrega engine TTS usando factory pattern (lazy initialization)
        
        Args:
            engine_type: 'xtts' ou 'f5tts'
        """
        if engine_type in self.engines:
            return  # Já carregado
        
        from .engines import create_engine_with_fallback
        logger.info(f"Initializing {engine_type} engine")
        
        try:
            self.engines[engine_type] = create_engine_with_fallback(
                engine_type=engine_type,
                settings=self.settings,
                fallback_engine='xtts'  # Sempre fallback para XTTS
            )
            logger.info(f"✅ {engine_type} engine loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load {engine_type} engine: {e}", exc_info=True)
            raise
    
    def _get_engine(self, engine_type: str):
        """
        Obtém engine TTS (lazy load se necessário)
        
        Args:
            engine_type: 'xtts' ou 'f5tts'
        
        Returns:
            TTSEngine instance
        """
        if engine_type not in self.engines:
            self._load_engine(engine_type)
        return self.engines[engine_type]
    
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
            # Determina qual engine usar
            engine_type = job.tts_engine or self.settings.get('tts_engine_default', 'xtts')
            logger.info("Processing dubbing job %s: mode=%s, engine=%s", job.id, job.mode, engine_type)
            
            # Garante que engine esteja carregado (lazy load)
            engine = self._get_engine(engine_type)
            
            # Registra engine usado (pode ser diferente se houve fallback)
            job.tts_engine_used = engine.engine_name
            
            job.status = JobStatus.PROCESSING
            job.progress = 10.0
            if self.job_store:
                self.job_store.update_job(job)
            
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
            
            # Gera áudio dublado com perfil de qualidade usando engine selecionado (+ RVC se habilitado)
            # Retry automático já aplicado via decorator em TTSEngine.generate_dubbing
            audio_bytes, duration = await engine.generate_dubbing(
                text=job.text,
                language=job.source_language or job.target_language or 'en',
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
            # Determina qual engine usar
            engine_type = job.tts_engine or self.settings.get('tts_engine_default', 'xtts')
            logger.info("Starting clone job %s with engine %s", job.id, engine_type)
            
            # Garante que engine esteja carregado (lazy load)
            engine = self._get_engine(engine_type)
            
            # Registra engine usado
            job.tts_engine_used = engine.engine_name
            
            # Validação
            logger.debug("  - input_file: %s", job.input_file)
            logger.debug("  - voice_name: %s", job.voice_name)
            logger.debug("  - language: %s", job.source_language)
            logger.debug("  - ref_text: %s", job.ref_text or '(auto-transcribe)')
            
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
            
            # Clona voz usando engine selecionado
            # Note: ref_text é usado por F5-TTS (auto-transcribed if None), ignorado por XTTS
            voice_profile = await engine.clone_voice(
                audio_path=job.input_file,
                language=job.source_language or 'en',
                voice_name=job.voice_name,
                description=job.voice_description,
                ref_text=job.ref_text  # F5-TTS: auto-transcribe if None, XTTS: ignored
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
