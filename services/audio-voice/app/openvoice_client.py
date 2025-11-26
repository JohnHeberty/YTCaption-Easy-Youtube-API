"""
OpenVoiceClient - Adapter de Compatibilidade para F5-TTS
=========================================================

Este módulo existe para manter compatibilidade com código legado que esperava
OpenVoice, mas internamente utiliza F5-TTS com modelo customizado pt-BR.

MODELO PADRÃO: /app/models/f5tts/pt-br/model_last.safetensors
GPU TARGET: GTX 1050 Ti (4GB VRAM)
"""
import logging
import os
import torch
import torchaudio
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional, Tuple

from .tts_interface import TTSEngine
from .models import VoiceProfile
from .config import get_settings
from .exceptions import OpenVoiceException, InvalidAudioException

logger = logging.getLogger(__name__)


class OpenVoiceClient(TTSEngine):
    """
    Adapter de compatibilidade: emula interface OpenVoice usando F5-TTS.
    
    ESPECIALIZAÇÃO:
    - Modelo pt-BR: model_last.safetensors (1.35 GB)
    - GPU: GTX 1050 Ti (4GB VRAM)
    - Otimizações: FP16, batch_size=1, no_grad
    """
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente F5-TTS com modelo pt-BR customizado
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        self.settings = get_settings()
        f5tts_config = self.settings.get('f5tts', {})
        
        # Device detection com fallback
        if device is None:
            self.device = f5tts_config.get('device', 'cuda')
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("⚠️ CUDA not available, falling back to CPU")
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"🚀 Initializing F5-TTS (pt-BR) on device: {self.device}")
        
        # Paths - MODELO CUSTOMIZADO pt-BR
        self.model_dir = Path('/app/models/f5tts/pt-br')
        self.custom_model_path = self.model_dir / 'model_last.safetensors'
        self.hf_cache_dir = Path(f5tts_config.get('hf_cache_dir', '/app/models/f5tts'))
        
        # Verificar modelo customizado
        if not self.custom_model_path.exists():
            raise FileNotFoundError(
                f"❌ Modelo pt-BR não encontrado: {self.custom_model_path}\n"
                f"   Esperado: model_last.safetensors (~1.35 GB)"
            )
        
        logger.info(f"✅ Custom pt-BR model found: {self.custom_model_path} ({self.custom_model_path.stat().st_size / (1024**3):.2f} GB)")
        
        # Configurações otimizadas para GTX 1050 Ti (4GB VRAM)
        self.sample_rate = 24000  # F5-TTS padrão
        self.nfe_step = f5tts_config.get('nfe_step', 16)  # REDUZIDO: 32 -> 16 (economia VRAM)
        self.target_rms = f5tts_config.get('target_rms', 0.1)
        self.use_fp16 = self.device == 'cuda'  # FP16 em GPU para economizar VRAM
        
        # State tracking
        self._models_loaded = False
        self.f5tts = None
        
        # Carrega modelo
        self._load_models()
    
    def _load_models(self):
        """Carrega modelo F5-TTS com modelo customizado pt-BR"""
        try:
            logger.info(f"📥 Loading F5-TTS with custom pt-BR model...")
            logger.info(f"   Model path: {self.custom_model_path}")
            logger.info(f"   Device: {self.device}")
            logger.info(f"   FP16: {self.use_fp16}")
            logger.info(f"   NFE steps: {self.nfe_step}")
            
            from f5_tts.api import F5TTS
            
            # Inicializa F5-TTS com modelo customizado pt-BR
            # Assinatura: F5TTS(model='F5TTS_v1_Base', ckpt_file='', vocab_file='',
            #                   ode_method='euler', use_ema=True, vocoder_local_path=None,
            #                   device=None, hf_cache_dir=None)
            # Arquivos config: F5TTS_Base.yaml, F5TTS_v1_Base.yaml, E2TTS_Base.yaml
            self.f5tts = F5TTS(
                model='F5TTS_Base',  # Nome do arquivo .yaml (sem extensão)
                ckpt_file=str(self.custom_model_path),  # MODELO CUSTOMIZADO pt-BR
                vocab_file="",  # Auto-detecta
                ode_method="euler",
                use_ema=True,
                device=self.device,
                hf_cache_dir=str(self.hf_cache_dir)
            )
            
            # Otimizações GPU (GTX 1050 Ti)
            if self.device == 'cuda':
                logger.info("⚙️ Applying GPU optimizations (GTX 1050 Ti)...")
                
                # FP16 para economia de VRAM
                if self.use_fp16 and hasattr(self.f5tts, 'model'):
                    try:
                        self.f5tts.model.half()
                        logger.info("   ✓ Model converted to FP16")
                    except Exception as e:
                        logger.warning(f"   ⚠️ FP16 conversion failed: {e}")
                
                # Limpa cache inicial
                torch.cuda.empty_cache()
                
                # Log VRAM usage
                if torch.cuda.is_available():
                    allocated = torch.cuda.memory_allocated(0) / (1024**3)
                    reserved = torch.cuda.memory_reserved(0) / (1024**3)
                    logger.info(f"   📊 VRAM: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved")
            
            self._models_loaded = True
            logger.info("✅ F5-TTS pt-BR model loaded successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to load F5-TTS model: {e}", exc_info=True)
            raise OpenVoiceException(f"Model loading failed: {str(e)}")
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,
        pitch: float = 1.0  # Ignorado (F5-TTS não suporta pitch direto)
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado usando F5-TTS pt-BR
        
        Args:
            text: Texto para dublar (pt-BR otimizado)
            language: Idioma (preferência pt-BR)
            voice_preset: Voz genérica
            voice_profile: Perfil de voz clonada
            speed: Velocidade (0.5-2.0)
            pitch: Ignorado
        
        Returns:
            (audio_bytes, duration)
        """
        try:
            logger.info(f"🎙️ F5-TTS pt-BR dubbing: '{text[:80]}...'")
            logger.info(f"   Language: {language}, Speed: {speed}")
            
            # Determina áudio de referência
            if voice_profile:
                ref_file = voice_profile.reference_audio_path
                ref_text = voice_profile.reference_text or "Olá, esta é uma voz de exemplo."
                logger.info(f"   Using cloned voice: {voice_profile.id}")
            else:
                ref_file, ref_text = self._get_preset_audio(voice_preset, language)
                logger.info(f"   Using preset: {voice_preset or 'default'}")
            
            # Valida referência
            if not Path(ref_file).exists():
                logger.warning(f"⚠️ Reference audio not found: {ref_file}, creating fallback")
                ref_file, ref_text = self._create_fallback_reference(language)
            
            # INFERÊNCIA com otimizações VRAM
            with torch.no_grad():  # CRÍTICO: sem gradiente para economizar VRAM
                # Limpa cache antes
                if self.device == 'cuda':
                    torch.cuda.empty_cache()
                
                wav, sr, _ = self.f5tts.infer(
                    ref_file=ref_file,
                    ref_text=ref_text,
                    gen_text=text,
                    speed=speed,
                    nfe_step=self.nfe_step,  # Reduzido para GTX 1050 Ti
                    remove_silence=False
                )
                
                # Limpa cache após
                if self.device == 'cuda':
                    torch.cuda.empty_cache()
            
            logger.info(f"   Generated: {len(wav)} samples @ {sr} Hz")
            
            # Converte para WAV bytes
            audio_bytes = self._wav_to_bytes(wav, sr)
            duration = len(wav) / sr
            
            logger.info(f"✅ Dubbing completed: {duration:.2f}s ({len(audio_bytes) / 1024:.1f} KB)")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"❌ Dubbing failed: {e}", exc_info=True)
            raise OpenVoiceException(f"Dubbing generation failed: {str(e)}")
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        """
        Clona voz usando F5-TTS (otimizado pt-BR)
        
        Args:
            audio_path: Caminho para amostra de áudio
            language: Idioma (pt-BR recomendado)
            voice_name: Nome do perfil
            description: Descrição opcional
        
        Returns:
            VoiceProfile
        """
        try:
            logger.info(f"🎤 F5-TTS voice cloning: {audio_path}")
            logger.info(f"   Voice name: {voice_name}, Language: {language}")
            
            # Validação
            if not audio_path or not Path(audio_path).exists():
                raise InvalidAudioException(f"Audio file not found: {audio_path}")
            
            # Valida duração/qualidade
            audio_info = self._validate_audio_for_cloning(audio_path)
            logger.info(f"   Audio validated: {audio_info['duration']:.2f}s, {audio_info['sample_rate']} Hz")
            
            # Transcreve com Whisper
            logger.info("   Transcribing audio with Whisper...")
            ref_text = self._transcribe_audio(audio_path, language)
            logger.info(f"   Transcription: '{ref_text}'")
            
            # Cria perfil
            voice_profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path="",  # preenchido abaixo
                description=description,
                duration=audio_info['duration'],
                sample_rate=audio_info['sample_rate']
            )
            
            # Salva áudio de referência
            voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
            voice_profiles_dir.mkdir(exist_ok=True, parents=True)
            
            ref_audio_path = voice_profiles_dir / f"{voice_profile.id}.wav"
            
            # Converte para WAV padrão F5-TTS
            self._convert_to_wav(audio_path, str(ref_audio_path))
            
            # Atualiza perfil
            voice_profile.reference_audio_path = str(ref_audio_path)
            voice_profile.reference_text = ref_text
            voice_profile.profile_path = str(ref_audio_path)
            
            logger.info(f"✅ Voice cloned successfully: {voice_profile.id}")
            
            return voice_profile
            
        except Exception as e:
            logger.error(f"❌ Voice cloning failed: {e}", exc_info=True)
            raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
    
    def _get_preset_audio(self, voice_preset: Optional[str], language: str) -> Tuple[str, str]:
        """Retorna (ref_file, ref_text) para voice preset (pt-BR otimizado)"""
        preset_dir = Path("/app/voice_profiles/presets")
        preset_dir.mkdir(exist_ok=True, parents=True)
        
        # Mapeamento pt-BR prioritário
        preset_map = {
            'female_generic': ('female_pt.wav', 'Olá, esta é uma voz feminina genérica.'),
            'male_generic': ('male_pt.wav', 'Olá, esta é uma voz masculina genérica.'),
            'female_pt': ('female_pt.wav', 'Esta é uma voz feminina em português brasileiro.'),
            'male_pt': ('male_pt.wav', 'Esta é uma voz masculina em português brasileiro.'),
            'male_deep': ('male_deep_pt.wav', 'Esta é uma voz masculina grave em português.'),
        }
        
        # Seleciona preset
        preset_key = voice_preset or 'female_generic'
        if preset_key not in preset_map:
            logger.warning(f"Preset '{preset_key}' not found, using 'female_generic'")
            preset_key = 'female_generic'
        
        file, text = preset_map[preset_key]
        preset_path = preset_dir / file
        
        # Cria se não existe
        if not preset_path.exists():
            logger.warning(f"Preset audio '{file}' not found, creating synthetic")
            self._create_temp_preset(preset_path, text, language)
        
        return str(preset_path), text
    
    def _create_fallback_reference(self, language: str) -> Tuple[str, str]:
        """Cria referência de emergência para pt-BR"""
        fallback_dir = Path("/app/voice_profiles/presets")
        fallback_dir.mkdir(exist_ok=True, parents=True)
        fallback_path = fallback_dir / 'fallback_pt.wav'
        fallback_text = "Esta é uma voz de referência para português brasileiro."
        
        if not fallback_path.exists():
            self._create_temp_preset(fallback_path, fallback_text, 'pt-BR')
        
        return str(fallback_path), fallback_text
    
    def _create_temp_preset(self, output_path: Path, text: str, language: str):
        """Cria preset sintético (fallback quando não há áudio real)"""
        try:
            logger.info(f"   Creating synthetic preset: {output_path.name}")
            
            # Gera tom simples
            duration = 3.0
            freq = 220  # A3
            samples = int(self.sample_rate * duration)
            t = np.linspace(0, duration, samples, dtype=np.float32)
            
            # Onda senoidal com envelope
            audio = 0.2 * np.sin(2 * np.pi * freq * t)
            envelope = np.exp(-t / duration)  # Decay
            audio = audio * envelope
            
            # Salva
            sf.write(str(output_path), audio, self.sample_rate)
            logger.info(f"   ✓ Synthetic preset created: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to create temp preset: {e}")
            raise
    
    def _transcribe_audio(self, audio_path: str, language: str) -> str:
        """
        Transcreve áudio usando Whisper (otimizado para pt-BR)
        
        Args:
            audio_path: Caminho do áudio
            language: Código de idioma (pt, pt-BR, etc.)
        
        Returns:
            Texto transcrito
        """
        try:
            from transformers import pipeline
            
            # Normaliza código de idioma para Whisper
            lang_code = language.lower().split('-')[0] if '-' in language else language.lower()
            
            # Whisper para pt-BR (SEMPRE CPU para economizar VRAM)
            logger.info(f"   Initializing Whisper on CPU (language: {lang_code})...")
            
            transcriber = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-base",  # base model (mais rápido)
                device=-1,  # CPU forçado
                torch_dtype=torch.float32  # FP32 na CPU
            )
            
            # Transcreve
            result = transcriber(
                audio_path,
                generate_kwargs={
                    "language": lang_code,
                    "task": "transcribe"
                }
            )
            
            transcription = result['text'].strip()
            
            # Libera modelo Whisper da memória
            del transcriber
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
            return transcription
            
        except Exception as e:
            logger.warning(f"Whisper transcription failed: {e}, using fallback")
            # Fallback genérico
            return "Esta é uma amostra de voz em português brasileiro."
    
    def _wav_to_bytes(self, wav: np.ndarray, sample_rate: int) -> bytes:
        """Converte numpy array para WAV bytes"""
        import io
        buffer = io.BytesIO()
        sf.write(buffer, wav, sample_rate, format='WAV', subtype='PCM_16')
        buffer.seek(0)
        return buffer.read()
    
    def _validate_audio_for_cloning(self, audio_path: str) -> dict:
        """
        Valida áudio para clonagem (F5-TTS guidelines)
        
        F5-TTS recomenda:
        - Duração: 3-12 segundos
        - Qualidade: limpa, sem ruído
        - Conteúdo: fala natural
        """
        audio, sr = sf.read(audio_path)
        
        duration = len(audio) / sr
        
        # Warnings
        if duration < 3.0:
            logger.warning(f"⚠️ Audio muito curto ({duration:.1f}s < 3s), qualidade pode ser afetada")
        elif duration > 12.0:
            logger.warning(f"⚠️ Audio muito longo ({duration:.1f}s > 12s), considere cortar")
        
        channels = audio.shape[1] if len(audio.shape) > 1 else 1
        
        return {
            'duration': duration,
            'sample_rate': sr,
            'channels': channels
        }
    
    def _convert_to_wav(self, input_path: str, output_path: str):
        """Converte áudio para WAV 24kHz mono (padrão F5-TTS)"""
        try:
            logger.info(f"   Converting to WAV: {Path(input_path).name} -> {Path(output_path).name}")
            
            audio, sr = sf.read(input_path)
            
            # Mono
            if len(audio.shape) > 1 and audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            
            # Resample se necessário
            if sr != self.sample_rate:
                logger.info(f"   Resampling: {sr} Hz -> {self.sample_rate} Hz")
                audio_tensor = torch.from_numpy(audio).float()
                audio_tensor = torchaudio.functional.resample(
                    audio_tensor, 
                    orig_freq=sr, 
                    new_freq=self.sample_rate
                )
                audio = audio_tensor.numpy()
            
            # Normaliza
            audio = audio / np.abs(audio).max() * 0.9  # Evita clipping
            
            # Salva
            sf.write(output_path, audio, self.sample_rate, subtype='PCM_16')
            logger.info(f"   ✓ Conversion complete")
            
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise
    
    def unload_models(self):
        """Libera memória de modelos"""
        try:
            logger.info("Unloading F5-TTS models...")
            
            if self.f5tts is not None:
                del self.f5tts
                self.f5tts = None
            
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
            self._models_loaded = False
            logger.info("✅ Models unloaded")
            
        except Exception as e:
            logger.error(f"Error unloading models: {e}")
