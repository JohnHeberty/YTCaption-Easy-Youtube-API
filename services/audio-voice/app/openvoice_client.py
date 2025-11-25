"""
Cliente OpenVoice - Adapter para dublagem e clonagem de voz

IMPORTANTE: Este é um ADAPTER/MOCK para OpenVoice.
A implementação real depende da instalação e API do OpenVoice.

Referência: https://github.com/myshell-ai/OpenVoice

Para integração completa:
1. Instalar OpenVoice: pip install git+https://github.com/myshell-ai/OpenVoice.git
2. Baixar modelos pré-treinados
3. Ajustar imports e chamadas conforme API OpenVoice
"""
import logging
import os
import torch
import torchaudio
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pickle

from .models import VoiceProfile
from .config import get_settings
from .exceptions import OpenVoiceException, InvalidAudioException

logger = logging.getLogger(__name__)

# ===== SIMULAÇÃO DE IMPORTS OPENVOICE =====
# Em produção, substituir por imports reais:
# from openvoice import se_extractor
# from openvoice.api import ToneColorConverter, BaseSpeakerTTS


class MockOpenVoiceModel:
    """Mock do modelo OpenVoice para desenvolvimento/teste"""
    def __init__(self, device='cpu'):
        self.device = device
        logger.warning("Using MOCK OpenVoice model - not production ready!")
    
    def tts(self, text: str, speaker: str, language: str, **kwargs) -> np.ndarray:
        """Simula geração de TTS"""
        # Em produção, chamar OpenVoice real
        logger.info(f"MOCK TTS: '{text[:50]}...' speaker={speaker} lang={language}")
        
        # Retorna áudio de exemplo (silêncio de 1 segundo)
        sample_rate = 24000
        duration = min(len(text) * 0.05, 10.0)  # ~0.05s por caractere, max 10s
        samples = int(sample_rate * duration)
        audio_data = np.zeros(samples, dtype=np.float32)
        
        return audio_data
    
    def tts_with_voice(self, text: str, voice_embedding: np.ndarray, **kwargs) -> np.ndarray:
        """Simula TTS com voz clonada"""
        logger.info(f"MOCK TTS with cloned voice: '{text[:50]}...'")
        
        # Retorna áudio de exemplo
        sample_rate = 24000
        duration = min(len(text) * 0.05, 10.0)
        samples = int(sample_rate * duration)
        audio_data = np.zeros(samples, dtype=np.float32)
        
        return audio_data
    
    def extract_voice_embedding(self, audio_path: str, language: str) -> np.ndarray:
        """Simula extração de embedding de voz"""
        logger.info(f"MOCK extract voice embedding from {audio_path}")
        
        # Retorna embedding de exemplo (vetor de 256 dimensões)
        embedding = np.random.randn(256).astype(np.float32)
        
        return embedding


