"""
XTTS v2 Engine Implementation
Refactored from xtts_client.py to implement TTSEngine interface

This module implements the XTTS v2 engine (Coqui TTS), providing high-quality
voice cloning and text-to-speech synthesis. XTTS is the default/primary engine,
proven stable and optimized for 16+ languages including Portuguese (PT-BR).

Key Features:
    - GPT-based autoregressive TTS architecture
    - High-quality voice cloning (only needs reference WAV)
    - Optimized for 16 languages (including PT-BR)
    - Lower VRAM usage (2-4GB vs F5-TTS 3-8GB)
    - Faster inference (RTF 0.3-0.5 vs F5-TTS 0.5-2.0)
    - RVC integration for voice conversion
    - Quality profiles (balanced, expressive, stable)

Performance:
    - Sample Rate: 24kHz
    - RTF: 0.3-0.5 (2-4x faster than F5-TTS)
    - VRAM: 2-4GB
    - Parameters: ~500M

Author: Audio Voice Service Team
Date: November 27, 2025
Sprint: 3 - XTTS Refactoring
"""
import logging
import os
import torch
import torchaudio
import soundfile as sf
import io
import asyncio
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from uuid import uuid4

# MONKEY PATCH para auto-aceitar ToS do Coqui TTS
import builtins
_original_input = builtins.input
def _auto_accept_tos(prompt=""):
    """Auto-aceita ToS do Coqui TTS quando solicitado"""
    if ">" in prompt or "agree" in prompt.lower() or "tos" in prompt.lower():
        return "y"
    return _original_input(prompt)
builtins.input = _auto_accept_tos

from TTS.api import TTS

from .base import TTSEngine
from ..models import VoiceProfile, QualityProfile, XTTSParameters, RvcModel, RvcParameters
from ..exceptions import InvalidAudioException, TTSEngineException
from ..resilience import retry_async, with_timeout
from ..vram_manager import vram_manager
from ..config import get_settings

logger = logging.getLogger(__name__)


