"""
Cliente F5-TTS - Adapter para dublagem e clonagem de voz

SPRINT 3: Usando F5TTSModelLoader com modelo pt-BR customizado
"""
import logging
import os
import torch
import torchaudio
import numpy as np
import soundfile as sf
import shutil
from pathlib import Path
from typing import Optional, Tuple

# USAR NOSSO LOADER CUSTOMIZADO
from .f5tts_loader import F5TTSModelLoader, load_f5tts_ptbr

from .tts_interface import TTSEngine
from .models import VoiceProfile
from .config import get_settings
from .validators import (
    normalize_text_ptbr,
    validate_voice_profile,
    validate_inference_params,
    validate_audio_path
)
from .exceptions import InvalidAudioException, OpenVoiceException
from .exceptions import OpenVoiceException, InvalidAudioException

logger = logging.getLogger(__name__)


class F5TTSClient(TTSEngine):
    """Cliente para F5-TTS - Dublagem e Clonagem de Voz com modelo pt-BR"""
    
    # Flag para aplicar patch apenas uma vez
    _patch_applied = False
    
    @staticmethod
    def _apply_chunk_text_patch():
        """
        🔥 MONKEY PATCH CRÍTICO: Corrige chunk_text() do F5-TTS para filtrar batches vazios
        
        PROBLEMA: chunk_text() gera batches vazios (strings com apenas espaços) que causam:
        TypeError: encoding without a string argument
        
        SOLUÇÃO: Wrapper que filtra batches vazios ANTES de retornar
        """
        if F5TTSClient._patch_applied:
            return
            
        try:
            from f5_tts.infer.utils_infer import chunk_text as original_chunk_text
            
            def safe_chunk_text(*args, **kwargs):
                """Wrapper que filtra batches vazios"""
                batches = original_chunk_text(*args, **kwargs)
                filtered = [b for b in batches if b and b.strip()]
                if len(filtered) < len(batches):
                    logger.warning(f"⚠️ chunk_text: removidos {len(batches) - len(filtered)} batches vazios de {len(batches)}")
                return filtered if filtered else [" "]  # Fallback: retorna batch com espaço se tudo vazio
            
            # Substituir função global
            import f5_tts.infer.utils_infer
            f5_tts.infer.utils_infer.chunk_text = safe_chunk_text
            F5TTSClient._patch_applied = True
            logger.info("✅ Monkey patch aplicado com sucesso em chunk_text()")
            
        except ImportError as e:
            logger.warning(f"⚠️ Não foi possível importar f5_tts: {e}")
        except Exception as e:
            logger.error(f"❌ Erro ao aplicar monkey patch: {e}")
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente F5-TTS com modelo pt-BR customizado
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        # Aplicar monkey patch ANTES de carregar modelo
        self._apply_chunk_text_patch()
        
        self.settings = get_settings()
        f5tts_config = self.settings.get('f5tts', {})
        
        # Device
        if device is None:
            self.device = f5tts_config.get('device', 'cuda')
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"Initializing F5-TTS client on device: {self.device}")
        
        # USAR LOADER CUSTOMIZADO
        self.model_path = self.settings.get('F5TTS_MODEL_PATH')
        logger.info(f"📂 Modelo pt-BR: {self.model_path}")
        
        # Parâmetros otimizados para GTX 1050 Ti
        self.sample_rate = 24000  # F5-TTS fixed
        self.nfe_step = f5tts_config.get('nfe_step', 16)  # REDUZIDO: 32 -> 16 para economia VRAM
        self.target_rms = f5tts_config.get('target_rms', 0.1)
        self.use_fp16 = f5tts_config.get('use_fp16', True)
        
        # LAZY LOADING: Modelo só será carregado sob demanda
        self.model = None
        self.loader = None
        self._model_loaded = False
        logger.info("F5-TTS client initialized (lazy loading enabled)")
    
    def _ensure_model_loaded(self):
        """Garante que o modelo está carregado (LAZY LOADING)"""
        if self._model_loaded:
            return
        
        try:
            logger.info("📥 Loading F5-TTS pt-BR model (lazy load)...")
            
            # Usar nosso loader customizado
            self.loader = F5TTSModelLoader(
                model_path=self.model_path,
                device=self.device
            )
            
            # Carregar modelo
            self.model = self.loader.load_model()
            
            # Carregar vocoder (Vocos) - importação correta
            logger.info("📥 Loading Vocos vocoder...")
            from vocos import Vocos
            self.vocoder = Vocos.from_pretrained("charactr/vocos-mel-24khz")
            logger.info("✅ Vocos vocoder loaded")
            
            # Log informações
            info = self.loader.get_model_info()
            logger.info("✅ F5-TTS pt-BR loaded successfully")
            logger.info(f"   Device: {info['device']}")
            logger.info(f"   Parameters: {info['total_parameters']:,}")
            logger.info(f"   Config: {info['config']}")
            
            # Log VRAM usage
            if self.device == 'cuda' and torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                logger.info(f"   📊 VRAM: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved")
            
            self._model_loaded = True
            
        except Exception as e:
            logger.error(f"❌ Failed to load F5-TTS model: {e}", exc_info=True)
            raise OpenVoiceException(f"Model loading failed: {str(e)}") from e
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,
        pitch: float = 1.0  # F5-TTS não suporta pitch direto
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado a partir de texto usando F5-TTS
        
        Args:
            text: Texto para sintetizar (será convertido para lowercase)
            language: Idioma (ignorado - modelo é pt-BR)
            voice_preset: Não usado no F5-TTS (precisa voice_profile)
            voice_profile: Perfil de voz clonada (obrigatório)
            speed: Velocidade de fala (1.0 = normal)
            pitch: Não suportado pelo F5-TTS (ignorado)
        
        Returns:
            Tuple[bytes, float]: (audio_bytes, duration)
        """
        # LAZY LOAD: Carrega modelo apenas quando necessário
        self._ensure_model_loaded()
        
        # VALIDAÇÃO ROBUSTA: Validar inputs ANTES de processar
        try:
            validate_voice_profile(voice_profile)
            validate_inference_params(text, speed, self.nfe_step)
        except (ValueError, InvalidAudioException) as e:
            logger.error(f"Input validation failed: {e}")
            raise InvalidAudioException(str(e)) from e
        
        try:
            import sys
            sys.path.insert(0, '/tmp/F5-TTS')
            from f5_tts.infer.utils_infer import infer_process
            
            # NORMALIZAÇÃO: Preparar texto para F5-TTS pt-BR
            try:
                gen_text = normalize_text_ptbr(text)
                # CRÍTICO: Remover espaços múltiplos e quebras de linha problemáticas
                gen_text = ' '.join(gen_text.split())
                
                # CRITICAL FIX: F5-TTS chunk_text() divide por pontuação e pode criar batches vazios
                # Remove caracteres problemáticos que causam batches com espaços soltos
                gen_text = gen_text.replace('  ', ' ')  # Remove espaços duplos (caso sobrem)
                gen_text = gen_text.replace(' ,', ',')   # Remove espaço antes de vírgula
                gen_text = gen_text.replace(' .', '.')   # Remove espaço antes de ponto
                gen_text = gen_text.replace(' !', '!')   # Remove espaço antes de exclamação
                gen_text = gen_text.replace(' ?', '?')   # Remove espaço antes de interrogação
                gen_text = gen_text.replace(' ;', ';')   # Remove espaço antes de ponto-vírgula
                gen_text = gen_text.replace(' :', ':')   # Remove espaço antes de dois-pontos
                gen_text = gen_text.strip()
                
                # Valida que texto não ficou vazio ou muito curto
                if not gen_text or len(gen_text) < 2:
                    raise ValueError(f"Texto muito curto após normalização: '{gen_text}'")
                    
                logger.info(f"🎙️ F5-TTS generating: '{gen_text[:50]}...'")
            except ValueError as e:
                logger.error(f"Text normalization failed: {e}")
                raise InvalidAudioException(f"Invalid text: {e}") from e
            
            # REFERENCE TEXT: Com fallback robusto
            ref_text = self._get_reference_text_with_fallback(
                voice_profile,
                language
            )
            
            logger.info(f"   Voice: {voice_profile.reference_audio_path}")
            logger.info(f"   Ref text: '{ref_text[:50]}...'")
            logger.info(f"   Gen text: '{gen_text[:50]}...'")
            logger.info(f"   NFE steps: {self.nfe_step}, Speed: {speed}")
            
            # 🔥 FIX CRÍTICO: Validar que gen_text não está vazio ou só com espaços
            if not gen_text or not gen_text.strip():
                raise OpenVoiceException(f"gen_text vazio após preprocessing: '{gen_text}'")
            
            # 🔥 DEBUG: Log completo do texto para análise
            logger.info(f"🔍 Gen text completo ({len(gen_text)} chars): {repr(gen_text)}")
            
            # F5-TTS infer_process: Espera STRINGS (não listas)
            # O batch processing é feito INTERNAMENTE pelo infer_process
            # Inferência F5-TTS
            generated_audio, sample_rate, _ = infer_process(
                ref_audio=voice_profile.reference_audio_path,
                ref_text=ref_text,      # STRING (não lista)
                gen_text=gen_text,      # STRING (não lista)
                model_obj=self.model,
                vocoder=self.vocoder,
                mel_spec_type="vocos",
                show_info=logger.info,
                target_rms=self.target_rms,
                nfe_step=self.nfe_step,
                speed=speed,
                device=self.device
            )
            
            # Converter para bytes
            duration = len(generated_audio) / sample_rate
            audio_bytes = self._wav_to_bytes(generated_audio, sample_rate)
            
            logger.info(
                f"✅ F5-TTS generated {duration:.2f}s audio "
                f"({len(audio_bytes)} bytes, {sample_rate} Hz)"
            )
            return audio_bytes, duration
            
        except InvalidAudioException:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"F5-TTS generation failed: {e}", exc_info=True)
            raise OpenVoiceException(f"TTS generation failed: {str(e)}") from e
    
    def _get_reference_text_with_fallback(
        self,
        voice_profile: VoiceProfile,
        language: str
    ) -> str:
        """
        Obtém reference text com fallbacks robustos.
        
        Priority:
        1. VoiceProfile.reference_text
        2. Transcribe from audio
        3. Generic fallback by language
        """
        # Priority 1: VoiceProfile reference_text
        if voice_profile.reference_text:
            text = voice_profile.reference_text.strip()
            if len(text) >= 3:
                normalized = normalize_text_ptbr(text)
                # CRÍTICO: Remover espaços múltiplos e quebras de linha
                normalized = ' '.join(normalized.split())
                # Remove espaços antes de pontuação (previne batches vazios)
                normalized = normalized.replace(' ,', ',').replace(' .', '.').replace(' !', '!').replace(' ?', '?')
                normalized = normalized.replace(' ;', ';').replace(' :', ':')
                return normalized.strip()
        
        # Priority 2: Transcribe from audio
        try:
            logger.info("reference_text missing, transcribing audio...")
            text = self._transcribe_audio(voice_profile.reference_audio_path, language)
            if text and len(text.strip()) > 3:
                normalized = normalize_text_ptbr(text)
                # CRÍTICO: Remover espaços múltiplos
                normalized = ' '.join(normalized.split())
                # Remove espaços antes de pontuação (previne batches vazios)
                normalized = normalized.replace(' ,', ',').replace(' .', '.').replace(' !', '!').replace(' ?', '?')
                normalized = normalized.replace(' ;', ';').replace(' :', ':')
                return normalized.strip()
        except Exception as e:
            logger.warning(f"Transcription fallback failed: {e}")
        
        # Priority 3: Generic fallback by language
        fallbacks = {
            'pt-BR': 'este é um exemplo de voz em português brasileiro',
            'pt': 'este é um exemplo de voz em português',
            'en': 'this is a sample voice in english',
            'es': 'este es un ejemplo de voz en español'
        }
        fallback_text = fallbacks.get(language, fallbacks['pt-BR'])
        logger.warning(
            f"Using generic fallback for {language}: '{fallback_text}'"
        )
        return fallback_text
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        """
        Clona voz a partir de amostra de áudio
        
        Args:
            audio_path: Caminho para amostra de áudio
            language: Idioma base da voz
            voice_name: Nome do perfil
            description: Descrição opcional
        
        Returns:
            VoiceProfile com referência de áudio
        """
        # LAZY LOAD: Carrega modelo apenas quando necessário
        self._ensure_model_loaded()
        
        try:
            logger.info(f"🎤 F5-TTS cloning voice from: {audio_path}")
            
            # Validação
            if not audio_path or not Path(audio_path).exists():
                raise InvalidAudioException(f"Audio file not found: {audio_path}")
            
            # Valida duração/qualidade
            audio_info = self._validate_audio_for_cloning(audio_path)
            
            # Transcreve com Whisper (via F5-TTS)
            logger.info("  Transcribing audio...")
            ref_text = self._transcribe_audio(audio_path, language)
            logger.info(f"  Transcription: '{ref_text}'")
            
            # Cria perfil temporário
            temp_profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path="",  # preenchido abaixo
                description=description,
                duration=audio_info['duration'],
                sample_rate=audio_info['sample_rate']
            )
            
            # Copia áudio para voice_profiles
            voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
            voice_profiles_dir.mkdir(exist_ok=True, parents=True)
            
            ref_audio_path = voice_profiles_dir / f"{temp_profile.id}.wav"
            
            # Converte para WAV se necessário
            self._convert_to_wav(audio_path, str(ref_audio_path))
            
            # Atualiza perfil
            temp_profile.reference_audio_path = str(ref_audio_path)
            temp_profile.reference_text = ref_text
            temp_profile.profile_path = str(ref_audio_path)  # compatibilidade
            
            logger.info(f"✅ Voice cloned: {temp_profile.id}")
            
            return temp_profile
            
        except Exception as e:
            logger.error(f"F5-TTS voice cloning failed: {e}")
            raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
    
    def _get_preset_audio(self, voice_preset: Optional[str], language: str) -> Tuple[str, str]:
        """Retorna (ref_file, ref_text) para voice preset"""
        preset_dir = Path("/app/voice_profiles/presets")
        preset_dir.mkdir(exist_ok=True, parents=True)
        
        # Mapeamento simples
        preset_map = {
            'female_generic': ('female_en.wav', 'Hello, this is a female voice.'),
            'male_deep': ('male_en.wav', 'Hello, this is a male voice.'),
            'female_pt': ('female_pt.wav', 'Olá, esta é uma voz feminina.'),
            'male_pt': ('male_pt.wav', 'Olá, esta é uma voz masculina.'),
        }
        
        if voice_preset and voice_preset in preset_map:
            file, text = preset_map[voice_preset]
            preset_path = preset_dir / file
            
            # Se não existe, cria preset temporário
            if not preset_path.exists():
                logger.warning(f"Preset '{voice_preset}' not found, creating temporary")
                self._create_temp_preset(preset_path, text, language)
            
            return str(preset_path), text
        else:
            # Fallback: cria preset genérico
            logger.warning(f"Preset '{voice_preset}' not found, using generic")
            fallback_path = preset_dir / 'generic.wav'
            fallback_text = "This is a generic voice."
            
            if not fallback_path.exists():
                self._create_temp_preset(fallback_path, fallback_text, 'en')
            
            return str(fallback_path), fallback_text
    
    def _create_temp_preset(self, output_path: Path, text: str, language: str):
        """Cria preset temporário usando síntese simples"""
        try:
            # Gera tom simples (fallback)
            duration = 2.0
            freq = 220  # A3
            samples = int(self.sample_rate * duration)
            t = np.linspace(0, duration, samples)
            audio = 0.3 * np.sin(2 * np.pi * freq * t)
            
            sf.write(str(output_path), audio, self.sample_rate)
            logger.info(f"  Created temp preset: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to create temp preset: {e}")
    
    def _transcribe_audio(self, audio_path: str, language: str) -> str:
        """Transcreve áudio usando Whisper (SEMPRE CPU)"""
        try:
            from transformers import pipeline
            
            # Inicializa Whisper na CPU (economiza VRAM para F5-TTS)
            logger.info("   Whisper running on CPU (saving GPU for F5-TTS)")
            transcriber = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-base",
                device=-1  # -1 = CPU forçado
            )
            
            # Transcreve
            result = transcriber(audio_path)
            return result['text'].strip()
            
        except Exception as e:
            logger.warning(f"Whisper transcription failed: {e}, using fallback")
            # Fallback: retorna texto genérico
            return "This is a voice sample."
    
    def _wav_to_bytes(self, wav: np.ndarray, sample_rate: int) -> bytes:
        """Converte numpy array para WAV bytes"""
        import io
        buffer = io.BytesIO()
        sf.write(buffer, wav, sample_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    def _validate_audio_for_cloning(self, audio_path: str) -> dict:
        """Valida áudio para clonagem"""
        audio, sr = sf.read(audio_path)
        
        duration = len(audio) / sr
        
        # F5-TTS recomenda <12s
        if duration > 12.0:
            logger.warning(f"Audio duration {duration:.1f}s > 12s, quality may degrade")
        
        return {
            'duration': duration,
            'sample_rate': sr,
            'channels': audio.shape[1] if len(audio.shape) > 1 else 1
        }
    
    def _convert_to_wav(self, input_path: str, output_path: str):
        """Converte áudio para WAV 24kHz mono"""
        audio, sr = sf.read(input_path)
        
        # Mono
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Resample se necessário
        if sr != self.sample_rate:
            import torchaudio.functional as F
            audio_tensor = torch.from_numpy(audio).float()
            audio_tensor = F.resample(audio_tensor, sr, self.sample_rate)
            audio = audio_tensor.numpy()
        
        # Salva
        sf.write(output_path, audio, self.sample_rate)
        logger.info(f"  Converted to WAV: {output_path}")
    
    def unload_models(self):
        """Libera memória"""
        if self.model is not None:
            del self.model
        if self.loader is not None:
            del self.loader
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        logger.info("F5-TTS models unloaded")
