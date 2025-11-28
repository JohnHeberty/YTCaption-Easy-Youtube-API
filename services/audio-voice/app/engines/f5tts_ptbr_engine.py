"""
F5-TTS PT-BR Engine Implementation (TESTE)
Modelo customizado otimizado para Português Brasileiro

⚠️ ENGINE DE TESTE - NÃO USAR EM PRODUÇÃO SEM VALIDAÇÃO
Este engine carrega o modelo customizado PT-BR localizado em:
/app/models/f5tts/models--ptbr/snapshots/model_last.safetensors

Diferenças vs F5-TTS padrão:
    - Modelo fine-tuned para PT-BR
    - Carregamento direto de safetensors
    - Pode ter arquitetura diferente (vocoder, config, etc)
    
Para testar:
    POST /api/v1/synthesize
    {
        "text": "Olá, como vai?",
        "voice_id": "default",
        "engine": "f5tts-ptbr"  # <<< engine name
    }

Downgrade:
    Se houver problemas, basta usar engine "f5tts" (original)

Author: Audio Voice Service Team
Date: November 28, 2025
Sprint: 3.3 - F5-TTS PT-BR Custom Model
"""
import logging
import io
from typing import Tuple, Optional, List
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

from .base import TTSEngine
from ..models import VoiceProfile, QualityProfile
from ..exceptions import TTSEngineException, InvalidAudioException
from ..vram_manager import vram_manager
from ..config import get_settings

logger = logging.getLogger(__name__)