class XttsEngine(TTSEngine):
    """
    XTTS v2 engine implementation (Coqui TTS).
    
    This is the default/primary TTS engine, proven stable and optimized for
    production use. Recommended for:
    - PT-BR content (optimized)
    - Real-time or near-real-time synthesis
    - Systems with limited VRAM (2-4GB)
    - General-purpose TTS (90% of use cases)
    
    Note: XTTS does NOT use ref_text (transcription) for voice cloning.
    It works directly with reference audio WAV files.
    """
    
    # Supported languages (XTTS v2 optimized)
    SUPPORTED_LANGUAGES = [
        'pt', 'pt-BR', 'en', 'es', 'fr', 'de', 'it', 
        'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 
        'hu', 'ko', 'ja', 'hi'
    ]
    
    # Audio constraints
    MIN_AUDIO_DURATION = 3.0  # seconds
    
    # Default speaker for generic (non-cloned) synthesis
    DEFAULT_SPEAKER_PATH = "/app/uploads/default_speaker.wav"
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    ):
        """
        Initialize XTTS v2 engine.
        
        Args:
            device: Device ('cuda', 'cpu', or None for auto-detect)
            fallback_to_cpu: If True, fallback to CPU when CUDA unavailable
            model_name: TTS model name
        """
        # Device selection
        self.device = self._select_device(device, fallback_to_cpu)
        logger.info(f"XttsEngine initializing on device: {self.device}")
        
        # Model configuration
        self.model_name = model_name
        
        # Cache directory para modelos
        self.cache_dir = Path('/app/models/xtts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"XTTS model cache: {self.cache_dir}")
        
        # Set environment variables for Coqui TTS
        os.environ['COQUI_TOS_AGREED'] = '1'
        # Coqui TTS usa XDG_CACHE_HOME para downloads
        os.environ['XDG_CACHE_HOME'] = str(self.cache_dir.parent)
        
        # Load XTTS model
        try:
            gpu = (self.device == 'cuda')
            settings = get_settings()
            
            # LOW_VRAM mode: lazy loading via VRAMManager
            if settings.get('low_vram_mode'):
                logger.info("LOW_VRAM mode enabled: models will be loaded on-demand")
                self.tts = None  # Lazy load
                self._model_loaded = False
            else:
                # Normal mode: load immediately
                # progress_bar=False evita prompts interativos
                self.tts = TTS(
                    self.model_name,
                    gpu=gpu,
                    progress_bar=False
                )
                logger.info(f"✅ XTTS model loaded: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load XTTS model: {e}", exc_info=True)
            raise TTSEngineException(
                f"XTTS initialization failed: {e}"
            ) from e
        
        # RVC client (lazy load)
        self.rvc_client = None
    
    def _select_device(self, device: Optional[str], fallback_to_cpu: bool) -> str:
        """Select computation device with fallback logic"""
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        if device == 'cuda' and not torch.cuda.is_available():
            if fallback_to_cpu:
                logger.warning("CUDA requested but not available, falling back to CPU")
                return 'cpu'
            else:
                raise TTSEngineException("CUDA requested but not available")
        
        return device
    
    def _load_model(self):
        """Load XTTS model (used in LOW_VRAM mode for lazy loading)"""
        if self.tts is None:
            gpu = (self.device == 'cuda')
            logger.info(f"Loading XTTS model on-demand: {self.model_name}")
            self.tts = TTS(
                self.model_name,
                gpu=gpu,
                progress_bar=False
            )
            self._model_loaded = True
            logger.info("✅ XTTS model loaded (lazy)")
        return self.tts
    
    def _load_rvc_client(self):
        """
        Load RVC client (lazy loading).
        
        Only loads when RVC is needed, saving 2-4GB VRAM.
        Idempotent (multiple calls don't recreate instance).
        """
        if self.rvc_client is not None:
            return  # Already loaded
        
        from ..rvc_client import RvcClient
        
        logger.info("Initializing RVC client (lazy load)")
        self.rvc_client = RvcClient(
            device=self.device,
            fallback_to_cpu=True
        )
        logger.info("RVC client ready")
    
    @property
    def engine_name(self) -> str:
        """Engine identifier"""
        return 'xtts'
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate (24kHz)"""
        return 24000
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        XTTS v2 is optimized for 16 languages.
        PT-BR is mapped to 'pt' internally.
        """
        if hasattr(self.tts, 'languages'):
            return self.tts.languages
        return self.SUPPORTED_LANGUAGES.copy()
    
    @retry_async(max_attempts=3, delay_seconds=5, backoff_multiplier=2.0)
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_profile: Optional[VoiceProfile] = None,
        quality_profile: QualityProfile = QualityProfile.BALANCED,
        speed: float = 1.0,
        **kwargs
    ) -> Tuple[bytes, float]:
        """
        Generate dubbed audio from text using XTTS v2.
        
        Args:
            text: Text to synthesize
            language: Language code (pt, pt-BR, en, etc.)
            voice_profile: Optional voice profile for cloning
            quality_profile: Quality preset (balanced, expressive, stable)
            speed: Speech speed (0.5-2.0)
            **kwargs: Engine-specific parameters:
                - enable_rvc: Use RVC for voice conversion
                - rvc_model: RVC model to use
                - rvc_params: RVC parameters
                - temperature: Temperature override (0.1-1.0)
        
        Returns:
            Tuple[bytes, float]: (WAV audio bytes, duration in seconds)
        
        Raises:
            ValueError: If invalid parameters
            TTSEngineException: If synthesis fails
        """
        # Validation
        if not text or not text.strip():
            raise ValueError("Empty text provided")
        
        text = text.strip()
        
        # Normalize language (pt-BR → pt for XTTS)
        normalized_lang = self._normalize_language(language)
        
        # Validate language
        supported_langs = self.get_supported_languages()
        if normalized_lang not in supported_langs:
            raise ValueError(
                f"Language '{normalized_lang}' (original: '{language}') not supported. "
                f"Supported: {supported_langs}"
            )
        
        logger.info(
            f"XTTS synthesis: text_len={len(text)}, lang={normalized_lang}, "
            f"voice={voice_profile.name if voice_profile else 'default'}, "
            f"quality_profile={quality_profile}"
        )
        
        # Get quality parameters
        # quality_profile agora é uma string (ID do profile no Redis)
        # Precisamos carregar o profile e extrair os parâmetros
        if quality_profile and isinstance(quality_profile, str):
            # Tentar carregar profile do Redis
            try:
                from ..quality_profile_manager import quality_profile_manager
                from ..quality_profiles import TTSEngine as QEngine
                profile_obj = quality_profile_manager.get_profile(QEngine.XTTS, quality_profile)

                if profile_obj:
                    # Aceitar objeto Pydantic ou dict
                    if hasattr(profile_obj, 'dict'):
                        profile_data = profile_obj.dict()
                    else:
                        profile_data = dict(profile_obj)
                    params = XTTSParameters(
                        temperature=profile_data.get('temperature', 0.75),
                        repetition_penalty=profile_data.get('repetition_penalty', 1.5),
                        top_p=profile_data.get('top_p', 0.9),
                        top_k=profile_data.get('top_k', 60),
                        length_penalty=profile_data.get('length_penalty', 1.2),
                        speed=profile_data.get('speed', 1.0),
                        enable_text_splitting=profile_data.get('enable_text_splitting', False)
                    )
                    logger.info(f"Loaded XTTS quality profile: {quality_profile}")
                else:
                    # Fallback para padrão
                    logger.warning(f"Profile '{quality_profile}' not found, using BALANCED")
                    from ..models import QualityProfile
                    params = XTTSParameters.from_profile(QualityProfile.BALANCED)
            except Exception as e:
                logger.warning(f"Failed to load quality profile: {e}, using BALANCED")
                from ..models import QualityProfile
                params = XTTSParameters.from_profile(QualityProfile.BALANCED)
        elif quality_profile:
            # Enum antigo (compatibilidade)
            params = XTTSParameters.from_profile(quality_profile)
        else:
            # Sem profile especificado, usa BALANCED
            from ..models import QualityProfile
            params = XTTSParameters.from_profile(QualityProfile.BALANCED)
        
        # Apply custom overrides
        if kwargs.get('temperature'):
            params.temperature = kwargs['temperature']
        if speed != 1.0:
            params.speed = speed
        
        logger.debug(
            f"XTTS params: temp={params.temperature}, "
            f"rep_pen={params.repetition_penalty}, "
            f"top_p={params.top_p}, top_k={params.top_k}, speed={params.speed}"
        )
        
        # Output temp file
        output_path = f"/tmp/xtts_output_{os.getpid()}_{datetime.now().timestamp()}.wav"
        
        try:
            # Configure XTTS model parameters
            self._apply_params_to_model(params)
            
            # Determine speaker wav
            if voice_profile is not None:
                # Voice cloning
                speaker_wav = voice_profile.source_audio_path
                
                if not os.path.exists(speaker_wav):
                    raise InvalidAudioException(
                        f"Reference audio not found: {speaker_wav}"
                    )
            else:
                # Generic voice (default speaker)
                speaker_wav = self.DEFAULT_SPEAKER_PATH
                
                if not os.path.exists(speaker_wav):
                    raise TTSEngineException(
                        f"Default speaker not found: {speaker_wav}. "
                        "Run scripts/create_default_speaker.py to create it."
                    )
                
                logger.info("Using default speaker for generic dubbing")
            
            # Run XTTS inference (blocking - use thread pool)
            loop = asyncio.get_event_loop()
            settings = get_settings()
            
            # LOW_VRAM mode: load model → synthesize → unload
            if settings.get('low_vram_mode'):
                with vram_manager.load_model('xtts', self._load_model):
                    await with_timeout(
                        loop.run_in_executor(
                            None,
                            self._synthesize_blocking,
                            text,
                            output_path,
                            speaker_wav,
                            normalized_lang,
                            params
                        ),
                        timeout_seconds=300
                    )
            else:
                # Normal mode: model already loaded
                await with_timeout(
                    loop.run_in_executor(
                        None,
                        self._synthesize_blocking,
                        text,
                        output_path,
                        speaker_wav,
                        normalized_lang,
                        params
                    ),
                    timeout_seconds=300
                )
            
            # Read generated audio
            audio_data, sr = sf.read(output_path)
            
            # RVC integration (voice conversion)
            if kwargs.get('enable_rvc'):
                audio_data = await self._apply_rvc(
                    audio_data,
                    sr,
                    kwargs.get('rvc_model'),
                    kwargs.get('rvc_params')
                )
            
            # Convert to WAV bytes
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sr, format='WAV')
            audio_bytes = buffer.getvalue()
            
            # Calculate duration
            duration = len(audio_data) / sr
            
            # Cleanup
            if os.path.exists(output_path):
                os.remove(output_path)
            
            logger.info(
                f"✅ XTTS synthesis complete: {duration:.2f}s, {len(audio_bytes)} bytes"
            )
            
            return audio_bytes, duration
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(output_path):
                os.remove(output_path)
            
            logger.error(f"XTTS synthesis failed: {e}", exc_info=True)
            raise TTSEngineException(f"XTTS synthesis error: {e}") from e
    
    def _synthesize_blocking(
        self,
        text: str,
        output_path: str,
        speaker_wav: str,
        language: str,
        params: XTTSParameters
    ):
        """
        Blocking XTTS synthesis (runs in thread pool).
        
        Args:
            text: Text to synthesize
            output_path: Output WAV file path
            speaker_wav: Reference speaker audio
            language: Language code
            params: XTTS parameters
        """
        self.tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=speaker_wav,
            language=language,
            split_sentences=params.enable_text_splitting,
            speed=params.speed
        )
    
    def _apply_params_to_model(self, params: XTTSParameters):
        """Apply parameters to XTTS model"""
        if not hasattr(self.tts, 'synthesizer') or not hasattr(self.tts.synthesizer, 'tts_model'):
            return
        
        model = self.tts.synthesizer.tts_model
        
        # Map parameters to model attributes
        param_mapping = {
            'temperature': params.temperature,
            'repetition_penalty': params.repetition_penalty,
            'top_p': params.top_p,
            'top_k': params.top_k,
            'length_penalty': params.length_penalty,
        }
        
        for attr_name, value in param_mapping.items():
            if hasattr(model, attr_name):
                setattr(model, attr_name, value)
                logger.debug(f"Set model.{attr_name} = {value}")
    
    @retry_async(max_attempts=2, delay_seconds=3, backoff_multiplier=2.0)
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None,
        ref_text: Optional[str] = None
    ) -> VoiceProfile:
        """
        Create voice profile from reference audio.
        
        XTTS does NOT use ref_text (it's provided for interface compatibility
        with F5-TTS but is ignored). XTTS works directly with reference audio.
        
        Args:
            audio_path: Path to reference audio (WAV, 3s+ recommended)
            language: Language code
            voice_name: Name for voice profile
            description: Optional description
            ref_text: Optional transcription (IGNORED by XTTS - for F5-TTS compatibility)
        
        Returns:
            VoiceProfile: Created voice profile
        
        Raises:
            FileNotFoundError: If audio not found
            InvalidAudioException: If audio invalid
        """
        audio_path = str(audio_path)
        
        # Validate file exists
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"XTTS cloning voice: {voice_name} from {audio_path}")
        
        # Normalize language
        normalized_lang = self._normalize_language(language)
        
        # Validate language
        supported_langs = self.get_supported_languages()
        if normalized_lang not in supported_langs:
            raise ValueError(
                f"Language '{normalized_lang}' (original: '{language}') not supported"
            )
        
        try:
            # Load and validate audio
            audio_data, sr = sf.read(audio_path)
            duration = len(audio_data) / sr
            
            # Validate duration
            if duration < self.MIN_AUDIO_DURATION:
                raise InvalidAudioException(
                    f"Audio too short: {duration:.1f}s (minimum {self.MIN_AUDIO_DURATION}s)"
                )
            
            # Create VoiceProfile
            # Note: XTTS uses audio directly, no separate embedding file
            # Note: ref_text is stored but not used by XTTS (for F5-TTS compatibility)
            profile = VoiceProfile(
                id=str(uuid4()),
                name=voice_name,
                language=language,  # Store original (pt-BR)
                source_audio_path=audio_path,
                profile_path=audio_path,  # XTTS uses audio directly
                description=description,
                ref_text=ref_text,  # Stored but NOT used by XTTS
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=30)
            )
            
            logger.info(f"✅ Voice profile created: {voice_name}")
            
            if ref_text:
                logger.debug(
                    f"ref_text provided but IGNORED by XTTS (used only by F5-TTS)"
                )
            
            return profile
            
        except sf.LibsndfileError as e:
            raise InvalidAudioException(f"Invalid audio format: {str(e)}")
        except InvalidAudioException:
            raise
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}", exc_info=True)
            raise TTSEngineException(f"Voice cloning error: {e}") from e
    
    def _normalize_language(self, language: str) -> str:
        """
        Normalize language code for XTTS.
        
        XTTS uses 'pt' internally for both 'pt' and 'pt-BR'.
        """
        if language.lower() in ['pt-br', 'pt_br']:
            return 'pt'
        return language
    
    async def _apply_rvc(
        self,
        audio_data,
        sample_rate: int,
        rvc_model: Optional[RvcModel],
        rvc_params: Optional[RvcParameters]
    ):
        """
        Apply RVC voice conversion.
        
        Args:
            audio_data: Audio numpy array
            sample_rate: Sample rate
            rvc_model: RVC model
            rvc_params: RVC parameters
        
        Returns:
            Converted audio array
        """
        if rvc_model is None:
            logger.warning("RVC enabled but no model provided, skipping")
            return audio_data
        
        try:
            logger.info(f"Applying RVC conversion with model: {rvc_model.name}")
            
            # Load RVC client (lazy)
            self._load_rvc_client()
            
            # Use default params if not provided
            if rvc_params is None:
                rvc_params = RvcParameters()
            
            # Apply RVC conversion
            converted_audio, _ = await self.rvc_client.convert_audio(
                audio_data=audio_data,
                sample_rate=sample_rate,
                rvc_model=rvc_model,
                params=rvc_params
            )
            
            logger.info("✅ RVC conversion successful")
            
            return converted_audio
            
        except Exception as e:
            # Fallback: return original audio if RVC fails
            logger.error(f"RVC conversion failed, using XTTS audio: {e}")
            logger.warning("Falling back to XTTS-only audio")
            return audio_data