class OpenVoiceClient:
    """
    Cliente para OpenVoice - Dublagem e Clonagem de Voz
    
    Responsabilidades:
    - Inicializar modelos OpenVoice
    - Gerar áudio dublado a partir de texto
    - Clonar vozes a partir de amostras
    - Sintetizar fala com vozes clonadas
    """
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente OpenVoice
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        self.settings = get_settings()
        openvoice_config = self.settings['openvoice']
        
        # Device
        if device is None:
            self.device = openvoice_config['device']
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"Initializing OpenVoice client on device: {self.device}")
        
        # Paths
        self.model_path = Path(openvoice_config['model_path'])
        self.model_path.mkdir(exist_ok=True, parents=True)
        
        # Modelos (carregados sob demanda)
        self._tts_model = None
        self._converter_model = None
        self._models_loaded = False
        
        # Parâmetros padrão
        self.sample_rate = openvoice_config['sample_rate']
        self.default_speed = openvoice_config['default_speed']
        self.default_pitch = openvoice_config['default_pitch']
        
        # Preload se configurado
        if openvoice_config['preload_models']:
            try:
                self._load_models()
            except Exception as e:
                logger.error(f"Failed to preload models: {e}")
    
    def _load_models(self):
        """Carrega modelos OpenVoice"""
        if self._models_loaded:
            return
        
        try:
            logger.info("Loading OpenVoice models...")
            
            # ===== PRODUÇÃO: Substituir por código real =====
            # from openvoice import se_extractor
            # from openvoice.api import ToneColorConverter, BaseSpeakerTTS
            # 
            # self._tts_model = BaseSpeakerTTS(
            #     model_path=str(self.model_path / "base_speakers"),
            #     device=self.device
            # )
            # 
            # self._converter_model = ToneColorConverter(
            #     model_path=str(self.model_path / "converter"),
            #     device=self.device
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK para desenvolvimento
            self._tts_model = MockOpenVoiceModel(device=self.device)
            self._converter_model = MockOpenVoiceModel(device=self.device)
            
            self._models_loaded = True
            logger.info("✅ OpenVoice models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load OpenVoice models: {e}")
            raise OpenVoiceException(f"Model loading failed: {str(e)}")
    
    def unload_models(self):
        """Descarrega modelos da memória (economia de recursos)"""
        if self._models_loaded:
            self._tts_model = None
            self._converter_model = None
            self._models_loaded = False
            
            # Limpa cache CUDA se aplicável
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
            logger.info("OpenVoice models unloaded")
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado a partir de texto
        
        Args:
            text: Texto para dublar
            language: Idioma de síntese
            voice_preset: Voz genérica (ex: 'female_generic')
            voice_profile: Perfil de voz clonada (alternativa a voice_preset)
            speed: Velocidade da fala (0.5-2.0)
            pitch: Tom de voz (0.5-2.0)
        
        Returns:
            (audio_bytes, duration): Bytes do áudio WAV e duração em segundos
        """
        try:
            self._load_models()
            
            logger.info(f"Generating dubbing for text: '{text[:100]}...' language={language}")
            
            # Valida parâmetros
            if not text or len(text.strip()) == 0:
                raise InvalidAudioException("Text cannot be empty")
            
            # Modo: voz genérica ou clonada
            if voice_profile:
                # Usa voz clonada
                audio_data = await self._synthesize_with_cloned_voice(
                    text=text,
                    voice_profile=voice_profile,
                    speed=speed,
                    pitch=pitch
                )
            else:
                # Usa voz genérica
                speaker = voice_preset or 'default_female'
                audio_data = await self._synthesize_with_preset(
                    text=text,
                    speaker=speaker,
                    language=language,
                    speed=speed,
                    pitch=pitch
                )
            
            # Converte para WAV bytes
            audio_bytes, duration = self._audio_to_wav_bytes(audio_data, self.sample_rate)
            
            logger.info(f"✅ Dubbing generated: {duration:.2f}s, {len(audio_bytes)/(1024*1024):.2f}MB")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"Error generating dubbing: {e}")
            raise OpenVoiceException(f"Dubbing generation failed: {str(e)}")
    
    async def _synthesize_with_preset(
        self,
        text: str,
        speaker: str,
        language: str,
        speed: float,
        pitch: float
    ) -> np.ndarray:
        """Sintetiza com voz genérica"""
        try:
            # ===== PRODUÇÃO: Substituir por código real =====
            # audio_data = self._tts_model.tts(
            #     text=text,
            #     speaker=speaker,
            #     language=language,
            #     speed=speed,
            #     pitch=pitch
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            audio_data = self._tts_model.tts(
                text=text,
                speaker=speaker,
                language=language,
                speed=speed,
                pitch=pitch
            )
            
            return audio_data
            
        except Exception as e:
            raise OpenVoiceException(f"TTS synthesis failed: {str(e)}")
    
    async def _synthesize_with_cloned_voice(
        self,
        text: str,
        voice_profile: VoiceProfile,
        speed: float,
        pitch: float
    ) -> np.ndarray:
        """Sintetiza com voz clonada"""
        try:
            # Carrega embedding do perfil
            voice_embedding = self._load_voice_embedding(voice_profile.profile_path)
            
            # ===== PRODUÇÃO: Substituir por código real =====
            # audio_data = self._tts_model.tts_with_voice(
            #     text=text,
            #     voice_embedding=voice_embedding,
            #     speed=speed,
            #     pitch=pitch
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            audio_data = self._tts_model.tts_with_voice(
                text=text,
                voice_embedding=voice_embedding,
                speed=speed,
                pitch=pitch
            )
            
            # Incrementa uso do perfil
            voice_profile.increment_usage()
            
            return audio_data
            
        except Exception as e:
            raise OpenVoiceException(f"Cloned voice synthesis failed: {str(e)}")
    
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
            VoiceProfile com embedding extraído
        """
        try:
            self._load_models()
            
            # Validação crítica: audio_path não pode ser None
            if not audio_path:
                raise InvalidAudioException("Audio path is required for voice cloning")
            
            logger.info(f"Cloning voice from {audio_path} language={language}")
            
            # Valida áudio
            audio_info = self._validate_audio_for_cloning(audio_path)
            
            # Extrai embedding de voz
            voice_embedding = await self._extract_voice_embedding(audio_path, language)
            
            # Salva embedding
            voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
            voice_profiles_dir.mkdir(exist_ok=True, parents=True)
            
            # Cria perfil temporário para gerar ID
            temp_profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path="",  # Será preenchido abaixo
                description=description,
                duration=audio_info['duration'],
                sample_rate=audio_info['sample_rate']
            )
            
            # Salva embedding
            profile_path = voice_profiles_dir / f"{temp_profile.id}.pkl"
            self._save_voice_embedding(voice_embedding, str(profile_path))
            
            # Atualiza perfil com caminho
            temp_profile.profile_path = str(profile_path)
            
            logger.info(f"✅ Voice cloned successfully: {temp_profile.id}")
            
            return temp_profile
            
        except Exception as e:
            logger.error(f"Error cloning voice: {e}")
            raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
    
    async def _extract_voice_embedding(self, audio_path: str, language: str) -> np.ndarray:
        """Extrai embedding de voz do áudio"""
        try:
            # ===== PRODUÇÃO: Substituir por código real =====
            # from openvoice import se_extractor
            # 
            # embedding = se_extractor.get_se(
            #     audio_path=audio_path,
            #     language=language,
            #     device=self.device
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            embedding = self._converter_model.extract_voice_embedding(audio_path, language)
            
            return embedding
            
        except Exception as e:
            raise OpenVoiceException(f"Voice embedding extraction failed: {str(e)}")
    
    def _validate_audio_for_cloning(self, audio_path: str) -> Dict[str, Any]:
        """Valida áudio para clonagem"""
        try:
            # Carrega áudio
            waveform, sample_rate = torchaudio.load(audio_path)
            
            # Duração
            duration = waveform.shape[1] / sample_rate
            
            # Validações
            min_duration = self.settings['openvoice']['min_clone_duration_sec']
            max_duration = self.settings['openvoice']['max_clone_duration_sec']
            
            if duration < min_duration:
                raise InvalidAudioException(f"Audio too short: {duration:.1f}s (min: {min_duration}s)")
            
            if duration > max_duration:
                raise InvalidAudioException(f"Audio too long: {duration:.1f}s (max: {max_duration}s)")
            
            # Sample rate mínimo
            if sample_rate < 16000:
                raise InvalidAudioException(f"Sample rate too low: {sample_rate}Hz (min: 16000Hz)")
            
            return {
                'duration': duration,
                'sample_rate': sample_rate,
                'channels': waveform.shape[0],
                'samples': waveform.shape[1]
            }
            
        except Exception as e:
            if isinstance(e, InvalidAudioException):
                raise
            raise InvalidAudioException(f"Invalid audio file: {str(e)}")
    
    def _save_voice_embedding(self, embedding: np.ndarray, path: str):
        """Salva embedding de voz em arquivo"""
        try:
            with open(path, 'wb') as f:
                pickle.dump(embedding, f)
            logger.debug(f"Voice embedding saved to {path}")
        except Exception as e:
            raise OpenVoiceException(f"Failed to save voice embedding: {str(e)}")
    
    def _load_voice_embedding(self, path: str) -> np.ndarray:
        """Carrega embedding de voz de arquivo"""
        try:
            with open(path, 'rb') as f:
                embedding = pickle.load(f)
            return embedding
        except Exception as e:
            raise OpenVoiceException(f"Failed to load voice embedding: {str(e)}")
    
    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[bytes, float]:
        """
        Converte array numpy para bytes WAV
        
        Returns:
            (wav_bytes, duration)
        """
        try:
            import io
            import wave
            
            # Normaliza áudio para int16
            if audio_data.dtype != np.int16:
                # Assume float32 em [-1, 1]
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data
            
            # Duração
            duration = len(audio_int16) / sample_rate
            
            # Cria WAV em memória
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            wav_bytes = wav_buffer.getvalue()
            
            return wav_bytes, duration
            
        except Exception as e:
            raise OpenVoiceException(f"Failed to convert audio to WAV: {str(e)}")
