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
        model_name: str = 'firstpixel/F5-TTS-pt-br',
        whisper_model: str = 'base'
    ):
        """
        Initialize F5-TTS engine.
        
        Args:
            device: Device ('cuda', 'cpu', or None for auto-detect)
            fallback_to_cpu: If True, fallback to CPU when CUDA unavailable
            model_name: HuggingFace model name (default: firstpixel/F5-TTS-pt-br)
            whisper_model: Whisper model for auto-transcription
                          ('tiny', 'base', 'small', 'medium', 'large')
        """
        # Model configuration
        # E2-TTS: Enhanced F5-TTS with emotion support
        # F5-TTS: Base model with high expressiveness
        # pt-br: Modelo otimizado para português brasileiro (firstpixel/F5-TTS-pt-br)
        
        # Salvar nome do modelo HuggingFace original
        self.hf_model_name = model_name
        
        # Config name (usado apenas para determinar YAML config interno)
        # Model names match YAML config files in f5_tts/configs/
        if 'E2-TTS' in model_name or 'E2TTS' in model_name:
            self.config_name = 'E2TTS_Base'  # Emotion model (E2TTS_Base.yaml)
        elif 'pt-br' in model_name.lower() or 'firstpixel' in model_name.lower():
            self.config_name = 'F5TTS_Base'  # PT-BR model uses F5TTS_Base config
        else:
            self.config_name = 'F5TTS_Base'  # Base model (F5TTS_Base.yaml)
        
        self.whisper_model_name = whisper_model
        
        # Cache directory para modelos
        self.cache_dir = Path('/app/models/f5tts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"F5-TTS model cache: {self.cache_dir}")
        
        # Device selection
        self.device = self._select_device(device, fallback_to_cpu)
        logger.info(f"F5TtsEngine initializing on device: {self.device}")
        
        # Aviso se GPU pequena sem LOW_VRAM
        settings = get_settings()
        if self.device == 'cuda' and not settings.get('low_vram_mode'):
            if torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
                if vram_gb < 6.0:
                    logger.warning(
                        f"⚠️  GPU pequena ({vram_gb:.2f}GB) sem LOW_VRAM! "
                        f"Risco de OOM. Recomenda-se LOW_VRAM=true."
                    )
        
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
                logger.info(f"Loading F5-TTS model: {self.hf_model_name}")
                ckpt_file = self._get_model_ckpt_file()
                self.tts = F5TTS(
                    model=self.config_name,  # Config YAML name (F5TTS_Base, E2TTS_Base)
                    ckpt_file=ckpt_file,     # Model checkpoint (pt-br ou vazio para default)
                    device=self.device,
                    hf_cache_dir=str(self.cache_dir)
                )
                
                # CRÍTICO: Garantir que todos os tensors estão no device correto
                self._ensure_model_on_device(self.tts)
                
                logger.info(f"✅ F5-TTS model loaded successfully: {self.hf_model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load F5-TTS model: {e}", exc_info=True)
            raise TTSEngineException(
                f"F5-TTS initialization failed: {e}"
            ) from e
        
        # Load Whisper for auto-transcription (lazy load)
        self._whisper = None
        
        # RVC client (lazy load from processor)
        self.rvc_client = None
    
    def _get_model_ckpt_file(self) -> str:
        """Get checkpoint file path for the model.
        
        For pt-br model (firstpixel/F5-TTS-pt-br), downloads from HuggingFace.
        For other models, returns empty string (uses default SWivid repo).
        """
        if 'firstpixel' in self.hf_model_name.lower() or 'pt-br' in self.hf_model_name.lower():
            from huggingface_hub import hf_hub_download
            logger.info(f"Downloading pt-br model checkpoint from {self.hf_model_name}...")
            ckpt_path = hf_hub_download(
                repo_id='firstpixel/F5-TTS-pt-br',
                filename='pt-br/model_last.safetensors',
                cache_dir=str(self.cache_dir)
            )
            logger.info(f"✅ PT-BR checkpoint downloaded: {ckpt_path}")
            return ckpt_path
        else:
            # Use default SWivid repo (leave ckpt_file empty)
            return ''
    
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
    
    def _ensure_model_on_device(self, model):
        """Garante que todos os tensors do modelo estão no device correto.
        
        Crítico para evitar RuntimeError: Expected all tensors to be on the same device.
        Isso acontece quando o modelo é recarregado no modo LOW_VRAM.
        """
        if not torch.cuda.is_available() or self.device == 'cpu':
            return  # Não fazer nada se for CPU
        
        try:
            # Estratégia 1: Mover modelo principal
            if hasattr(model, 'to'):
                logger.debug(f"Moving main model to {self.device}")
                model.to(self.device)
            
            # Estratégia 2: Mover submodelos internos (F5TTS API wrapper)
            # F5TTS tem: .ema_model, .vocoder, etc
            moved_count = 0
            for attr_name in ['ema_model', 'vocoder', 'model', 'mel_spec']:
                if hasattr(model, attr_name):
                    try:
                        attr = getattr(model, attr_name)
                        if hasattr(attr, 'to') and callable(attr.to):
                            logger.debug(f"Moving {attr_name} to {self.device}")
                            attr.to(self.device)
                            moved_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to move {attr_name} to {self.device}: {e}")
            
            # Estratégia 3: Verificar tensors dentro do __dict__
            if hasattr(model, '__dict__'):
                for key, value in model.__dict__.items():
                    if isinstance(value, torch.nn.Module):
                        try:
                            logger.debug(f"Moving __dict__['{key}'] to {self.device}")
                            value.to(self.device)
                            moved_count += 1
                        except Exception as e:
                            logger.debug(f"Skip moving {key}: {e}")
            
            if moved_count > 0:
                logger.info(f"✅ Ensured {moved_count} submodel(s) are on {self.device}")
            
            # Flush CUDA cache para garantir
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.error(f"Failed to ensure model on device {self.device}: {e}")
            # Não falhar aqui, apenas logar
    
    def _load_model(self):
        """Load F5-TTS model (used in LOW_VRAM mode for lazy loading)"""
        if self.tts is None:
            logger.info(f"Loading F5-TTS model on-demand: {self.hf_model_name}")
            ckpt_file = self._get_model_ckpt_file()
            self.tts = self._f5tts_class(
                model=self.config_name,  # Config YAML name (F5TTS_Base, E2TTS_Base)
                ckpt_file=ckpt_file,     # Model checkpoint (pt-br ou vazio para default)
                device=self.device,
                hf_cache_dir=str(self.cache_dir)
            )
            self._model_loaded = True
            logger.info(f"✅ F5-TTS model loaded (lazy): {self.hf_model_name}")
        
        # CRÍTICO: SEMPRE garantir que modelo está no device correto
        # Isso é essencial após unload em modo LOW_VRAM
        self._ensure_model_on_device(self.tts)
        
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
            
            # CHUNKING: Verificar se deve dividir texto por pontuação
            settings = get_settings()
            chunk_by_punctuation = settings.get('chunk_by_punctuation', True)
            max_chunk_chars = settings.get('max_chunk_chars', 200)
            cross_fade_duration = settings.get('cross_fade_duration', 0.05)
            
            # LOW_VRAM mode: load model → synthesize → unload
            if settings.get('low_vram_mode'):
                with vram_manager.load_model('f5tts', self._load_model):
                    model_params = self._normalize_f5_params(tts_params)
                    audio_array = await loop.run_in_executor(
                        None,
                        self._synthesize_with_chunking,
                        text,
                        ref_audio_path,
                        ref_text,
                        model_params,
                        chunk_by_punctuation,
                        max_chunk_chars,
                        cross_fade_duration
                    )
            else:
                # Normal mode: model already loaded
                model_params = self._normalize_f5_params(tts_params)
                audio_array = await loop.run_in_executor(
                    None,
                    self._synthesize_with_chunking,
                    text,
                    ref_audio_path,
                    ref_text,
                    model_params,
                    chunk_by_punctuation,
                    max_chunk_chars,
                    cross_fade_duration
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
    
    def _synthesize_with_chunking(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str,
        tts_params: dict,
        chunk_by_punctuation: bool = True,
        max_chunk_chars: int = 200,
        cross_fade_duration: float = 0.05
    ) -> np.ndarray:
        """
        Sintetiza texto com chunking inteligente por pontuação.
        
        OBJETIVO: Respeitar vírgulas e pontos para pausas naturais.
        
        Se chunk_by_punctuation=True:
        - Divide texto em chunks por pontuação
        - Sintetiza cada chunk separadamente
        - Concatena com cross-fade suave
        
        Isso resulta em fala mais natural e menos corrida.
        
        Args:
            text: Texto completo
            ref_audio_path: Caminho do áudio de referência
            ref_text: Transcrição do áudio de referência
            tts_params: Parâmetros F5-TTS
            chunk_by_punctuation: Se True, divide por pontuação
            max_chunk_chars: Tamanho máximo de cada chunk
            cross_fade_duration: Duração do cross-fade (segundos)
        
        Returns:
            Audio array concatenado
        """
        if not chunk_by_punctuation or len(text) <= max_chunk_chars:
            # Texto pequeno ou chunking desabilitado: síntese direta
            logger.debug("Text chunking disabled or text is short, using direct synthesis")
            return self._synthesize_blocking(text, ref_audio_path, ref_text, tts_params)
        
        # Dividir texto por pontuação
        chunks = self._split_text_by_punctuation(text, max_chunk_chars)
        logger.info(f"Text split into {len(chunks)} chunks for natural prosody")
        
        # Sintetizar cada chunk
        audio_chunks = []
        for i, chunk in enumerate(chunks):
            logger.debug(f"Synthesizing chunk {i+1}/{len(chunks)}: {len(chunk)} chars")
            chunk_audio = self._synthesize_blocking(chunk, ref_audio_path, ref_text, tts_params)
            audio_chunks.append(chunk_audio)
        
        # Concatenar com cross-fade
        final_audio = self._concatenate_audio_chunks(
            audio_chunks,
            cross_fade_duration,
            self.sample_rate
        )
        
        logger.info(f"✅ Concatenated {len(chunks)} chunks with cross-fade")
        return final_audio
    
    def _concatenate_audio_chunks(
        self,
        chunks: List[np.ndarray],
        cross_fade_duration: float,
        sample_rate: int
    ) -> np.ndarray:
        """
        Concatena chunks de áudio com cross-fade suave.
        
        Cross-fade evita clicks e transições bruscas entre chunks,
        criando uma fala mais natural e contínua.
        
        Args:
            chunks: Lista de arrays de áudio
            cross_fade_duration: Duração do cross-fade (segundos)
            sample_rate: Taxa de amostragem
        
        Returns:
            Array de áudio concatenado
        """
        if len(chunks) == 0:
            return np.array([], dtype=np.float32)
        
        if len(chunks) == 1:
            return chunks[0]
        
        # Número de samples para cross-fade
        fade_samples = int(cross_fade_duration * sample_rate)
        
        # Começar com primeiro chunk
        result = chunks[0]
        
        for chunk in chunks[1:]:
            # Aplicar cross-fade entre final de result e início de chunk
            if len(result) >= fade_samples and len(chunk) >= fade_samples:
                # Fade out no final de result
                fade_out = np.linspace(1.0, 0.0, fade_samples)
                result[-fade_samples:] *= fade_out
                
                # Fade in no início de chunk
                fade_in = np.linspace(0.0, 1.0, fade_samples)
                chunk[:fade_samples] *= fade_in
                
                # Sobrepor a região de cross-fade
                result[-fade_samples:] += chunk[:fade_samples]
                
                # Adicionar resto do chunk
                result = np.concatenate([result, chunk[fade_samples:]])
            else:
                # Chunk muito curto para cross-fade, concatenar direto
                result = np.concatenate([result, chunk])
        
        return result
    
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
        try:
            # Garantir modelo no device correto ANTES de inferência
            self._ensure_model_on_device(self.tts)
            
            # F5-TTS API nova: infer(ref_file, ref_text, gen_text, ...)
            audio_np, sample_rate, _ = self.tts.infer(
                ref_file=ref_audio_path,
                ref_text=ref_text,
                gen_text=text,
                nfe_step=tts_params.get('nfe_step', 32),
                cfg_strength=tts_params.get('cfg_strength', 2.0),
                sway_sampling_coef=tts_params.get('sway_sampling_coef', -1.0),
                speed=tts_params.get('speed', 1.0),
                show_info=lambda x: None  # Suppress print
                # progress removed - uses default tqdm
            )
            
            return audio_np
            
        except RuntimeError as e:
            # Proteção contra device mismatch
            if 'Expected all tensors to be on the same device' in str(e):
                logger.warning(f"⚠️  Device mismatch detected, attempting recovery...")
                logger.warning(f"Original error: {e}")
                
                # Estratégia de recuperação: mover tudo para CPU e tentar novamente
                if self.device == 'cuda':
                    logger.warning("🔄 Falling back to CPU for this synthesis...")
                    
                    # Mover modelo para CPU temporariamente
                    if hasattr(self.tts, 'to'):
                        self.tts.to('cpu')
                    
                    # Mover submodelos
                    for attr_name in ['ema_model', 'vocoder', 'model']:
                        if hasattr(self.tts, attr_name):
                            attr = getattr(self.tts, attr_name)
                            if hasattr(attr, 'to'):
                                attr.to('cpu')
                    
                    # Tentar síntese em CPU
                    try:
                        audio_np, sample_rate, _ = self.tts.infer(
                            ref_file=ref_audio_path,
                            ref_text=ref_text,
                            gen_text=text,
                            nfe_step=tts_params.get('nfe_step', 32),
                            cfg_strength=tts_params.get('cfg_strength', 2.0),
                            sway_sampling_coef=tts_params.get('sway_sampling_coef', -1.0),
                            speed=tts_params.get('speed', 1.0),
                            show_info=lambda x: None
                        )
                        logger.info("✅ CPU fallback synthesis succeeded")
                        return audio_np
                    except Exception as cpu_error:
                        logger.error(f"❌ CPU fallback also failed: {cpu_error}")
                        raise
                else:
                    # Já estava em CPU, não tem como fazer fallback
                    raise
            else:
                # Outro tipo de RuntimeError
                raise
    
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
                engine='f5tts',  # Mark as F5-TTS voice profile
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
                'sway_sampling_coef': 0.5
            }
        else:  # BALANCED (default) - Otimizado para PT-BR natural
            # Good balance of quality and speed, prosódia natural
            return {
                'nfe_step': 40,
                'cfg_strength': 2.2,
                'sway_sampling_coef': 0.3  # Micro-variações naturais
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
    
    def _split_text_by_punctuation(self, text: str, max_chunk_chars: int = 200) -> List[str]:
        """
        Divide texto em chunks respeitando pontuação para prosódia natural.
        
        ESTRATÉGIA:
        1. Quebra por pontuação final (.!?) -> sentenças
        2. Se sentença > max_chunk_chars, quebra por vírgulas/ponto-e-vírgula
        3. Se ainda grande, quebra por espaços respeitando limite
        
        Isso garante:
        - Pausas naturais nas vírgulas e pontos
        - Chunks processáveis pelo modelo
        - Fala mais humana e menos corrida
        
        Args:
            text: Texto completo a processar
            max_chunk_chars: Máximo de caracteres por chunk
        
        Returns:
            Lista de chunks de texto prontos para síntese
        """
        import re
        
        # Remover espaços extras
        text = ' '.join(text.split())
        
        # Quebra por pontuação final (., !, ?, ..., !!, ??)
        sentence_pattern = r'([.!?]+)\s+'
        sentences = re.split(sentence_pattern, text)
        
        # Recompor sentenças com sua pontuação
        full_sentences = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and sentences[i + 1] and sentences[i + 1][0] in '.!?':
                # Juntar texto + pontuação
                full_sentences.append(sentences[i] + sentences[i + 1])
                i += 2
            else:
                if sentences[i].strip():
                    full_sentences.append(sentences[i])
                i += 1
        
        # Se última sentença não tem pontuação, adicionar ponto
        if full_sentences and not full_sentences[-1].rstrip()[-1:] in '.!?':
            full_sentences[-1] += '.'
        
        chunks = []
        for sentence in full_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Se sentença cabe no limite, adiciona direto
            if len(sentence) <= max_chunk_chars:
                chunks.append(sentence)
            else:
                # Sentença grande: quebrar por vírgulas
                sub_pattern = r'([,;:])\s+'
                sub_parts = re.split(sub_pattern, sentence)
                
                # Recompor partes com pontuação
                current_chunk = ""
                i = 0
                while i < len(sub_parts):
                    part = sub_parts[i]
                    
                    # Se é pontuação, adiciona ao chunk atual
                    if part in ',;:':
                        current_chunk += part + ' '
                        i += 1
                        continue
                    
                    # Tentar adicionar ao chunk atual
                    test_chunk = current_chunk + part
                    if len(test_chunk) <= max_chunk_chars:
                        current_chunk = test_chunk
                    else:
                        # Chunk atual cheio, salvar e começar novo
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = part
                    
                    i += 1
                
                # Adicionar último chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
        
        logger.debug(f"Split text into {len(chunks)} chunks: {[len(c) for c in chunks]}")
        return chunks
    
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
