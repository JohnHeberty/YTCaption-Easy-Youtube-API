"""Interface abstrata para motores TTS"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from .models import VoiceProfile


class TTSEngine(ABC):
    """Interface para motores de TTS/clonagem"""
    
    @abstractmethod
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
        Gera áudio dublado
        
        Returns:
            (audio_bytes, duration)
        """
        pass
    
    @abstractmethod
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        """
        Clona voz a partir de amostra
        
        Returns:
            VoiceProfile
        """
        pass
    
    @abstractmethod
    def unload_models(self):
        """Libera memória de modelos"""
        pass
