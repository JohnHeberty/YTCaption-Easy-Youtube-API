"""
F5-TTS Engine Implementation
Flow Matching Diffusion TTS for maximum expressiveness

This module implements the F5-TTS engine, providing high-quality text-to-speech
with exceptional expressiveness, emotion, and naturalness. F5-TTS uses Flow 
Matching Diffusion architecture (ConvNeXt V2) and excels at audiobooks, narration,
and premium voice applications.

Key Features:
    - Flow Matching Diffusion (state-of-the-art quality)
    - Zero-shot multilingual (100+ languages)
    - Requires ref_text for best voice cloning quality
    - Auto-transcription fallback with Whisper
    - RVC integration for voice conversion
    - Quality profiles (balanced, expressive, stable)

Performance:
    - Sample Rate: 24kHz
    - RTF: 0.5-2.0 (2-4x slower than XTTS)
    - VRAM: 3-8GB (50-100% more than XTTS)
    - Parameters: 450M (base) / 1.2B (large)

Author: Audio Voice Service Team
Date: November 27, 2025
Sprint: 2 - F5-TTS Integration
"""
import logging
import asyncio
import io
from typing import Tuple, Optional, List
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy import signal

from .base import TTSEngine
from ..models import VoiceProfile, QualityProfile
from ..exceptions import TTSEngineException, InvalidAudioException
from ..vram_manager import vram_manager
from ..config import get_settings

logger = logging.getLogger(__name__)


