"""
Cliente F5-TTS - Adapter para dublagem e clonagem de voz

Motor de produção para síntese de voz natural e clonagem automática.
GPU-first com fallback automático para CPU em caso de CUDA OOM.

Referência: https://github.com/SWivid/F5-TTS
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

from f5_tts.api import F5TTS

from .tts_interface import TTSEngine
from .models import VoiceProfile
from .config import get_settings
from .exceptions import VoiceCloneException, InvalidAudioException, DubbingException

logger = logging.getLogger(__name__)


class F5TTSClient(TTSEngine):
    """Cliente para F5-TTS - Dublagem e Clonagem de Voz"""
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente F5-TTS
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        self.settings = get_settings()
        f5tts_config = self.settings.get('f5tts', {})
        
        # Device - GPU first, fallback to CPU
        if device is None:
            # Sempre tenta GPU primeiro (padrão)
            self.device = f5tts_config.get('device', 'cuda')
            
            # Checa se CUDA está disponível
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("⚠️ CUDA not available on system, falling back to CPU")
                self.device = 'cpu'
            elif self.device == 'cuda':
                logger.info(f"🎮 GPU available: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB)")
        else:
            self.device = device
        
        logger.info(f"Initializing F5-TTS client on device: {self.device}")
        
        # Paths
        self.hf_cache_dir = Path(f5tts_config.get('hf_cache_dir', '/app/models/f5tts'))
        self.hf_cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Parâmetros
        self.model_name = f5tts_config.get('model', 'F5-TTS')
        self.sample_rate = 24000  # F5-TTS fixed
        
        # Configurações F5-TTS
        self.nfe_step = f5tts_config.get('nfe_step', 32)
        self.cfg_strength = f5tts_config.get('cfg_strength', 2.0)
        self.sway_coef = f5tts_config.get('sway_sampling_coef', -1.0)
        self.target_rms = f5tts_config.get('target_rms', 0.1)
        
        # Carrega modelo
        self.f5tts = None
        self._load_models()
    
    def _load_models(self):
        """Carrega modelo F5-TTS com fallback GPU→CPU automático"""
        f5tts_config = self.settings.get('f5tts', {})
        model_name = 'F5TTS_v1_Base' if self.model_name == 'F5-TTS' else 'E2TTS_Base'
        
        # Verifica se há modelo customizado (PT-BR)
        custom_model_path = f5tts_config.get('custom_model_path', '')
        custom_vocab_path = f5tts_config.get('custom_vocab_path', '')
        
        # Detecta se está usando modelo customizado
        is_custom_model = custom_model_path and Path(custom_model_path).exists()
        
        # Usa modelo customizado se especificado, senão usa padrão HF
        if is_custom_model:
            ckpt_file = custom_model_path
            logger.info(f"📦 Using CUSTOM PT-BR model: {custom_model_path}")
        else:
            ckpt_file = str(self.hf_cache_dir / "model_1200000.safetensors") if (self.hf_cache_dir / "model_1200000.safetensors").exists() else ""
        
        if custom_vocab_path and Path(custom_vocab_path).exists():
            vocab_file = custom_vocab_path
            logger.info(f"📦 Using CUSTOM vocab: {custom_vocab_path}")
        else:
            vocab_file = str(self.hf_cache_dir / "vocab.txt") if (self.hf_cache_dir / "vocab.txt").exists() else ""
        
        # Modelos customizados geralmente não têm EMA weights
        use_ema_param = False if is_custom_model else True
        
        try:
            logger.info(f"Loading F5-TTS model: {self.model_name} on {self.device.upper()}")
            logger.info(f"  use_ema: {use_ema_param}, ckpt: {Path(ckpt_file).name if ckpt_file else 'HF default'}")
            
            self.f5tts = F5TTS(
                model=model_name,
                ckpt_file=ckpt_file,
                vocab_file=vocab_file,
                ode_method="midpoint",
                use_ema=use_ema_param,
                device=self.device,
                hf_cache_dir=str(self.hf_cache_dir)
            )
            
            logger.info(f"✅ F5-TTS model loaded successfully on {self.device.upper()}")
            
        except RuntimeError as e:
            # CUDA Out of Memory - Fallback automático para CPU
            if "CUDA out of memory" in str(e) or "out of memory" in str(e).lower():
                logger.error(f"❌ GPU out of memory: {e}")
                logger.warning(f"⚠️ Migrating to CPU automatically...")
                
                # Libera memória GPU
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Retry em CPU
                self.device = 'cpu'
                try:
                    logger.info(f"Loading F5-TTS model: {self.model_name} on CPU (fallback)")
                    self.f5tts = F5TTS(
                        model=model_name,
                        ckpt_file=ckpt_file,
                        vocab_file=vocab_file,
                        ode_method="midpoint",
                        use_ema=use_ema_param,
                        device='cpu',
                        hf_cache_dir=str(self.hf_cache_dir)
                    )
                    logger.info("✅ F5-TTS model loaded successfully on CPU (fallback from GPU OOM)")
                except Exception as cpu_error:
                    logger.error(f"Failed to load F5-TTS on CPU fallback: {cpu_error}")
                    raise VoiceCloneException(f"Model loading failed on both GPU and CPU: {str(cpu_error)}")
            else:
                # Outro erro de RuntimeError
                logger.error(f"Failed to load F5-TTS model: {e}")
                raise VoiceCloneException(f"Model loading failed: {str(e)}")
                
        except Exception as e:
            logger.error(f"Failed to load F5-TTS model: {e}")
            raise VoiceCloneException(f"Model loading failed: {str(e)}")
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,  # 1.0 = ritmo natural PT-BR (180-200 WPM)
        pitch: float = 1.0  # F5-TTS não suporta pitch direto
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado a partir de texto
        
        Args:
            text: Texto para dublar
            language: Idioma de síntese
            voice_preset: Voz genérica (ex: 'female_generic')
            voice_profile: Perfil de voz clonada
            speed: Velocidade da fala (0.5-2.0)
            pitch: Ignorado (F5-TTS não suporta)
        
        Returns:
            (audio_bytes, duration): Bytes do áudio WAV e duração
        """
        try:
            logger.info(f"🎙️ F5-TTS generate_dubbing: '{text[:50]}...'")
            
            # Determina áudio de referência
            if voice_profile:
                ref_file = voice_profile.reference_audio_path
                ref_text = voice_profile.reference_text
                logger.info(f"  Using cloned voice: {voice_profile.id}")
                logger.debug(f"    ref_file: {ref_file}")
                logger.debug(f"    ref_text: '{ref_text}'")
                logger.debug(f"    gen_text: '{text}'")
            else:
                ref_file, ref_text = self._get_preset_audio(voice_preset, language)
                logger.info(f"  Using preset voice: {voice_preset}")
                logger.debug(f"    ref_file: {ref_file}")
                logger.debug(f"    ref_text: '{ref_text}'")
                logger.debug(f"    gen_text: '{text}'")
            
            # Inferência F5-TTS
            wav, sr, _ = self.f5tts.infer(
                ref_file=ref_file,
                ref_text=ref_text,
                gen_text=text,
                speed=speed,
                nfe_step=self.nfe_step,
                cfg_strength=self.cfg_strength,
                sway_sampling_coef=self.sway_coef,
                remove_silence=True  # Remove silêncios que causam artefatos e chiado
            )
            
            logger.info(f"  Generated audio: {len(wav)} samples, {sr} Hz")
            
            # Converte para WAV bytes
            audio_bytes = self._wav_to_bytes(wav, sr)
            duration = len(wav) / sr
            
            logger.info(f"✅ F5-TTS dubbing generated: {duration:.2f}s")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"F5-TTS dubbing failed: {e}")
            raise DubbingException(f"Dubbing generation failed: {str(e)}")
    
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
            raise VoiceCloneException(f"Voice cloning failed: {str(e)}")
    
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
        """Transcreve áudio usando Whisper (GPU dedicada) com parâmetros avançados PT-BR"""
        try:
            from transformers import pipeline
            
            # Whisper config dedicada
            whisper_config = self.settings.get('whisper', {})
            whisper_device = whisper_config.get('device', 'cuda')
            whisper_model = whisper_config.get('model', 'medium')  # medium para PT-BR nativo
            whisper_language = whisper_config.get('language', 'pt')
            use_fp16 = whisper_config.get('use_fp16', True)
            
            # Parâmetros avançados PT-BR
            initial_prompt = whisper_config.get('initial_prompt', 'Olá, tudo bem? Como você está? Ótimo!')
            temperature = whisper_config.get('temperature', 0.0)
            compression_ratio = whisper_config.get('compression_ratio_threshold', 2.4)
            logprob_threshold = whisper_config.get('logprob_threshold', -1.0)
            no_speech_threshold = whisper_config.get('no_speech_threshold', 0.6)
            condition_on_previous = whisper_config.get('condition_on_previous_text', False)
            
            # Device index: 0 para CUDA, -1 para CPU
            device_idx = 0 if whisper_device == 'cuda' else -1
            
            logger.info(f"🎙️ Transcribing with Whisper ({whisper_model}) on {whisper_device.upper()} [lang={whisper_language}, temp={temperature}]")
            
            # Inicializa Whisper
            transcriber = pipeline(
                "automatic-speech-recognition",
                model=f"openai/whisper-{whisper_model}",
                device=device_idx,
                torch_dtype=torch.float16 if (whisper_device == 'cuda' and use_fp16) else torch.float32
            )
            
            # Transcreve com parâmetros avançados PT-BR
            result = transcriber(
                audio_path, 
                generate_kwargs={
                    "language": whisper_language,
                    "initial_prompt": initial_prompt,
                    "temperature": temperature,
                    "compression_ratio_threshold": compression_ratio,
                    "logprob_threshold": logprob_threshold,
                    "no_speech_threshold": no_speech_threshold,
                    "condition_on_previous_text": condition_on_previous,
                }
            )
            transcription = result['text'].strip()
            
            logger.info(f"✅ Transcription completed: '{transcription[:100]}...'")
            
            return transcription
            
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
        del self.f5tts
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        logger.info("F5-TTS models unloaded")