class F5TtsPtBrEngine(TTSEngine):
    """
    F5-TTS PT-BR engine com modelo customizado.
    
    ⚠️ EXPERIMENTAL - Engine de teste para modelo customizado PT-BR.
    Carrega modelo fine-tuned em português brasileiro.
    
    Características:
    - Modelo: /app/models/f5tts/models--ptbr/snapshots/model_last.safetensors
    - Otimizado para vozes brasileiras
    - Pode ter configuração/vocoder customizado
    - Fallback para F5-TTS padrão se houver problemas
    """
    
    # Supported languages (foco em PT-BR)
    SUPPORTED_LANGUAGES = [
        'pt', 'pt-BR',  # Português Brasileiro (primário)
        'pt-PT',  # Português Europeu (secundário)
    ]
    
    # Audio constraints
    MIN_AUDIO_DURATION = 3.0  # seconds
    MAX_AUDIO_DURATION = 30.0  # seconds
    
    # Paths do modelo customizado
    CUSTOM_MODEL_DIR = Path('/app/models/f5tts/models--ptbr/snapshots')
    CUSTOM_MODEL_PATH = CUSTOM_MODEL_DIR / 'model_last.safetensors'
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        whisper_model: str = 'base'
    ):
        """
        Initialize F5-TTS PT-BR engine.
        
        Args:
            device: Device ('cuda', 'cpu', or None for auto-detect)
            fallback_to_cpu: If True, fallback to CPU when CUDA unavailable
            whisper_model: Whisper model for auto-transcription
        """
        # Model configuration
        self.model_name = 'F5TTS_PTBR_Custom'
        self.whisper_model_name = whisper_model
        
        # Cache directory para modelos
        self.cache_dir = Path('/app/models/f5tts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"F5-TTS PT-BR model cache: {self.cache_dir}")
        
        # Verificar se modelo customizado existe
        if not self.CUSTOM_MODEL_PATH.exists():
            raise TTSEngineException(
                f"Modelo PT-BR não encontrado: {self.CUSTOM_MODEL_PATH}\n"
                f"Por favor, verifique se o modelo foi baixado corretamente."
            )
        logger.info(f"✅ Modelo PT-BR encontrado: {self.CUSTOM_MODEL_PATH}")
        
        # Device selection
        self.device = self._select_device(device, fallback_to_cpu)
        logger.info(f"F5TtsPtBrEngine initializing on device: {self.device}")
        
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
        
        # Load F5-TTS PT-BR model
        try:
            # Tentar carregar com F5TTS API padrão primeiro
            self._try_load_with_api()
            
        except Exception as e:
            logger.error(f"Failed to load F5-TTS PT-BR model: {e}", exc_info=True)
            raise TTSEngineException(
                f"F5-TTS PT-BR initialization failed: {e}\n"
                f"Modelo: {self.CUSTOM_MODEL_PATH}"
            ) from e
        
        # Load Whisper for auto-transcription (lazy load)
        self._whisper = None
        
        # RVC client (lazy load from processor)
        self.rvc_client = None
    
    def _try_load_with_api(self):
        """
        Tenta carregar modelo customizado com F5TTS API.
        
        Estratégias:
        1. F5TTS API com custom_checkpoint
        2. Carregar manualmente safetensors + instantiate model
        3. Fallback para F5TTS padrão com warning
        """
        from f5_tts.api import F5TTS
        settings = get_settings()
        
        # LOW_VRAM mode: lazy loading
        if settings.get('low_vram_mode'):
            logger.info("LOW_VRAM mode enabled: F5-TTS PT-BR will be loaded on-demand")
            self.tts = None
            self._model_loaded = False
            self._f5tts_class = F5TTS
            return
        
        # Normal mode: load immediately
        logger.info(f"Loading F5-TTS PT-BR custom model from: {self.CUSTOM_MODEL_PATH}")
        
        # Estratégia 1: Tentar com ckpt_file parameter
        try:
            logger.info("Tentando carregar com ckpt_file parameter...")
            self.tts = F5TTS(
                model='F5TTS_Base',  # Base architecture
                ckpt_file=str(self.CUSTOM_MODEL_PATH),  # Custom checkpoint
                device=self.device,
                hf_cache_dir=str(self.cache_dir)
            )
            logger.info(f"✅ F5-TTS PT-BR loaded successfully (strategy: ckpt_file)")
            return
        except Exception as e:
            logger.warning(f"Strategy 1 failed (ckpt_file): {e}")
        
        # Estratégia 2: Tentar com vocab_file + ckpt_file
        try:
            logger.info("Tentando carregar com vocab_file + ckpt_file...")
            # Procurar vocab.txt no mesmo diretório
            vocab_file = self.CUSTOM_MODEL_DIR / 'vocab.txt'
            if not vocab_file.exists():
                vocab_file = None
            
            self.tts = F5TTS(
                model='F5TTS_Base',
                ckpt_file=str(self.CUSTOM_MODEL_PATH),
                vocab_file=str(vocab_file) if vocab_file else None,
                device=self.device,
                hf_cache_dir=str(self.cache_dir)
            )
            logger.info(f"✅ F5-TTS PT-BR loaded successfully (strategy: vocab + ckpt)")
            return
        except Exception as e:
            logger.warning(f"Strategy 2 failed (vocab + ckpt): {e}")
        
        # Estratégia 3: Fallback para modelo padrão com warning
        logger.warning(
            f"⚠️  Não foi possível carregar modelo customizado PT-BR!\n"
            f"Fallback: usando modelo F5-TTS padrão.\n"
            f"Modelo tentado: {self.CUSTOM_MODEL_PATH}"
        )
        self.tts = F5TTS(
            model='F5TTS_Base',
            device=self.device,
            hf_cache_dir=str(self.cache_dir)
        )
        logger.info(f"✅ F5-TTS padrão carregado (fallback)")
    
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
        """Load F5-TTS PT-BR model (used in LOW_VRAM mode for lazy loading)"""
        if self.tts is None:
            logger.info(f"Loading F5-TTS PT-BR model on-demand: {self.CUSTOM_MODEL_PATH}")
            
            # Tentar estratégias de carregamento
            try:
                self.tts = self._f5tts_class(
                    model='F5TTS_Base',
                    ckpt_file=str(self.CUSTOM_MODEL_PATH),
                    device=self.device,
                    hf_cache_dir=str(self.cache_dir)
                )
                logger.info(f"✅ F5-TTS PT-BR loaded (lazy, strategy: ckpt_file)")
            except Exception as e:
                logger.warning(f"Lazy load failed, using fallback: {e}")
                self.tts = self._f5tts_class(
                    model='F5TTS_Base',
                    device=self.device,
                    hf_cache_dir=str(self.cache_dir)
                )
                logger.info(f"✅ F5-TTS padrão loaded (lazy fallback)")
            
            self._model_loaded = True
        return self.tts
    
    @property
    def engine_name(self) -> str:
        """Engine identifier"""
        return 'f5tts-ptbr'  # <<<< Diferente do f5tts padrão
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate (24kHz)"""
        return 24000
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        PT-BR optimized, but supports Portuguese variants.
        """
        return self.SUPPORTED_LANGUAGES.copy()
    
    async def synthesize(
        self,
        text: str,
        voice_profile: VoiceProfile,
        quality: QualityProfile = QualityProfile.BALANCED,
        language: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> Tuple[bytes, int]:
        """
        Synthesize speech from text using F5-TTS PT-BR.
        
        Args:
            text: Text to synthesize
            voice_profile: Voice profile with reference audio
            quality: Quality profile (balanced, expressive, stable)
            language: Language code (auto-detect if None)
            speed: Speech speed multiplier (0.5-2.0)
            pitch: Pitch shift in semitones (-12 to +12)
        
        Returns:
            Tuple of (audio_bytes, sample_rate)
        
        Raises:
            TTSEngineException: If synthesis fails
        """
        # Validações
        if not text or not text.strip():
            raise TTSEngineException("Text cannot be empty")
        
        # Language detection/validation
        detected_language = self._detect_language(text, language)
        logger.info(f"Synthesizing with F5-TTS PT-BR: '{text[:50]}...' (lang={detected_language})")
        
        # Load reference audio
        ref_audio_path, ref_text = await self._prepare_reference_audio(voice_profile)
        
        # Synthesis with LOW_VRAM support
        settings = get_settings()
        if settings.get('low_vram_mode'):
            # LOW_VRAM: carregar modelo temporariamente
            with vram_manager.load_model('f5tts-ptbr', self._load_model):
                audio_data = await self._synthesize_internal(
                    text, ref_audio_path, ref_text, speed
                )
        else:
            # Normal mode: modelo já carregado
            audio_data = await self._synthesize_internal(
                text, ref_audio_path, ref_text, speed
            )
        
        # Apply pitch shift if needed
        if abs(pitch) > 0.01:
            audio_data = self._apply_pitch_shift(audio_data, pitch)
        
        # Convert to bytes
        audio_bytes = self._to_bytes(audio_data)
        
        logger.info(f"✅ F5-TTS PT-BR synthesis complete: {len(audio_bytes)} bytes")
        return audio_bytes, self.sample_rate
    
    async def _synthesize_internal(
        self,
        text: str,
        ref_audio_path: Path,
        ref_text: str,
        speed: float
    ) -> np.ndarray:
        """Internal synthesis with F5TTS API"""
        try:
            # F5TTS.infer() - nova API
            wav, sr, _ = self.tts.infer(
                ref_file=str(ref_audio_path),
                ref_text=ref_text,
                gen_text=text,
                speed=speed,
                show_info=lambda x: logger.debug(f"F5-TTS: {x}")
            )
            
            # Converter para numpy array (F5TTS retorna torch.Tensor)
            if isinstance(wav, torch.Tensor):
                wav = wav.cpu().numpy()
            
            # Garantir mono
            if wav.ndim > 1:
                wav = wav.mean(axis=0)
            
            # Normalizar
            wav = wav / np.abs(wav).max() if np.abs(wav).max() > 0 else wav
            
            return wav
            
        except Exception as e:
            logger.error(f"F5-TTS PT-BR synthesis error: {e}", exc_info=True)
            raise TTSEngineException(f"F5-TTS PT-BR synthesis failed: {e}") from e
    
    async def _prepare_reference_audio(
        self,
        voice_profile: VoiceProfile
    ) -> Tuple[Path, str]:
        """Prepare reference audio and get transcription"""
        # Voice profile validation
        if not voice_profile or not voice_profile.audio_path:
            raise TTSEngineException("Voice profile must include reference audio")
        
        ref_audio_path = Path(voice_profile.audio_path)
        if not ref_audio_path.exists():
            raise TTSEngineException(f"Reference audio not found: {ref_audio_path}")
        
        # Get or generate transcription
        ref_text = voice_profile.ref_text
        if not ref_text or not ref_text.strip():
            logger.info("No ref_text provided, auto-transcribing with Whisper...")
            ref_text = await self._transcribe_audio(ref_audio_path)
        
        logger.info(f"Reference: {ref_audio_path.name}, text: '{ref_text[:50]}...'")
        return ref_audio_path, ref_text
    
    async def _transcribe_audio(self, audio_path: Path) -> str:
        """Auto-transcribe audio using Whisper"""
        try:
            if self._whisper is None:
                import whisper
                logger.info(f"Loading Whisper model: {self.whisper_model_name}")
                self._whisper = whisper.load_model(self.whisper_model_name)
            
            result = self._whisper.transcribe(
                str(audio_path),
                language='pt',  # PT-BR forced
                task='transcribe'
            )
            transcription = result['text'].strip()
            logger.info(f"Auto-transcription: '{transcription[:100]}...'")
            return transcription
            
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}", exc_info=True)
            raise TTSEngineException(f"Auto-transcription failed: {e}") from e
    
    def _detect_language(self, text: str, language: Optional[str]) -> str:
        """Detect or validate language"""
        if language:
            # Normalizar código
            lang = language.lower().replace('_', '-')
            if lang not in self.SUPPORTED_LANGUAGES:
                logger.warning(
                    f"Language '{language}' not in supported list for PT-BR model. "
                    f"Using anyway (zero-shot)."
                )
            return lang
        
        # Auto-detect: sempre PT-BR para este engine
        return 'pt-BR'
    
    def _apply_pitch_shift(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """Apply pitch shift using phase vocoder"""
        try:
            # Converter para tensor
            audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)
            
            # Pitch shift (resampling)
            rate = 2 ** (semitones / 12)
            shifted = torchaudio.functional.resample(
                audio_tensor,
                orig_freq=self.sample_rate,
                new_freq=int(self.sample_rate * rate)
            )
            
            # Resample de volta ao sample rate original
            shifted = torchaudio.functional.resample(
                shifted,
                orig_freq=int(self.sample_rate * rate),
                new_freq=self.sample_rate
            )
            
            return shifted.squeeze(0).numpy()
            
        except Exception as e:
            logger.warning(f"Pitch shift failed: {e}, using original audio")
            return audio
    
    def _to_bytes(self, audio: np.ndarray) -> bytes:
        """Convert numpy array to WAV bytes"""
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.sample_rate, format='WAV', subtype='PCM_16')
        buffer.seek(0)
        return buffer.read()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up F5-TTS PT-BR engine resources")
        
        if hasattr(self, 'tts') and self.tts is not None:
            del self.tts
            self.tts = None
        
        if self._whisper is not None:
            del self._whisper
            self._whisper = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