class F5TtsEngine(TTSEngine):
    """
    F5-TTS engine implementation using Flow Matching Diffusion.
    
    This engine provides maximum expressiveness and naturalness, ideal for:
    - Audiobooks and long-form narration
    - Marketing and promotional content
    - Premium voice applications requiring emotional range
    - Multilingual synthesis (100+ languages)
    
    Note: Requires ref_text (transcription) for optimal voice cloning.
    Auto-transcribes with Whisper if ref_text not provided.
    """
    
    # Supported languages (multilingual zero-shot)
    SUPPORTED_LANGUAGES = [
        'en', 'en-US', 'en-GB',  # English
        'pt', 'pt-BR', 'pt-PT',  # Portuguese
        'es', 'es-ES', 'es-MX',  # Spanish
        'fr', 'de', 'it',  # European
        'zh', 'zh-CN', 'zh-TW',  # Chinese
        'ja', 'ko',  # Asian
        'ru', 'ar', 'hi',  # Others
        # F5-TTS supports 100+ more via zero-shot
    ]
    
    # Audio constraints
    MIN_AUDIO_DURATION = 3.0  # seconds
    MAX_AUDIO_DURATION = 30.0  # seconds
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        model_name: str = 'SWivid/E2-TTS',
        whisper_model: str = 'base'
    ):
        """
        Initialize F5-TTS engine.
        
        Args:
            device: Device ('cuda', 'cpu', or None for auto-detect)
            fallback_to_cpu: If True, fallback to CPU when CUDA unavailable
            model_name: HuggingFace model name (default: E2-TTS with emotion support)
            whisper_model: Whisper model for auto-transcription
                          ('tiny', 'base', 'small', 'medium', 'large')
        """
        # Model configuration
        # E2-TTS: Enhanced F5-TTS with emotion support
        # Options: 'F5TTS_v1_Base', 'E2TTS_v1_Base'
        self.model_name = 'E2TTS_v1_Base' if model_name == 'SWivid/E2-TTS' else 'F5TTS_v1_Base'
        self.whisper_model_name = whisper_model
        
        # Cache directory para modelos
        self.cache_dir = Path('/app/models/f5tts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"F5-TTS model cache: {self.cache_dir}")
        
        # Device selection
        # F5-TTS SEMPRE USA CPU para evitar OOM em GPUs pequenas (<8GB)
        # XTTS já ocupa ~3.5GB, F5-TTS precisa ~2GB adicional
        self.device = 'cpu'  # FIXME: Force CPU até implementar VRAM management
        logger.info(f"F5TtsEngine initializing on device: {self.device} (forced CPU to avoid OOM)")
        
        # Load F5-TTS model (new API)
        try:
            from f5_tts.api import F5TTS
            settings = get_settings()
            
            # LOW_VRAM mode: lazy loading via VRAMManager
            if settings.get('low_vram_mode'):
                logger.info("LOW_VRAM mode enabled: F5-TTS will be loaded on-demand")
                self.tts = None  # Lazy load
                self._model_loaded = False
                self._f5tts_class = F5TTS  # Store class for lazy loading
            else:
                # Normal mode: load immediately
                logger.info(f"Loading F5-TTS model: {self.model_name}")
                self.tts = F5TTS(
                    model=self.model_name,
                    device=self.device,
                    hf_cache_dir=str(self.cache_dir)
                )
                logger.info(f"✅ F5-TTS model loaded successfully: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load F5-TTS model: {e}", exc_info=True)
            raise TTSEngineException(
                f"F5-TTS initialization failed: {e}"
            ) from e
        
        # Load Whisper for auto-transcription (lazy load)
        self._whisper = None
        
        # RVC client (lazy load from processor)
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
        """Load F5-TTS model (used in LOW_VRAM mode for lazy loading)"""
        if self.tts is None:
            logger.info(f"Loading F5-TTS model on-demand: {self.model_name}")
            self.tts = self._f5tts_class(
                model=self.model_name,
                device=self.device,
                hf_cache_dir=str(self.cache_dir)
            )
            self._model_loaded = True
            logger.info(f"✅ F5-TTS model loaded (lazy): {self.model_name}")
        return self.tts
    
    @property
    def engine_name(self) -> str:
        """Engine identifier"""
        return 'f5tts'
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate (24kHz)"""
        return 24000
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        F5-TTS supports 100+ languages via zero-shot learning.
        This list contains commonly used languages.
        """
        return self.SUPPORTED_LANGUAGES.copy()
    
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
        Generate dubbed audio from text using F5-TTS.
        
        Args:
            text: Text to synthesize
            language: Language code (pt, pt-BR, en, etc.)
            voice_profile: Optional voice profile for cloning
            quality_profile: Quality preset (balanced, expressive, stable)
            speed: Speech speed (0.5-2.0) - applied post-synthesis
            **kwargs: Engine-specific parameters:
                - enable_rvc: Use RVC for voice conversion
                - rvc_model: RVC model to use
                - rvc_params: RVC parameters
        
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
        
        # Normalize language code
        language = self._normalize_language(language)
        
        logger.info(
            f"F5-TTS synthesis: text_len={len(text)}, lang={language}, "
            f"voice={voice_profile.name if voice_profile else 'default'}, "
            f"quality_profile={quality_profile}"
        )
        
        try:
            # Get quality parameters
            # quality_profile agora é uma string (ID do profile no Redis)
            if quality_profile and isinstance(quality_profile, str):
                # Tentar carregar profile (embutido ou custom) via manager
                try:
                    from ..quality_profile_manager import quality_profile_manager
                    from ..quality_profiles import TTSEngine as QEngine
                    profile_obj = quality_profile_manager.get_profile(QEngine.F5TTS, quality_profile)

                    if profile_obj:
                        # Converter para dict se necessário
                        if hasattr(profile_obj, 'dict'):
                            tts_params = profile_obj.dict()
                        else:
                            tts_params = dict(profile_obj)
                        logger.info(f"Loaded F5-TTS quality profile: {quality_profile}")
                    else:
                        # Fallback para BALANCED
                        logger.warning(f"Profile '{quality_profile}' not found, using BALANCED")
                        from ..models import QualityProfile
                        tts_params = self._map_quality_profile(QualityProfile.BALANCED)
                except Exception as e:
                    logger.warning(f"Failed to load quality profile: {e}, using BALANCED")
                    from ..models import QualityProfile
                    tts_params = self._map_quality_profile(QualityProfile.BALANCED)
            elif quality_profile:
                # Enum antigo (compatibilidade)
                tts_params = self._map_quality_profile(quality_profile)
            else:
                # Sem profile especificado, usa BALANCED
                from ..models import QualityProfile
                tts_params = self._map_quality_profile(QualityProfile.BALANCED)
            
            # Prepare reference audio and text for voice cloning
            ref_audio_path = None
            ref_text = None
            
            if voice_profile:
                ref_audio_path = voice_profile.source_audio_path
                
                # F5-TTS requires ref_text for best quality
                if voice_profile.ref_text:
                    ref_text = voice_profile.ref_text
                    logger.info(f"Using provided ref_text: {ref_text[:50]}...")
                else:
                    # Auto-transcribe if not provided
                    logger.info("ref_text not provided, auto-transcribing...")
                    ref_text = await self._auto_transcribe(ref_audio_path, language)
                    logger.info(f"Auto-transcribed: {ref_text[:50]}...")
            
            # Run F5-TTS inference (blocking - use thread pool)
            loop = asyncio.get_event_loop()
            settings = get_settings()
            
            # Add speed to params
            tts_params['speed'] = speed
            
            # LOW_VRAM mode: load model → synthesize → unload
            if settings.get('low_vram_mode'):
                with vram_manager.load_model('f5tts', self._load_model):
                    model_params = self._normalize_f5_params(tts_params)
                    audio_array = await loop.run_in_executor(
                        None,
                        self._synthesize_blocking,
                        text,
                        ref_audio_path,
                        ref_text,
                        model_params
                    )
            else:
                # Normal mode: model already loaded
                model_params = self._normalize_f5_params(tts_params)
                audio_array = await loop.run_in_executor(
                    None,
                    self._synthesize_blocking,
                    text,
                    ref_audio_path,
                    ref_text,
                    model_params
                )
            
            # Apply speed adjustment if needed (already done in infer)
            # if speed != 1.0:
            #     audio_array = self._adjust_speed(audio_array, speed)
            
            # Pós-processamento para reduzir chiado e artefatos
            audio_array = self._post_process_audio(audio_array, tts_params)

            # Normalize audio (headroom)
            audio_array = self._normalize_audio(audio_array)
            
            # Calculate duration
            duration = len(audio_array) / self.sample_rate
            
            # RVC integration (voice conversion)
            if kwargs.get('enable_rvc') and self.rvc_client:
                logger.info("Applying RVC voice conversion...")
                audio_array, duration = await self._apply_rvc(
                    audio_array,
                    duration,
                    kwargs.get('rvc_model'),
                    kwargs.get('rvc_params')
                )
            
            # Convert to WAV bytes
            audio_bytes = self._array_to_wav_bytes(audio_array)
            
            logger.info(f"✅ F5-TTS synthesis complete: {duration:.2f}s, {len(audio_bytes)} bytes")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"F5-TTS synthesis failed: {e}", exc_info=True)
            raise TTSEngineException(f"F5-TTS synthesis error: {e}") from e
    
    def _synthesize_blocking(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str,
        tts_params: dict
    ) -> np.ndarray:
        """
        Blocking F5-TTS synthesis (runs in thread pool).
        
        Args:
            text: Text to synthesize
            ref_audio_path: Path to reference audio file
            ref_text: Reference transcription
            tts_params: TTS parameters (nfe_step, cfg_strength, etc.)
        
        Returns:
            np.ndarray: Generated audio
        """
        # F5-TTS API nova: infer(ref_file, ref_text, gen_text, ...)
        audio_np, sample_rate, _ = self.tts.infer(
            ref_file=ref_audio_path,
            ref_text=ref_text,
            gen_text=text,
            nfe_step=tts_params.get('nfe_step', 32),
            cfg_strength=tts_params.get('cfg_strength', 2.0),
            sway_sampling_coef=tts_params.get('sway_sampling_coef', -1.0),
            speed=tts_params.get('speed', 1.0),
            show_info=lambda x: None,  # Suppress print
            progress=False  # Disable progress bar
        )
        
        return audio_np
    
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
        
        For F5-TTS, ref_text (transcription) is highly recommended for
        best cloning quality. If not provided, auto-transcribes with Whisper.
        
        Args:
            audio_path: Path to reference audio (WAV, 3-30s recommended)
            language: Language code
            voice_name: Name for voice profile
            description: Optional description
            ref_text: Optional transcription of the reference audio
        
        Returns:
            VoiceProfile: Created voice profile
        
        Raises:
            FileNotFoundError: If audio not found
            InvalidAudioException: If audio invalid (too short, wrong format, etc.)
        """
        audio_path = str(audio_path)
        
        # Validate file exists
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"F5-TTS cloning voice: {voice_name} from {audio_path}")
        
        try:
            # Load and validate audio
            audio, sr = sf.read(audio_path)
            duration = len(audio) / sr
            
            # Validate duration
            if duration < self.MIN_AUDIO_DURATION:
                raise InvalidAudioException(
                    f"Audio too short: {duration:.1f}s (minimum {self.MIN_AUDIO_DURATION}s)"
                )
            
            if duration > self.MAX_AUDIO_DURATION:
                logger.warning(
                    f"Audio longer than recommended: {duration:.1f}s "
                    f"(recommended max {self.MAX_AUDIO_DURATION}s)"
                )
            
            # Auto-transcribe if ref_text not provided
            if not ref_text:
                logger.info("ref_text not provided, auto-transcribing for F5-TTS...")
                ref_text = await self._auto_transcribe(audio_path, language)
                logger.info(f"Auto-transcribed: {ref_text[:100]}...")
            
            # Create VoiceProfile
            from datetime import datetime, timedelta
            from uuid import uuid4
            
            profile = VoiceProfile(
                id=str(uuid4()),
                name=voice_name,
                language=self._normalize_language(language),
                source_audio_path=audio_path,
                profile_path=audio_path,  # F5-TTS uses raw audio
                description=description,
                ref_text=ref_text,  # Store transcription
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
            
            logger.info(f"✅ Voice profile created: {voice_name}")
            
            return profile
            
        except InvalidAudioException:
            raise
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}", exc_info=True)
            raise TTSEngineException(f"Voice cloning error: {e}") from e
    
    async def _auto_transcribe(self, audio_path: str, language: str) -> str:
        """
        Auto-transcribe audio using Whisper.
        SEMPRE roda em CPU na memória (int8) para não ocupar VRAM.
        
        Args:
            audio_path: Path to audio file
            language: Language hint for Whisper
        
        Returns:
            str: Transcribed text
        """
        # Lazy load Whisper (SEMPRE EM CPU)
        if self._whisper is None:
            logger.info(f"Loading Whisper model: {self.whisper_model_name} (CPU-only, int8)")
            try:
                from faster_whisper import WhisperModel
                
                # SEMPRE CPU + int8 para economia de memória
                self._whisper = WhisperModel(
                    self.whisper_model_name,
                    device='cpu',  # SEMPRE CPU (não usa VRAM)
                    compute_type='int8'  # Quantização int8 para menor uso de RAM
                )
                logger.info("✅ Whisper model loaded (CPU, int8)")
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")
                raise TTSEngineException(f"Whisper initialization failed: {e}") from e
        
        # Transcribe (blocking - run in thread pool)
        loop = asyncio.get_event_loop()
        
        def _transcribe_blocking():
            segments, info = self._whisper.transcribe(
                audio_path,
                language=language.split('-')[0],  # Use base language (pt, en, etc.)
                beam_size=5
            )
            # Concatenate all segments
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        
        transcribed_text = await loop.run_in_executor(None, _transcribe_blocking)
        
        return transcribed_text
    
    def _map_quality_profile(self, quality: QualityProfile) -> dict:
        """
        Map QualityProfile to F5-TTS parameters.
        
        Args:
            quality: Quality profile enum
        
        Returns:
            dict: F5-TTS parameters (nfe_step, cfg_strength, etc.)
        """
        # NFE steps: Number of function evaluations (higher = better quality, slower)
        # CFG strength: Classifier-free guidance (higher = more adherence to prompt)
        
        if quality == QualityProfile.STABLE:
            # Fast, stable, lower quality
            return {
                'nfe_step': 16,
                'cfg_strength': 1.5,
                'sway_sampling_coef': -1.0
            }
        elif quality == QualityProfile.EXPRESSIVE:
            # Highest quality, most expressive, slowest
            return {
                'nfe_step': 64,
                'cfg_strength': 2.5,
                'sway_sampling_coef': 0.0
            }
        else:  # BALANCED (default)
            # Good balance of quality and speed
            return {
                'nfe_step': 32,
                'cfg_strength': 2.0,
                'sway_sampling_coef': -1.0
            }
    
    def _normalize_language(self, language: str) -> str:
        """Normalize language code to F5-TTS format"""
        # Map common variants
        lang_map = {
            'pt': 'pt',
            'pt-br': 'pt-BR',
            'pt-pt': 'pt-PT',
            'en': 'en',
            'en-us': 'en-US',
            'en-gb': 'en-GB',
            'es': 'es',
            'zh': 'zh',
        }
        
        lang_lower = language.lower()
        normalized = lang_map.get(lang_lower, language)
        
        # Validate language is supported (loose check for zero-shot)
        base_lang = normalized.split('-')[0]
        if base_lang not in [l.split('-')[0] for l in self.SUPPORTED_LANGUAGES]:
            logger.warning(f"Language {language} may not be optimized for F5-TTS")
        
        return normalized
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio amplitude to prevent clipping"""
        max_amp = np.max(np.abs(audio))
        if max_amp > 0:
            audio = audio / max_amp * 0.95  # Leave 5% headroom
        return audio
    
    def _adjust_speed(self, audio: np.ndarray, speed: float) -> np.ndarray:
        """Adjust audio speed using resampling"""
        if speed == 1.0:
            return audio
        
        # Calculate new length
        new_length = int(len(audio) / speed)
        
        # Resample
        from scipy import signal
        resampled = signal.resample(audio, new_length)
        
        return resampled

    def _normalize_f5_params(self, params: dict) -> dict:
        """Normaliza parâmetros para o F5-TTS, aplicando aliases e filtrando apenas os aceitos pelo modelo."""
        if not isinstance(params, dict):
            return {}
        out = dict(params)
        # Alias: cfg_scale -> cfg_strength (compatibilidade)
        if 'cfg_strength' not in out and 'cfg_scale' in out:
            out['cfg_strength'] = out.pop('cfg_scale')
        # Filtrar somente os parâmetros do modelo (resto fica para pós-processamento)
        allowed = {'nfe_step', 'cfg_strength', 'sway_sampling_coef'}
        return {k: v for k, v in out.items() if k in allowed}

    def _remove_dc_offset(self, audio: np.ndarray) -> np.ndarray:
        """Remove DC offset subtraindo a média."""
        return audio - np.mean(audio)

    def _butter_highpass(self, cutoff_hz: float, order: int = 2):
        nyq = 0.5 * self.sample_rate
        normal_cutoff = cutoff_hz / nyq
        sos = signal.butter(order, normal_cutoff, btype='highpass', output='sos')
        return sos

    def _butter_lowpass(self, cutoff_hz: float, order: int = 4):
        nyq = 0.5 * self.sample_rate
        normal_cutoff = cutoff_hz / nyq
        sos = signal.butter(order, normal_cutoff, btype='lowpass', output='sos')
        return sos

    def _apply_filter(self, audio: np.ndarray, sos) -> np.ndarray:
        return signal.sosfiltfilt(sos, audio)

    def _apply_wiener_denoise(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """Redução simples de ruído via filtro de Wiener, com mix proporcional ao strength."""
        den = signal.wiener(audio)
        return (1 - strength) * audio + strength * den

    def _apply_deesser(self, audio: np.ndarray, center_freq: int = 6000, q: float = 3.0, amount: float = 0.4) -> np.ndarray:
        """Aplicar de-esser simples via filtro notch em torno de center_freq.
        amount controla a mistura do filtrado (0-1)."""
        nyq = 0.5 * self.sample_rate
        w0 = center_freq / nyq
        # Notch (iirnotch: b, a). Usar filtfilt para fase linear
        b, a = signal.iirnotch(w0, q)
        deessed = signal.filtfilt(b, a, audio)
        return (1 - amount) * audio + amount * deessed

    def _post_process_audio(self, audio: np.ndarray, params: dict) -> np.ndarray:
        """Pós-processamento para redução de chiado e artefatos em F5-TTS.

        Passos:
        - Remoção de DC offset
        - High-pass suave (40-60 Hz) para remover rumble
        - Redução de ruído (Wiener) quando habilitado
        - De-esser opcional em 5-8 kHz
        - Low-pass suave (12 kHz) para atenuar hiss alto
        """
        if audio is None or len(audio) == 0:
            return audio

        out = np.copy(audio)

        # Mono expected; se vier multi-canal, mixar para mono
        if out.ndim > 1:
            out = np.mean(out, axis=0)

        # 1) DC offset
        out = self._remove_dc_offset(out)

        # 2) High-pass leve
        try:
            hp_sos = self._butter_highpass(50.0, order=2)
            out = self._apply_filter(out, hp_sos)
        except Exception:
            pass

        # 3) Redução de ruído (Wiener) se habilitado
        if params.get('denoise_audio', True):
            strength = float(params.get('noise_reduction_strength', 0.6))
            strength = max(0.0, min(1.0, strength))
            try:
                out = self._apply_wiener_denoise(out, strength)
            except Exception:
                pass

        # 4) De-esser opcional
        if params.get('apply_deessing', True):
            freq = int(params.get('deessing_frequency', 6000))
            try:
                out = self._apply_deesser(out, center_freq=freq, q=3.0, amount=0.35)
            except Exception:
                pass

        # 5) Low-pass suave para reduzir hiss muito alto
        try:
            lp_sos = self._butter_lowpass(12000.0, order=4)
            out = self._apply_filter(out, lp_sos)
        except Exception:
            pass

        return out
    
    def _array_to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert numpy array to WAV bytes"""
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.sample_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    async def _apply_rvc(
        self,
        audio: np.ndarray,
        duration: float,
        rvc_model,
        rvc_params
    ) -> Tuple[np.ndarray, float]:
        """Apply RVC voice conversion"""
        if not self.rvc_client:
            logger.warning("RVC requested but client not available")
            return audio, duration
        
        try:
            # Convert to bytes for RVC
            audio_bytes = self._array_to_wav_bytes(audio)
            
            # Apply RVC
            converted_audio, new_duration = await self.rvc_client.convert_audio(
                audio_bytes,
                rvc_model,
                rvc_params
            )
            
            return converted_audio, new_duration
            
        except Exception as e:
            logger.error(f"RVC conversion failed: {e}", exc_info=True)
            # Return original audio on RVC failure
            return audio, duration
